"""Unit tests for PassthroughMixin."""

import unittest
from unittest.mock import MagicMock, patch

from mindsdb.integrations.libs.passthrough import (
    PassthroughMixin,
    REDACTED_SENTINEL,
)
from mindsdb.integrations.libs.passthrough_types import (
    HostNotAllowedError,
    PassthroughConfigError,
    PassthroughRequest,
    PassthroughValidationError,
)


class _FakeHandler(PassthroughMixin):
    """Minimal handler stub for exercising the mixin."""

    _bearer_token_arg = "api_key"
    _base_url_default = "https://api.example.com"
    _test_request = PassthroughRequest(method="GET", path="/me")

    def __init__(self, connection_data: dict):
        self.name = "fake_ds"
        self.connection_data = connection_data


def _mock_response(status_code=200, body=b'{"ok":true}', headers=None, content_type="application/json"):
    """Return a mock requests.Response exposing the bits the mixin uses."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {"Content-Type": content_type, **(headers or {})}
    resp.iter_content = MagicMock(return_value=iter([body]))
    resp.close = MagicMock()
    return resp


class PassthroughHappyPathTests(unittest.TestCase):
    def setUp(self):
        self.handler = _FakeHandler({"api_key": "secret-token-abcdef1234567890"})

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_injects_bearer_and_uses_default_base_url(self, mock_request):
        mock_request.return_value = _mock_response()
        resp = self.handler.api_passthrough(PassthroughRequest("GET", "/me"))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, {"ok": True})

        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], "GET")
        self.assertEqual(args[1], "https://api.example.com/me")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret-token-abcdef1234567890")
        self.assertEqual(kwargs["headers"]["X-Minds-Passthrough"], "1")

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_user_base_url_overrides_default(self, mock_request):
        self.handler.connection_data["base_url"] = "https://api.eu.example.com"
        mock_request.return_value = _mock_response()
        self.handler.api_passthrough(PassthroughRequest("GET", "/me"))
        self.assertEqual(mock_request.call_args[0][1], "https://api.eu.example.com/me")

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_query_params_forwarded(self, mock_request):
        mock_request.return_value = _mock_response()
        self.handler.api_passthrough(PassthroughRequest("GET", "/x", query={"a": "1"}))
        self.assertEqual(mock_request.call_args.kwargs["params"], {"a": "1"})

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_json_body_forwarded(self, mock_request):
        mock_request.return_value = _mock_response()
        self.handler.api_passthrough(PassthroughRequest("POST", "/x", body={"name": "foo"}))
        self.assertEqual(mock_request.call_args.kwargs["json"], {"name": "foo"})

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_default_headers_merged(self, mock_request):
        self.handler.connection_data["default_headers"] = {"Accept": "application/json"}
        mock_request.return_value = _mock_response()
        self.handler.api_passthrough(PassthroughRequest("GET", "/x"))
        self.assertEqual(mock_request.call_args.kwargs["headers"]["Accept"], "application/json")


class PassthroughHeaderFilteringTests(unittest.TestCase):
    def setUp(self):
        self.handler = _FakeHandler({"api_key": "secret-token-abcdef1234567890"})

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_caller_cannot_override_authorization(self, mock_request):
        mock_request.return_value = _mock_response()
        self.handler.api_passthrough(
            PassthroughRequest("GET", "/x", headers={"Authorization": "Bearer hijack", "Cookie": "s=1"})
        )
        outgoing = mock_request.call_args.kwargs["headers"]
        self.assertEqual(outgoing["Authorization"], "Bearer secret-token-abcdef1234567890")
        self.assertNotIn("Cookie", outgoing)

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_proxy_headers_stripped(self, mock_request):
        mock_request.return_value = _mock_response()
        self.handler.api_passthrough(PassthroughRequest("GET", "/x", headers={"Proxy-Authorization": "hijack"}))
        outgoing = mock_request.call_args.kwargs["headers"]
        self.assertNotIn("Proxy-Authorization", outgoing)

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_hop_by_hop_response_headers_stripped(self, mock_request):
        mock_request.return_value = _mock_response(
            headers={"Connection": "close", "X-Safe": "1", "Transfer-Encoding": "chunked"}
        )
        resp = self.handler.api_passthrough(PassthroughRequest("GET", "/x"))
        self.assertNotIn("Connection", resp.headers)
        self.assertNotIn("Transfer-Encoding", resp.headers)
        self.assertEqual(resp.headers.get("X-Safe"), "1")


class PassthroughHostAllowlistTests(unittest.TestCase):
    def test_rejects_host_outside_allowlist(self):
        handler = _FakeHandler(
            {
                "api_key": "t",
                "base_url": "https://api.example.com",
                "allowed_hosts": ["api.example.com"],
            }
        )
        # Direct host check using a bad URL
        with self.assertRaises(HostNotAllowedError):
            handler._check_host_allowed("evil.com")

    def test_wildcard_allows_any_host(self):
        handler = _FakeHandler(
            {
                "api_key": "t",
                "base_url": "https://api.example.com",
                "allowed_hosts": ["*"],
            }
        )
        handler._check_host_allowed("evil.com")  # must not raise

    def test_private_ip_rejected_by_default(self):
        handler = _FakeHandler({"api_key": "t", "base_url": "http://10.0.0.1"})
        with self.assertRaises(HostNotAllowedError):
            handler._check_host_allowed("10.0.0.1")

    def test_private_ip_allowed_when_explicitly_listed(self):
        handler = _FakeHandler(
            {
                "api_key": "t",
                "base_url": "http://10.0.0.1",
                "allowed_hosts": ["10.0.0.1"],
            }
        )
        # Explicitly allowlisted private IP should still be rejected — the
        # mixin treats explicit private-IP allowlisting as a foot-gun that
        # requires the "*" escape hatch. Document this behavior.
        with self.assertRaises(HostNotAllowedError):
            handler._check_host_allowed("10.0.0.1")

    def test_loopback_rejected_with_wildcard_when_asterisk_not_used(self):
        handler = _FakeHandler(
            {
                "api_key": "t",
                "base_url": "http://127.0.0.1",
                "allowed_hosts": ["127.0.0.1"],
            }
        )
        with self.assertRaises(HostNotAllowedError):
            handler._check_host_allowed("127.0.0.1")


class PassthroughValidationTests(unittest.TestCase):
    def test_missing_bearer_raises(self):
        handler = _FakeHandler({})  # no api_key
        with self.assertRaises(PassthroughConfigError):
            handler.api_passthrough(PassthroughRequest("GET", "/me"))

    def test_missing_base_url_raises(self):
        class NoDefault(_FakeHandler):
            _base_url_default = None

        handler = NoDefault({"api_key": "t"})
        with self.assertRaises(PassthroughConfigError):
            handler.api_passthrough(PassthroughRequest("GET", "/me"))

    def test_path_must_start_with_slash(self):
        handler = _FakeHandler({"api_key": "t"})
        with self.assertRaises(PassthroughValidationError):
            handler.api_passthrough(PassthroughRequest("GET", "me"))

    def test_method_allowlist(self):
        handler = _FakeHandler({"api_key": "t"})
        with self.assertRaises(PassthroughValidationError):
            handler.api_passthrough(PassthroughRequest("TRACE", "/me"))


class PassthroughSecretScrubTests(unittest.TestCase):
    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_token_scrubbed_from_json_body(self, mock_request):
        token = "secret-token-abcdef1234567890"
        # Non-UTF-8 byte (0xFF) positioned adjacent to the token. Spec §7.6
        # mandates byte-level scrubbing: if the scrub ran after a
        # errors="replace" decode, U+FFFD insertions would risk fragmenting
        # a token mid-match. Byte-level scrub avoids that entirely.
        body = b'{"error":"Invalid token ' + token.encode("utf-8") + b' \xff trailing"}'
        handler = _FakeHandler({"api_key": token})
        # Use plain-text content-type so the non-UTF-8 body survives without
        # a json.loads detour; the scrub is still invoked.
        mock_request.return_value = _mock_response(body=body, content_type="text/plain")

        resp = handler.api_passthrough(PassthroughRequest("GET", "/x"))
        # Token must not survive anywhere in the body.
        self.assertNotIn(token, str(resp.body))
        self.assertIn(REDACTED_SENTINEL, str(resp.body))

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_token_scrubbed_from_headers(self, mock_request):
        token = "secret-token-abcdef1234567890"
        handler = _FakeHandler({"api_key": token})
        mock_request.return_value = _mock_response(
            headers={"X-Debug-Auth": f"Bearer {token}"},
        )
        resp = handler.api_passthrough(PassthroughRequest("GET", "/x"))
        self.assertIn(REDACTED_SENTINEL, resp.headers["X-Debug-Auth"])
        self.assertNotIn(token, resp.headers["X-Debug-Auth"])

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_long_default_header_values_scrubbed(self, mock_request):
        token = "secret-token-abcdef1234567890"
        long_secret = "x" * 32
        handler = _FakeHandler(
            {
                "api_key": token,
                "default_headers": {"X-Api-Secondary": long_secret},
            }
        )
        mock_request.return_value = _mock_response(body=('{"echoed":"' + long_secret + '"}').encode("utf-8"))
        resp = handler.api_passthrough(PassthroughRequest("GET", "/x"))
        self.assertEqual(resp.body["echoed"], REDACTED_SENTINEL)

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_token_scrubbed_in_nested_json_without_corrupting_structure(self, mock_request):
        token = "secret-token-abcdef1234567890"
        handler = _FakeHandler({"api_key": token})
        body = ('{"data": {"nested": {"token": "' + token + '"}}}').encode("utf-8")
        mock_request.return_value = _mock_response(body=body)

        resp = handler.api_passthrough(PassthroughRequest("GET", "/x"))

        # Structure preserved: dict-of-dict-of-dict with the expected keys.
        self.assertIsInstance(resp.body, dict)
        self.assertIsInstance(resp.body["data"], dict)
        self.assertIsInstance(resp.body["data"]["nested"], dict)
        self.assertEqual(set(resp.body.keys()), {"data"})
        self.assertEqual(set(resp.body["data"].keys()), {"nested"})
        self.assertEqual(set(resp.body["data"]["nested"].keys()), {"token"})
        # Value redacted at the leaf; token does not survive anywhere.
        self.assertEqual(resp.body["data"]["nested"]["token"], REDACTED_SENTINEL)
        self.assertNotIn(token, str(resp.body))


class PassthroughTestEndpointTests(unittest.TestCase):
    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_returns_ok_on_200(self, mock_request):
        handler = _FakeHandler({"api_key": "t"})
        mock_request.return_value = _mock_response(status_code=200)
        result = handler.test_passthrough()
        self.assertTrue(result["ok"])
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["host"], "api.example.com")

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_returns_auth_failed_on_401(self, mock_request):
        handler = _FakeHandler({"api_key": "t"})
        mock_request.return_value = _mock_response(status_code=401)
        result = handler.test_passthrough()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "auth_failed")

    def test_returns_not_implemented_when_no_test_request(self):
        class NoTest(_FakeHandler):
            _test_request = None

        handler = NoTest({"api_key": "t"})
        result = handler.test_passthrough()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "not_implemented")


class PassthroughAllowedMethodsTests(unittest.TestCase):
    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_rejects_method_not_in_allowed_methods(self, mock_request):
        handler = _FakeHandler(
            {
                "api_key": "t",
                "allowed_methods": ["GET"],
            }
        )
        mock_request.return_value = _mock_response()

        with self.assertRaises(PassthroughValidationError) as cm:
            handler.api_passthrough(PassthroughRequest("POST", "/x"))

        self.assertEqual(cm.exception.error_code, "method_not_allowed")
        self.assertEqual(cm.exception.http_status, 405)
        mock_request.assert_not_called()

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_all_methods_allowed_when_config_absent(self, mock_request):
        handler = _FakeHandler({"api_key": "t"})
        mock_request.return_value = _mock_response()

        for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            mock_request.reset_mock()
            mock_request.return_value = _mock_response()
            handler.api_passthrough(PassthroughRequest(method, "/x"))
            self.assertEqual(mock_request.call_args[0][0], method)

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_string_allowed_methods_raises_config_error(self, mock_request):
        handler = _FakeHandler({"api_key": "t", "allowed_methods": "GET"})

        with self.assertRaises(PassthroughConfigError):
            handler.api_passthrough(PassthroughRequest("GET", "/x"))

        mock_request.assert_not_called()

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_lowercase_allowed_methods_normalized(self, mock_request):
        handler = _FakeHandler({"api_key": "t", "allowed_methods": ["get"]})
        mock_request.return_value = _mock_response()

        # GET passes after uppercase normalization.
        handler.api_passthrough(PassthroughRequest("GET", "/x"))
        self.assertEqual(mock_request.call_args[0][0], "GET")

        mock_request.reset_mock()
        # POST is rejected with method_not_allowed.
        with self.assertRaises(PassthroughValidationError) as cm:
            handler.api_passthrough(PassthroughRequest("POST", "/x"))
        self.assertEqual(cm.exception.error_code, "method_not_allowed")
        self.assertEqual(cm.exception.http_status, 405)
        mock_request.assert_not_called()

    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_unknown_verb_in_allowed_methods_raises_config_error(self, mock_request):
        handler = _FakeHandler({"api_key": "t", "allowed_methods": ["GET", "TRACE"]})

        with self.assertRaises(PassthroughConfigError) as cm:
            handler.api_passthrough(PassthroughRequest("GET", "/x"))
        self.assertIn("TRACE", str(cm.exception))
        mock_request.assert_not_called()


class PassthroughAuthHeaderOverrideTests(unittest.TestCase):
    @patch("mindsdb.integrations.libs.passthrough.requests.request")
    def test_custom_auth_header_name_and_format(self, mock_request):
        class ShopifyLikeHandler(_FakeHandler):
            _auth_header_name = "X-Shopify-Access-Token"
            _auth_header_format = "{token}"

        handler = ShopifyLikeHandler({"api_key": "shpat_abc123"})
        mock_request.return_value = _mock_response()

        handler.api_passthrough(PassthroughRequest("GET", "/x"))

        outgoing = mock_request.call_args.kwargs["headers"]
        # Custom header present, with raw token (no "Bearer " prefix).
        self.assertEqual(outgoing["X-Shopify-Access-Token"], "shpat_abc123")
        # Default Authorization header must NOT be added when the handler
        # overrides the auth header name.
        self.assertNotIn("Authorization", outgoing)


class PassthroughProtocolTests(unittest.TestCase):
    def test_non_mixin_class_satisfies_protocol(self):
        from mindsdb.integrations.libs.passthrough import PassthroughProtocol
        from mindsdb.integrations.libs.passthrough_types import PassthroughResponse

        class ManualHandler:
            def api_passthrough(self, req: PassthroughRequest) -> PassthroughResponse:
                return PassthroughResponse(status_code=200, headers={}, body=None, content_type=None)

            def test_passthrough(self) -> dict:
                return {"ok": True}

        self.assertIsInstance(ManualHandler(), PassthroughProtocol)

    def test_class_missing_methods_fails_protocol(self):
        from mindsdb.integrations.libs.passthrough import PassthroughProtocol

        class Incomplete:
            def api_passthrough(self, req): ...

            # missing test_passthrough

        self.assertNotIsInstance(Incomplete(), PassthroughProtocol)


if __name__ == "__main__":
    unittest.main()
