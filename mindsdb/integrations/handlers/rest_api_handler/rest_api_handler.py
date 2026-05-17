from typing import Any

from mindsdb.integrations.libs.api_handler import APIHandler
from mindsdb.integrations.libs.passthrough import PassthroughMixin
from mindsdb.integrations.libs.passthrough_types import PassthroughRequest
from mindsdb.integrations.libs.response import (
    HandlerStatusResponse as StatusResponse,
    HandlerResponse as Response,
    RESPONSE_TYPE,
)
from mindsdb.utilities import log

logger = log.getLogger(__name__)


class RestApiHandler(APIHandler, PassthroughMixin):
    """Generic REST API handler — passthrough only, no SQL tables.

    This is the "bring your own URL" escape hatch for any bearer-token API
    that mindsdb doesn't have a named handler for. Users supply a base_url
    and a bearer_token and get full passthrough access.
    """

    name = "rest_api"

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name)
        self.connection_data = kwargs.get("connection_data") or {}
        self.kwargs = kwargs
        self.is_connected = False

        # PassthroughMixin reads these instance attributes at runtime.
        self._bearer_token_arg = "bearer_token"
        self._base_url_default = None  # user must supply base_url

        # Build the test request from connection_data. Default to GET /
        # unless the user provided a custom test_path.
        test_path = self.connection_data.get("test_path", "/")
        if not test_path.startswith("/"):
            test_path = f"/{test_path}"
        self._test_request = PassthroughRequest(method="GET", path=test_path)

    def connect(self) -> None:
        """No persistent connection needed — passthrough is stateless.

        Validation happens in check_connection(), which we
        call separately during CREATE DATABASE.
        """
        self.is_connected = True

    def check_connection(self) -> StatusResponse:
        """Validate that base_url and bearer_token are present."""
        response = StatusResponse(False)
        try:
            base_url = self._build_base_url()
            if not base_url:
                response.error_message = "base_url is required"
                return response
            token = self.connection_data.get(self._bearer_token_arg)
            if not token:
                response.error_message = "bearer_token is required"
                return response
            response.success = True
            self.is_connected = True
        except Exception as e:
            response.error_message = str(e)
        return response

    def native_query(self, query: str) -> Response:
        """Not supported — use passthrough instead."""
        return Response(
            RESPONSE_TYPE.ERROR,
            error_message="rest_api handler is passthrough-only. Use the /passthrough endpoint.",
        )

    def get_tables(self) -> Response:
        """No SQL tables — passthrough only."""
        import pandas as pd

        return Response(RESPONSE_TYPE.TABLE, data_frame=pd.DataFrame())

    def get_columns(self, table_name: str) -> Response:
        """No SQL tables — passthrough only."""
        return Response(
            RESPONSE_TYPE.ERROR,
            error_message="rest_api handler is passthrough-only. No tables available.",
        )
