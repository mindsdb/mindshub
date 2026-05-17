import unittest
from unittest.mock import MagicMock, patch
import sys
import json

from mindsdb.integrations.libs.response import HandlerStatusResponse as StatusResponse
from mindsdb.integrations.libs.api_handler_exceptions import (
    MissingConnectionParams,
    ConnectionFailed,
)

# Mock shopify and requests modules before importing the handler
if "shopify" not in sys.modules:
    sys.modules["shopify"] = MagicMock()
    sys.modules["shopify.ShopifyResource"] = MagicMock()
    sys.modules["shopify.Session"] = MagicMock()
    sys.modules["shopify.Shop"] = MagicMock()

if "requests" not in sys.modules:
    sys.modules["requests"] = MagicMock()

from mindsdb.integrations.handlers.shopify_handler.shopify_handler import ShopifyHandler
from mindsdb.integrations.handlers.shopify_handler.utils import query_graphql_nodes, MAX_PAGE_LIMIT
from mindsdb.integrations.handlers.shopify_handler.models.products import Products


class BaseShopifyHandlerTest(unittest.TestCase):
    """Base test class with common setup and helper methods."""

    # Test constants
    TEST_SHOP_URL = "test-shop.myshopify.com"
    TEST_CLIENT_ID = "test_client_id"
    TEST_CLIENT_SECRET = "test_client_secret"
    TEST_HANDLER_NAME = "test_shopify_handler"

    def setUp(self):
        """Set up test fixtures."""
        self.connection_data = {
            "shop_url": self.TEST_SHOP_URL,
            "client_id": self.TEST_CLIENT_ID,
            "client_secret": self.TEST_CLIENT_SECRET,
        }

    def tearDown(self):
        """Clean up after tests."""
        pass


class TestShopifyHandlerInitialization(BaseShopifyHandlerTest):
    """Test suite for Shopify Handler initialization."""

    def test_handler_initialization_success(self):
        """Test successful handler initialization with all required parameters."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)

        self.assertEqual(handler.name, self.TEST_HANDLER_NAME)
        self.assertEqual(handler.connection_data, self.connection_data)
        self.assertFalse(handler.is_connected)
        self.assertIsNone(handler.connection)

    def test_handler_initialization_without_connection_data(self):
        """Test handler initialization fails when connection_data is missing."""
        with self.assertRaises(MissingConnectionParams) as context:
            ShopifyHandler(self.TEST_HANDLER_NAME)

        self.assertIn("Incomplete parameters", str(context.exception))

    def test_handler_initialization_missing_shop_url(self):
        """Test handler initialization fails when shop_url is missing."""
        incomplete_data = {
            "client_id": self.TEST_CLIENT_ID,
            "client_secret": self.TEST_CLIENT_SECRET,
        }

        with self.assertRaises(MissingConnectionParams) as context:
            ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=incomplete_data)

        self.assertIn("shop_url", str(context.exception))

    def test_handler_initialization_missing_client_id(self):
        """Test handler initialization fails when client_id is missing."""
        incomplete_data = {
            "shop_url": self.TEST_SHOP_URL,
            "client_secret": self.TEST_CLIENT_SECRET,
        }

        with self.assertRaises(MissingConnectionParams) as context:
            ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=incomplete_data)

        self.assertIn("client_id", str(context.exception))

    def test_handler_initialization_missing_client_secret(self):
        """Test handler initialization fails when client_secret is missing."""
        incomplete_data = {
            "shop_url": self.TEST_SHOP_URL,
            "client_id": self.TEST_CLIENT_ID,
        }

        with self.assertRaises(MissingConnectionParams) as context:
            ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=incomplete_data)

        self.assertIn("client_secret", str(context.exception))

    def test_handler_tables_registered(self):
        """Test that all required tables are registered during initialization."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)

        expected_tables = [
            "products",
            "customers",
            "orders",
            "product_variants",
            "marketing_events",
            "inventory_items",
            "staff_members",
            "gift_cards",
        ]

        for table_name in expected_tables:
            self.assertIn(table_name, handler._tables)


class TestShopifyHandlerConnection(BaseShopifyHandlerTest):
    """Test suite for Shopify Handler connection management."""

    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.requests")
    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.shopify")
    def test_connect_success(self, mock_shopify, mock_requests):
        """Test successful connection to Shopify API."""
        # Mock the OAuth response
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test_access_token"}
        mock_requests.post.return_value = mock_response

        # Mock the Session
        mock_session = MagicMock()
        mock_shopify.Session.return_value = mock_session

        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        result = handler.connect()

        # Verify OAuth request was made
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        self.assertIn(self.TEST_SHOP_URL, call_args[0][0])
        self.assertEqual(call_args[1]["data"]["client_id"], self.TEST_CLIENT_ID)
        self.assertEqual(call_args[1]["data"]["client_secret"], self.TEST_CLIENT_SECRET)

        # Verify session was created
        mock_shopify.Session.assert_called_once_with(self.TEST_SHOP_URL, "2025-10", "test_access_token")

        self.assertTrue(handler.is_connected)
        self.assertEqual(result, mock_session)

    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.requests")
    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.shopify")
    def test_connect_when_already_connected(self, mock_shopify, mock_requests):
        """Test that connect returns existing connection when already connected."""
        mock_session = MagicMock()

        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        handler.connection = mock_session
        handler.is_connected = True

        result = handler.connect()

        # Should not make new OAuth request
        mock_requests.post.assert_not_called()
        mock_shopify.Session.assert_not_called()

        self.assertEqual(result, mock_session)

    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.requests")
    def test_connect_oauth_failure(self, mock_requests):
        """Test connection failure when OAuth request fails."""
        error_msg = "Invalid credentials"
        mock_requests.post.side_effect = Exception(error_msg)

        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)

        with self.assertRaises(Exception) as context:
            handler.connect()

        self.assertIn(error_msg, str(context.exception))
        self.assertFalse(handler.is_connected)

    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.requests")
    def test_connect_missing_access_token(self, mock_requests):
        """Test connection failure when access token is missing from response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}  # No access_token
        mock_requests.post.return_value = mock_response

        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)

        with self.assertRaises(ConnectionFailed) as context:
            handler.connect()

        self.assertIn("Unable to get an access token", str(context.exception))
        self.assertFalse(handler.is_connected)

    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.requests")
    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.shopify")
    def test_check_connection_success(self, mock_shopify, mock_requests):
        """Test successful connection check."""
        # Mock OAuth response
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test_access_token"}
        mock_requests.post.return_value = mock_response

        # Mock session and shop
        mock_session = MagicMock()
        mock_shopify.Session.return_value = mock_session
        mock_shopify.ShopifyResource.activate_session = MagicMock()
        mock_shopify.Shop.current.return_value = MagicMock()

        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        result = handler.check_connection()

        self.assertIsInstance(result, StatusResponse)
        self.assertTrue(result.success)
        self.assertTrue(handler.is_connected)

        # Verify session was activated and Shop.current was called
        mock_shopify.ShopifyResource.activate_session.assert_called_once_with(mock_session)
        mock_shopify.Shop.current.assert_called_once()

    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.requests")
    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.shopify")
    def test_check_connection_failure(self, mock_shopify, mock_requests):
        """Test connection check failure."""
        # Mock OAuth response
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test_access_token"}
        mock_requests.post.return_value = mock_response

        # Mock session
        mock_session = MagicMock()
        mock_shopify.Session.return_value = mock_session
        mock_shopify.ShopifyResource.activate_session = MagicMock()

        # Make Shop.current fail
        error_message = "Invalid shop"
        mock_shopify.Shop.current.side_effect = Exception(error_message)

        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)

        response = handler.check_connection()
        self.assertFalse(response.success)

    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.requests")
    def test_check_connection_oauth_failure(self, mock_requests):
        """Test connection check failure during OAuth."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_requests.post.return_value = mock_response

        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)

        with self.assertRaises(ConnectionFailed):
            handler.connect()


class TestShopifyHandlerConnectionArgs(BaseShopifyHandlerTest):
    """Test suite for Shopify Handler connection arguments validation."""

    def test_connection_args_structure(self):
        """Test that connection_args has the correct structure."""
        from mindsdb.integrations.handlers.shopify_handler.connection_args import connection_args

        required_fields = ["type", "description", "required", "label"]

        # Check shop_url
        self.assertIn("shop_url", connection_args)
        for field in required_fields:
            self.assertIn(field, connection_args["shop_url"])
        self.assertTrue(connection_args["shop_url"]["required"])

        # Check client_id
        self.assertIn("client_id", connection_args)
        for field in required_fields:
            self.assertIn(field, connection_args["client_id"])
        self.assertTrue(connection_args["client_id"]["required"])

        # Check client_secret
        self.assertIn("client_secret", connection_args)
        for field in required_fields:
            self.assertIn(field, connection_args["client_secret"])
        self.assertTrue(connection_args["client_secret"]["required"])
        self.assertTrue(connection_args["client_secret"].get("secret", False))

    def test_connection_args_example_structure(self):
        """Test that connection_args_example has the correct structure."""
        from mindsdb.integrations.handlers.shopify_handler.connection_args import (
            connection_args_example,
        )

        self.assertIn("shop_url", connection_args_example)
        self.assertIn("client_id", connection_args_example)
        self.assertIn("client_secret", connection_args_example)

        self.assertIsInstance(connection_args_example["shop_url"], str)
        self.assertIsInstance(connection_args_example["client_id"], str)
        self.assertIsInstance(connection_args_example["client_secret"], str)


class TestShopifyHandlerEdgeCases(BaseShopifyHandlerTest):
    """Test suite for Shopify Handler edge cases."""

    def test_handler_name_attribute(self):
        """Test that handler has correct name attribute."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        self.assertEqual(handler.name, self.TEST_HANDLER_NAME)

    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.requests")
    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.shopify")
    def test_multiple_connections(self, mock_shopify, mock_requests):
        """Test multiple connection attempts."""
        # Mock OAuth response
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test_access_token"}
        mock_requests.post.return_value = mock_response

        # Mock session
        mock_session = MagicMock()
        mock_shopify.Session.return_value = mock_session

        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)

        # First connection
        result1 = handler.connect()
        self.assertTrue(handler.is_connected)

        # Second connection (should return existing)
        result2 = handler.connect()
        self.assertEqual(result1, result2)

        # Should only call OAuth once
        self.assertEqual(mock_requests.post.call_count, 1)

    def test_connection_data_preserved(self):
        """Test that connection data is preserved after initialization."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)

        self.assertEqual(handler.connection_data["shop_url"], self.TEST_SHOP_URL)
        self.assertEqual(handler.connection_data["client_id"], self.TEST_CLIENT_ID)
        self.assertEqual(handler.connection_data["client_secret"], self.TEST_CLIENT_SECRET)

    def test_table_list_raises_for_unknown_target(self):
        """Test that table list() fails fast when a requested target field is unknown."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        handler.connect = MagicMock(return_value=MagicMock())

        products_table = handler._tables["products"]

        with self.assertRaises(ValueError) as context:
            products_table.list(targets=["__not_a_real_column__"])

        self.assertEqual(
            str(context.exception),
            "The specified fields were not found in the table schema: __not_a_real_column__",
        )

    def test_empty_connection_data(self):
        """Test handler initialization with empty connection_data."""
        with self.assertRaises(MissingConnectionParams):
            ShopifyHandler(self.TEST_HANDLER_NAME, connection_data={})

    def test_partial_connection_data(self):
        """Test handler initialization with partial connection_data."""
        partial_data = {"shop_url": self.TEST_SHOP_URL}

        with self.assertRaises(MissingConnectionParams) as context:
            ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=partial_data)

        # Should mention the missing parameters
        error_message = str(context.exception)
        self.assertTrue("client_id" in error_message or "client_secret" in error_message)


class TestShopifyHandlerIntegration(BaseShopifyHandlerTest):
    """Test suite for Shopify Handler integration scenarios."""

    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.requests")
    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.shopify")
    def test_connection_and_check(self, mock_shopify, mock_requests):
        """Test connection followed by check_connection."""
        # Mock OAuth response
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test_access_token"}
        mock_requests.post.return_value = mock_response

        # Mock session
        mock_session = MagicMock()
        mock_shopify.Session.return_value = mock_session
        mock_shopify.ShopifyResource.activate_session = MagicMock()
        mock_shopify.Shop.current.return_value = MagicMock()

        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)

        # First connect
        handler.connect()
        self.assertTrue(handler.is_connected)

        # Then check connection
        result = handler.check_connection()
        self.assertTrue(result.success)

    def test_handler_with_extra_kwargs(self):
        """Test handler initialization with extra keyword arguments."""
        extra_kwargs = {
            "connection_data": self.connection_data,
            "extra_param": "extra_value",
        }

        handler = ShopifyHandler(self.TEST_HANDLER_NAME, **extra_kwargs)
        self.assertEqual(handler.name, self.TEST_HANDLER_NAME)
        self.assertTrue(handler.is_connected is False)

    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.requests")
    @patch("mindsdb.integrations.handlers.shopify_handler.shopify_handler.shopify")
    def test_native_query_products(self, mock_shopify, mock_requests):
        """Test native query for fetching products."""
        # Mock OAuth response
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test_access_token"}
        mock_requests.post.return_value = mock_response

        # Mock session
        mock_session = MagicMock()
        mock_shopify.Session.return_value = mock_session
        mock_shopify.ShopifyResource.activate_session = MagicMock()

        # Mock GraphQL response
        graphql_result = {
            "data": {
                "products": {
                    "edges": [
                        {"node": {"id": "gid://shopify/Product/1", "title": "Product 1"}},
                        {"node": {"id": "gid://shopify/Product/2", "title": "Product 2"}},
                        {"node": {"id": "gid://shopify/Product/3", "title": "Product 3"}},
                        {"node": {"id": "gid://shopify/Product/4", "title": "Product 4"}},
                        {"node": {"id": "gid://shopify/Product/5", "title": "Product 5"}},
                    ]
                }
            }
        }

        mock_graphql = MagicMock()
        mock_graphql.execute.return_value = json.dumps(graphql_result)
        mock_shopify.GraphQL.return_value = mock_graphql

        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        result = handler.native_query("{ products(first: 5) { edges { node { id title } } } }")

        # Verify result
        from mindsdb.integrations.libs.response import RESPONSE_TYPE

        self.assertEqual(result.type, RESPONSE_TYPE.TABLE)
        self.assertIsNotNone(result.data_frame)


class TestShopifyHandlerTableMetadata(BaseShopifyHandlerTest):
    """Test suite for Shopify Handler table metadata methods."""

    def test_products_table_meta_get_tables(self):
        """Test meta_get_tables method for products table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        products_table = handler._tables["products"]

        # Mock the query_graphql method on the instance
        products_table.query_graphql = MagicMock(return_value={"data": {"productsCount": {"count": 100}}})

        result = products_table.meta_get_tables()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["table_name"], "products")
        self.assertEqual(result["table_type"], "BASE TABLE")
        self.assertIn("table_description", result)
        self.assertEqual(result["row_count"], 100)

    def test_products_table_meta_get_primary_keys(self):
        """Test meta_get_primary_keys method for products table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        products_table = handler._tables["products"]

        result = products_table.meta_get_primary_keys("products")

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["table_name"], "products")
        self.assertEqual(result[0]["column_name"], "id")

    def test_products_table_meta_get_foreign_keys(self):
        """Test meta_get_foreign_keys method for products table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        products_table = handler._tables["products"]

        result = products_table.meta_get_foreign_keys("products", ["products", "orders"])

        self.assertIsInstance(result, list)
        # Products table should have no foreign keys
        self.assertEqual(len(result), 0)

    def test_products_table_get_columns(self):
        """Test get_columns method for products table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        products_table = handler._tables["products"]

        result = products_table.get_columns()

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        # Check that some expected columns are present
        self.assertIn("id", result)
        self.assertIn("title", result)
        # All items should be strings
        for column_name in result:
            self.assertIsInstance(column_name, str)

    def test_products_table_meta_get_columns(self):
        """Test meta_get_columns method for products table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        products_table = handler._tables["products"]

        result = products_table.meta_get_columns()

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        # Each column should be a dictionary with metadata
        for column in result:
            self.assertIsInstance(column, dict)
            self.assertIn("COLUMN_NAME", column)

    def test_product_variants_table_meta_get_tables(self):
        """Test meta_get_tables method for product_variants table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        variants_table = handler._tables["product_variants"]

        # Mock the query_graphql method on the instance
        variants_table.query_graphql = MagicMock(return_value={"data": {"productVariantsCount": {"count": 250}}})

        result = variants_table.meta_get_tables()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["table_name"], "product_variants")
        self.assertEqual(result["table_type"], "BASE TABLE")
        self.assertIn("table_description", result)
        self.assertEqual(result["row_count"], 250)

    def test_product_variants_table_meta_get_primary_keys(self):
        """Test meta_get_primary_keys method for product_variants table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        variants_table = handler._tables["product_variants"]

        result = variants_table.meta_get_primary_keys("product_variants")

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["table_name"], "product_variants")
        self.assertEqual(result[0]["column_name"], "id")

    def test_product_variants_table_meta_get_foreign_keys(self):
        """Test meta_get_foreign_keys method for product_variants table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        variants_table = handler._tables["product_variants"]

        result = variants_table.meta_get_foreign_keys("product_variants", ["products", "product_variants"])

        self.assertIsInstance(result, list)
        # Product variants should have a foreign key to products
        self.assertGreater(len(result), 0)
        self.assertEqual(result[0]["PARENT_TABLE_NAME"], "product_variants")
        self.assertEqual(result[0]["PARENT_COLUMN_NAME"], "productId")
        self.assertEqual(result[0]["CHILD_TABLE_NAME"], "products")
        self.assertEqual(result[0]["CHILD_COLUMN_NAME"], "id")

    def test_product_variants_table_get_columns(self):
        """Test get_columns method for product_variants table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        variants_table = handler._tables["product_variants"]

        result = variants_table.get_columns()

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        # Check that some expected columns are present
        self.assertIn("id", result)
        self.assertIn("productId", result)

    def test_product_variants_table_meta_get_columns(self):
        """Test meta_get_columns method for product_variants table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        variants_table = handler._tables["product_variants"]

        result = variants_table.meta_get_columns()

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        for column in result:
            self.assertIsInstance(column, dict)
            self.assertIn("COLUMN_NAME", column)

    def test_customers_table_meta_get_tables(self):
        """Test meta_get_tables method for customers table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        customers_table = handler._tables["customers"]

        # Mock the query_graphql method on the instance
        customers_table.query_graphql = MagicMock(return_value={"data": {"customersCount": {"count": 500}}})

        result = customers_table.meta_get_tables()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["table_name"], "customers")
        self.assertEqual(result["table_type"], "BASE TABLE")
        self.assertIn("table_description", result)
        self.assertEqual(result["row_count"], 500)

    def test_customers_table_meta_get_primary_keys(self):
        """Test meta_get_primary_keys method for customers table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        customers_table = handler._tables["customers"]

        result = customers_table.meta_get_primary_keys("customers")

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["table_name"], "customers")
        self.assertEqual(result[0]["column_name"], "id")

    def test_customers_table_meta_get_foreign_keys(self):
        """Test meta_get_foreign_keys method for customers table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        customers_table = handler._tables["customers"]

        result = customers_table.meta_get_foreign_keys("customers", ["customers", "orders"])

        self.assertIsInstance(result, list)
        # Customers table should have no foreign keys
        self.assertEqual(len(result), 0)

    def test_customers_table_get_columns(self):
        """Test get_columns method for customers table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        customers_table = handler._tables["customers"]

        result = customers_table.get_columns()

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        # Check that some expected columns are present
        self.assertIn("id", result)
        self.assertIn("emailAddress", result)

    def test_customers_table_meta_get_columns(self):
        """Test meta_get_columns method for customers table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        customers_table = handler._tables["customers"]

        result = customers_table.meta_get_columns()

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        for column in result:
            self.assertIsInstance(column, dict)
            self.assertIn("COLUMN_NAME", column)

    def test_orders_table_meta_get_tables(self):
        """Test meta_get_tables method for orders table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        orders_table = handler._tables["orders"]

        # Mock the query_graphql method on the instance
        orders_table.query_graphql = MagicMock(return_value={"data": {"ordersCount": {"count": 1000}}})

        result = orders_table.meta_get_tables()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["table_name"], "orders")
        self.assertEqual(result["table_type"], "BASE TABLE")
        self.assertIn("table_description", result)
        self.assertEqual(result["row_count"], 1000)

    def test_orders_table_meta_get_primary_keys(self):
        """Test meta_get_primary_keys method for orders table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        orders_table = handler._tables["orders"]

        result = orders_table.meta_get_primary_keys("orders")

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["table_name"], "orders")
        self.assertEqual(result[0]["column_name"], "id")

    def test_orders_table_meta_get_foreign_keys(self):
        """Test meta_get_foreign_keys method for orders table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        orders_table = handler._tables["orders"]

        # Test with customers in the table list
        result = orders_table.meta_get_foreign_keys("orders", ["customers", "orders"])

        self.assertIsInstance(result, list)
        # Orders table should have a foreign key to customers
        self.assertGreater(len(result), 0)
        self.assertEqual(result[0]["PARENT_TABLE_NAME"], "orders")
        self.assertEqual(result[0]["PARENT_COLUMN_NAME"], "customerId")
        self.assertEqual(result[0]["CHILD_TABLE_NAME"], "customers")
        self.assertEqual(result[0]["CHILD_COLUMN_NAME"], "id")

    def test_orders_table_get_columns(self):
        """Test get_columns method for orders table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        orders_table = handler._tables["orders"]

        result = orders_table.get_columns()

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        # Check that some expected columns are present
        self.assertIn("id", result)
        self.assertIn("customerId", result)

    def test_orders_table_meta_get_columns(self):
        """Test meta_get_columns method for orders table."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)
        orders_table = handler._tables["orders"]

        result = orders_table.meta_get_columns()

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        for column in result:
            self.assertIsInstance(column, dict)
            self.assertIn("COLUMN_NAME", column)

    def test_all_tables_have_metadata_methods(self):
        """Test that all registered tables have required metadata methods."""
        handler = ShopifyHandler(self.TEST_HANDLER_NAME, connection_data=self.connection_data)

        expected_tables = [
            "products",
            "customers",
            "orders",
            "product_variants",
            "marketing_events",
            "inventory_items",
            "staff_members",
            "gift_cards",
        ]

        for table_name in expected_tables:
            with self.subTest(table=table_name):
                table = handler._tables[table_name]

                # Check that all required methods exist
                self.assertTrue(hasattr(table, "meta_get_tables"))
                self.assertTrue(hasattr(table, "meta_get_primary_keys"))
                self.assertTrue(hasattr(table, "meta_get_foreign_keys"))
                self.assertTrue(hasattr(table, "get_columns"))
                self.assertTrue(hasattr(table, "meta_get_columns"))

                # Check that methods are callable
                self.assertTrue(callable(table.meta_get_tables))
                self.assertTrue(callable(table.meta_get_primary_keys))
                self.assertTrue(callable(table.meta_get_foreign_keys))
                self.assertTrue(callable(table.get_columns))
                self.assertTrue(callable(table.meta_get_columns))

    @patch("mindsdb.integrations.handlers.shopify_handler.utils.ShopifyQuery")
    def test_limit_large_than_max_page_limit(self, mock_shopify_query):
        """Test pagination when limit exceeds MAX_PAGE_LIMIT."""
        # First request returns MAX_PAGE_LIMIT items
        first_result = {
            "data": {
                "products": {
                    "nodes": [{"id": str(i), "title": f"Product {i}"} for i in range(MAX_PAGE_LIMIT)],
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor"},
                }
            }
        }
        # Second request returns remaining items
        second_result = {
            "data": {
                "products": {
                    "nodes": [{"id": str(i), "title": f"Product {i}"} for i in range(MAX_PAGE_LIMIT, 300)],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }

        mock_query_instance = MagicMock()
        mock_query_instance.execute.side_effect = [first_result, second_result]
        mock_shopify_query.return_value = mock_query_instance

        result = query_graphql_nodes(
            root_name="products",
            root_class=Products,
            columns="id title",
            limit=300,
        )

        # Verify that two requests were made
        self.assertEqual(mock_shopify_query.call_count, 2)

        # First call should request min(300, 250) = 250
        first_call_kwargs = mock_shopify_query.call_args_list[0][1]
        self.assertEqual(first_call_kwargs["limit"], MAX_PAGE_LIMIT)

        # Second call should request min(max(300-250, 1), 250) = 50
        second_call_kwargs = mock_shopify_query.call_args_list[1][1]
        self.assertEqual(second_call_kwargs["limit"], 50)

        # Result should be exactly 300 items
        self.assertEqual(len(result), 300)


class TestShopifyPassthrough(unittest.TestCase):
    """Exercise the PassthroughMixin retrofit (X-Shopify-Access-Token auth)."""

    CONNECTION_DATA = {
        "shop_url": "test-shop.myshopify.com",
        "client_id": "cid",
        "client_secret": "csec",
        "access_token": "shpat_tokenvalue",
    }

    def _mock_response(self, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.headers = {"Content-Type": "application/json"}
        resp.iter_content = MagicMock(return_value=iter([b'{"shop":{"id":1}}']))
        resp.close = MagicMock()
        return resp

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_passthrough_uses_shopify_header_and_per_shop_base_url(self, mock_request):
        mock_request.return_value = self._mock_response()
        handler = ShopifyHandler("shopify", connection_data=self.CONNECTION_DATA)
        from mindsdb.integrations.libs.passthrough_types import PassthroughRequest

        resp = handler.api_passthrough(PassthroughRequest("GET", "/admin/api/2024-01/shop.json"))

        self.assertEqual(resp.status_code, 200)
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], "GET")
        self.assertEqual(args[1], "https://test-shop.myshopify.com/admin/api/2024-01/shop.json")
        # Custom Shopify auth header; no bearer Authorization.
        self.assertEqual(kwargs["headers"]["X-Shopify-Access-Token"], "shpat_tokenvalue")
        self.assertNotIn("Authorization", kwargs["headers"])

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_test_passthrough_returns_ok_on_200(self, mock_request):
        mock_request.return_value = self._mock_response(status_code=200)
        handler = ShopifyHandler("shopify", connection_data=self.CONNECTION_DATA)

        result = handler.test_passthrough()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["host"], "test-shop.myshopify.com")
        self.assertIsInstance(result["latency_ms"], int)
        # The probe should hit the version-less endpoint so it survives
        # Shopify's quarterly Admin API version retirements.
        self.assertEqual(mock_request.call_args[0][1], "https://test-shop.myshopify.com/admin/shop.json")

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_test_passthrough_returns_auth_failed_on_401(self, mock_request):
        mock_request.return_value = self._mock_response(status_code=401)
        handler = ShopifyHandler("shopify", connection_data=self.CONNECTION_DATA)

        result = handler.test_passthrough()

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "auth_failed")
        self.assertEqual(result["status_code"], 401)
        self.assertEqual(result["host"], "test-shop.myshopify.com")


if __name__ == "__main__":
    unittest.main()
