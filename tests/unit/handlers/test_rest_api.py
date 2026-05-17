"""Unit tests for the generic REST API passthrough handler."""

from unittest.mock import patch, MagicMock

from mindsdb.integrations.handlers.rest_api_handler.rest_api_handler import RestApiHandler
from mindsdb.integrations.libs.passthrough import PassthroughProtocol
from mindsdb.integrations.libs.passthrough_types import PassthroughRequest, PassthroughResponse
from mindsdb.integrations.libs.response import (
    HandlerStatusResponse as StatusResponse,
)


VALID_DATA = {
    "base_url": "https://api.example.com",
    "bearer_token": "test-token-123",
}


def _make_handler(connection_data=None):
    if connection_data is None:
        connection_data = dict(VALID_DATA)
    return RestApiHandler("test_rest", connection_data=connection_data)


class TestRestApiHandlerInit:
    def test_satisfies_passthrough_protocol(self):
        assert issubclass(RestApiHandler, PassthroughProtocol)

    def test_stores_connection_data(self):
        data = {"base_url": "https://x.com", "bearer_token": "tok"}
        handler = _make_handler(data)
        assert handler.connection_data == data

    def test_default_test_request_path(self):
        handler = _make_handler()
        assert handler._test_request.method == "GET"
        assert handler._test_request.path == "/"

    def test_custom_test_path(self):
        handler = _make_handler(
            {
                "base_url": "https://api.example.com",
                "bearer_token": "tok",
                "test_path": "/health",
            }
        )
        assert handler._test_request.path == "/health"

    def test_custom_test_path_without_slash(self):
        handler = _make_handler(
            {
                "base_url": "https://api.example.com",
                "bearer_token": "tok",
                "test_path": "status",
            }
        )
        assert handler._test_request.path == "/status"


class TestCheckConnection:
    def test_success(self):
        handler = _make_handler()
        response = handler.check_connection()
        assert isinstance(response, StatusResponse)
        assert response.success is True
        assert not response.error_message

    def test_missing_base_url(self):
        handler = _make_handler({"bearer_token": "tok"})
        response = handler.check_connection()
        assert response.success is False
        assert "base_url" in response.error_message

    def test_missing_bearer_token(self):
        handler = _make_handler({"base_url": "https://api.example.com"})
        response = handler.check_connection()
        assert response.success is False
        assert "bearer_token" in response.error_message

    def test_empty_connection_data(self):
        handler = _make_handler({})
        response = handler.check_connection()
        assert response.success is False


class TestPassthroughIntegration:
    """Test that the mixin methods work correctly on RestApiHandler."""

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_api_passthrough_injects_bearer(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.iter_content.return_value = [b'{"ok": true}']
        mock_resp.close = MagicMock()
        mock_request.return_value = mock_resp

        handler = _make_handler()
        result = handler.api_passthrough(PassthroughRequest(method="GET", path="/v1/users"))

        assert isinstance(result, PassthroughResponse)
        assert result.status_code == 200
        headers = mock_request.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer test-token-123"

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_api_passthrough_uses_base_url(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.iter_content.return_value = [b""]
        mock_resp.close = MagicMock()
        mock_request.return_value = mock_resp

        handler = _make_handler()
        handler.api_passthrough(PassthroughRequest(method="GET", path="/foo"))

        called_url = mock_request.call_args.args[1]
        assert called_url == "https://api.example.com/foo"

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_api_passthrough_includes_default_headers(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.iter_content.return_value = [b""]
        mock_resp.close = MagicMock()
        mock_request.return_value = mock_resp

        handler = _make_handler(
            {
                "base_url": "https://api.example.com",
                "bearer_token": "tok",
                "default_headers": {"Accept": "application/json", "X-Team": "data"},
            }
        )
        handler.api_passthrough(PassthroughRequest(method="GET", path="/"))

        headers = mock_request.call_args.kwargs["headers"]
        assert headers["Accept"] == "application/json"
        assert headers["X-Team"] == "data"

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_test_passthrough_success(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.iter_content.return_value = [b'{"ok": true}']
        mock_resp.close = MagicMock()
        mock_request.return_value = mock_resp

        handler = _make_handler()
        result = handler.test_passthrough()

        assert isinstance(result, dict)
        assert result["ok"] is True
        assert result["status_code"] == 200

    def test_test_passthrough_with_no_network(self):
        """test_passthrough catches connection errors gracefully."""
        handler = _make_handler()
        result = handler.test_passthrough()
        assert isinstance(result, dict)
        assert result["ok"] is False
        assert result["error_code"] in ("network", "unknown")
