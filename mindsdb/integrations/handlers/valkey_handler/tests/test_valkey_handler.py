"""
Unit and integration tests for the Valkey vector store handler.

Unit tests: Always run (no external dependencies, uses mocks).
Integration tests: Require a running Valkey instance with Search module.
    - Set VALKEY_HOST and VALKEY_PORT environment variables to configure.
    - Tests skip gracefully if Valkey is unavailable.
"""

import os
import struct
import time
import uuid
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from mindsdb.integrations.handlers.valkey_handler.valkey_handler import (
    DEFAULT_DB,
    DEFAULT_DISTANCE_METRIC,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_PREFIX,
    DEFAULT_VECTOR_DIMENSION,
    VECTOR_FIELD_NAME,
    ValkeyHandler,
)
from mindsdb.integrations.libs.response import RESPONSE_TYPE
from mindsdb.integrations.libs.vectordatabase_handler import (
    FilterCondition,
    FilterOperator,
)

from glide import RequestError


# =============================================================================
# Unit Tests
# =============================================================================


class TestValkeyHandlerUnit:
    """Unit tests that do not require a running Valkey instance."""

    def _make_handler(self, connection_data=None):
        """Create a handler instance with mock storage."""
        return ValkeyHandler(
            "test",
            connection_data=connection_data or {},
            handler_storage=MagicMock(),
        )

    def test_validate_connection_defaults(self):
        """Handler uses correct defaults when no connection_data provided."""
        h = self._make_handler()
        assert h._host == DEFAULT_HOST
        assert h._port == DEFAULT_PORT
        assert h._db == DEFAULT_DB
        assert h._password is None
        assert h._vector_dimension == DEFAULT_VECTOR_DIMENSION
        assert h._distance_metric == DEFAULT_DISTANCE_METRIC
        assert h._prefix == DEFAULT_PREFIX

    def test_validate_connection_custom(self):
        """Handler correctly stores custom connection parameters."""
        h = self._make_handler(
            {
                "host": "valkey.io",
                "port": 6380,
                "password": "secret",
                "db": 2,
                "vector_dimension": 768,
                "distance_metric": "L2",
                "prefix": "vec:",
            }
        )
        assert h._host == "valkey.io"
        assert h._port == 6380
        assert h._password == "secret"
        assert h._db == 2
        assert h._vector_dimension == 768
        assert h._distance_metric == "L2"
        assert h._prefix == "vec:"

    def test_parse_doc_fields_basic(self):
        """Correctly parses raw Valkey hash fields into Python types."""
        h = self._make_handler()
        fields = {
            b"id": b"doc1",
            b"content": b"hello world",
            b"embeddings": struct.pack("4f", 0.1, 0.2, 0.3, 0.4),
            b"metadata": b'{"source": "web"}',
        }
        row = h._parse_doc_fields(fields, include_score=False)
        assert row["id"] == "doc1"
        assert row["content"] == "hello world"
        assert len(row["embeddings"]) == 4
        assert abs(row["embeddings"][0] - 0.1) < 1e-6
        assert row["metadata"] == {"source": "web"}
        assert "distance" not in row

    def test_parse_doc_fields_with_score(self):
        """Correctly extracts distance score when present."""
        h = self._make_handler()
        fields = {
            b"id": b"doc1",
            b"content": b"hello",
            b"embeddings": struct.pack("4f", 0.1, 0.2, 0.3, 0.4),
            b"metadata": b"{}",
            b"__embeddings_score": b"0.123",
        }
        row = h._parse_doc_fields(fields, include_score=True)
        assert abs(row["distance"] - 0.123) < 1e-6

    def test_parse_doc_fields_empty_metadata(self):
        """Handles empty or invalid metadata gracefully."""
        h = self._make_handler()
        fields = {
            b"id": b"doc1",
            b"content": b"",
            b"embeddings": b"",
            b"metadata": b"not-json",
        }
        row = h._parse_doc_fields(fields, include_score=False)
        assert row["metadata"] == {}
        assert row["embeddings"] == []

    def test_build_filter_expression_empty(self):
        """Returns '*' when no filters provided."""
        h = self._make_handler()
        expr = h._build_filter_expression([], [])
        assert expr == "*"

    def test_build_filter_expression_id_equal(self):
        """Builds correct TAG filter for single ID equality."""
        h = self._make_handler()
        cond = FilterCondition("id", FilterOperator.EQUAL, "doc1")
        expr = h._build_filter_expression([cond], [])
        assert "@id:{doc1}" in expr

    def test_build_filter_expression_id_in(self):
        """Builds correct TAG filter for ID IN list."""
        h = self._make_handler()
        cond = FilterCondition("id", FilterOperator.IN, ["d1", "d2"])
        expr = h._build_filter_expression([cond], [])
        assert "@id:{d1|d2}" in expr

    def test_build_filter_expression_id_not_equal(self):
        """Builds correct negation filter for ID != value."""
        h = self._make_handler()
        cond = FilterCondition("id", FilterOperator.NOT_EQUAL, "doc1")
        expr = h._build_filter_expression([cond], [])
        assert "-@id:{doc1}" in expr

    def test_escape_tag_special_chars(self):
        """Escapes special characters in TAG values."""
        h = self._make_handler()
        result = h._escape_tag("hello world!@#")
        assert "\\ " in result or "\\!" in result
        # Spaces and special chars should be escaped
        assert "hello" in result
        assert "world" in result

    @patch("mindsdb.integrations.handlers.valkey_handler.valkey_handler.ft")
    def test_get_tables_returns_dataframe(self, mock_ft):
        """get_tables returns a DataFrame with table_name column."""
        h = self._make_handler()
        h.is_connected = True
        h._client = MagicMock()

        async def mock_list(client):
            return [b"idx1", b"idx2"]

        mock_ft.list = mock_list

        result = h.get_tables()
        assert result.resp_type == RESPONSE_TYPE.TABLE
        assert list(result.data_frame["table_name"]) == ["idx1", "idx2"]

    @patch("mindsdb.integrations.handlers.valkey_handler.valkey_handler.ft")
    def test_select_builds_knn_query(self, mock_ft):
        """select with search_vector builds correct KNN query string."""
        h = self._make_handler({"vector_dimension": 4})
        h.is_connected = True
        h._client = MagicMock()

        search_result = [
            1,
            {
                b"doc:t:d1": {
                    b"id": b"d1",
                    b"content": b"hi",
                    b"embeddings": struct.pack("4f", 0.1, 0.2, 0.3, 0.4),
                    b"metadata": b"{}",
                    b"__embeddings_score": b"0.05",
                }
            },
        ]

        captured_args = {}

        async def mock_search(client, index_name, query, options=None):
            captured_args["query"] = query
            captured_args["options"] = options
            return search_result

        mock_ft.search = mock_search

        cond = FilterCondition("search_vector", FilterOperator.EQUAL, [0.1, 0.2, 0.3, 0.4])
        result = h.select("t", columns=["id", "content", "distance"], conditions=[cond], limit=5)

        assert "KNN 5" in captured_args["query"]
        assert f"@{VECTOR_FIELD_NAME} $query_vec" in captured_args["query"]
        assert len(result) == 1
        assert result.iloc[0]["id"] == "d1"

    def test_insert_serializes_embeddings(self):
        """insert correctly serializes embeddings to float32 bytes."""
        h = self._make_handler()
        h.is_connected = True
        h._client = MagicMock()

        captured_calls = []

        async def mock_hset(key, field_map):
            captured_calls.append((key, field_map))
            return 1

        h._client.hset = mock_hset

        df = pd.DataFrame(
            {
                "id": ["doc1"],
                "content": ["hello world"],
                "embeddings": [[0.1, 0.2, 0.3, 0.4]],
                "metadata": [{"source": "web"}],
            }
        )
        h.insert("table", df)

        assert len(captured_calls) == 1
        key, field_map = captured_calls[0]
        assert key == "doc:table:doc1"
        expected_bytes = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32).tobytes()
        assert field_map["embeddings"] == expected_bytes
        assert field_map["content"] == "hello world"
        assert field_map["metadata"] == '{"source": "web"}'

    def test_delete_by_id(self):
        """delete correctly builds keys and calls unlink."""
        h = self._make_handler()
        h.is_connected = True
        h._client = MagicMock()

        captured_keys = []

        async def mock_unlink(keys):
            captured_keys.extend(keys)
            return len(keys)

        h._client.unlink = mock_unlink

        conditions = [FilterCondition("id", FilterOperator.IN, ["d1", "d2"])]
        h.delete("t", conditions)

        assert "doc:t:d1" in captured_keys
        assert "doc:t:d2" in captured_keys

    @patch("mindsdb.integrations.handlers.valkey_handler.valkey_handler.ft")
    def test_drop_table_calls_dropindex(self, mock_ft):
        """drop_table calls ft.dropindex and cleans up keys."""
        h = self._make_handler()
        h.is_connected = True
        h._client = MagicMock()

        dropindex_called = []

        async def mock_dropindex(client, index_name):
            dropindex_called.append(index_name)
            return "OK"

        mock_ft.dropindex = mock_dropindex

        # Mock scan to return no keys (empty cleanup)
        async def mock_scan(cursor, match=None, count=None):
            return [b"0", []]

        h._client.scan = mock_scan

        h.drop_table("my_index")
        assert "my_index" in dropindex_called

    def test_build_filter_expression_id_not_in(self):
        """Builds correct negation filter for ID NOT_IN list."""
        h = self._make_handler()
        cond = FilterCondition("id", FilterOperator.NOT_IN, ["d1", "d2"])
        expr = h._build_filter_expression([cond], [])
        assert "-@id:{d1|d2}" in expr

    def test_build_filter_expression_metadata_equal(self):
        """Builds correct phrase search for metadata EQUAL condition."""
        h = self._make_handler()
        cond = FilterCondition("metadata.source", FilterOperator.EQUAL, "web")
        expr = h._build_filter_expression([], [cond])
        assert '@metadata:("web")' in expr

    def test_build_filter_expression_metadata_not_equal(self):
        """Builds correct negation phrase search for metadata NOT_EQUAL."""
        h = self._make_handler()
        cond = FilterCondition("metadata.source", FilterOperator.NOT_EQUAL, "web")
        expr = h._build_filter_expression([], [cond])
        assert '-@metadata:("web")' in expr

    def test_build_filter_expression_metadata_escapes_quotes(self):
        """Metadata filter properly escapes double quotes in values."""
        h = self._make_handler()
        cond = FilterCondition("metadata.desc", FilterOperator.EQUAL, 'say "hello"')
        expr = h._build_filter_expression([], [cond])
        assert '\\"hello\\"' in expr
        assert '@metadata:(' in expr

    @patch("mindsdb.integrations.handlers.valkey_handler.valkey_handler.ft")
    def test_select_id_not_equal_falls_through_to_search(self, mock_ft):
        """NOT_EQUAL on id falls through to FT.SEARCH instead of returning empty."""
        h = self._make_handler({"vector_dimension": 4})
        h.is_connected = True
        h._client = MagicMock()

        search_called = {}

        async def mock_search(client, index_name, query, options=None):
            search_called["query"] = query
            return [0, {}]

        mock_ft.search = mock_search

        cond = FilterCondition("id", FilterOperator.NOT_EQUAL, "doc1")
        result = h.select("t", columns=["id"], conditions=[cond])

        # Should have called ft.search with negation filter, not returned empty
        assert "query" in search_called
        assert "-@id:{doc1}" in search_called["query"]

    @patch("mindsdb.integrations.handlers.valkey_handler.valkey_handler.ft")
    def test_select_id_not_in_falls_through_to_search(self, mock_ft):
        """NOT_IN on id falls through to FT.SEARCH instead of returning empty."""
        h = self._make_handler({"vector_dimension": 4})
        h.is_connected = True
        h._client = MagicMock()

        search_called = {}

        async def mock_search(client, index_name, query, options=None):
            search_called["query"] = query
            return [0, {}]

        mock_ft.search = mock_search

        cond = FilterCondition("id", FilterOperator.NOT_IN, ["doc1", "doc2"])
        result = h.select("t", columns=["id"], conditions=[cond])

        assert "query" in search_called
        assert "-@id:{doc1|doc2}" in search_called["query"]

    def test_connect_logs_error_on_failure(self):
        """connect logs error when connection fails."""
        h = self._make_handler({"host": "nonexistent.invalid", "port": 9999})
        with patch("mindsdb.integrations.handlers.valkey_handler.valkey_handler.logger") as mock_logger:
            with pytest.raises(Exception):
                h.connect()
            mock_logger.error.assert_called_once()
            assert "nonexistent.invalid" in mock_logger.error.call_args[0][0]

    def test_disconnect_logs_debug_on_error(self):
        """disconnect logs at debug level when close raises."""
        h = self._make_handler()
        h.is_connected = True
        h._client = MagicMock()

        async def mock_close():
            raise RuntimeError("close failed")

        h._client.close = mock_close

        with patch("mindsdb.integrations.handlers.valkey_handler.valkey_handler.logger") as mock_logger:
            h.disconnect()
            mock_logger.debug.assert_called_once()
            assert "close failed" in mock_logger.debug.call_args[0][0]

        assert h.is_connected is False
        assert h._client is None

    def test_check_connection_failure(self):
        """check_connection returns failure status on connection error."""
        h = self._make_handler({"host": "nonexistent.invalid", "port": 9999})
        status = h.check_connection()
        assert status.success is False
        assert status.error_message is not None

    def test_delete_no_conditions_raises(self):
        """delete raises exception when no conditions provided."""
        h = self._make_handler()
        h.is_connected = True
        h._client = MagicMock()
        with pytest.raises(Exception, match="Delete requires at least one condition"):
            h.delete("table", conditions=None)

    def test_parse_search_result_empty(self):
        """_parse_search_result returns empty DataFrame on zero results."""
        h = self._make_handler()
        result = [0, {}]
        df = h._parse_search_result(result, columns=["id", "content"], include_score=False)
        assert len(df) == 0
        assert "id" in df.columns

    @patch("mindsdb.integrations.handlers.valkey_handler.valkey_handler.ft")
    def test_select_metadata_filter_uses_search(self, mock_ft):
        """Select with metadata filter uses FT.SEARCH with correct expression."""
        h = self._make_handler({"vector_dimension": 4})
        h.is_connected = True
        h._client = MagicMock()

        search_called = {}

        async def mock_search(client, index_name, query, options=None):
            search_called["query"] = query
            return [0, {}]

        mock_ft.search = mock_search

        cond = FilterCondition("metadata.source", FilterOperator.EQUAL, "web")
        h.select("t", columns=["id"], conditions=[cond])

        assert "query" in search_called
        assert '@metadata:("web")' in search_called["query"]

    @patch("mindsdb.integrations.handlers.valkey_handler.valkey_handler.ft")
    def test_get_columns_nonexistent_table(self, mock_ft):
        """get_columns returns error response for non-existent table."""
        h = self._make_handler()
        h.is_connected = True
        h._client = MagicMock()

        async def mock_info(client, index_name):
            raise RequestError("Unknown Index name: not found")

        mock_ft.info = mock_info

        result = h.get_columns("no_such_table")
        assert result.resp_type == RESPONSE_TYPE.ERROR
        assert "does not exist" in result.error_message

    def test_insert_handles_none_content_and_metadata(self):
        """insert sets empty defaults when content is None and metadata is not a dict."""
        h = self._make_handler()
        h.is_connected = True
        h._client = MagicMock()

        captured_calls = []

        async def mock_hset(key, field_map):
            captured_calls.append((key, field_map))
            return 1

        h._client.hset = mock_hset

        df = pd.DataFrame(
            {
                "id": ["doc1"],
                "content": [None],
                "embeddings": [[0.1, 0.2, 0.3, 0.4]],
                "metadata": ["not_a_dict"],
            }
        )
        h.insert("table", df)

        assert len(captured_calls) == 1
        _, field_map = captured_calls[0]
        assert field_map["content"] == ""
        assert field_map["metadata"] == "{}"

    def test_scan_all_docs_with_offset_and_limit(self):
        """_scan_all_docs respects offset and limit parameters."""
        h = self._make_handler()
        h.is_connected = True
        h._client = MagicMock()

        # Mock scan to return 5 keys
        async def mock_scan(cursor, match=None, count=None):
            if cursor == b"0":
                return [b"0", [f"doc:t:doc{i}".encode() for i in range(5)]]
            return [b"0", []]

        h._client.scan = mock_scan

        # Mock hgetall for each key
        async def mock_hgetall(key):
            doc_id = key.split(":")[-1]
            return {
                b"id": doc_id.encode(),
                b"content": b"text",
                b"embeddings": np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32).tobytes(),
                b"metadata": b"{}",
            }

        h._client.hgetall = mock_hgetall

        # Request offset=1, limit=2
        df = h._scan_all_docs("t", columns=["id"], offset=1, limit=2)
        assert len(df) == 2
        assert df.iloc[0]["id"] == "doc1"
        assert df.iloc[1]["id"] == "doc2"


# =============================================================================
# Integration Tests
# =============================================================================

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))
VALKEY_PASSWORD = os.environ.get("VALKEY_PASSWORD", None)
VECTOR_DIM = 4  # Small dimension for fast tests


@pytest.fixture(scope="class")
def handler():
    """Create handler and skip if Valkey not available."""
    h = ValkeyHandler(
        "test_valkey",
        connection_data={
            "host": VALKEY_HOST,
            "port": VALKEY_PORT,
            "password": VALKEY_PASSWORD,
            "vector_dimension": VECTOR_DIM,
            "distance_metric": "COSINE",
        },
        handler_storage=MagicMock(),
    )
    status = h.check_connection()
    if not status.success:
        pytest.skip(f"Valkey not available: {status.error_message}")
    yield h
    h.disconnect()


@pytest.fixture
def unique_table():
    """Generate unique table name to avoid test collisions."""
    return f"test_{uuid.uuid4().hex[:8]}"


def _make_test_df(num_docs=3):
    """Create a test DataFrame with sample documents."""
    embeddings = [np.random.rand(VECTOR_DIM).tolist() for _ in range(num_docs)]
    return pd.DataFrame(
        {
            "id": [f"doc{i}" for i in range(1, num_docs + 1)],
            "content": [f"content_{i}" for i in range(1, num_docs + 1)],
            "embeddings": embeddings,
            "metadata": [{"src": f"source_{i}"} for i in range(1, num_docs + 1)],
        }
    )


class TestValkeyHandlerIntegration:
    """Integration tests requiring a running Valkey instance with Search module."""

    def test_check_connection(self, handler):
        """Verify connection to Valkey is successful."""
        status = handler.check_connection()
        assert status.success is True

    def test_create_table(self, handler, unique_table):
        """Create an index and verify it appears in table list."""
        try:
            handler.create_table(unique_table)
            tables = handler.get_tables()
            assert unique_table in tables.data_frame["table_name"].values
        finally:
            handler.drop_table(unique_table, if_exists=True)

    def test_create_table_if_not_exists(self, handler, unique_table):
        """Creating an existing table with if_not_exists=True does not raise."""
        try:
            handler.create_table(unique_table)
            # Should not raise
            handler.create_table(unique_table, if_not_exists=True)
        finally:
            handler.drop_table(unique_table, if_exists=True)

    def test_insert_and_select_all(self, handler, unique_table):
        """Insert documents and select all to verify they are stored."""
        try:
            handler.create_table(unique_table)
            df = pd.DataFrame(
                {
                    "id": ["doc1", "doc2", "doc3"],
                    "content": ["hello", "world", "foo"],
                    "embeddings": [
                        [0.1, 0.2, 0.3, 0.4],
                        [0.5, 0.6, 0.7, 0.8],
                        [0.9, 0.1, 0.2, 0.3],
                    ],
                    "metadata": [{"src": "a"}, {"src": "b"}, {"src": "c"}],
                }
            )
            handler.insert(unique_table, df)
            # Allow indexing time
            time.sleep(0.5)

            result = handler.select(unique_table, columns=["id", "content"])
            assert len(result) == 3
            assert set(result["id"].tolist()) == {"doc1", "doc2", "doc3"}
        finally:
            handler.drop_table(unique_table, if_exists=True)

    def test_select_knn(self, handler, unique_table):
        """KNN vector search returns nearest neighbors sorted by distance."""
        try:
            handler.create_table(unique_table)
            df = pd.DataFrame(
                {
                    "id": ["doc1", "doc2", "doc3"],
                    "content": ["hello", "world", "foo"],
                    "embeddings": [
                        [0.1, 0.2, 0.3, 0.4],
                        [0.5, 0.6, 0.7, 0.8],
                        [0.9, 0.1, 0.2, 0.3],
                    ],
                    "metadata": [{"src": "a"}, {"src": "b"}, {"src": "c"}],
                }
            )
            handler.insert(unique_table, df)
            time.sleep(0.5)

            result = handler.select(
                unique_table,
                columns=["id", "content", "distance"],
                conditions=[
                    FilterCondition(
                        "search_vector",
                        FilterOperator.EQUAL,
                        [0.1, 0.2, 0.3, 0.4],
                    )
                ],
                limit=2,
            )
            assert len(result) == 2
            assert "distance" in result.columns
            # doc1 should be closest (identical vector)
            assert result.iloc[0]["id"] == "doc1"
            assert result.iloc[0]["distance"] <= result.iloc[1]["distance"]
        finally:
            handler.drop_table(unique_table, if_exists=True)

    def test_select_by_id(self, handler, unique_table):
        """Select a document by its ID."""
        try:
            handler.create_table(unique_table)
            df = pd.DataFrame(
                {
                    "id": ["doc1", "doc2"],
                    "content": ["hello", "world"],
                    "embeddings": [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]],
                    "metadata": [{}, {}],
                }
            )
            handler.insert(unique_table, df)
            time.sleep(0.5)

            result = handler.select(
                unique_table,
                columns=["id", "content"],
                conditions=[FilterCondition("id", FilterOperator.EQUAL, "doc2")],
            )
            assert len(result) == 1
            assert result.iloc[0]["id"] == "doc2"
            assert result.iloc[0]["content"] == "world"
        finally:
            handler.drop_table(unique_table, if_exists=True)

    def test_select_by_id_in(self, handler, unique_table):
        """Select multiple documents by ID list."""
        try:
            handler.create_table(unique_table)
            df = pd.DataFrame(
                {
                    "id": ["doc1", "doc2", "doc3"],
                    "content": ["a", "b", "c"],
                    "embeddings": [
                        [0.1, 0.2, 0.3, 0.4],
                        [0.5, 0.6, 0.7, 0.8],
                        [0.9, 0.1, 0.2, 0.3],
                    ],
                    "metadata": [{}, {}, {}],
                }
            )
            handler.insert(unique_table, df)
            time.sleep(0.5)

            result = handler.select(
                unique_table,
                columns=["id"],
                conditions=[FilterCondition("id", FilterOperator.IN, ["doc1", "doc3"])],
            )
            assert len(result) == 2
            assert set(result["id"].tolist()) == {"doc1", "doc3"}
        finally:
            handler.drop_table(unique_table, if_exists=True)

    def test_select_with_offset_limit(self, handler, unique_table):
        """Select with offset and limit restricts results."""
        try:
            handler.create_table(unique_table)
            df = pd.DataFrame(
                {
                    "id": [f"doc{i}" for i in range(5)],
                    "content": [f"c{i}" for i in range(5)],
                    "embeddings": [np.random.rand(VECTOR_DIM).tolist() for _ in range(5)],
                    "metadata": [{} for _ in range(5)],
                }
            )
            handler.insert(unique_table, df)
            time.sleep(0.5)

            result = handler.select(
                unique_table,
                columns=["id"],
                offset=1,
                limit=2,
            )
            assert len(result) <= 2
        finally:
            handler.drop_table(unique_table, if_exists=True)

    def test_delete_by_id(self, handler, unique_table):
        """Delete a single document by ID."""
        try:
            handler.create_table(unique_table)
            df = pd.DataFrame(
                {
                    "id": ["doc1", "doc2", "doc3"],
                    "content": ["a", "b", "c"],
                    "embeddings": [
                        [0.1, 0.2, 0.3, 0.4],
                        [0.5, 0.6, 0.7, 0.8],
                        [0.9, 0.1, 0.2, 0.3],
                    ],
                    "metadata": [{}, {}, {}],
                }
            )
            handler.insert(unique_table, df)
            time.sleep(0.5)

            handler.delete(
                unique_table,
                [FilterCondition("id", FilterOperator.EQUAL, "doc2")],
            )
            time.sleep(0.3)

            result = handler.select(unique_table, columns=["id"])
            assert "doc2" not in result["id"].tolist()
            assert len(result) == 2
        finally:
            handler.drop_table(unique_table, if_exists=True)

    def test_delete_by_id_in(self, handler, unique_table):
        """Delete multiple documents by ID list."""
        try:
            handler.create_table(unique_table)
            df = pd.DataFrame(
                {
                    "id": ["doc1", "doc2", "doc3"],
                    "content": ["a", "b", "c"],
                    "embeddings": [
                        [0.1, 0.2, 0.3, 0.4],
                        [0.5, 0.6, 0.7, 0.8],
                        [0.9, 0.1, 0.2, 0.3],
                    ],
                    "metadata": [{}, {}, {}],
                }
            )
            handler.insert(unique_table, df)
            time.sleep(0.5)

            handler.delete(
                unique_table,
                [FilterCondition("id", FilterOperator.IN, ["doc1", "doc3"])],
            )
            time.sleep(0.3)

            result = handler.select(unique_table, columns=["id"])
            assert set(result["id"].tolist()) == {"doc2"}
        finally:
            handler.drop_table(unique_table, if_exists=True)

    def test_drop_table(self, handler, unique_table):
        """Drop table removes index from table list."""
        handler.create_table(unique_table)
        handler.drop_table(unique_table)

        tables = handler.get_tables()
        assert unique_table not in tables.data_frame["table_name"].values

    def test_drop_table_if_exists_nonexistent(self, handler):
        """Dropping a non-existent table with if_exists=True does not raise."""
        # Should not raise
        handler.drop_table("nonexistent_table_xyz_999", if_exists=True)

    def test_get_columns(self, handler, unique_table):
        """get_columns returns expected schema."""
        try:
            handler.create_table(unique_table)
            result = handler.get_columns(unique_table)
            cols = result.data_frame["COLUMN_NAME"].tolist()
            assert "id" in cols
            assert "content" in cols
            assert "embeddings" in cols
            assert "metadata" in cols
            assert "distance" in cols
        finally:
            handler.drop_table(unique_table, if_exists=True)

    def test_upsert_existing_doc(self, handler, unique_table):
        """Re-inserting with same ID overwrites the document (upsert)."""
        try:
            handler.create_table(unique_table)
            df1 = pd.DataFrame(
                {
                    "id": ["d1"],
                    "content": ["original"],
                    "embeddings": [[0.1, 0.2, 0.3, 0.4]],
                    "metadata": [{}],
                }
            )
            handler.insert(unique_table, df1)
            time.sleep(0.3)

            df2 = pd.DataFrame(
                {
                    "id": ["d1"],
                    "content": ["updated"],
                    "embeddings": [[0.9, 0.8, 0.7, 0.6]],
                    "metadata": [{"new": "meta"}],
                }
            )
            handler.insert(unique_table, df2)
            time.sleep(0.3)

            result = handler.select(
                unique_table,
                columns=["id", "content"],
                conditions=[FilterCondition("id", FilterOperator.EQUAL, "d1")],
            )
            assert len(result) == 1
            assert result.iloc[0]["content"] == "updated"
        finally:
            handler.drop_table(unique_table, if_exists=True)

    def test_large_vectors(self, unique_table):
        """Test with high-dimensional vectors (768 dims).

        Note: Uses its own handler instance because it needs a different
        vector_dimension than the class-level fixture.
        """
        dim = 768
        h = ValkeyHandler(
            "test_large",
            connection_data={
                "host": VALKEY_HOST,
                "port": VALKEY_PORT,
                "password": VALKEY_PASSWORD,
                "vector_dimension": dim,
                "distance_metric": "COSINE",
            },
            handler_storage=MagicMock(),
        )
        try:
            status = h.check_connection()
            if not status.success:
                pytest.skip(f"Valkey not available: {status.error_message}")

            h.create_table(unique_table)
            vec = np.random.rand(dim).tolist()
            df = pd.DataFrame(
                {
                    "id": ["bigvec1"],
                    "content": ["large vector test"],
                    "embeddings": [vec],
                    "metadata": [{}],
                }
            )
            h.insert(unique_table, df)
            time.sleep(0.5)

            result = h.select(
                unique_table,
                columns=["id", "embeddings"],
                conditions=[FilterCondition("search_vector", FilterOperator.EQUAL, vec)],
                limit=1,
            )
            assert len(result) == 1
            assert result.iloc[0]["id"] == "bigvec1"
            assert len(result.iloc[0]["embeddings"]) == dim
        finally:
            h.drop_table(unique_table, if_exists=True)
            h.disconnect()
