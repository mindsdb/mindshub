"""HTTP-layer tests for the /api/integrations/<name>/passthrough routes.

Exercises the Flask blueprint in isolation: the session's integration
controller is mocked to return handlers that satisfy
PassthroughProtocol, so these tests do not touch real handlers and do
not make network calls.
"""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

from mindsdb.integrations.libs.passthrough import PassthroughMixin
from mindsdb.integrations.libs.passthrough_types import PassthroughResponse


class _StubPassthroughHandler(PassthroughMixin):
    """Handler double: the HTTP layer checks the PassthroughProtocol, then
    calls `api_passthrough`. We bypass all mixin internals by overriding
    `api_passthrough` directly so the endpoint test does not depend on
    connection_data, base_url resolution, or the requests library."""

    def __init__(self, response: PassthroughResponse):
        self._response = response
        self.calls: list = []

    def api_passthrough(self, req):  # type: ignore[override]
        self.calls.append(req)
        return self._response

    def test_passthrough(self):
        return {"ok": True, "status_code": self._response.status_code}


def _patch_handler(handler):
    """Patch FakeMysqlProxy so the endpoint resolves `name` to `handler`."""
    proxy = MagicMock()
    proxy.session.integration_controller.get_data_handler.return_value = handler
    return patch(
        "mindsdb.api.http.namespaces.integrations.FakeMysqlProxy",
        return_value=proxy,
    )


def test_passthrough_happy_path_returns_200_and_serialized_body(client):
    handler = _StubPassthroughHandler(
        PassthroughResponse(
            status_code=200,
            headers={"X-Safe": "1"},
            body={"hello": "world"},
            content_type="application/json",
        )
    )

    with _patch_handler(handler):
        response = client.post(
            "/api/integrations/any_ds/passthrough",
            json={"method": "GET", "path": "/me"},
        )

    assert response.status_code == HTTPStatus.OK
    payload = response.get_json()
    assert payload == {
        "status_code": 200,
        "headers": {"X-Safe": "1"},
        "body": {"hello": "world"},
        "content_type": "application/json",
    }
    # Request actually reached the mixin with the parsed PassthroughRequest.
    assert len(handler.calls) == 1
    assert handler.calls[0].method == "GET"
    assert handler.calls[0].path == "/me"


def test_passthrough_returns_501_when_handler_does_not_support_mixin(client):
    # A bare object does not satisfy PassthroughProtocol, so the endpoint
    # should surface passthrough_not_supported (501) instead of a 500.
    with _patch_handler(object()):
        response = client.post(
            "/api/integrations/mysql/passthrough",
            json={"method": "GET", "path": "/anything"},
        )

    assert response.status_code == HTTPStatus.NOT_IMPLEMENTED
    payload = response.get_json()
    assert payload["error_code"] == "passthrough_not_supported"
    assert "mysql" in payload["message"]


def test_passthrough_returns_400_on_invalid_method(client):
    handler = _StubPassthroughHandler(PassthroughResponse(status_code=200, headers={}, body=None, content_type=None))

    with _patch_handler(handler):
        response = client.post(
            "/api/integrations/any_ds/passthrough",
            json={"method": "TRACE", "path": "/me"},
        )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    payload = response.get_json()
    assert payload["error_code"] == "invalid_request"
    # The handler must not have been invoked when validation fails up front.
    assert handler.calls == []


def _patch_handler_modules(modules: dict):
    return patch(
        "mindsdb.api.http.namespaces.integrations.integration_controller.handler_modules",
        modules,
        create=True,
    )


def test_capabilities_returns_handlers_dict_and_legacy_list(client):
    # Two opted-in handlers covering both auth modes, one non-opt-in, and
    # one broken module that lacks a Handler attribute. auth_modes is
    # surfaced from the handler's declarative `_auth_mode` class attr —
    # not inferred from header format.
    class _BearerHandler(PassthroughMixin):
        pass  # inherits _auth_mode = "bearer"

    class _CustomHeaderHandler(PassthroughMixin):
        _auth_header_name = "X-Shopify-Access-Token"
        _auth_header_format = "{token}"
        _auth_mode = "custom"

    class _NotOptedIn:
        pass

    bearer_mod = MagicMock()
    bearer_mod.Handler = _BearerHandler
    custom_mod = MagicMock()
    custom_mod.Handler = _CustomHeaderHandler
    plain_mod = MagicMock()
    plain_mod.Handler = _NotOptedIn
    no_handler_mod = MagicMock(spec=[])

    fake_modules = {
        "hubspot": bearer_mod,
        "shopify": custom_mod,
        "mysql": plain_mod,
        "broken": no_handler_mod,
    }

    with _patch_handler_modules(fake_modules):
        response = client.get("/api/integrations/capabilities")

    assert response.status_code == HTTPStatus.OK
    payload = response.get_json()

    # New structured shape: every opted-in handler appears with auth_modes
    # and operations metadata.
    assert payload["handlers"] == {
        "hubspot": {"auth_modes": ["bearer"], "operations": ["passthrough"]},
        "shopify": {"auth_modes": ["custom"], "operations": ["passthrough"]},
    }

    # Legacy flat list: only bearer-auth handlers (Minds migration compat).
    assert payload["bearer_passthrough"] == ["hubspot"]


def test_capabilities_auth_mode_is_declarative_not_format_derived(client):
    # Handler keeps the default "Bearer {token}" header format but flags
    # itself as oauth_refresh. The old format-matching heuristic would
    # have bucketed this as "bearer"; the new declarative path returns
    # the explicit mode and correctly omits it from the legacy list.
    class _OAuthRefreshHandler(PassthroughMixin):
        _auth_mode = "oauth_refresh"
        # _auth_header_format intentionally left as the default.

    oauth_mod = MagicMock()
    oauth_mod.Handler = _OAuthRefreshHandler

    with _patch_handler_modules({"hubspot_oauth": oauth_mod}):
        response = client.get("/api/integrations/capabilities")

    assert response.status_code == HTTPStatus.OK
    payload = response.get_json()
    assert payload["handlers"] == {
        "hubspot_oauth": {"auth_modes": ["oauth_refresh"], "operations": ["passthrough"]},
    }
    # oauth_refresh is NOT surfaced in the legacy bearer-only list even
    # though the underlying header format is still "Bearer {token}".
    assert payload["bearer_passthrough"] == []


def test_capabilities_empty_when_no_handlers_opted_in(client):
    class _NotOptedIn:
        pass

    plain_mod = MagicMock()
    plain_mod.Handler = _NotOptedIn

    with _patch_handler_modules({"mysql": plain_mod}):
        response = client.get("/api/integrations/capabilities")

    assert response.status_code == HTTPStatus.OK
    payload = response.get_json()
    assert payload == {"handlers": {}, "bearer_passthrough": []}
