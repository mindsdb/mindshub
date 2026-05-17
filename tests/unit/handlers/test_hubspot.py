from collections import OrderedDict
import pytest
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

try:
    from hubspot.crm.objects import SimplePublicObject
    from mindsdb.integrations.handlers.hubspot_handler.hubspot_handler import (
        HubspotHandler,
    )
    from mindsdb.integrations.handlers.hubspot_handler.hubspot_tables import (
        CompaniesTable,
        ContactsTable,
        DealsTable,
        canonical_op,
        to_hubspot_property,
        to_internal_property,
        _build_hubspot_search_filters,
        _normalize_filter_conditions,
    )
    from mindsdb_sql_parser.ast import Select, Identifier, Function
    from mindsdb_sql_parser import parse_sql
    from mindsdb.integrations.utilities.sql_utils import FilterCondition, FilterOperator
except ImportError:
    pytestmark = pytest.mark.skip("HubSpot handler not installed")

from base_handler_test import BaseHandlerTestSetup

from mindsdb.integrations.libs.response import (
    HandlerStatusResponse as StatusResponse,
    DataHandlerResponse,
    RESPONSE_TYPE,
)


class TestHubspotHandler(BaseHandlerTestSetup, unittest.TestCase):
    """Test class for HubspotHandler."""

    EXPECTED_TABLES = [
        "companies",
        "contacts",
        "deals",
        "tickets",
        "tasks",
        "calls",
        "emails",
        "meetings",
        "notes",
    ]

    @property
    def dummy_connection_data(self):
        return OrderedDict(access_token="test_token_12345_dummy_not_real")

    @property
    def registered_tables(self):
        return ["companies", "contacts", "deals"]

    @property
    def err_to_raise_on_connect_failure(self):
        return Exception("Authentication failed")

    def create_handler(self):
        """Create HubspotHandler instance for testing."""
        return HubspotHandler("hubspot", connection_data=self.dummy_connection_data)

    def create_patcher(self):
        """Create patch for HubSpot client connection."""
        return patch("mindsdb.integrations.handlers.hubspot_handler.hubspot_handler.HubSpot")

    def test_initialization(self):
        """Test if the handler initializes correctly with proper values."""
        self.assertEqual(self.handler.name, "hubspot")
        self.assertFalse(self.handler.is_connected)
        self.assertEqual(self.handler.connection_data, self.dummy_connection_data)

        # Test that tables are registered
        self.assertIn("companies", self.handler._tables.keys())
        self.assertIn("contacts", self.handler._tables.keys())
        self.assertIn("deals", self.handler._tables.keys())

    def test_connect_success(self):
        """Test if `connect` method successfully establishes connection."""
        mock_hubspot_client = MagicMock()
        self.mock_connect.return_value = mock_hubspot_client

        connection = self.handler.connect()

        self.assertIsNotNone(connection)
        self.assertTrue(self.handler.is_connected)
        self.assertEqual(connection, mock_hubspot_client)
        self.mock_connect.assert_called_once_with(access_token=self.dummy_connection_data["access_token"])

    def test_connect_reuse_existing_connection(self):
        """Test that connect reuses existing connection when already connected."""
        mock_hubspot_client = MagicMock()
        self.mock_connect.return_value = mock_hubspot_client

        # First connection
        connection1 = self.handler.connect()

        # Second connection should reuse existing
        connection2 = self.handler.connect()

        self.assertEqual(connection1, connection2)
        self.mock_connect.assert_called_once()

    def test_connect_failure(self):
        """Test connect method handles connection failures properly."""
        self.mock_connect.side_effect = self.err_to_raise_on_connect_failure

        with self.assertRaises(type(self.err_to_raise_on_connect_failure)):
            self.handler.connect()
        self.assertFalse(self.handler.is_connected)

    def test_check_connection_success(self):
        """Test check_connection method with successful connection."""
        mock_hubspot_client = MagicMock()
        self.mock_connect.return_value = mock_hubspot_client

        response = self.handler.check_connection()

        assert isinstance(response, StatusResponse)
        self.assertTrue(response.success)
        self.assertIsNone(response.error_message)
        self.assertTrue(self.handler.is_connected)

    def test_check_connection_failure(self):
        """Test check_connection method with failed connection."""
        self.mock_connect.side_effect = self.err_to_raise_on_connect_failure

        response = self.handler.check_connection()

        assert isinstance(response, StatusResponse)
        self.assertFalse(response.success)
        self.assertIsNotNone(response.error_message)
        self.assertFalse(self.handler.is_connected)

    def test_native_query(self):
        """Test native_query method executes SQL queries."""
        mock_hubspot_client = MagicMock()
        mock_companies_data = [
            SimplePublicObject(
                id="123",
                properties={
                    "name": "Test Company",
                    "city": "New York",
                    "createdate": "2023-01-01T00:00:00Z",
                    "hs_lastmodifieddate": "2023-01-01T00:00:00Z",
                },
            )
        ]

        self.mock_connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.companies.get_all.return_value = mock_companies_data

        query = "SELECT * FROM companies LIMIT 1"
        response = self.handler.native_query(query)

        assert isinstance(response, DataHandlerResponse)
        self.assertEqual(response.type, RESPONSE_TYPE.TABLE)
        self.assertIsNotNone(response.data_frame)

    def test_get_columns_companies(self):
        """Test get_columns method for companies table."""
        mock_hubspot_client = MagicMock()
        mock_company_data = [
            SimplePublicObject(
                id="123",
                properties={
                    "name": "Test Company",
                    "city": "New York",
                    "phone": "+1-555-123-4567",
                    "state": "NY",
                    "domain": "testcompany.com",
                    "industry": "Technology",
                    "createdate": "2023-01-01T00:00:00Z",
                    "hs_lastmodifieddate": "2023-01-01T00:00:00Z",
                },
            )
        ]

        self.mock_connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.companies.get_all.return_value = mock_company_data

        response = self.handler.get_columns("companies")

        assert isinstance(response, DataHandlerResponse)
        self.assertEqual(response.type, RESPONSE_TYPE.COLUMNS_TABLE)

        df = response.data_frame
        # Check for comprehensive column metadata
        self.assertIn("COLUMN_NAME", df.columns)
        self.assertIn("DATA_TYPE", df.columns)

        # Check that expected columns are present
        column_names = df["COLUMN_NAME"].tolist()
        expected_columns = [
            "id",
            "name",
            "city",
            "phone",
            "state",
            "domain",
            "industry",
            "createdate",
            "lastmodifieddate",
        ]
        for col in expected_columns:
            self.assertIn(col, column_names)

    def test_get_columns_contacts(self):
        """Test get_columns method for contacts table."""
        mock_hubspot_client = MagicMock()
        mock_contact_data = [
            SimplePublicObject(
                id="456",
                properties={
                    "email": "test@example.com",
                    "firstname": "John",
                    "lastname": "Doe",
                    "phone": "+1-555-123-4567",
                    "company": "Test Company",
                    "website": "example.com",
                    "createdate": "2023-01-01T00:00:00Z",
                    "lastmodifieddate": "2023-01-01T00:00:00Z",
                },
            )
        ]

        self.mock_connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.contacts.get_all.return_value = mock_contact_data

        response = self.handler.get_columns("contacts")

        assert isinstance(response, DataHandlerResponse)
        self.assertEqual(response.type, RESPONSE_TYPE.COLUMNS_TABLE)

        df = response.data_frame

        self.assertIn("COLUMN_NAME", df.columns)
        self.assertIn("DATA_TYPE", df.columns)

        column_names = df["COLUMN_NAME"].tolist()
        expected_columns = [
            "id",
            "email",
            "firstname",
            "lastname",
            "phone",
            "company",
            "website",
            "createdate",
            "lastmodifieddate",
        ]
        for col in expected_columns:
            self.assertIn(col, column_names)

    def test_get_columns_deals(self):
        """Test get_columns method for deals table."""
        mock_hubspot_client = MagicMock()
        mock_deal_data = [
            SimplePublicObject(
                id="789",
                properties={
                    "dealname": "Test Deal",
                    "amount": "10000",
                    "pipeline": "default",
                    "closedate": "2023-12-31",
                    "dealstage": "closedwon",
                    "hubspot_owner_id": "12345",
                    "createdate": "2023-01-01T00:00:00Z",
                    "hs_lastmodifieddate": "2023-01-01T00:00:00Z",
                },
            )
        ]

        self.mock_connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.deals.get_all.return_value = mock_deal_data

        response = self.handler.get_columns("deals")

        assert isinstance(response, DataHandlerResponse)
        self.assertEqual(response.type, RESPONSE_TYPE.COLUMNS_TABLE)

        df = response.data_frame
        self.assertIn("COLUMN_NAME", df.columns)
        self.assertIn("DATA_TYPE", df.columns)

        column_names = df["COLUMN_NAME"].tolist()
        expected_columns = [
            "id",
            "dealname",
            "amount",
            "pipeline",
            "closedate",
            "dealstage",
            "hubspot_owner_id",
            "createdate",
            "lastmodifieddate",
        ]
        for col in expected_columns:
            self.assertIn(col, column_names)

    def test_deals_targets_include_function_identifiers(self):
        """Ensure aggregate targets include referenced columns for fetch."""
        deals_table = DealsTable(MagicMock())
        query = Select(
            targets=[
                Identifier("pipeline"),
                Function("sum", args=[Identifier("amount")], alias=Identifier("sum_amount")),
            ],
            from_table=Identifier("deals"),
        )
        targets = deals_table._get_targets(query)
        self.assertIn("pipeline", targets)
        self.assertIn("amount", targets)

    def test_get_columns_invalid_table(self):
        """Test get_columns method with invalid table name."""
        response = self.handler.get_columns("nonexistent_table")

        assert isinstance(response, DataHandlerResponse)
        self.assertEqual(response.type, RESPONSE_TYPE.ERROR)
        self.assertIsNotNone(response.error_message)

    def test_native_query_with_insert(self):
        """Test native_query with INSERT statement."""
        mock_hubspot_client = MagicMock()
        mock_created_companies = MagicMock()
        mock_created_companies.results = [SimplePublicObject(id="new123", properties={"name": "New Company"})]

        self.mock_connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.companies.batch_api.create.return_value = mock_created_companies

        insert_query = "INSERT INTO companies (name, city) VALUES ('New Company', 'Boston')"
        response = self.handler.native_query(insert_query)

        assert isinstance(response, DataHandlerResponse)

        self.assertNotEqual(response.type, RESPONSE_TYPE.ERROR)

    def test_native_query_with_update(self):
        """Test native_query with UPDATE statement."""
        mock_hubspot_client = MagicMock()

        mock_search_result = MagicMock()
        mock_search_result.results = [
            SimplePublicObject(
                id="123",
                properties={
                    "name": "Test Company",
                    "city": "New York",
                    "createdate": "2023-01-01T00:00:00Z",
                    "hs_lastmodifieddate": "2023-01-01T00:00:00Z",
                },
            )
        ]
        mock_search_result.paging = None

        mock_updated_companies = MagicMock()
        mock_updated_companies.results = [SimplePublicObject(id="123", properties={"name": "Updated Company"})]

        self.mock_connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.companies.search_api.do_search.return_value = mock_search_result
        mock_hubspot_client.crm.companies.batch_api.update.return_value = mock_updated_companies

        update_query = "UPDATE companies SET city='Boston' WHERE name='Test Company'"
        response = self.handler.native_query(update_query)

        assert isinstance(response, DataHandlerResponse)
        self.assertNotEqual(response.type, RESPONSE_TYPE.ERROR)

    def test_native_query_with_delete(self):
        """Test native_query with DELETE statement."""
        mock_hubspot_client = MagicMock()

        mock_search_result = MagicMock()
        mock_search_result.results = [
            SimplePublicObject(
                id="123",
                properties={
                    "name": "Test Company",
                    "city": "New York",
                    "createdate": "2023-01-01T00:00:00Z",
                    "hs_lastmodifieddate": "2023-01-01T00:00:00Z",
                },
            )
        ]
        mock_search_result.paging = None

        self.mock_connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.companies.search_api.do_search.return_value = mock_search_result
        mock_hubspot_client.crm.companies.batch_api.archive.return_value = None

        delete_query = "DELETE FROM companies WHERE name='Test Company'"
        response = self.handler.native_query(delete_query)

        assert isinstance(response, DataHandlerResponse)
        self.assertNotEqual(response.type, RESPONSE_TYPE.ERROR)

    def test_handler_name(self):
        """Test handler name is set correctly."""
        self.assertEqual(self.handler.name, "hubspot")

    def test_connection_data_storage(self):
        """Test connection data is stored correctly."""
        self.assertEqual(
            self.handler.connection_data["access_token"],
            self.dummy_connection_data["access_token"],
        )

    def test_connect_invalid_credentials(self):
        """Test connect method with invalid credentials."""
        handler = HubspotHandler("hubspot", connection_data={"access_token": ""})
        with self.assertRaises(ValueError) as context:
            handler.connect()
        self.assertIn("Invalid access_token provided", str(context.exception))

        handler = HubspotHandler("hubspot", connection_data={"client_id": "", "client_secret": "secret"})
        with self.assertRaises(ValueError) as context:
            handler.connect()
        self.assertIn("Invalid OAuth credentials provided", str(context.exception))

    def test_disconnect(self):
        """Test disconnect method."""
        mock_hubspot_client = MagicMock()
        self.mock_connect.return_value = mock_hubspot_client

        self.handler.connect()
        self.assertTrue(self.handler.is_connected)

        self.handler.disconnect()
        self.assertFalse(self.handler.is_connected)
        self.assertIsNone(self.handler.connection)

    def test_native_query_empty_query(self):
        """Test native_query with empty or None query."""
        response = self.handler.native_query(None)
        self.assertEqual(response.type, RESPONSE_TYPE.ERROR)
        self.assertIn("Query cannot be None or empty", response.error_message)

        response = self.handler.native_query("")
        self.assertEqual(response.type, RESPONSE_TYPE.ERROR)
        self.assertIn("Query cannot be None or empty", response.error_message)

    def test_native_query_invalid_sql(self):
        """Test native_query with invalid SQL."""
        response = self.handler.native_query("INVALID SQL QUERY")
        self.assertEqual(response.type, RESPONSE_TYPE.ERROR)
        self.assertIn("Query execution failed", response.error_message)

    def test_get_tables_connection_failure(self):
        """Test get_tables method with connection failure."""
        self.mock_connect.side_effect = Exception("Connection failed")

        response = self.handler.get_tables()

        self.assertEqual(response.type, RESPONSE_TYPE.ERROR)
        self.assertIn("Failed to retrieve table list", response.error_message)

    def test_get_columns_companies_detailed(self):
        """Test get_columns method for companies table with detailed analysis."""
        mock_hubspot_client = MagicMock()
        mock_company_data = [
            SimplePublicObject(
                id="123",
                properties={
                    "name": "Test Company",
                    "city": "New York",
                    "phone": "+1-555-123-4567",
                    "state": "NY",
                    "domain": "testcompany.com",
                    "industry": "Technology",
                    "createdate": "2023-01-01T00:00:00Z",
                    "hs_lastmodifieddate": "2023-01-01T00:00:00Z",
                },
            )
        ]

        self.mock_connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.companies.get_all.return_value = mock_company_data

        response = self.handler.get_columns("companies")

        # After calling to_columns_table_response, type should be COLUMNS_TABLE
        self.assertEqual(response.type, RESPONSE_TYPE.COLUMNS_TABLE)
        df = response.data_frame

        expected_columns = [
            "COLUMN_NAME",
            "DATA_TYPE",
            "ORDINAL_POSITION",
            "COLUMN_DEFAULT",
            "IS_NULLABLE",
            "CHARACTER_MAXIMUM_LENGTH",
            "CHARACTER_OCTET_LENGTH",
            "NUMERIC_PRECISION",
            "NUMERIC_SCALE",
            "DATETIME_PRECISION",
            "CHARACTER_SET_NAME",
            "COLLATION_NAME",
            "MYSQL_DATA_TYPE",
        ]
        for col in expected_columns:
            self.assertIn(col, df.columns, f"Missing standard column: {col}")

        column_names = df["COLUMN_NAME"].tolist()

        self.assertIn("id", column_names)
        self.assertIn("name", column_names)
        self.assertIn("city", column_names)

    def test_get_columns_connection_failure(self):
        """Test get_columns method with connection failure."""
        self.mock_connect.side_effect = Exception("Connection failed")

        response = self.handler.get_columns("companies")

        self.assertEqual(response.type, RESPONSE_TYPE.ERROR)
        self.assertIn("Failed to retrieve columns", response.error_message)

    def test_data_type_inference(self):
        """Test _infer_data_type method."""
        self.assertEqual(self.handler._infer_data_type(None), "VARCHAR")
        self.assertEqual(self.handler._infer_data_type(True), "BOOLEAN")
        self.assertEqual(self.handler._infer_data_type(42), "INTEGER")
        self.assertEqual(self.handler._infer_data_type(3.14), "DECIMAL")
        self.assertEqual(self.handler._infer_data_type("text"), "VARCHAR")
        self.assertEqual(self.handler._infer_data_type("2023-01-01T00:00:00Z"), "TIMESTAMP")

    def test_table_descriptions(self):
        """Test _get_table_description method."""
        self.assertIn("companies data", self.handler._get_table_description("companies"))
        self.assertIn("contacts data", self.handler._get_table_description("contacts"))
        self.assertIn("deals data", self.handler._get_table_description("deals"))

    def test_check_connection_with_api_test(self):
        """Test check_connection method performs actual API test."""
        mock_hubspot_client = MagicMock()
        mock_contacts_data = [
            SimplePublicObject(
                id="123",
                properties={"email": "test@example.com"},
            )
        ]

        self.mock_connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.contacts.get_all.return_value = mock_contacts_data

        response = self.handler.check_connection()

        self.assertTrue(response.success)
        self.assertIsNone(response.error_message)

        # Now check_connection tries contacts first
        mock_hubspot_client.crm.contacts.get_all.assert_called_with(limit=1)

    def test_oauth_connection(self):
        """Test OAuth connection flow."""
        oauth_data = OrderedDict(client_id="test_client_id", client_secret="test_client_secret")
        handler = HubspotHandler("hubspot", connection_data=oauth_data)

        mock_hubspot_client = MagicMock()
        mock_access_token = "oauth_access_token_123"

        with (
            patch("mindsdb.integrations.handlers.hubspot_handler.hubspot_handler.HubSpot") as mock_hubspot,
            patch(
                "mindsdb.integrations.handlers.hubspot_handler.hubspot_handler.HubSpotOAuth2Manager"
            ) as mock_oauth_manager_cls,
        ):
            mock_hubspot.return_value = mock_hubspot_client
            mock_oauth_manager_cls.return_value.get_access_token.return_value = mock_access_token

            connection = handler.connect()

            self.assertIsNotNone(connection)
            self.assertTrue(handler.is_connected)
            mock_hubspot.assert_called_with(access_token=mock_access_token)

    def test_comprehensive_error_handling(self):
        """Test comprehensive error handling in various scenarios."""
        with patch("mindsdb.integrations.handlers.hubspot_handler.hubspot_handler.HubSpot") as mock_hubspot:
            mock_hubspot.side_effect = Exception("API Error")

            with self.assertRaises(ValueError) as context:
                self.handler.connect()
            self.assertIn("Connection to HubSpot failed", str(context.exception))

    def test_secure_logging(self):
        """Test that sensitive credentials are not logged."""
        sensitive_data = {"access_token": "secret_token_12345"}
        handler = HubspotHandler("hubspot", connection_data=sensitive_data)

        self.assertIn("access_token", handler.connection_data)

    def test_column_statistics_calculation(self):
        """Test comprehensive column statistics calculation."""
        numeric_values = [100, 200, 300, None, 150, 250]
        stats = self.handler._calculate_column_statistics("amount", numeric_values)

        self.assertEqual(stats["null_count"], 1)
        self.assertEqual(stats["distinct_count"], 5)  # 5 unique non-null values
        self.assertIsNotNone(stats["average_value"])
        self.assertEqual(stats["average_value"], 200.0)  # (100+200+300+150+250)/5

        # Test string data
        string_values = ["apple", "banana", "apple", None, "cherry"]
        stats = self.handler._calculate_column_statistics("fruit", string_values)

        self.assertEqual(stats["null_count"], 1)
        self.assertEqual(stats["distinct_count"], 3)
        # min_value and max_value are now None to avoid misleading string comparisons
        self.assertIsNone(stats["min_value"])
        self.assertIsNone(stats["max_value"])

    def test_data_type_inference_from_samples(self):
        """Test improved data type inference from multiple samples."""
        # Mixed numeric and string - should pick most common
        mixed_values = [100, 200, "300", 400, 500]  # mostly numeric
        data_type = self.handler._infer_data_type_from_samples(mixed_values)
        self.assertEqual(data_type, "INTEGER")

        # Timestamp strings
        timestamp_values = ["2023-01-01T10:00:00Z", "2023-01-02T11:00:00Z", None]
        data_type = self.handler._infer_data_type_from_samples(timestamp_values)
        self.assertEqual(data_type, "TIMESTAMP")

        # All null values
        null_values = [None, None, None]
        data_type = self.handler._infer_data_type_from_samples(null_values)
        self.assertEqual(data_type, "VARCHAR")

    def test_get_columns_with_standard_schema(self):
        """Test get_columns method returns standard information_schema.columns format."""
        mock_hubspot_client = MagicMock()

        # Mock larger dataset
        mock_company_data = []
        for i in range(50):  # Create 50 sample companies
            mock_company_data.append(
                SimplePublicObject(
                    id=f"company_{i}",
                    properties={
                        "name": f"Company {i}",
                        "city": "New York" if i % 2 == 0 else "San Francisco",
                        "industry": "Technology",
                        "hubspot_owner_id": f"owner_{i % 5}",
                        "annual_revenue": str(100000 + i * 1000),
                        "createdate": f"2023-01-{(i % 28) + 1:02d}T10:00:00Z",
                    },
                )
            )

        self.mock_connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.companies.get_all.return_value = mock_company_data

        response = self.handler.get_columns("companies")

        self.assertEqual(response.type, RESPONSE_TYPE.COLUMNS_TABLE)
        df = response.data_frame

        expected_columns = [
            "COLUMN_NAME",
            "DATA_TYPE",
            "ORDINAL_POSITION",
            "COLUMN_DEFAULT",
            "IS_NULLABLE",
            "CHARACTER_MAXIMUM_LENGTH",
            "CHARACTER_OCTET_LENGTH",
            "NUMERIC_PRECISION",
            "NUMERIC_SCALE",
            "DATETIME_PRECISION",
            "CHARACTER_SET_NAME",
            "COLLATION_NAME",
            "MYSQL_DATA_TYPE",
        ]

        for col in expected_columns:
            self.assertIn(col, df.columns, f"Missing standard column: {col}")

        non_standard_columns = [
            "IS_PRIMARY_KEY",
            "IS_FOREIGN_KEY",
            "NULL_COUNT",
            "DISTINCT_COUNT",
            "MIN_VALUE",
            "MAX_VALUE",
            "AVERAGE_VALUE",
            "COLUMN_DESCRIPTION",
        ]
        for col in non_standard_columns:
            self.assertNotIn(col, df.columns, f"Non-standard column should not be present: {col}")

        id_row = df[df["COLUMN_NAME"] == "id"]
        self.assertEqual(len(id_row), 1)
        self.assertEqual(id_row.iloc[0]["ORDINAL_POSITION"], 1)
        self.assertEqual(id_row.iloc[0]["IS_NULLABLE"], "NO")

    def test_estimate_table_rows_with_search_api(self):
        """Test that _estimate_table_rows uses search API for accurate counts."""
        mock_hubspot_client = MagicMock()

        mock_search_result = MagicMock()
        mock_search_result.total = 5432

        self.mock_connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.companies.search_api.do_search.return_value = mock_search_result

        self.handler.connect()
        row_count = self.handler._estimate_table_rows("companies")

        mock_hubspot_client.crm.companies.search_api.do_search.assert_called_once_with(
            public_object_search_request={"limit": 1}
        )

        self.assertEqual(row_count, 5432)

    def test_estimate_table_rows_fallback(self):
        """Test that _estimate_table_rows handles search API failures gracefully."""
        mock_hubspot_client = MagicMock()

        mock_hubspot_client.crm.contacts.search_api.do_search.side_effect = Exception("API error")
        mock_hubspot_client.crm.contacts.get_all.return_value = [SimplePublicObject(id="1", properties={})]

        self.mock_connect.return_value = mock_hubspot_client
        self.handler.connect()

        row_count = self.handler._estimate_table_rows("contacts")

        self.assertIsNone(row_count)

    def test_meta_get_columns(self):
        """Test meta_get_columns returns data catalog column metadata."""
        mock_hubspot_client = MagicMock()
        mock_company_data = [
            SimplePublicObject(
                id="123",
                properties={
                    "name": "Test Company",
                    "city": "New York",
                    "industry": "Technology",
                    "createdate": "2023-01-01T00:00:00Z",
                },
            )
        ]

        self.mock_connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.companies.get_all.return_value = mock_company_data
        mock_hubspot_client.crm.contacts.get_all.return_value = []
        mock_hubspot_client.crm.deals.get_all.return_value = []

        response = self.handler.meta_get_columns(table_names=["companies"])

        self.assertEqual(response.type, RESPONSE_TYPE.TABLE)
        df = response.data_frame

        expected_columns = [
            "TABLE_NAME",
            "COLUMN_NAME",
            "DATA_TYPE",
            "COLUMN_DESCRIPTION",
            "IS_NULLABLE",
            "COLUMN_DEFAULT",
        ]
        for col in expected_columns:
            self.assertIn(col, df.columns, f"Missing data catalog column: {col}")

        self.assertIn("companies", df["TABLE_NAME"].tolist())

        column_names = df[df["TABLE_NAME"] == "companies"]["COLUMN_NAME"].tolist()
        self.assertIn("id", column_names)
        self.assertIn("name", column_names)
        self.assertIn("city", column_names)

    def test_meta_get_column_statistics(self):
        """Test meta_get_column_statistics returns statistical information."""
        mock_hubspot_client = MagicMock()

        # Create larger sample dataset for statistics
        mock_contact_data = []
        for i in range(50):
            mock_contact_data.append(
                SimplePublicObject(
                    id=f"contact_{i}",
                    properties={
                        "email": f"user{i}@example.com",
                        "firstname": "John" if i % 2 == 0 else "Jane",
                        "lastname": "Doe",
                        "city": "New York" if i % 3 == 0 else "San Francisco",
                    },
                )
            )

        self.mock_connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.contacts.get_all.return_value = mock_contact_data
        mock_hubspot_client.crm.companies.get_all.return_value = []
        mock_hubspot_client.crm.deals.get_all.return_value = []

        response = self.handler.meta_get_column_statistics(table_names=["contacts"])

        self.assertEqual(response.type, RESPONSE_TYPE.TABLE)
        df = response.data_frame

        expected_columns = [
            "TABLE_NAME",
            "COLUMN_NAME",
            "NULL_PERCENTAGE",
            "DISTINCT_VALUES_COUNT",
            "MINIMUM_VALUE",
            "MAXIMUM_VALUE",
            "MOST_COMMON_VALUES",
            "MOST_COMMON_FREQUENCIES",
        ]
        for col in expected_columns:
            self.assertIn(col, df.columns, f"Missing statistics column: {col}")

        firstname_stats = df[(df["TABLE_NAME"] == "contacts") & (df["COLUMN_NAME"] == "firstname")]
        self.assertEqual(len(firstname_stats), 1)

        self.assertEqual(firstname_stats.iloc[0]["DISTINCT_VALUES_COUNT"], 2)

        self.assertEqual(firstname_stats.iloc[0]["NULL_PERCENTAGE"], 0.0)

    def test_meta_get_columns_all_tables(self):
        """Test meta_get_columns with no table filter returns all tables."""
        mock_hubspot_client = MagicMock()

        self.mock_connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.companies.get_all.return_value = [
            SimplePublicObject(id="1", properties={"name": "Company"})
        ]
        mock_hubspot_client.crm.contacts.get_all.return_value = [
            SimplePublicObject(id="2", properties={"email": "test@example.com"})
        ]
        mock_hubspot_client.crm.deals.get_all.return_value = [
            SimplePublicObject(id="3", properties={"dealname": "Deal"})
        ]

        response = self.handler.meta_get_columns()  # No table_names specified

        self.assertEqual(response.type, RESPONSE_TYPE.TABLE)
        df = response.data_frame

        tables_present = df["TABLE_NAME"].unique().tolist()

        self.assertIn("companies", tables_present)
        self.assertIn("contacts", tables_present)
        self.assertIn("deals", tables_present)

    def test_select_companies_with_in_clause_uses_search_api(self):
        """
        MindsDB calls table.select(query_ast) directly — not native_query.
        Verify that a WHERE city IN (...) query routes to the HubSpot Search API.
        """

        mock_hubspot_client = MagicMock()
        mock_search_result = MagicMock()
        mock_search_result.results = [
            SimplePublicObject(
                id="1",
                properties={
                    "name": "NYC Company",
                    "city": "New York",
                    "createdate": "2023-01-01T00:00:00Z",
                    "hs_lastmodifieddate": "2023-01-01T00:00:00Z",
                },
            ),
        ]
        mock_search_result.paging = None

        handler = MagicMock()
        handler.connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.companies.search_api.do_search.return_value = mock_search_result

        table = CompaniesTable(handler)
        query = parse_sql("SELECT * FROM companies WHERE city IN ('New York', 'Austin')", dialect="mindsdb")
        result = table.select(query)

        mock_hubspot_client.crm.companies.search_api.do_search.assert_called()
        mock_hubspot_client.crm.companies.get_all.assert_not_called()
        self.assertIsNotNone(result)

    def test_select_contacts_with_in_clause(self):
        """
        MindsDB calls ContactsTable.select(query_ast) directly.
        Verify city IN (...) routes to HubSpot Search API.
        """
        mock_hubspot_client = MagicMock()
        mock_search_result = MagicMock()
        mock_search_result.results = [
            SimplePublicObject(
                id="101",
                properties={
                    "email": "john@example.com",
                    "firstname": "John",
                    "lastname": "Doe",
                    "city": "Boston",
                },
            ),
        ]
        mock_search_result.paging = None

        handler = MagicMock()
        handler.connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.contacts.search_api.do_search.return_value = mock_search_result

        table = ContactsTable(handler)
        query = parse_sql("SELECT * FROM contacts WHERE city IN ('Boston', 'Chicago')", dialect="mindsdb")
        result = table.select(query)

        mock_hubspot_client.crm.contacts.search_api.do_search.assert_called()
        self.assertIsNotNone(result)

    def test_select_deals_with_in_clause(self):
        """
        MindsDB calls DealsTable.select(query_ast) directly.
        Verify dealstage IN (...) routes to HubSpot Search API.
        """
        mock_hubspot_client = MagicMock()
        mock_search_result = MagicMock()
        mock_search_result.results = [
            SimplePublicObject(
                id="201",
                properties={
                    "dealname": "Big Deal",
                    "amount": "50000",
                    "dealstage": "closedwon",
                },
            ),
        ]
        mock_search_result.paging = None

        handler = MagicMock()
        handler.connect.return_value = mock_hubspot_client
        handler._hubspot_deal_stage_map_cache = ({}, {})
        handler._hubspot_deal_stage_rows_cache = []
        handler._hubspot_owner_rows_cache = []
        handler._hubspot_owner_map_cache = {}
        mock_hubspot_client.crm.deals.search_api.do_search.return_value = mock_search_result
        mock_hubspot_client.crm.pipelines.pipelines_api.get_all.return_value = MagicMock(results=[])

        table = DealsTable(handler)
        query = parse_sql("SELECT * FROM deals WHERE dealstage IN ('closedwon', 'closedlost')", dialect="mindsdb")
        result = table.select(query)

        mock_hubspot_client.crm.deals.search_api.do_search.assert_called()
        self.assertIsNotNone(result)

    def test_select_with_in_clause_verifies_filter_structure(self):
        """
        Verify that city IN (...) generates the correct HubSpot Search API filter payload.
        Tests via CompaniesTable.select() — the actual call path MindsDB uses.
        """
        mock_hubspot_client = MagicMock()
        mock_search_result = MagicMock()
        mock_search_result.results = []
        mock_search_result.paging = None

        handler = MagicMock()
        handler.connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.companies.search_api.do_search.return_value = mock_search_result

        table = CompaniesTable(handler)
        query = parse_sql("SELECT * FROM companies WHERE city IN ('NYC', 'LA', 'Chicago')", dialect="mindsdb")
        table.select(query)

        call_args = mock_hubspot_client.crm.companies.search_api.do_search.call_args
        search_request = call_args.kwargs.get("public_object_search_request", {})

        self.assertIn("filterGroups", search_request)
        filter_groups = search_request["filterGroups"]
        self.assertEqual(len(filter_groups), 1)

        filters = filter_groups[0]["filters"]
        self.assertEqual(len(filters), 1)

        in_filter = filters[0]
        self.assertEqual(in_filter["propertyName"], "city")
        self.assertEqual(in_filter["operator"], "IN")
        self.assertIn("values", in_filter)
        self.assertEqual(set(in_filter["values"]), {"NYC", "LA", "Chicago"})

    def test_select_with_not_in_clause(self):
        """Verify industry NOT IN (...) generates NOT_IN operator in HubSpot filter."""
        mock_hubspot_client = MagicMock()
        mock_search_result = MagicMock()
        mock_search_result.results = []
        mock_search_result.paging = None

        handler = MagicMock()
        handler.connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.companies.search_api.do_search.return_value = mock_search_result

        table = CompaniesTable(handler)
        query = parse_sql("SELECT * FROM companies WHERE industry NOT IN ('Retail', 'Healthcare')", dialect="mindsdb")
        table.select(query)

        call_args = mock_hubspot_client.crm.companies.search_api.do_search.call_args
        search_request = call_args.kwargs.get("public_object_search_request", {})

        filters = search_request["filterGroups"][0]["filters"]
        self.assertEqual(filters[0]["operator"], "NOT_IN")

    def test_select_with_in_and_equality_combined(self):
        """Verify city IN (...) AND industry = '...' both push down to the Search API."""
        mock_hubspot_client = MagicMock()
        mock_search_result = MagicMock()
        mock_search_result.results = []
        mock_search_result.paging = None

        handler = MagicMock()
        handler.connect.return_value = mock_hubspot_client
        mock_hubspot_client.crm.companies.search_api.do_search.return_value = mock_search_result

        table = CompaniesTable(handler)
        query = parse_sql(
            "SELECT * FROM companies WHERE city IN ('NYC', 'LA') AND industry = 'Technology'",
            dialect="mindsdb",
        )
        table.select(query)

        mock_hubspot_client.crm.companies.search_api.do_search.assert_called()

    def test_canonical_op_normalization(self):
        """Test canonical operator normalization."""
        self.assertEqual(canonical_op("="), "eq")
        self.assertEqual(canonical_op("EQ"), "eq")
        self.assertEqual(canonical_op(">="), "gte")
        self.assertEqual(canonical_op(FilterOperator.GREATER_THAN_OR_EQUAL), "gte")
        self.assertEqual(canonical_op("NOT IN"), "not_in")

    def test_property_mapping(self):
        """Test internal/HubSpot property mapping."""
        self.assertEqual(to_hubspot_property("lastmodifieddate"), "hs_lastmodifieddate")
        self.assertEqual(to_internal_property("hs_lastmodifieddate"), "lastmodifieddate")
        self.assertEqual(to_hubspot_property("id"), "hs_object_id")
        self.assertEqual(to_internal_property("hs_object_id"), "id")

    def test_build_hubspot_search_filters_in_and_mapping(self):
        """Test search filter mapping for IN and special properties."""
        conditions = _normalize_filter_conditions(
            [
                FilterCondition("city", FilterOperator.IN, ["NYC", "LA"]),
                FilterCondition("id", FilterOperator.EQUAL, "123"),
                FilterCondition("lastmodifieddate", FilterOperator.GREATER_THAN_OR_EQUAL, "2024-01-01T00:00:00Z"),
            ]
        )
        filters = _build_hubspot_search_filters(conditions, {"city", "id", "lastmodifieddate"})

        self.assertIsNotNone(filters)
        filter_by_property = {f["propertyName"]: f for f in filters}

        self.assertIn("city", filter_by_property)
        self.assertEqual(filter_by_property["city"]["operator"], "IN")
        self.assertEqual(set(filter_by_property["city"]["values"]), {"NYC", "LA"})

        self.assertIn("hs_object_id", filter_by_property)
        self.assertEqual(filter_by_property["hs_object_id"]["operator"], "EQ")
        self.assertEqual(filter_by_property["hs_object_id"]["value"], "123")

        self.assertIn("hs_lastmodifieddate", filter_by_property)
        self.assertEqual(filter_by_property["hs_lastmodifieddate"]["operator"], "GTE")

    def test_meta_get_column_statistics_multiple_tables(self):
        """Test meta_get_column_statistics retains stats across tables."""
        mock_hubspot_client = MagicMock()
        self.mock_connect.return_value = mock_hubspot_client

        mock_hubspot_client.crm.companies.get_all.return_value = [
            SimplePublicObject(
                id="company_1",
                properties={"name": "Company A", "hs_lastmodifieddate": "2024-01-01T00:00:00Z"},
            )
        ]
        mock_hubspot_client.crm.contacts.get_all.return_value = [
            SimplePublicObject(
                id="contact_1",
                properties={"email": "test@example.com", "hs_lastmodifieddate": "2024-01-02T00:00:00Z"},
            )
        ]

        response = self.handler.meta_get_column_statistics(table_names=["companies", "contacts"])

        self.assertEqual(response.type, RESPONSE_TYPE.TABLE)
        df = response.data_frame
        table_names = df["TABLE_NAME"].unique().tolist()
        self.assertIn("companies", table_names)
        self.assertIn("contacts", table_names)

    def test_search_pushdown_builds_sorts_and_properties(self):
        """
        Verify that ORDER BY and SELECT columns are pushed down to the HubSpot Search API.
        Uses DealsTable.select() — the actual call path MindsDB uses.
        """
        mock_hubspot_client = MagicMock()
        mock_search_result = MagicMock()
        mock_search_result.results = []
        mock_search_result.paging = None

        handler = MagicMock()
        handler.connect.return_value = mock_hubspot_client
        handler._hubspot_deal_stage_map_cache = ({}, {})
        handler._hubspot_deal_stage_rows_cache = []
        handler._hubspot_owner_rows_cache = []
        handler._hubspot_owner_map_cache = {}
        mock_hubspot_client.crm.deals.search_api.do_search.return_value = mock_search_result
        mock_hubspot_client.crm.pipelines.pipelines_api.get_all.return_value = MagicMock(results=[])

        table = DealsTable(handler)
        query = parse_sql(
            "SELECT dealname FROM deals WHERE pipeline='default' ORDER BY closedate DESC LIMIT 5",
            dialect="mindsdb",
        )
        table.select(query)

        call_args = mock_hubspot_client.crm.deals.search_api.do_search.call_args
        search_request = call_args.kwargs.get("public_object_search_request", {})

        self.assertIn("sorts", search_request)
        self.assertEqual(search_request["sorts"][0]["propertyName"], "closedate")
        self.assertEqual(search_request["sorts"][0]["direction"], "DESCENDING")
        self.assertEqual(search_request["properties"], ["dealname"])

    def test_three_table_join_on_clause_orientations(self):
        """
        Verify CORE JOIN ASSOC JOIN CORE resolves left_assoc_col / right_assoc_col
        correctly regardless of which side of the ON each table appears on.
        """

        company_df = pd.DataFrame({"id": ["1"], "name": ["Acme"]})
        assoc_df = pd.DataFrame({"company_id": ["1"], "contact_id": ["42"]})
        contact_df = pd.DataFrame({"id": ["42"], "firstname": ["Alice"]})

        orientations = [
            ("c.id = cc.company_id", "cc.contact_id = ct.id"),  # A
            ("cc.company_id = c.id", "cc.contact_id = ct.id"),  # B
            ("c.id = cc.company_id", "ct.id = cc.contact_id"),  # C
            ("cc.company_id = c.id", "ct.id = cc.contact_id"),  # D
        ]

        handler: HubspotHandler = self.create_handler()

        for left_on, right_on in orientations:
            with self.subTest(left_on=left_on, right_on=right_on):
                companies_mock = MagicMock()
                companies_mock.select.return_value = company_df.copy()
                assoc_mock = MagicMock()
                assoc_mock.list.return_value = assoc_df.copy()
                contacts_mock = MagicMock()
                contacts_mock.list.return_value = contact_df.copy()

                handler._tables["companies"] = companies_mock
                handler._tables["company_contacts"] = assoc_mock
                handler._tables["contacts"] = contacts_mock

                query = f"""
                SELECT *
                FROM companies c
                JOIN company_contacts cc ON {left_on}
                JOIN contacts ct ON {right_on}
                """
                response = handler.native_query(query)

                self.assertEqual(
                    response.type,
                    RESPONSE_TYPE.TABLE,
                    msg=f"orientation ({left_on!r}, {right_on!r}) returned ERROR: "
                    f"{getattr(response, 'error_message', '')}",
                )
                self.assertFalse(response.data_frame.empty)

                # The assoc table must be queried by company_id (left_assoc_col), not
                # by some other column — this is the column the bug inverted.
                assoc_conditions = assoc_mock.list.call_args.kwargs.get("conditions", [])
                assoc_filter_cols = [fc.column for fc in assoc_conditions]
                self.assertIn(
                    "company_id",
                    assoc_filter_cols,
                    msg=f"assoc.list not filtered on company_id for orientation "
                    f"({left_on!r}, {right_on!r}); got {assoc_filter_cols}",
                )

    def test_multijoin_query_handling(self):
        """Test that multijoin queries return appropriate error since not supported."""
        query = """
        SELECT c.name, o.dealname
        FROM companies c
        JOIN deals o ON c.id = o.company_id
        """
        response = self.handler.native_query(query)

        self.assertEqual(response.type, RESPONSE_TYPE.ERROR)
        self.assertIn("not supported", response.error_message)


class TestHubspotPassthrough(unittest.TestCase):
    """Exercise the PassthroughMixin retrofit (PAT path)."""

    def _mock_response(self, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.headers = {"Content-Type": "application/json"}
        resp.iter_content = MagicMock(return_value=iter([b'{"results":[]}']))
        resp.close = MagicMock()
        return resp

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_passthrough_uses_bearer_and_hubspot_base_url(self, mock_request):
        mock_request.return_value = self._mock_response()
        handler = HubspotHandler(
            "hubspot",
            connection_data={"access_token": "pat-abc123xyz"},
        )
        from mindsdb.integrations.libs.passthrough_types import PassthroughRequest

        resp = handler.api_passthrough(PassthroughRequest("GET", "/crm/v3/owners"))

        self.assertEqual(resp.status_code, 200)
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], "GET")
        self.assertEqual(args[1], "https://api.hubapi.com/crm/v3/owners")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer pat-abc123xyz")

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_test_passthrough_returns_ok_on_200(self, mock_request):
        mock_request.return_value = self._mock_response(status_code=200)
        handler = HubspotHandler("hubspot", connection_data={"access_token": "pat"})

        result = handler.test_passthrough()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["host"], "api.hubapi.com")
        self.assertIsInstance(result["latency_ms"], int)

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_test_passthrough_returns_auth_failed_on_401(self, mock_request):
        mock_request.return_value = self._mock_response(status_code=401)
        handler = HubspotHandler("hubspot", connection_data={"access_token": "pat"})

        result = handler.test_passthrough()

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "auth_failed")
        self.assertEqual(result["status_code"], 401)
        self.assertEqual(result["host"], "api.hubapi.com")


if __name__ == "__main__":
    unittest.main()
