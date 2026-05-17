from collections import OrderedDict
import pytest
import unittest
from unittest.mock import patch, MagicMock

try:
    from salesforce_api.exceptions import AuthenticationError, RestRequestCouldNotBeUnderstoodError
    from mindsdb.integrations.handlers.salesforce_handler.salesforce_handler import SalesforceHandler
    from mindsdb.integrations.handlers.salesforce_handler.salesforce_tables import create_table_class
    from mindsdb.integrations.handlers.salesforce_handler.constants import get_soql_instructions
except ImportError:
    pytestmark = pytest.mark.skip("Salesforce handler not installed")

from mindsdb_sql_parser.ast import BinaryOperation, Constant, Identifier, Select, Star
from base_handler_test import BaseHandlerTestSetup, BaseAPIResourceTestSetup
from mindsdb.integrations.utilities.sql_utils import FilterCondition, FilterOperator

from mindsdb.integrations.libs.response import (
    TableResponse,
    HandlerStatusResponse as StatusResponse,
    RESPONSE_TYPE,
)


class TestSalesforceHandler(BaseHandlerTestSetup, unittest.TestCase):
    @property
    def dummy_connection_data(self):
        return OrderedDict(
            username="demo@example.com",
            password="demo_password",
            client_id="3MVG9lKcPoNINVBIPJjdw1J9LLM82HnZz9Yh7ZJnY",
            client_secret="5A52C1A1E21DF9012IODC9ISNXXAADDA9",
        )

    def create_handler(self):
        return SalesforceHandler("salesforce", connection_data=self.dummy_connection_data)

    def create_patcher(self):
        return patch("salesforce_api.Salesforce")

    def test_salesforce_init_success(self):
        import mindsdb.integrations.handlers.salesforce_handler as m

        assert m.import_error is None
        assert m.Handler is not None
        # Check metadata
        assert m.name == "salesforce"
        assert m.title == "Salesforce"
        assert m.type is not None

    def test_connect(self):
        """
        Test if `connect` method successfully establishes a connection and sets `is_connected` flag to True.
        Also, verifies that salesforce_api.Salesforce is instantiated exactly once.
        """
        self.mock_connect.return_value = MagicMock()
        connection = self.handler.connect()

        self.assertIsNotNone(connection)
        self.assertTrue(self.handler.is_connected)
        self.mock_connect.assert_called_once()

    def test_connect_missing_required_params_raises(self):
        handler = SalesforceHandler("salesforce", connection_data={"username": "demo"})
        with self.assertRaises(ValueError):
            handler.connect()

    def test_connect_reuses_existing_connection(self):
        existing = MagicMock()
        self.handler.connection = existing
        self.handler.is_connected = True

        connection = self.handler.connect()

        self.assertIs(connection, existing)
        self.mock_connect.assert_not_called()

    def test_connect_authentication_error_is_raised(self):
        self.mock_connect.side_effect = AuthenticationError("invalid")
        with self.assertRaises(AuthenticationError):
            self.handler.connect()

    def test_connect_unknown_error_is_raised(self):
        self.mock_connect.side_effect = RuntimeError("boom")
        with self.assertRaises(RuntimeError):
            self.handler.connect()

    def test_native_query_flattens_nested_resources(self):
        connection = MagicMock()
        connection.sobjects.query.return_value = [
            {
                "attributes": {"type": "Opportunity"},
                "Id": "1",
                "Name": "Opp",
                "Account": {
                    "attributes": {"type": "Account"},
                    "Name": "Acme",
                    "Industry": "Tech",
                },
            }
        ]
        self.handler.connection = connection
        self.handler.is_connected = True
        self.handler.resource_names = ["Account"]

        response = self.handler.native_query("SELECT Id FROM Opportunity")

        self.assertEqual(response.type, RESPONSE_TYPE.TABLE)
        df = response.data_frame
        self.assertIn("Account_Name", df.columns)
        self.assertIn("Account_Industry", df.columns)
        self.assertEqual(df.iloc[0]["Account_Name"], "Acme")

    def test_native_query_handles_rest_error(self):
        connection = MagicMock()
        rest_error = RestRequestCouldNotBeUnderstoodError("bad query")
        connection.sobjects.query.side_effect = rest_error
        self.handler.connection = connection
        self.handler.is_connected = True

        response = self.handler.native_query("SELECT Id FROM Bad")

        self.assertEqual(response.type, RESPONSE_TYPE.ERROR)
        self.assertEqual(response.error_message, str(rest_error))

    def test_native_query_handles_generic_error(self):
        connection = MagicMock()
        connection.sobjects.query.side_effect = RuntimeError("boom")
        self.handler.connection = connection
        self.handler.is_connected = True

        response = self.handler.native_query("SELECT Id FROM Bad")

        self.assertEqual(response.type, RESPONSE_TYPE.ERROR)
        self.assertIn("boom", response.error_message)

    def test_check_connection_success(self):
        """
        Test that the `check_connection` method returns a StatusResponse object and accurately reflects the connection status on a successful connection.
        """
        response = self.handler.check_connection()

        self.assertTrue(response.success)
        assert isinstance(response, StatusResponse)
        self.assertFalse(response.error_message)

    def test_check_connection_failure(self):
        """
        Test that the `check_connection` method returns a StatusResponse object and accurately reflects the connection status on a failed connection.
        """
        self.mock_connect.side_effect = AuthenticationError("Invalid credentials")
        response = self.handler.check_connection()

        self.assertFalse(response.success)
        assert isinstance(response, StatusResponse)
        self.assertTrue(response.error_message)

    def test_get_tables(self):
        """
        Test that the `get_tables` method returns a TableResponse with a list of tables mapped from the Salesforce API.
        """
        mock_tables = ["Account", "Contact"]
        self.mock_connect.return_value = MagicMock(
            sobjects=MagicMock(
                describe=lambda: {"sobjects": [{"name": table, "queryable": True} for table in mock_tables]}
            )
        )
        self.handler.connect()
        response = self.handler.get_tables()

        assert isinstance(response, TableResponse)
        self.assertEqual(response.type, RESPONSE_TYPE.TABLE)

        df = response.data_frame
        self.assertEqual(len(df), len(mock_tables))
        self.assertEqual(list(df["table_name"]), [name.lower() for name in mock_tables])

    def test_get_columns(self):
        """
        Test that the `get_columns` method returns a TableResponse with a list of columns for a given table.
        """
        mock_columns = ["Id", "Name", "Email"]
        mock_table = "Contact"

        # Create a mock for the Contact object that will be accessed via getattr
        contact_mock = MagicMock()
        contact_mock.describe.return_value = {"fields": [{"name": column} for column in mock_columns]}

        # Create the main sobjects mock
        sobjects_mock = MagicMock()
        sobjects_mock.describe.return_value = {"sobjects": [{"name": mock_table, "queryable": True}]}

        # Set the contact attribute (lowercase) on the sobjects mock since the handler uses resource_name.lower()
        setattr(sobjects_mock, mock_table.lower(), contact_mock)

        # Create the client mock
        client_mock = MagicMock()
        client_mock.sobjects = sobjects_mock

        # Make sure the mock_connect always returns the same client mock
        self.mock_connect.return_value = client_mock

        self.handler.connect()
        response = self.handler.get_columns(mock_table)

        assert isinstance(response, TableResponse)
        self.assertEqual(response.type, RESPONSE_TYPE.TABLE)

        df = response.data_frame
        self.assertEqual(len(df), len(mock_columns))
        self.assertEqual(list(df["Field"]), mock_columns)

    def test_pre_filtering_with_include_tables(self):
        """
        Test that pre-filtering works correctly when include_tables is specified.
        """
        # Setup handler with include_tables
        connection_data = OrderedDict(
            username="demo@example.com",
            password="demo_password",
            client_id="3MVG9lKcPoNINVBIPJjdw1J9LLM82HnZz9Yh7ZJnY",
            client_secret="5A52C1A1E21DF9012IODC9ISNXXAADDA9",
            include_tables=["Account", "Contact"],
        )
        handler = SalesforceHandler("salesforce", connection_data=connection_data)

        # Mock connection and individual table describe calls
        mock_connection = MagicMock()
        mock_connection.sobjects.Account = MagicMock()
        mock_connection.sobjects.Account.describe.return_value = {"queryable": True}
        mock_connection.sobjects.Contact = MagicMock()
        mock_connection.sobjects.Contact.describe.return_value = {"queryable": True}

        # Set the connection attribute directly and mark as connected
        handler.connection = mock_connection
        handler.is_connected = True

        resource_names = handler._get_resource_names()

        # Should only return the specified tables
        self.assertEqual(set(resource_names), {"Account", "Contact"})

        # Should NOT call global describe() method
        mock_connection.sobjects.describe.assert_not_called()

        # Should call individual table describe() methods
        mock_connection.sobjects.Account.describe.assert_called_once()
        mock_connection.sobjects.Contact.describe.assert_called_once()

    def test_pre_filtering_with_tables_parameter(self):
        """
        Test that pre-filtering works correctly when 'tables' parameter is specified (alternative to include_tables).
        """
        # Setup handler with 'tables' parameter
        connection_data = OrderedDict(
            username="demo@example.com",
            password="demo_password",
            client_id="3MVG9lKcPoNINVBIPJjdw1J9LLM82HnZz9Yh7ZJnY",
            client_secret="5A52C1A1E21DF9012IODC9ISNXXAADDA9",
            tables=["Lead", "Opportunity"],
        )
        handler = SalesforceHandler("salesforce", connection_data=connection_data)

        # Mock connection and individual table describe calls
        mock_connection = MagicMock()
        mock_connection.sobjects.Lead = MagicMock()
        mock_connection.sobjects.Lead.describe.return_value = {"queryable": True}
        mock_connection.sobjects.Opportunity = MagicMock()
        mock_connection.sobjects.Opportunity.describe.return_value = {"queryable": True}

        # Set the connection attribute directly and mark as connected
        handler.connection = mock_connection
        handler.is_connected = True

        resource_names = handler._get_resource_names()

        # Should only return the specified tables
        self.assertEqual(set(resource_names), {"Lead", "Opportunity"})

        # Should NOT call global describe() method
        mock_connection.sobjects.describe.assert_not_called()

        # Should call individual table describe() methods
        mock_connection.sobjects.Lead.describe.assert_called_once()
        mock_connection.sobjects.Opportunity.describe.assert_called_once()

    def test_pre_filtering_with_exclude_tables(self):
        """
        Test that exclude_tables parameter properly filters out specified tables.
        """
        # Setup handler with include_tables and exclude_tables
        connection_data = OrderedDict(
            username="demo@example.com",
            password="demo_password",
            client_id="3MVG9lKcPoNINVBIPJjdw1J9LLM82HnZz9Yh7ZJnY",
            client_secret="5A52C1A1E21DF9012IODC9ISNXXAADDA9",
            include_tables=["Account", "Contact", "Lead"],
            exclude_tables=["Lead"],
        )
        handler = SalesforceHandler("salesforce", connection_data=connection_data)

        # Mock connection and individual table describe calls
        mock_connection = MagicMock()
        mock_connection.sobjects.Account = MagicMock()
        mock_connection.sobjects.Account.describe.return_value = {"queryable": True}
        mock_connection.sobjects.Contact = MagicMock()
        mock_connection.sobjects.Contact.describe.return_value = {"queryable": True}
        mock_connection.sobjects.Lead = MagicMock()
        mock_connection.sobjects.Lead.describe.return_value = {"queryable": True}

        # Set the connection attribute directly and mark as connected
        handler.connection = mock_connection
        handler.is_connected = True

        resource_names = handler._get_resource_names()

        # Should only return Account and Contact (Lead should be excluded)
        self.assertEqual(set(resource_names), {"Account", "Contact"})

        # Should NOT call global describe() method
        mock_connection.sobjects.describe.assert_not_called()

        # Should call describe() only for non-excluded tables
        mock_connection.sobjects.Account.describe.assert_called_once()
        mock_connection.sobjects.Contact.describe.assert_called_once()
        mock_connection.sobjects.Lead.describe.assert_not_called()

    def test_fallback_to_full_discovery_when_no_include_tables(self):
        """
        Test that fallback to full discovery works when no include_tables/tables specified.
        """
        # Setup handler without include_tables or tables
        connection_data = OrderedDict(
            username="demo@example.com",
            password="demo_password",
            client_id="3MVG9lKcPoNINVBIPJjdw1J9LLM82HnZz9Yh7ZJnY",
            client_secret="5A52C1A1E21DF9012IODC9ISNXXAADDA9",
        )
        handler = SalesforceHandler("salesforce", connection_data=connection_data)

        # Mock connection with global describe response
        mock_connection = MagicMock()
        mock_connection.sobjects.describe.return_value = {
            "sobjects": [
                {"name": "Account", "queryable": True},
                {"name": "Contact", "queryable": True},
                {"name": "AccountHistory", "queryable": True},  # Should be filtered out by hard-coded rules
                {"name": "CustomObject__c", "queryable": True},
            ]
        }

        # Set the connection attribute directly and mark as connected
        handler.connection = mock_connection
        handler.is_connected = True

        resource_names = handler._get_resource_names()

        # Should return filtered tables (excluding History tables per hard-coded rules)
        self.assertIn("Account", resource_names)
        self.assertIn("Contact", resource_names)
        self.assertIn("CustomObject__c", resource_names)
        self.assertNotIn("AccountHistory", resource_names)  # Should be filtered out

        # Should call global describe() method for full discovery
        mock_connection.sobjects.describe.assert_called_once()

    def test_error_handling_for_non_existent_tables(self):
        """
        Test that non-existent tables are handled gracefully with warnings.
        """
        # Setup handler with include_tables containing non-existent table
        connection_data = OrderedDict(
            username="demo@example.com",
            password="demo_password",
            client_id="3MVG9lKcPoNINVBIPJjdw1J9LLM82HnZz9Yh7ZJnY",
            client_secret="5A52C1A1E21DF9012IODC9ISNXXAADDA9",
            include_tables=["Account", "NonExistentTable", "Contact"],
        )
        handler = SalesforceHandler("salesforce", connection_data=connection_data)

        # Mock connection where NonExistentTable raises an exception
        mock_connection = MagicMock()
        mock_connection.sobjects.Account = MagicMock()
        mock_connection.sobjects.Account.describe.return_value = {"queryable": True}
        mock_connection.sobjects.Contact = MagicMock()
        mock_connection.sobjects.Contact.describe.return_value = {"queryable": True}

        # Mock NonExistentTable to raise an exception
        mock_non_existent = MagicMock()
        mock_non_existent.describe.side_effect = Exception("Table not found")
        mock_connection.sobjects.NonExistentTable = mock_non_existent

        # Set the connection attribute directly and mark as connected
        handler.connection = mock_connection
        handler.is_connected = True

        resource_names = handler._get_resource_names()

        # Should only return existing tables (Account, Contact) and skip non-existent one
        self.assertEqual(set(resource_names), {"Account", "Contact"})

        # Should NOT call global describe() method
        mock_connection.sobjects.describe.assert_not_called()

        # Should call describe() for all specified tables (including non-existent)
        mock_connection.sobjects.Account.describe.assert_called_once()
        mock_connection.sobjects.Contact.describe.assert_called_once()
        mock_connection.sobjects.NonExistentTable.describe.assert_called_once()

    def test_validate_specified_tables_skips_non_queryable(self):
        handler = self.create_handler()
        handler.connection = MagicMock()
        handler.is_connected = True
        handler.connection.sobjects.Account = MagicMock()
        handler.connection.sobjects.Account.describe.return_value = {"queryable": False}

        validated = handler._validate_specified_tables(["Account"], [])

        self.assertEqual(validated, [])
        handler.connection.sobjects.Account.describe.assert_called_once()

    def test_meta_get_handler_info_returns_prompt(self):
        info = self.handler.meta_get_handler_info()
        self.assertIn("SOQL", info)

    def test_meta_get_tables_filters_requested_tables(self):
        mock_connection = MagicMock()
        mock_connection.sobjects.describe.return_value = {
            "sobjects": [
                {"name": "Account", "queryable": True},
                {"name": "Contact", "queryable": True},
            ]
        }
        self.mock_connect.return_value = mock_connection

        with patch(
            "mindsdb.integrations.handlers.salesforce_handler.salesforce_handler.MetaAPIHandler.meta_get_tables",
            return_value=TableResponse(),
        ) as mock_meta:
            response = self.handler.meta_get_tables(table_names=["contact"])

        self.assertEqual(response.type, RESPONSE_TYPE.TABLE)
        mock_meta.assert_called_once()
        kwargs = mock_meta.call_args.kwargs
        self.assertEqual(len(kwargs["main_metadata"]), 1)
        self.assertEqual(kwargs["main_metadata"][0]["name"], "Contact")


class TestSalesforceAnyTable(BaseAPIResourceTestSetup, unittest.TestCase):
    @property
    def dummy_connection_data(self):
        return OrderedDict(
            username="demo@example.com",
            password="demo_password",
            client_id="3MVG9lKcPoNINVBIPJjdw1J9LLM82HnZz9Yh7ZJnY",
            client_secret="5A52C1A1E21DF9012IODC9ISNXXAADDA9",
        )

    def create_handler(self):
        return SalesforceHandler("salesforce", connection_data=self.dummy_connection_data)

    def create_patcher(self):
        return patch("salesforce_api.Salesforce")

    def create_resource(self):
        return create_table_class(self.table_name)(self.handler)

    def setUp(self):
        """
        Set up common test fixtures.
        """
        self.table_name = "contact"
        self.mock_columns = ["Id", "Name", "Email"]
        self.mock_record = {column: f"{column}_value" for column in self.mock_columns}

        super().setUp()

        table_api = MagicMock()
        table_api.describe.return_value = {
            "fields": [
                {
                    "name": column,
                    "type": "string",
                    "nillable": True,
                    "defaultValue": "",
                    "inlineHelpText": "",
                }
                for column in self.mock_columns
            ]
        }
        table_api.insert = MagicMock()
        table_api.update = MagicMock()
        table_api.delete = MagicMock()

        self._row_count = 5

        def fake_query(query_str):
            if query_str.startswith("SELECT COUNT"):
                return [{"expr0": self._row_count}]
            return [{"attributes": {"type": self.table_name}, **self.mock_record}]

        sobjects = MagicMock()
        sobjects.query.side_effect = fake_query
        setattr(sobjects, self.table_name, table_api)

        self.mock_client = MagicMock(sobjects=sobjects)
        self.mock_connect.return_value = self.mock_client

    def test_select_all(self):
        """
        Test that the `select` method returns the data from the Salesforce resource for a simple SELECT * query.
        """
        select_query = Select(targets=[Star()], from_table=Identifier(parts=[self.table_name]))
        df = self.resource.select(select_query)

        self.assertEqual(len(df), 1)
        self.assertEqual(list(df.columns), self.mock_columns)
        self.assertEqual(list(df.iloc[0]), list(self.mock_record.values()))

    def test_select_columns(self):
        """
        Test that the `select` method returns the data from the Salesforce resource for a SELECT query with specific columns.
        """
        select_query = Select(
            targets=[Identifier(parts=[column]) for column in self.mock_columns],
            from_table=Identifier(parts=[self.table_name]),
        )
        df = self.resource.select(select_query)

        self.assertEqual(len(df), 1)
        self.assertEqual(list(df.columns), self.mock_columns)
        self.assertEqual(list(df.iloc[0]), list(self.mock_record.values()))

    def test_select_columns_with_alias(self):
        """
        Test that the `select` method returns the data from the Salesforce resource for a SELECT query with specific columns and aliases.
        """
        select_query = Select(
            targets=[
                Identifier(parts=[column], alias=Identifier(parts=[f"{column}_alias"])) for column in self.mock_columns
            ],
            from_table=Identifier(parts=[self.table_name]),
        )
        df = self.resource.select(select_query)

        self.assertEqual(len(df), 1)
        self.assertEqual(list(df.columns), [f"{column}_alias" for column in self.mock_columns])
        self.assertEqual(list(df.iloc[0]), list(self.mock_record.values()))

    def test_select_columns_with_condition(self):
        """
        Test that the `select` method returns the data from the Salesforce resource for a SELECT query with specific columns and a WHERE condition.
        """
        select_query = Select(
            targets=[Identifier(parts=[column]) for column in self.mock_columns],
            from_table=Identifier(parts=[self.table_name]),
            where=BinaryOperation(op="=", args=[Identifier("Id"), Constant("Id_value")]),
        )
        df = self.resource.select(select_query)

        self.assertEqual(len(df), 1)
        self.assertEqual(list(df.columns), self.mock_columns)
        self.assertEqual(list(df.iloc[0]), list(self.mock_record.values()))

    def test_select_columns_with_condition_and_limit(self):
        """
        Test that the `select` method returns the data from the Salesforce resource for a SELECT query with specific columns, a WHERE condition, and a LIMIT clause.
        """
        select_query = Select(
            targets=[Identifier(parts=[column]) for column in self.mock_columns],
            from_table=Identifier(parts=[self.table_name]),
            where=BinaryOperation(op="=", args=[Identifier("Id"), Constant("Id_value")]),
            limit=Constant(1),
        )
        df = self.resource.select(select_query)

        self.assertEqual(len(df), 1)
        self.assertEqual(list(df.columns), self.mock_columns)
        self.assertEqual(list(df.iloc[0]), list(self.mock_record.values()))

    def test_select_columns_with_conditions(self):
        """
        Test that the `select` method returns the data from the Salesforce resource for a SELECT query with specific columns and multiple WHERE conditions.
        """
        select_query = Select(
            targets=[Identifier(parts=[column]) for column in self.mock_columns],
            from_table=Identifier(parts=[self.table_name]),
            where=BinaryOperation(
                op="AND",
                args=[
                    BinaryOperation(op="=", args=[Identifier("Id"), Constant("Id_value")]),
                    BinaryOperation(op="=", args=[Identifier("Name"), Constant("Name_value")]),
                ],
            ),
        )
        df = self.resource.select(select_query)

        self.assertEqual(len(df), 1)
        self.assertEqual(list(df.columns), self.mock_columns)
        self.assertEqual(list(df.iloc[0]), list(self.mock_record.values()))

    def test_constants_in_soql_instructions(self):
        """
        Test that the SOQL instructions contain the expected constants.
        """
        instructions = get_soql_instructions("DummyIntegration")
        # Prompt may chage but these keywords must be present related to SOQL syntax
        required_syntax = [
            "SOQL",
            "SELECT",
            "FROM",
            "WHERE",
            "LIMIT",
            "INCLUDES",
            "EXCLUDES",
            "OPERATORS",
            "FROM DummyIntegration(",  # native query examples
        ]
        for term in required_syntax:
            self.assertIn(term, instructions, f"Missing syntax in instructions: {term}")

    def test_add_uses_salesforce_insert(self):
        payload = {"Name": "Abc"}
        table_api = getattr(self.mock_client.sobjects, self.table_name)
        self.resource.add(payload)
        table_api.insert.assert_called_once_with(payload)

    def test_modify_updates_ids_from_conditions(self):
        table_api = getattr(self.mock_client.sobjects, self.table_name)
        self.resource.modify(
            [FilterCondition(column="Id", op=FilterOperator.EQUAL, value="123")],
            {"Name": "Updated"},
        )
        table_api.update.assert_called_once_with("123", {"Name": "Updated"})

    def test_remove_deletes_ids_from_conditions(self):
        table_api = getattr(self.mock_client.sobjects, self.table_name)
        self.resource.remove([FilterCondition(column="Id", op=FilterOperator.IN, value=["1", "2"])])
        table_api.delete.assert_any_call("1")
        table_api.delete.assert_any_call("2")
        self.assertEqual(table_api.delete.call_count, 2)

    def test_validate_conditions_only_allows_id(self):
        with self.assertRaises(ValueError):
            self.resource._validate_conditions([FilterCondition(column="Name", op=FilterOperator.EQUAL, value="A")])

    def test_validate_conditions_requires_supported_operator(self):
        with self.assertRaises(ValueError):
            self.resource._validate_conditions([FilterCondition(column="Id", op=FilterOperator.NOT_EQUAL, value="1")])

    def test_meta_get_tables_returns_metadata_with_rowcount(self):
        result = self.resource.meta_get_tables(
            self.table_name,
            [{"name": self.table_name, "fields": [{"name": "Id"}], "label": "Contacts"}],
        )
        self.assertEqual(result["table_name"], self.table_name)
        self.assertEqual(result["table_type"], "BASE TABLE")
        self.assertEqual(result["row_count"], self._row_count)

    def test_meta_get_tables_handles_missing_resource(self):
        result = self.resource.meta_get_tables(self.table_name, [])
        self.assertIsNone(result["row_count"])
        self.assertEqual(result["table_name"], self.table_name)

    def test_meta_get_columns_builds_schema(self):
        metadata = {
            "fields": [
                {
                    "name": "Id",
                    "type": "string",
                    "nillable": False,
                    "defaultValue": "foo",
                    "inlineHelpText": "Identifier",
                }
            ]
        }
        self.resource._get_resource_metadata = MagicMock(return_value=metadata)
        columns = self.resource.meta_get_columns(self.table_name)
        self.assertEqual(columns[0]["column_name"], "Id")
        self.assertEqual(columns[0]["data_type"], "string")


class TestSalesforcePassthrough(unittest.TestCase):
    """Exercise the PassthroughMixin retrofit (per-instance base URL)."""

    CONNECTION_DATA = {
        "username": "u",
        "password": "p",
        "client_id": "cid",
        "client_secret": "csec",
        "access_token": "sf_access_tok",
        "instance_url": "https://my-org.my.salesforce.com",
    }

    def _mock_response(self, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.headers = {"Content-Type": "application/json"}
        resp.iter_content = MagicMock(return_value=iter([b'{"sobjects":[]}']))
        resp.close = MagicMock()
        return resp

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_passthrough_uses_bearer_and_instance_url(self, mock_request):
        mock_request.return_value = self._mock_response()
        handler = SalesforceHandler("salesforce", connection_data=self.CONNECTION_DATA)
        from mindsdb.integrations.libs.passthrough_types import PassthroughRequest

        resp = handler.api_passthrough(PassthroughRequest("GET", "/services/data/v60.0/"))

        self.assertEqual(resp.status_code, 200)
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], "GET")
        self.assertEqual(args[1], "https://my-org.my.salesforce.com/services/data/v60.0/")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sf_access_tok")

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_test_passthrough_returns_ok_on_200(self, mock_request):
        mock_request.return_value = self._mock_response(status_code=200)
        handler = SalesforceHandler("salesforce", connection_data=self.CONNECTION_DATA)

        result = handler.test_passthrough()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["host"], "my-org.my.salesforce.com")
        self.assertIsInstance(result["latency_ms"], int)

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_test_passthrough_returns_auth_failed_on_401(self, mock_request):
        mock_request.return_value = self._mock_response(status_code=401)
        handler = SalesforceHandler("salesforce", connection_data=self.CONNECTION_DATA)

        result = handler.test_passthrough()

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "auth_failed")
        self.assertEqual(result["status_code"], 401)
        self.assertEqual(result["host"], "my-org.my.salesforce.com")


if __name__ == "__main__":
    unittest.main()
