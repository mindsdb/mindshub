import time
from enum import Enum
from http import HTTPStatus
from collections import defaultdict

from flask import request, Response
from flask_restx import Resource

from mindsdb_sql_parser import parse_sql
from mindsdb_sql_parser import ast

import mindsdb.utilities.hooks as hooks
import mindsdb.utilities.profiler as profiler
from mindsdb.api.http.utils import http_error
from mindsdb.api.http.namespaces.configs.sql import ns_conf
from mindsdb.api.mysql.mysql_proxy.classes.fake_mysql_proxy import FakeMysqlProxy
from mindsdb.api.executor.data_types.sql_answer import SQLAnswer
from mindsdb.api.executor.data_types.response_type import RESPONSE_TYPE as SQL_RESPONSE_TYPE
from mindsdb.api.executor.sql_query.result_set import ResultSet
from mindsdb.api.executor.exceptions import ExecutorException, UnknownError
from mindsdb.integrations.utilities.query_traversal import query_traversal
from mindsdb.metrics.metrics import api_endpoint_metrics
from mindsdb.utilities import log
from mindsdb.utilities.config import Config
from mindsdb.utilities.context import context as ctx
from mindsdb.utilities.exception import QueryError
from mindsdb.utilities.functions import mark_process
from mindsdb.interfaces.agents.chart_agent import ChartAgent

logger = log.getLogger(__name__)


class ReponseFormat(Enum):
    DEFAULT = None
    SSE = "sse"
    JSONLINES = "jsonlines"


@ns_conf.route("/query")
@ns_conf.param("query", "Execute query")
class Query(Resource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @ns_conf.doc("query")
    @api_endpoint_metrics("POST", "/sql/query")
    @mark_process(name="http_query")
    def post(self):
        start_time = time.time()
        query = request.json["query"]
        context = request.json.get("context", {})

        if "params" in request.json:
            ctx.params = request.json["params"]

        try:
            response_format = ReponseFormat(request.json.get("response_format", None))
        except ValueError:
            return http_error(HTTPStatus.BAD_REQUEST, "Invalid stream format", "Please provide a valid stream format.")

        if isinstance(query, str) is False or isinstance(context, dict) is False:
            return http_error(HTTPStatus.BAD_REQUEST, "Wrong arguments", 'Please provide "query" with the request.')
        logger.debug(f"Incoming query: {query}")

        if context.get("profiling") is True:
            profiler.enable()

        error_type = None
        error_traceback = None

        profiler.set_meta(query=query, api="http", environment=Config().get("environment"))
        with profiler.Context("http_query_processing"):
            mysql_proxy = FakeMysqlProxy()
            mysql_proxy.set_context(context)

            if context.get("native_query"):
                db = context.get("db")
                if not db:
                    return {
                        "type": "error",
                        "error_code": 0,
                        "error_message": "native_query requires 'db' in context",
                    }, 400

                logger.debug(f"Running query natively for database {db}")

                try:
                    handler = mysql_proxy.session.integration_controller.get_data_handler(db)
                    raw_result = handler.native_query(query)
                except Exception as e:
                    error_type = "unexpected"
                    result = SQLAnswer(
                        resp_type=SQL_RESPONSE_TYPE.ERROR,
                        error_code=0,
                        error_message=str(e),
                    )
                else:
                    if raw_result.type == SQL_RESPONSE_TYPE.ERROR:
                        # raw_result will be ErrorResponse.
                        error_type = "expected"
                        result = SQLAnswer(
                            resp_type=SQL_RESPONSE_TYPE.ERROR,
                            error_code=0,
                            error_message=raw_result.error_message,
                        )
                    elif raw_result.type == SQL_RESPONSE_TYPE.OK:
                        result = SQLAnswer(
                            resp_type=SQL_RESPONSE_TYPE.OK,
                            error_code=0,
                            error_message=None,
                        )
                    else:
                        # raw_result will be TableResponse.
                        result_set = ResultSet.from_table_response(raw_result)
                        result = SQLAnswer(
                            resp_type=SQL_RESPONSE_TYPE.TABLE,
                            result_set=result_set,
                        )

            else:
                try:
                    result: SQLAnswer = mysql_proxy.process_query(query)
                except ExecutorException as e:
                    # classified error
                    error_type = "expected"
                    result = SQLAnswer(
                        resp_type=SQL_RESPONSE_TYPE.ERROR,
                        error_code=0,
                        error_message=str(e),
                    )
                    logger.warning(f"Error query processing: {e}")
                except QueryError as e:
                    error_type = "expected" if e.is_expected else "unexpected"
                    result = SQLAnswer(
                        resp_type=SQL_RESPONSE_TYPE.ERROR,
                        error_code=0,
                        error_message=str(e),
                    )
                    if e.is_expected:
                        logger.warning(f"Query failed due to expected reason: {e}")
                    else:
                        logger.exception("Error query processing:")
                except (UnknownError, Exception) as e:
                    error_type = "unexpected"
                    result = SQLAnswer(
                        resp_type=SQL_RESPONSE_TYPE.ERROR,
                        error_code=0,
                        error_message=str(e),
                    )
                    logger.exception("Error query processing:")

            context = mysql_proxy.get_context()

            if response_format == ReponseFormat.JSONLINES:
                query_response = result.stream_http_response_jsonlines(context=context)
                query_response = Response(query_response, mimetype="application/jsonlines")
            elif response_format == ReponseFormat.SSE:
                query_response = result.stream_http_response_sse(context=context)
                query_response = Response(query_response, mimetype="text/event-stream")
            else:
                query_response = result.dump_http_response(context=context), 200

        hooks.after_api_query(
            company_id=ctx.company_id,
            user_id=ctx.user_id,
            api="http",
            command=None,
            payload=query,
            error_type=error_type,
            error_code=result.error_code,
            error_text=result.error_message,
            traceback=error_traceback,
        )

        end_time = time.time()
        log_msg = f"SQL processed in {(end_time - start_time):.2f}s ({end_time:.2f}-{start_time:.2f}), result is {result.type}, "
        if result.type is SQL_RESPONSE_TYPE.TABLE and response_format is ReponseFormat.DEFAULT:
            log_msg += f" one-piece result ({len(query_response[0]['data'])} rows), "
        elif result.type is SQL_RESPONSE_TYPE.TABLE:
            log_msg += f" {response_format} result, "
        elif result.type is SQL_RESPONSE_TYPE.ERROR:
            log_msg += f" ({result.error_message}), "
        log_msg += f"used handlers: {ctx.used_handlers}"
        logger.debug(log_msg)

        return query_response


@ns_conf.route("/charter")
@ns_conf.param("charter", "Generate Chart.js configuration from SQL query")
class Charter(Resource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _extract_error_message(self, error: Exception, context: str) -> str:
        """
        Extract a user-friendly error message from an exception.

        Args:
            error: The exception to extract message from
            context: Context string for the error (e.g., "chart generation", "query execution")

        Returns:
            str: User-friendly error message
        """
        error_str = str(error)

        # Handle Pydantic validation errors
        if "validation" in error_str.lower() or "pydantic" in error_str.lower():
            # Try to extract validation details
            if hasattr(error, "errors"):
                # Pydantic validation errors
                try:
                    errors = error.errors()
                    if errors:
                        error_details = []
                        for err in errors[:3]:  # Limit to first 3 errors
                            loc = " -> ".join(str(x) for x in err.get("loc", []))
                            msg = err.get("msg", "Validation error")
                            error_details.append(f"{loc}: {msg}")
                        if error_details:
                            return f"Chart configuration validation failed: {'; '.join(error_details)}"
                except Exception:
                    pass

            # Check for retry errors from Pydantic AI
            if "retries" in error_str.lower() or "retry" in error_str.lower():
                return "Failed to generate valid chart configuration after multiple attempts. The AI model may have generated an invalid format. Please try again or check your query."

        # Handle QueryError with db_error_msg
        if isinstance(error, QueryError):
            if hasattr(error, "db_error_msg") and error.db_error_msg:
                msg = error.db_error_msg
                if hasattr(error, "failed_query") and error.failed_query:
                    msg += f"\n\nFailed query: {error.failed_query[:200]}..."
                return msg
            if hasattr(error, "failed_query") and error.failed_query:
                return f"Query execution failed: {error_str}\n\nFailed query: {error.failed_query[:200]}..."

        # Handle ExecutorException
        if isinstance(error, ExecutorException):
            return f"Query execution error: {error_str}"

        # For other exceptions, try to extract the main message
        # Remove traceback-like content
        lines = error_str.split("\n")
        # Take the first line which usually contains the main error message
        main_message = lines[0] if lines else error_str

        # If it's a generic exception, add context
        if len(main_message) < 50 and context:
            return f"Error during {context}: {main_message}"

        return main_message

    @ns_conf.doc("charter")
    @api_endpoint_metrics("POST", "/sql/charter")
    @mark_process(name="http_charter")
    def post(self):
        start_time = time.time()

        # Validate request
        if not request.json:
            return http_error(HTTPStatus.BAD_REQUEST, "Wrong arguments", 'Please provide JSON body with "query".')

        query = request.json.get("query")
        prompt = request.json.get("prompt")
        context = request.json.get("context", {})
        if "params" in request.json:
            ctx.params = request.json["params"]

        if not isinstance(query, str):
            return http_error(HTTPStatus.BAD_REQUEST, "Wrong arguments", 'Please provide "query" as a string.')

        if not isinstance(context, dict):
            return http_error(HTTPStatus.BAD_REQUEST, "Wrong arguments", 'Please provide "context" as a dictionary.')

        logger.debug(f"Incoming charter request: query={query[:100]}..., prompt={prompt}")

        mysql_proxy = FakeMysqlProxy()
        mysql_proxy.set_context(context)
        try:
            result: SQLAnswer = mysql_proxy.process_query(query)
        except Exception as e:
            error_msg = self._extract_error_message(e, "query execution")
            logger.warning(f"Query error: {error_msg}")
            return http_error(HTTPStatus.BAD_REQUEST, "Query error", error_msg)

        df = result.result_set.to_df()

        try:
            chart_agent = ChartAgent(executor=mysql_proxy)
            response = chart_agent.generate_chart_with_data(query, df, prompt)

            end_time = time.time()
            logger.debug(f"Charter processed in {(end_time - start_time):.2f}s")

            return response, 200

        except Exception as e:
            error_msg = self._extract_error_message(e, "chart generation or execution")
            logger.warning(f"Error in chart generation or execution: {error_msg}")
            return http_error(HTTPStatus.BAD_REQUEST, "Chart generation failed", error_msg)


@ns_conf.route("/query/utils/parametrize_constants")
class ParametrizeConstants(Resource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @api_endpoint_metrics("POST", "/query/utils/parametrize_constants")
    def post(self):
        sql_query = request.json["query"]

        # find constants in the query and replace them with parameters
        query = parse_sql(sql_query)

        parameters = []
        param_counts = {}
        databases = defaultdict(set)

        def to_parameter(param_name, value):
            if param_name is None:
                param_name = default_param_name

            num = param_counts.get(param_name, 1)
            param_counts[param_name] = num + 1

            if num > 1:
                param_name = param_name + str(num)

            parameters.append({"name": param_name, "value": value, "type": type(value).__name__})
            return ast.Parameter(param_name)

        def find_constants_f(node, is_table, is_target, callstack, **kwargs):
            if is_table and isinstance(node, ast.Identifier):
                if len(node.parts) > 1:
                    databases[node.parts[0]].add(".".join(node.parts[1:]))

            if not isinstance(node, ast.Constant):
                return

            # it is a target
            if is_target and node.alias is not None:
                return to_parameter(node.alias.parts[-1], node.value)

            param_name = None

            for item in callstack:
                # try to find the name
                if isinstance(item, (ast.BinaryOperation, ast.BetweenOperation)) and item.op.lower() not in (
                    "and",
                    "or",
                ):
                    # it is probably a condition
                    for arg in item.args:
                        if isinstance(arg, ast.Identifier):
                            param_name = arg.parts[-1]
                            break
                    if param_name is not None:
                        break

                if item.alias is not None:
                    # it is probably a query target
                    param_name = item.alias.parts[-1]
                    break

            return to_parameter(param_name, node.value)

        if isinstance(query, ast.Update):
            for name, value in dict(query.update_columns).items():
                if isinstance(value, ast.Constant):
                    query.update_columns[name] = to_parameter(name, value.value)
                else:
                    default_param_name = name
                    query_traversal(value, find_constants_f)

        elif isinstance(query, ast.Insert):
            # iterate over node.values and do some processing
            if query.values:
                values = []
                for row in query.values:
                    row2 = []
                    for i, val in enumerate(row):
                        if isinstance(val, ast.Constant):
                            param_name = None
                            if query.columns and i < len(query.columns):
                                param_name = query.columns[i].name
                            elif query.table:
                                param_name = query.table.parts[-1]
                            val = to_parameter(param_name, val.value)
                        row2.append(val)
                    values.append(row2)
                query.values = values

        default_param_name = "param"
        query_traversal(query, find_constants_f)

        # to lists:
        databases = {k: list(v) for k, v in databases.items()}
        response = {"query": str(query), "parameters": parameters, "databases": databases}
        return response, 200


@ns_conf.route("/list_databases")
@ns_conf.param("list_databases", "lists databases of mindsdb")
class ListDatabases(Resource):
    @ns_conf.doc("list_databases")
    @api_endpoint_metrics("GET", "/sql/list_databases")
    def get(self):
        listing_query = "SHOW DATABASES"
        mysql_proxy = FakeMysqlProxy()
        try:
            result: SQLAnswer = mysql_proxy.process_query(listing_query)

            # iterate over result.data and perform a query on each item to get the name of the tables
            if result.type == SQL_RESPONSE_TYPE.ERROR:
                listing_query_response = {
                    "type": "error",
                    "error_code": result.error_code,
                    "error_message": result.error_message,
                }
            elif result.type == SQL_RESPONSE_TYPE.OK:
                listing_query_response = {"type": "ok"}
            elif result.type == SQL_RESPONSE_TYPE.TABLE:
                listing_query_response = {
                    "data": [
                        {
                            "name": db_row[0],
                            "tables": [
                                table_row[0]
                                for table_row in mysql_proxy.process_query(
                                    "SHOW TABLES FROM `{}`".format(db_row[0])
                                ).result_set.to_lists()
                            ],
                        }
                        for db_row in result.result_set.to_lists()
                    ]
                }
        except Exception as e:
            logger.exception("Error while retrieving list of databases")
            listing_query_response = {
                "type": "error",
                "error_code": 0,
                "error_message": str(e),
            }

        return listing_query_response, 200
