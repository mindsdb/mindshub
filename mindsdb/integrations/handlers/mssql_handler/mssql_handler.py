from typing import Any, Union, TYPE_CHECKING
import datetime

import pymssql
from pymssql import OperationalError
import pandas as pd
from pandas.api import types as pd_types
from sqlalchemy.exc import SQLAlchemyError

from mindsdb_sql_parser import parse_sql
from mindsdb_sql_parser.ast.base import ASTNode
from mindsdb_sql_parser.ast import Identifier

from mindsdb.integrations.libs.base import MetaDatabaseHandler
from mindsdb.integrations.utilities.query_traversal import query_traversal
from mindsdb.utilities import log
from mindsdb.utilities.render.sqlalchemy_render import SqlalchemyRender, RenderError
from mindsdb.integrations.libs.response import (
    HandlerStatusResponse as StatusResponse,
    HandlerResponse as Response,
    RESPONSE_TYPE,
)
from mindsdb.api.mysql.mysql_proxy.libs.constants.mysql import MYSQL_DATA_TYPE

if TYPE_CHECKING:
    import pyodbc

logger = log.getLogger(__name__)


def _map_type(mssql_type_text: str) -> MYSQL_DATA_TYPE:
    """Map MSSQL text types names to MySQL types as enum.

    Args:
        mssql_type_text (str): The name of the MSSQL type to map.

    Returns:
        MYSQL_DATA_TYPE: The MySQL type enum that corresponds to the MSSQL text type name.
    """
    internal_type_name = mssql_type_text.lower()
    types_map = {
        ("tinyint", "smallint", "int", "bigint"): MYSQL_DATA_TYPE.INT,
        ("bit",): MYSQL_DATA_TYPE.BOOL,
        ("money", "smallmoney", "float", "real"): MYSQL_DATA_TYPE.FLOAT,
        ("decimal", "numeric"): MYSQL_DATA_TYPE.DECIMAL,
        ("date",): MYSQL_DATA_TYPE.DATE,
        ("time",): MYSQL_DATA_TYPE.TIME,
        ("datetime2", "datetimeoffset", "datetime", "smalldatetime"): MYSQL_DATA_TYPE.DATETIME,
        ("varchar", "nvarchar"): MYSQL_DATA_TYPE.VARCHAR,
        ("char", "text", "nchar", "ntext"): MYSQL_DATA_TYPE.TEXT,
        ("binary", "varbinary", "image"): MYSQL_DATA_TYPE.BINARY,
    }

    for db_types_list, mysql_data_type in types_map.items():
        if internal_type_name in db_types_list:
            return mysql_data_type

    logger.debug(f"MSSQL handler type mapping: unknown type: {internal_type_name}, use VARCHAR as fallback.")
    return MYSQL_DATA_TYPE.VARCHAR


def _make_table_response(
    result: list[Union[dict[str, Any], tuple]], cursor: Union[pymssql.Cursor, "pyodbc.Cursor"], use_odbc: bool = False
) -> Response:
    """Build response from result and cursor.

    Args:
        result (list[Union[dict[str, Any], tuple]]): result of the query.
        cursor (Union[pymssql.Cursor, pyodbc.Cursor]): cursor object.
        use_odbc (bool): whether ODBC connection is being used.

    Returns:
        Response: response object.
    """
    description: list[tuple[Any]] = cursor.description
    mysql_types: list[MYSQL_DATA_TYPE] = []
    columns = [x[0] for x in cursor.description]

    if not result:
        data_frame = pd.DataFrame(columns=columns)
    elif use_odbc:
        # from_records() understands tuple-like records (including pyodbc.Row)
        data_frame = pd.DataFrame.from_records(result, columns=columns)
    else:
        # pymssql with as_dict=True returns list of dicts
        data_frame = pd.DataFrame(result)

    for column in description:
        column_name = column[0]
        column_type = column[1]
        column_dtype = data_frame[column_name].dtype

        if use_odbc:
            # For pyodbc, use type inference based on pandas dtype
            if pd_types.is_integer_dtype(column_dtype):
                mysql_types.append(MYSQL_DATA_TYPE.INT)
            elif pd_types.is_float_dtype(column_dtype):
                mysql_types.append(MYSQL_DATA_TYPE.FLOAT)
            elif pd_types.is_bool_dtype(column_dtype):
                mysql_types.append(MYSQL_DATA_TYPE.TINYINT)
            elif pd_types.is_datetime64_any_dtype(column_dtype):
                mysql_types.append(MYSQL_DATA_TYPE.DATETIME)
            elif pd_types.is_object_dtype(column_dtype):
                if len(data_frame) > 0 and isinstance(
                    data_frame[column_name].iloc[0], (datetime.datetime, datetime.date, datetime.time)
                ):
                    mysql_types.append(MYSQL_DATA_TYPE.DATETIME)
                else:
                    mysql_types.append(MYSQL_DATA_TYPE.TEXT)
            else:
                mysql_types.append(MYSQL_DATA_TYPE.TEXT)
        else:
            match column_type:
                case pymssql.NUMBER:
                    if pd_types.is_integer_dtype(column_dtype):
                        mysql_types.append(MYSQL_DATA_TYPE.INT)
                    elif pd_types.is_float_dtype(column_dtype):
                        mysql_types.append(MYSQL_DATA_TYPE.FLOAT)
                    elif pd_types.is_bool_dtype(column_dtype):
                        mysql_types.append(MYSQL_DATA_TYPE.TINYINT)
                    else:
                        mysql_types.append(MYSQL_DATA_TYPE.DOUBLE)
                case pymssql.DECIMAL:
                    mysql_types.append(MYSQL_DATA_TYPE.DECIMAL)
                case pymssql.STRING:
                    mysql_types.append(MYSQL_DATA_TYPE.TEXT)
                case pymssql.DATETIME:
                    mysql_types.append(MYSQL_DATA_TYPE.DATETIME)
                case pymssql.BINARY:
                    # DATE and TIME types returned as 'BINARY' type, and dataframe type is 'object', so it is not possible
                    # to infer correct mysql type for them
                    if pd_types.is_datetime64_any_dtype(column_dtype):
                        # pymssql return datetimes as 'binary' type
                        # if timezone is present, then it is datetime.timezone
                        series = data_frame[column_name]
                        if (
                            series.dt.tz is not None
                            and isinstance(series.dt.tz, datetime.timezone)
                            and series.dt.tz != datetime.timezone.utc
                        ):
                            series = series.dt.tz_convert("UTC")
                            data_frame[column_name] = series.dt.tz_localize(None)
                        mysql_types.append(MYSQL_DATA_TYPE.DATETIME)
                    else:
                        mysql_types.append(MYSQL_DATA_TYPE.BINARY)
                case _:
                    logger.warning(f"Unknown type: {column_type}, use TEXT as fallback.")
                    mysql_types.append(MYSQL_DATA_TYPE.TEXT)

    return Response(RESPONSE_TYPE.TABLE, data_frame=data_frame, mysql_types=mysql_types)


class SqlServerHandler(MetaDatabaseHandler):
    """
    This handler handles connection and execution of the Microsoft SQL Server statements.
    Supports both native pymssql connections and ODBC connections via pyodbc.

    To use ODBC connection, specify either:
    - 'use_odbc': True in connection parameters, or
    - 'driver': '<ODBC driver name>' in connection parameters
    """

    name = "mssql"

    def __init__(self, name, **kwargs):
        super().__init__(name)
        self.parser = parse_sql
        self.connection_args = kwargs.get("connection_data")
        self.dialect = "mssql"
        self.database = self.connection_args.get("database")
        self.schema = self.connection_args.get("schema")
        self.renderer = SqlalchemyRender("mssql")

        # Determine if ODBC should be used
        self.use_odbc = self.connection_args.get("use_odbc", False) or "driver" in self.connection_args

        self.connection = None
        self.is_connected = False

    def __del__(self):
        if self.is_connected is True:
            self.disconnect()

    def connect(self):
        """
        Establishes a connection to a Microsoft SQL Server database.
        Uses either pymssql (native) or pyodbc based on configuration.

        Raises:
            pymssql._mssql.OperationalError or pyodbc.Error: If an error occurs while connecting to the database.

        Returns:
            Union[pymssql.Connection, pyodbc.Connection]: A connection object to the Microsoft SQL Server database.
        """

        if self.is_connected is True:
            return self.connection

        if self.use_odbc:
            return self._connect_odbc()
        else:
            return self._connect_pymssql()

    def _connect_pymssql(self):
        """Connect using pymssql (native FreeTDS-based connection)."""
        # Mandatory connection parameters
        if not all(key in self.connection_args for key in ["host", "user", "password", "database"]):
            raise ValueError("Required parameters (host, user, password, database) must be provided.")

        config = {
            "host": self.connection_args.get("host"),
            "user": self.connection_args.get("user"),
            "password": self.connection_args.get("password"),
            "database": self.connection_args.get("database"),
        }

        # Optional connection parameters
        if "port" in self.connection_args:
            config["port"] = self.connection_args.get("port")

        if "server" in self.connection_args:
            config["server"] = self.connection_args.get("server")

        try:
            self.connection = pymssql.connect(**config)
            self.is_connected = True
            return self.connection
        except OperationalError as e:
            logger.error(f"Error connecting to Microsoft SQL Server {self.database}, {e}!")
            self.is_connected = False
            raise

    def _connect_odbc(self):
        """Connect using pyodbc (ODBC connection)."""
        try:
            import pyodbc
        except ImportError as e:
            raise ImportError(
                "pyodbc is not installed. Install it with 'pip install pyodbc' or "
                "'pip install mindsdb[mssql-odbc]' to use ODBC connections."
            ) from e

        # Mandatory connection parameters
        if not all(key in self.connection_args for key in ["host", "user", "password", "database"]):
            raise ValueError("Required parameters (host, user, password, database) must be provided.")

        driver = self.connection_args.get("driver", "ODBC Driver 18 for SQL Server")
        host = self.connection_args.get("host")
        port = self.connection_args.get("port", 1433)
        database = self.connection_args.get("database")
        user = self.connection_args.get("user")
        password = self.connection_args.get("password")

        conn_str_parts = [
            f"DRIVER={{{driver}}}",
            f"SERVER={host},{port}",
            f"DATABASE={database}",
            f"UID={user}",
            f"PWD={password}",
        ]

        # Add optional parameters
        if "encrypt" in self.connection_args:
            conn_str_parts.append(f"Encrypt={self.connection_args.get('encrypt', 'yes')}")
        if "trust_server_certificate" in self.connection_args:
            conn_str_parts.append(
                f"TrustServerCertificate={self.connection_args.get('trust_server_certificate', 'yes')}"
            )

        if "connection_string_args" in self.connection_args:
            conn_str_parts.append(self.connection_args["connection_string_args"])

        conn_str = ";".join(conn_str_parts)

        try:
            self.connection = pyodbc.connect(conn_str, timeout=10)
            self.is_connected = True
            return self.connection
        except pyodbc.Error as e:
            logger.error(f"Error connecting to Microsoft SQL Server {self.database} via ODBC, {e}!")
            self.is_connected = False

            # Check if it's a driver not found error
            error_msg = str(e)
            if "Driver" in error_msg and ("not found" in error_msg or "specified" in error_msg):
                raise ConnectionError(
                    f"ODBC Driver not found: {driver}. "
                    f"Please install the Microsoft ODBC Driver for SQL Server. "
                    f"Error: {e}"
                ) from e
            raise
        except Exception as e:
            logger.error(f"Error connecting to Microsoft SQL Server {self.database} via ODBC, {e}!")
            self.is_connected = False
            raise

    def disconnect(self):
        """
        Closes the connection to the Microsoft SQL Server database if it's currently open.
        """

        if not self.is_connected:
            return
        if self.connection is not None:
            try:
                self.connection.close()
            except Exception:
                logger.exception("Failed to close connection:")
                pass
        self.connection = None
        self.is_connected = False

    def check_connection(self) -> StatusResponse:
        """
        Checks the status of the connection to the Microsoft SQL Server database.

        Returns:
            StatusResponse: An object containing the success status and an error message if an error occurs.
        """

        response = StatusResponse(False)
        need_to_close = self.is_connected is False

        try:
            connection = self.connect()
            with connection.cursor() as cur:
                # Execute a simple query to test the connection
                cur.execute("select 1;")
            response.success = True
        except Exception as e:
            logger.error(f"Error connecting to Microsoft SQL Server {self.database}, {e}!")
            response.error_message = str(e)

        if response.success and need_to_close:
            self.disconnect()
        elif not response.success and self.is_connected:
            self.is_connected = False

        return response

    def native_query(self, query: str) -> Response:
        """
        Executes a SQL query on the Microsoft SQL Server database and returns the result.

        Args:
            query (str): The SQL query to be executed.

        Returns:
            Response: A response object containing the result of the query or an error message.
        """

        need_to_close = self.is_connected is False

        connection = self.connect()

        if self.use_odbc:
            with connection.cursor() as cur:
                try:
                    cur.execute(query)
                    if cur.description:
                        result = cur.fetchall()
                        response = _make_table_response(result, cur, use_odbc=True)
                    else:
                        response = Response(RESPONSE_TYPE.OK, affected_rows=cur.rowcount)
                    connection.commit()
                except Exception as e:
                    logger.exception(f"Error running query: {query} on {self.database}, {e}!")
                    response = Response(RESPONSE_TYPE.ERROR, error_code=0, error_message=str(e))
                    connection.rollback()
        else:
            with connection.cursor(as_dict=True) as cur:
                try:
                    cur.execute(query)
                    if cur.description:
                        result = cur.fetchall()
                        response = _make_table_response(result, cur, use_odbc=False)
                    else:
                        response = Response(RESPONSE_TYPE.OK, affected_rows=cur.rowcount)
                    connection.commit()
                except Exception as e:
                    logger.exception(f"Error running query: {query} on {self.database}, {e}!")
                    response = Response(RESPONSE_TYPE.ERROR, error_code=0, error_message=str(e))
                    connection.rollback()

        if need_to_close is True:
            self.disconnect()

        return response

    def _add_schema_to_tables(self, node, is_table=False, **kwargs):
        """
        Callback for query_traversal that adds schema prefix to table identifiers.

        Args:
            node: The AST node being visited
            is_table: True if this node represents a table reference
            **kwargs: Other arguments from query_traversal (parent_query, callstack, etc.)

        Returns:
            None to keep traversing, or a replacement node
        Note: This is mostly a workaround for Minds but it should still work for FQE
        """
        if is_table and isinstance(node, Identifier):
            # Only add schema if the identifier doesn't already have one (single part)
            if len(node.parts) == 1:
                node.parts.insert(0, self.schema)
                node.is_quoted.insert(0, False)
        return None

    def query(self, query: ASTNode) -> Response:
        """
        Executes a SQL query represented by an ASTNode and retrieves the data.

        Args:
            query (ASTNode): An ASTNode representing the SQL query to be executed.

        Returns:
            Response: The response from the `native_query` method, containing the result of the SQL query execution.
        """
        # Add schema prefix to table identifiers if schema is configured
        if self.schema:
            query_traversal(query, self._add_schema_to_tables)
        query_str, render_error = None, None
        try:
            query_str = self.renderer.get_string(query, with_failback=False)
        except (SQLAlchemyError, NotImplementedError, RenderError) as e:
            render_error = str(e)

        if query_str is None:
            query_str = self.renderer.get_string(query, with_failback=True)

        logger.debug(f"Executing SQL query: {query_str}")
        resp = self.native_query(query_str)
        if resp.resp_type == RESPONSE_TYPE.ERROR and render_error:
            resp.error_message += f"\nThe problem with render: {render_error}"
        return resp

    def get_tables(self, all: bool = False) -> Response:
        """
        Retrieves a list of all non-system tables and views in the Microsoft SQL Server database.

        When a specific schema is configured (``self.schema``), only tables belonging to that
        schema are returned regardless of the ``all`` flag.  When no schema is configured:

        * ``all=False`` (default, used by ``INFORMATION_SCHEMA.TABLES``) – returns tables from
          every non-system schema and exposes the real SQL schema name in *table_schema*.
          ``table_name`` is qualified as ``<schema>.<table>`` so that the three-part name
          ``<datasource>.<schema>.<table>`` works transparently in MindsDB SQL.
        * ``all=True`` (used by the Explorer UI / tree endpoint) – same query but
          ``table_name`` is **not** prefixed; the raw ``table_schema`` column is kept so the
          UI can group tables under their schema nodes.

        Args:
            all (bool): When *True* the unqualified ``table_name`` is returned (Explorer mode).
                        When *False* (default) ``table_name`` is prefixed with the schema so
                        that ``INFORMATION_SCHEMA.TABLES`` exposes the full three-part table
                        reference.

        Returns:
            Response: A response object containing the list of tables and views, formatted as
                      per the ``Response`` class.
        """

        if self.schema:
            # Single-schema mode: schema filter is always applied; names are unambiguous.
            query = f"""
                SELECT
                    table_schema,
                    table_name,
                    table_type
                FROM {self.database}.INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE in ('BASE TABLE', 'VIEW')
                  AND table_schema = '{self.schema}'
            """
            return self.native_query(query)

        if all:
            # Explorer / tree mode: return raw schema + table columns so the UI can
            # group tables under their schema nodes.
            query = f"""
                SELECT
                    table_schema,
                    table_name,
                    table_type
                FROM {self.database}.INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE in ('BASE TABLE', 'VIEW')
                  AND table_schema NOT IN ('sys', 'INFORMATION_SCHEMA', 'guest', 'db_owner',
                      'db_accessadmin', 'db_securityadmin', 'db_ddladmin', 'db_backupoperator',
                      'db_datareader', 'db_datawriter', 'db_denydatareader', 'db_denydatawriter')
                ORDER BY table_schema, table_name
            """
            return self.native_query(query)

        # INFORMATION_SCHEMA.TABLES mode (all=False, no explicit schema): qualify
        # table_name as "<schema>.<table>" so the datasource-level TABLE_SCHEMA
        # override in MindsDB's system_tables layer does not hide the real schema.
        query = f"""
            SELECT
                table_schema,
                table_schema + '.' + table_name AS table_name,
                table_type
            FROM {self.database}.INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE in ('BASE TABLE', 'VIEW')
              AND table_schema NOT IN ('sys', 'INFORMATION_SCHEMA', 'guest', 'db_owner',
                  'db_accessadmin', 'db_securityadmin', 'db_ddladmin', 'db_backupoperator',
                  'db_datareader', 'db_datawriter', 'db_denydatareader', 'db_denydatawriter')
            ORDER BY table_schema, table_name
        """
        return self.native_query(query)

    def get_columns(self, table_name: str, schema_name: str | None = None) -> Response:
        """
        Retrieves column details for a specified table in the Microsoft SQL Server database.

        ``table_name`` may arrive as a qualified ``<schema>.<table>`` string (produced by
        :meth:`get_tables` when no explicit schema is configured).  In that case the schema
        part is extracted automatically and used as the ``table_schema`` filter.

        Args:
            table_name (str): The name of the table, optionally qualified as
                ``<schema>.<table>``.
            schema_name (str | None): Explicit schema override.  When provided it takes
                precedence over any schema embedded in ``table_name`` and over
                ``self.schema``.

        Returns:
            Response: A response object containing the column details, formatted as per the
                      ``Response`` class.
        Raises:
            ValueError: If the 'table_name' is not a valid string.
        """

        # Resolve schema: explicit arg > embedded in table_name > handler-level self.schema.
        effective_schema = schema_name or self.schema
        if effective_schema is None and "." in table_name:
            # table_name was qualified by get_tables() as "<schema>.<table>"
            parts = table_name.split(".", 1)
            effective_schema, table_name = parts[0], parts[1]

        query = f"""
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                ORDINAL_POSITION,
                COLUMN_DEFAULT,
                IS_NULLABLE,
                CHARACTER_MAXIMUM_LENGTH,
                CHARACTER_OCTET_LENGTH,
                NUMERIC_PRECISION,
                NUMERIC_SCALE,
                DATETIME_PRECISION,
                CHARACTER_SET_NAME,
                COLLATION_NAME
            FROM
                information_schema.columns
            WHERE
                table_name = '{table_name}'
        """

        if effective_schema:
            query += f" AND table_schema = '{effective_schema}'"

        result = self.native_query(query)
        result.to_columns_table_response(map_type_fn=_map_type)
        return result

    def meta_get_tables(self, table_names: list[str] | None = None) -> Response:
        """
        Retrieves metadata information about the tables in the Microsoft SQL Server database
        to be stored in the data catalog.

        Args:
            table_names (list): A list of table names for which to retrieve metadata information.

        Returns:
            Response: A response object containing the metadata information, formatted as per the `Response` class.
        """
        query = f"""
            SELECT 
                t.TABLE_NAME as table_name,
                t.TABLE_SCHEMA as table_schema,
                t.TABLE_TYPE as table_type,
                CAST(ep.value AS NVARCHAR(MAX)) as table_description,
                SUM(p.rows) as row_count
            FROM {self.database}.INFORMATION_SCHEMA.TABLES t
            LEFT JOIN {self.database}.sys.tables st 
                ON t.TABLE_NAME = st.name
            LEFT JOIN {self.database}.sys.schemas s 
                ON st.schema_id = s.schema_id AND t.TABLE_SCHEMA = s.name
            LEFT JOIN {self.database}.sys.extended_properties ep 
                ON st.object_id = ep.major_id 
                AND ep.minor_id = 0 
                AND ep.class = 1
                AND ep.name = 'MS_Description'
            LEFT JOIN {self.database}.sys.partitions p 
                ON st.object_id = p.object_id 
                AND p.index_id IN (0, 1)
            WHERE t.TABLE_TYPE IN ('BASE TABLE', 'VIEW')
                AND t.TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
        """

        if self.schema:
            query += f" AND t.TABLE_SCHEMA = '{self.schema}'"

        query += " GROUP BY t.TABLE_NAME, t.TABLE_SCHEMA, t.TABLE_TYPE, ep.value"

        if table_names is not None and len(table_names) > 0:
            quoted_names = [f"'{t}'" for t in table_names]
            query += f" HAVING t.TABLE_NAME IN ({','.join(quoted_names)})"

        result = self.native_query(query)
        return result

    def meta_get_columns(self, table_names: list[str] | None = None) -> Response:
        """
        Retrieves column metadata for the specified tables (or all tables if no list is provided).

        Args:
            table_names (list): A list of table names for which to retrieve column metadata.

        Returns:
            Response: A response object containing the column metadata.
        """
        query = f"""
            SELECT 
                c.TABLE_NAME as table_name,
                c.COLUMN_NAME as column_name,
                c.DATA_TYPE as data_type,
                CAST(ep.value AS NVARCHAR(MAX)) as column_description,
                c.COLUMN_DEFAULT as column_default,
                CASE WHEN c.IS_NULLABLE = 'YES' THEN 1 ELSE 0 END as is_nullable
            FROM {self.database}.INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN {self.database}.sys.tables st 
                ON c.TABLE_NAME = st.name
            LEFT JOIN {self.database}.sys.schemas s 
                ON st.schema_id = s.schema_id AND c.TABLE_SCHEMA = s.name
            LEFT JOIN {self.database}.sys.columns sc 
                ON st.object_id = sc.object_id AND c.COLUMN_NAME = sc.name
            LEFT JOIN {self.database}.sys.extended_properties ep 
                ON st.object_id = ep.major_id 
                AND sc.column_id = ep.minor_id 
                AND ep.name = 'MS_Description'
            WHERE c.TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
        """

        if self.schema:
            query += f" AND c.TABLE_SCHEMA = '{self.schema}'"

        if table_names is not None and len(table_names) > 0:
            quoted_names = [f"'{t}'" for t in table_names]
            query += f" AND c.TABLE_NAME IN ({','.join(quoted_names)})"

        result = self.native_query(query)
        return result

    def meta_get_column_statistics(self, table_names: list[str] | None = None) -> Response:
        """
        Retrieves column statistics (e.g., null percentage, distinct value count, min/max values)
        for the specified tables or all tables if no list is provided.

        Note: Uses SQL Server's sys.dm_db_stats_properties and sys.dm_db_stats_histogram
        (similar to PostgreSQL's pg_stats). Statistics are only available for columns that
        have statistics objects created by SQL Server (typically indexed columns or columns
        used in queries after AUTO_CREATE_STATISTICS).

        Args:
            table_names (list): A list of table names for which to retrieve column statistics.

        Returns:
            Response: A response object containing the column statistics.
        """
        table_filter = ""
        if table_names is not None and len(table_names) > 0:
            quoted_names = [f"'{t}'" for t in table_names]
            table_filter = f" AND t.name IN ({','.join(quoted_names)})"

        schema_filter = ""
        if self.schema:
            schema_filter = f" AND s.name = '{self.schema}'"

        # Using OUTER APPLY to handle table-valued functions properly
        # This is equivalent to PostgreSQL's pg_stats view approach
        # Includes all statistics: auto-created, user-created, and index-based
        # dm_db_stats_histogram columns: range_high_key, range_rows, equal_rows,
        #                                 distinct_range_rows, average_range_rows
        query = f"""
            SELECT DISTINCT
                t.name AS TABLE_NAME,
                c.name AS COLUMN_NAME,
                CAST(NULL AS DECIMAL(10,2)) AS NULL_PERCENTAGE,
                CAST(h.distinct_count AS BIGINT) AS DISTINCT_VALUES_COUNT,
                NULL AS MOST_COMMON_VALUES,
                NULL AS MOST_COMMON_FREQUENCIES,
                CAST(h.min_value AS NVARCHAR(MAX)) AS MINIMUM_VALUE,
                CAST(h.max_value AS NVARCHAR(MAX)) AS MAXIMUM_VALUE
            FROM {self.database}.sys.tables t
            INNER JOIN {self.database}.sys.schemas s 
                ON t.schema_id = s.schema_id
            INNER JOIN {self.database}.sys.columns c 
                ON t.object_id = c.object_id
            LEFT JOIN {self.database}.sys.stats st
                ON st.object_id = t.object_id
            LEFT JOIN {self.database}.sys.stats_columns sc
                ON sc.object_id = st.object_id 
                AND sc.stats_id = st.stats_id
                AND sc.column_id = c.column_id
                AND sc.stats_column_id = 1  -- Only leading column in multi-column stats
            OUTER APPLY (
                SELECT 
                    MIN(CAST(range_high_key AS NVARCHAR(MAX))) AS min_value,
                    MAX(CAST(range_high_key AS NVARCHAR(MAX))) AS max_value,
                    SUM(CAST(distinct_range_rows AS BIGINT)) + COUNT(*) AS distinct_count
                FROM {self.database}.sys.dm_db_stats_histogram(st.object_id, st.stats_id)
                WHERE st.object_id IS NOT NULL
            ) h
            WHERE s.name NOT IN ('sys', 'INFORMATION_SCHEMA')
            {schema_filter}
            {table_filter}
            ORDER BY t.name, c.name
        """

        result = self.native_query(query)
        return result

    def meta_get_primary_keys(self, table_names: list[str] | None = None) -> Response:
        """
        Retrieves primary key information for the specified tables (or all tables if no list is provided).

        Args:
            table_names (list): A list of table names for which to retrieve primary key information.

        Returns:
            Response: A response object containing the primary key information.
        """
        query = f"""
            SELECT 
                tc.TABLE_NAME as table_name,
                kcu.COLUMN_NAME as column_name,
                kcu.ORDINAL_POSITION as ordinal_position,
                tc.CONSTRAINT_NAME as constraint_name
            FROM {self.database}.INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            INNER JOIN {self.database}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
                AND tc.TABLE_NAME = kcu.TABLE_NAME
            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
        """

        if self.schema:
            query += f" AND tc.TABLE_SCHEMA = '{self.schema}'"

        if table_names is not None and len(table_names) > 0:
            quoted_names = [f"'{t}'" for t in table_names]
            query += f" AND tc.TABLE_NAME IN ({','.join(quoted_names)})"

        query += " ORDER BY tc.TABLE_NAME, kcu.ORDINAL_POSITION"

        result = self.native_query(query)
        return result

    def meta_get_foreign_keys(self, table_names: list[str] | None = None) -> Response:
        """
        Retrieves foreign key information for the specified tables (or all tables if no list is provided).

        Args:
            table_names (list): A list of table names for which to retrieve foreign key information.

        Returns:
            Response: A response object containing the foreign key information.
        """
        query = f"""
            SELECT 
                OBJECT_NAME(fk.referenced_object_id) as parent_table_name,
                COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) as parent_column_name,
                OBJECT_NAME(fk.parent_object_id) as child_table_name,
                COL_NAME(fkc.parent_object_id, fkc.parent_column_id) as child_column_name,
                fk.name as constraint_name
            FROM {self.database}.sys.foreign_keys fk
            INNER JOIN {self.database}.sys.foreign_key_columns fkc 
                ON fk.object_id = fkc.constraint_object_id
            INNER JOIN {self.database}.sys.tables t 
                ON fk.parent_object_id = t.object_id
            INNER JOIN {self.database}.sys.schemas s 
                ON t.schema_id = s.schema_id
            WHERE s.name NOT IN ('sys', 'INFORMATION_SCHEMA')
        """

        if self.schema:
            query += f" AND s.name = '{self.schema}'"

        if table_names is not None and len(table_names) > 0:
            quoted_names = [f"'{t}'" for t in table_names]
            query += f" AND OBJECT_NAME(fk.parent_object_id) IN ({','.join(quoted_names)})"

        query += " ORDER BY child_table_name, constraint_name"

        result = self.native_query(query)
        return result
