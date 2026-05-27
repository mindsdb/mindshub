import json
import asyncio
from typing import List, Optional

import numpy as np
import pandas as pd

from glide import (
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
    ServerCredentials,
    ft,
    FtCreateOptions,
    FtSearchOptions,
    FtSearchLimit,
    DataType,
    VectorField,
    TextField,
    TagField,
    VectorAlgorithm,
    VectorFieldAttributesHnsw,
    DistanceMetricType,
    VectorType,
    RequestError,
)

from mindsdb.integrations.libs.response import RESPONSE_TYPE
from mindsdb.integrations.libs.response import HandlerResponse as Response
from mindsdb.integrations.libs.response import HandlerStatusResponse as StatusResponse
from mindsdb.integrations.libs.vectordatabase_handler import (
    FilterCondition,
    FilterOperator,
    TableField,
    VectorStoreHandler,
)
from mindsdb.utilities import log

logger = log.getLogger(__name__)

# Constants
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 6379
DEFAULT_DB = 0
DEFAULT_VECTOR_DIMENSION = 384
DEFAULT_DISTANCE_METRIC = "COSINE"
DEFAULT_PREFIX = "doc:"
VECTOR_FIELD_NAME = "embeddings"
SCORE_FIELD_NAME = f"__{VECTOR_FIELD_NAME}_score"  # "__embeddings_score"
ID_FIELD_NAME = "id"
CONTENT_FIELD_NAME = "content"
METADATA_FIELD_NAME = "metadata"


class ValkeyHandler(VectorStoreHandler):
    """MindsDB handler for Valkey Vector Store using valkey-glide client."""

    name = "valkey"

    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.handler_storage = kwargs.get("handler_storage")
        connection_data = kwargs.get("connection_data", {})

        self._host = connection_data.get("host", DEFAULT_HOST)
        self._port = int(connection_data.get("port", DEFAULT_PORT))
        self._password = connection_data.get("password", None)
        self._db = int(connection_data.get("db", DEFAULT_DB))
        self._vector_dimension = int(connection_data.get("vector_dimension", DEFAULT_VECTOR_DIMENSION))
        self._distance_metric = connection_data.get("distance_metric", DEFAULT_DISTANCE_METRIC).upper()
        self._prefix = connection_data.get("prefix", DEFAULT_PREFIX)

        self._client: Optional[GlideClient] = None
        self.is_connected = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create an event loop for running async operations."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop

    def _run(self, coro):
        """Execute an async coroutine synchronously."""
        loop = self._get_loop()
        return loop.run_until_complete(coro)

    def _get_distance_metric(self) -> DistanceMetricType:
        """Map string distance metric to DistanceMetricType enum."""
        mapping = {
            "COSINE": DistanceMetricType.COSINE,
            "L2": DistanceMetricType.L2,
            "IP": DistanceMetricType.IP,
        }
        return mapping.get(self._distance_metric, DistanceMetricType.COSINE)

    def connect(self) -> GlideClient:
        """Connect to Valkey server and return the client instance."""
        if self.is_connected and self._client is not None:
            return self._client

        try:
            credentials = ServerCredentials(password=self._password) if self._password else None
            config = GlideClientConfiguration(
                addresses=[NodeAddress(host=self._host, port=self._port)],
                credentials=credentials,
                database_id=self._db,
                client_name="mindsdb_valkey_handler",
            )
            self._client = self._run(GlideClient.create(config))
            self.is_connected = True
            return self._client
        except Exception as e:
            logger.error(f"Error connecting to Valkey at {self._host}:{self._port}: {e}")
            self.is_connected = False
            raise

    def disconnect(self):
        """Disconnect from Valkey server."""
        if self.is_connected and self._client is not None:
            try:
                self._run(self._client.close())
            except Exception as e:
                logger.debug(f"Error during Valkey disconnect: {e}")
        self._client = None
        self.is_connected = False
        if self._loop is not None and not self._loop.is_closed():
            self._loop.close()
            self._loop = None

    def check_connection(self) -> StatusResponse:
        """Check connectivity to Valkey server."""
        response = StatusResponse(False)
        need_to_close = not self.is_connected
        try:
            client = self.connect()
            self._run(client.ping())
            response.success = True
        except Exception as e:
            logger.error(f"Error connecting to Valkey: {e}")
            response.error_message = str(e)
        finally:
            if response.success and need_to_close:
                self.disconnect()
            if not response.success and self.is_connected:
                self.is_connected = False
        return response

    def create_table(self, table_name: str, if_not_exists: bool = True):
        """Create a vector index in Valkey.

        Args:
            table_name: Name of the index to create.
            if_not_exists: If True, silently skip if index already exists.
        """
        self.connect()

        schema = [
            TextField(CONTENT_FIELD_NAME),
            TagField(ID_FIELD_NAME),
            VectorField(
                VECTOR_FIELD_NAME,
                VectorAlgorithm.HNSW,
                VectorFieldAttributesHnsw(
                    dimensions=self._vector_dimension,
                    distance_metric=self._get_distance_metric(),
                    type=VectorType.FLOAT32,
                ),
            ),
            TextField(METADATA_FIELD_NAME),
        ]

        options = FtCreateOptions(
            data_type=DataType.HASH,
            prefixes=[f"{self._prefix}{table_name}:"],
        )

        try:
            self._run(ft.create(self._client, table_name, schema, options))
        except RequestError as e:
            if "already exists" in str(e).lower() and if_not_exists:
                return
            raise

    def drop_table(self, table_name: str, if_exists: bool = True):
        """Drop a vector index and its associated data.

        Args:
            table_name: Name of the index to drop.
            if_exists: If True, silently skip if index doesn't exist.
        """
        self.connect()

        try:
            self._run(ft.dropindex(self._client, table_name))
        except RequestError as e:
            if "not found" in str(e).lower() and if_exists:
                return
            raise

        # Clean up hash keys with the table's prefix
        cursor = b"0"
        while True:
            result = self._run(
                self._client.scan(
                    cursor,
                    match=f"{self._prefix}{table_name}:*",
                    count=1000,
                )
            )
            cursor = result[0]
            keys = result[1]
            if keys:
                self._run(self._client.unlink(keys))
            if cursor == b"0":
                break

    def insert(self, table_name: str, data: pd.DataFrame):
        """Insert documents with embeddings into the vector store.

        Args:
            table_name: Name of the target index.
            data: DataFrame with columns: id, content, embeddings, metadata.
        """
        self.connect()

        async def _batch_insert():
            for _, row in data.iterrows():
                doc_id = str(row[TableField.ID.value])
                key = f"{self._prefix}{table_name}:{doc_id}"

                # Serialize embeddings to float32 bytes
                embeddings = row[TableField.EMBEDDINGS.value]
                emb_bytes = np.array(embeddings, dtype=np.float32).tobytes()

                field_map = {
                    ID_FIELD_NAME: doc_id,
                    VECTOR_FIELD_NAME: emb_bytes,
                }

                # Content field
                content = row.get(TableField.CONTENT.value)
                if content is not None and pd.notna(content):
                    field_map[CONTENT_FIELD_NAME] = str(content)
                else:
                    field_map[CONTENT_FIELD_NAME] = ""

                # Metadata field
                metadata = row.get(TableField.METADATA.value)
                if metadata is not None and isinstance(metadata, dict):
                    field_map[METADATA_FIELD_NAME] = json.dumps(metadata)
                else:
                    field_map[METADATA_FIELD_NAME] = "{}"

                try:
                    await self._client.hset(key, field_map)
                except Exception as e:
                    logger.error(f"Error inserting document {doc_id} into {table_name}: {e}")

        self._run(_batch_insert())

    def select(
        self,
        table_name: str,
        columns: List[str] = None,
        conditions: List[FilterCondition] = None,
        offset: int = None,
        limit: int = None,
    ) -> pd.DataFrame:
        """Select documents from the vector store.

        Args:
            table_name: Name of the index to query.
            columns: List of columns to return.
            conditions: Filter conditions (search_vector for KNN, id for lookup).
            offset: Result offset.
            limit: Maximum number of results (K for KNN).

        Returns:
            DataFrame with requested columns.
        """
        self.connect()

        # Separate conditions by type
        search_vector = None
        id_filters: List[FilterCondition] = []
        metadata_filters: List[FilterCondition] = []

        if conditions:
            for cond in conditions:
                if cond.column == TableField.SEARCH_VECTOR.value:
                    search_vector = cond.value
                elif cond.column == TableField.ID.value:
                    id_filters.append(cond)
                elif cond.column.startswith(TableField.METADATA.value):
                    metadata_filters.append(cond)

        # Case A: KNN Vector Search
        if search_vector is not None:
            k = limit if limit else 10
            query_vec = np.array(search_vector, dtype=np.float32).tobytes()

            filter_expr = self._build_filter_expression(id_filters, metadata_filters)
            query_str = f"{filter_expr}=>[KNN {k} @{VECTOR_FIELD_NAME} $query_vec]"

            options = FtSearchOptions(
                params={"query_vec": query_vec},
                limit=FtSearchLimit(offset or 0, k),
                dialect=2,
            )
            result = self._run(ft.search(self._client, table_name, query_str, options))
            return self._parse_search_result(result, columns, include_score=True)

        # Case B: ID-only lookup (direct hash access for EQUAL/IN only)
        if id_filters and not metadata_filters:
            # Check if any filter uses NOT_EQUAL or NOT_IN — these cannot be
            # resolved via direct hash lookup and need the FT.SEARCH path.
            has_negation = any(
                cond.op in (FilterOperator.NOT_EQUAL, FilterOperator.NOT_IN)
                for cond in id_filters
            )
            if not has_negation:
                docs = []
                for cond in id_filters:
                    if cond.op == FilterOperator.EQUAL:
                        ids = [cond.value]
                    elif cond.op == FilterOperator.IN:
                        ids = cond.value
                    else:
                        ids = []
                    for doc_id in ids:
                        key = f"{self._prefix}{table_name}:{doc_id}"
                        fields = self._run(self._client.hgetall(key))
                        if fields:
                            docs.append(fields)

                rows = [self._parse_doc_fields(f, include_score=False) for f in docs]
                df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=columns or [c["name"] for c in self.SCHEMA])
                if columns and not df.empty:
                    available = [c for c in columns if c in df.columns]
                    df = df[available]
                return df
            # Fall through to Case C for negation filters

        # Case C: Full scan / metadata filter
        filter_expr = self._build_filter_expression(id_filters, metadata_filters)

        if filter_expr == "*":
            # Valkey Search does not support "*" as a match-all query.
            # Use SCAN to fetch all keys with the table prefix instead.
            return self._scan_all_docs(table_name, columns, offset, limit)

        options = FtSearchOptions(
            limit=FtSearchLimit(offset or 0, limit or 100),
            dialect=2,
        )
        result = self._run(ft.search(self._client, table_name, filter_expr, options))
        return self._parse_search_result(result, columns, include_score=False)

    def delete(self, table_name: str, conditions: List[FilterCondition] = None):
        """Delete documents from the vector store.

        Args:
            table_name: Name of the index.
            conditions: Conditions specifying which documents to delete.
        """
        self.connect()

        if not conditions:
            raise Exception("Delete requires at least one condition")

        ids_to_delete: List[str] = []

        for cond in conditions:
            if cond.column == TableField.ID.value:
                if cond.op == FilterOperator.EQUAL:
                    ids_to_delete.append(str(cond.value))
                elif cond.op == FilterOperator.IN:
                    ids_to_delete.extend(str(v) for v in cond.value)
            elif cond.column.startswith(TableField.METADATA.value):
                # Search for matching docs to get their IDs
                filter_expr = self._build_filter_expression([], [cond])
                options = FtSearchOptions(limit=FtSearchLimit(0, 10000), dialect=2)
                result = self._run(ft.search(self._client, table_name, filter_expr, options))
                if result[0] > 0 and len(result) > 1:
                    for doc_key in result[1].keys():
                        key_str = doc_key.decode() if isinstance(doc_key, bytes) else doc_key
                        # Extract doc_id from key: "prefix:table:doc_id"
                        prefix_str = f"{self._prefix}{table_name}:"
                        if key_str.startswith(prefix_str):
                            doc_id = key_str[len(prefix_str) :]
                        else:
                            doc_id = key_str.split(":", 2)[-1]
                        ids_to_delete.append(doc_id)

        if ids_to_delete:
            keys = [f"{self._prefix}{table_name}:{doc_id}" for doc_id in ids_to_delete]
            self._run(self._client.unlink(keys))

    def get_tables(self) -> Response:
        """List all vector indexes.

        Returns:
            HandlerResponse with DataFrame containing table_name column.
        """
        self.connect()
        indexes = self._run(ft.list(self._client))
        index_names = [idx.decode() if isinstance(idx, bytes) else str(idx) for idx in indexes]
        df = pd.DataFrame({"table_name": index_names})
        return Response(resp_type=RESPONSE_TYPE.TABLE, data_frame=df)

    def get_columns(self, table_name: str):
        """Get columns for a table (index).

        Args:
            table_name: Name of the index.

        Returns:
            TableResponse with column schema.
        """
        self.connect()
        try:
            self._run(ft.info(self._client, table_name))
        except RequestError as e:
            if "not found" in str(e).lower():
                return Response(
                    resp_type=RESPONSE_TYPE.ERROR,
                    error_message=f"Table {table_name} does not exist!",
                )
            raise
        return super().get_columns(table_name)

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _scan_all_docs(
        self,
        table_name: str,
        columns: Optional[List[str]],
        offset: Optional[int],
        limit: Optional[int],
    ) -> pd.DataFrame:
        """Scan all documents for a table using SCAN + HGETALL.

        Valkey Search does not support '*' as a match-all query, so this method
        iterates over all hash keys matching the table prefix and returns their
        fields as a DataFrame.

        Note: SCAN does not guarantee key ordering. Offset-based pagination
        may return inconsistent results across calls if keys are being
        added or removed concurrently. This is a known Valkey/Redis limitation.

        Args:
            table_name: Name of the index/table.
            columns: Columns to include in output.
            offset: Number of rows to skip.
            limit: Maximum number of rows to return.

        Returns:
            DataFrame with document data.
        """
        prefix = f"{self._prefix}{table_name}:"
        all_keys: List[str] = []
        cursor = b"0"
        while True:
            result = self._run(self._client.scan(cursor, match=f"{prefix}*", count=1000))
            cursor = result[0]
            keys = result[1]
            if keys:
                all_keys.extend(k.decode() if isinstance(k, bytes) else k for k in keys)
            if cursor == b"0":
                break

        # Apply offset and limit
        start = offset or 0
        end = start + (limit or 100)
        selected_keys = all_keys[start:end]

        rows = []
        for key in selected_keys:
            fields = self._run(self._client.hgetall(key))
            if fields:
                rows.append(self._parse_doc_fields(fields, include_score=False))

        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=columns or [c["name"] for c in self.SCHEMA])
        if columns and not df.empty:
            available = [c for c in columns if c in df.columns]
            df = df[available]
        return df

    def _parse_search_result(self, result, columns: Optional[List[str]], include_score: bool) -> pd.DataFrame:
        """Parse ft.search result into a DataFrame.

        Args:
            result: Raw result from ft.search [total_count, {doc_key: {fields}}].
            columns: Columns to include in output.
            include_score: Whether to include distance/score column.

        Returns:
            DataFrame with parsed results.
        """
        total_count = result[0]
        if total_count == 0 or len(result) < 2:
            return pd.DataFrame(columns=columns or [c["name"] for c in self.SCHEMA])

        docs_map = result[1]
        rows = []
        for doc_key, fields in docs_map.items():
            row = self._parse_doc_fields(fields, include_score=include_score)
            rows.append(row)

        df = pd.DataFrame(rows)
        if columns and not df.empty:
            available = [c for c in columns if c in df.columns]
            df = df[available]
        return df

    def _parse_doc_fields(self, fields: dict, include_score: bool = False) -> dict:
        """Convert raw bytes fields from Valkey hash into Python types.

        Args:
            fields: Raw field dict from Valkey (keys and values may be bytes).
            include_score: Whether to extract the distance score.

        Returns:
            Dict with parsed field values.
        """
        # Decode bytes keys to str
        decoded = {(k.decode() if isinstance(k, bytes) else k): v for k, v in fields.items()}

        row = {}
        row[TableField.ID.value] = self._decode_value(decoded.get(ID_FIELD_NAME, b""))
        row[TableField.CONTENT.value] = self._decode_value(decoded.get(CONTENT_FIELD_NAME, b""))

        # Embeddings: raw float32 bytes → list of floats
        raw_emb = decoded.get(VECTOR_FIELD_NAME, b"")
        if isinstance(raw_emb, bytes) and len(raw_emb) > 0:
            row[TableField.EMBEDDINGS.value] = np.frombuffer(raw_emb, dtype=np.float32).tolist()
        else:
            row[TableField.EMBEDDINGS.value] = []

        # Metadata: JSON string → dict
        raw_meta = self._decode_value(decoded.get(METADATA_FIELD_NAME, b"{}"))
        try:
            row[TableField.METADATA.value] = json.loads(raw_meta) if raw_meta else {}
        except (json.JSONDecodeError, TypeError):
            row[TableField.METADATA.value] = {}

        # Distance/score (only from KNN search results)
        if include_score and SCORE_FIELD_NAME in decoded:
            score_val = self._decode_value(decoded[SCORE_FIELD_NAME])
            try:
                row[TableField.DISTANCE.value] = float(score_val)
            except (ValueError, TypeError):
                row[TableField.DISTANCE.value] = 0.0

        return row

    def _decode_value(self, val) -> str:
        """Decode a bytes value to string."""
        if isinstance(val, bytes):
            return val.decode("utf-8", errors="replace")
        return str(val) if val is not None else ""

    def _build_filter_expression(
        self,
        id_filters: List[FilterCondition],
        metadata_filters: List[FilterCondition],
    ) -> str:
        """Build Valkey Search query filter string from FilterCondition objects.

        Args:
            id_filters: Conditions on the id field.
            metadata_filters: Conditions on metadata fields.

        Returns:
            Filter expression string for ft.search query.
        """
        parts = []

        for cond in id_filters:
            if cond.op == FilterOperator.EQUAL:
                parts.append(f"@{ID_FIELD_NAME}:{{{self._escape_tag(str(cond.value))}}}")
            elif cond.op == FilterOperator.IN:
                escaped = "|".join(self._escape_tag(str(v)) for v in cond.value)
                parts.append(f"@{ID_FIELD_NAME}:{{{escaped}}}")
            elif cond.op == FilterOperator.NOT_EQUAL:
                parts.append(f"-@{ID_FIELD_NAME}:{{{self._escape_tag(str(cond.value))}}}")
            elif cond.op == FilterOperator.NOT_IN:
                escaped = "|".join(self._escape_tag(str(v)) for v in cond.value)
                parts.append(f"-@{ID_FIELD_NAME}:{{{escaped}}}")

        for cond in metadata_filters:
            # Metadata is stored as a flat JSON string in a TextField.
            # Full-text search on a TextField cannot reliably filter by JSON
            # sub-keys. We support basic substring matching for simple cases,
            # but this is a best-effort approach with known limitations.
            # For precise metadata filtering, consider using dedicated fields.
            field_name = cond.column.split(".", 1)[-1]
            if cond.op == FilterOperator.EQUAL:
                # Search for the value as a phrase within the metadata text field.
                # This matches documents whose metadata JSON contains the value string.
                escaped_value = str(cond.value).replace('"', '\\"')
                parts.append(f'@{METADATA_FIELD_NAME}:("{escaped_value}")')
            elif cond.op == FilterOperator.NOT_EQUAL:
                escaped_value = str(cond.value).replace('"', '\\"')
                parts.append(f'-@{METADATA_FIELD_NAME}:("{escaped_value}")')

        if not parts:
            return "*"
        return " ".join(parts)

    def _escape_tag(self, value: str) -> str:
        """Escape special characters for Valkey Search TAG field queries.

        Args:
            value: Raw tag value.

        Returns:
            Escaped string safe for use in TAG filter expressions.
        """
        special = r',.<>{}[]"\';:!@#$%^&*()-+=~/ '
        result = ""
        for ch in str(value):
            if ch in special:
                result += f"\\{ch}"
            else:
                result += ch
        return result
