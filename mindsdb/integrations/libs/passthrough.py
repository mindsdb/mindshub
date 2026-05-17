"""
PassthroughMixin — generic HTTP passthrough for authenticated REST APIs.

A handler opts in by declaring three class attributes:

    class MyHandler(APIHandler, PassthroughMixin):
        _bearer_token_arg = "api_key"                 # key in connection_data
        _base_url_default = "https://api.example.com" # fallback if user omits
        _test_request = PassthroughRequest("GET", "/me")

The mixin defaults to ``Authorization: Bearer <token>``. Handlers using a
different auth scheme (e.g. Shopify's ``X-Shopify-Access-Token``) override
``_auth_header_name`` and ``_auth_header_format`` — see CHANGE 3.

The mixin reads ``self.connection_data`` (a dict populated from
integration setup) to pull the token, resolve the base URL, and enforce
the host allowlist. Handlers that need custom URL composition (e.g.
``http://{host}:{port}``) override ``_build_base_url``.

``PassthroughProtocol`` is a structural type describing the two public
methods (``api_passthrough`` and ``test_passthrough``). The HTTP layer
checks against the protocol rather than the mixin class, so a handler
can satisfy the contract without inheriting the default implementation.
"""

import ipaddress
import os
import time
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlparse

import requests

from mindsdb.integrations.libs.passthrough_types import (
    ALLOWED_METHODS,
    FORBIDDEN_REQUEST_HEADERS,
    HOP_BY_HOP_RESPONSE_HEADERS,
    HostNotAllowedError,
    PassthroughConfigError,
    PassthroughRequest,
    PassthroughResponse,
    PassthroughValidationError,
)
from mindsdb.utilities import log

logger = log.getLogger(__name__)


PASSTHROUGH_TIMEOUT_SECONDS = int(os.getenv("MINDSDB_PASSTHROUGH_TIMEOUT_SECONDS", "30"))
PASSTHROUGH_MAX_REQUEST_BYTES = int(os.getenv("MINDSDB_PASSTHROUGH_MAX_REQUEST_BYTES", str(1 * 1024 * 1024)))
PASSTHROUGH_MAX_RESPONSE_BYTES = int(os.getenv("MINDSDB_PASSTHROUGH_MAX_RESPONSE_BYTES", str(10 * 1024 * 1024)))

REDACTED_SENTINEL = "[REDACTED_API_KEY]"


def _is_private_host(hostname: str) -> bool:
    """Return True if `hostname` resolves to a private/loopback/link-local IP literal.

    Only IP literals are checked; DNS resolution is intentionally not performed
    (handlers may legitimately point at an internal DNS name the operator has
    approved via `allowed_hosts`). The IP-literal check prevents a caller from
    smuggling `http://127.0.0.1/` or `http://10.0.0.1/` through a typo'd base_url.
    """
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved


def _host_matches(host: str, allowlist: list[str]) -> bool:
    if not host:
        return False
    host = host.lower()
    return any(host == entry.lower() for entry in allowlist)


@runtime_checkable
class PassthroughProtocol(Protocol):
    """Structural contract for handlers that expose HTTP passthrough.

    The HTTP namespace checks against this Protocol rather than the
    `PassthroughMixin` class, which lets future handlers satisfy the
    contract without inheriting the default implementation.
    """

    def api_passthrough(self, req: PassthroughRequest) -> PassthroughResponse: ...

    def test_passthrough(self) -> dict[str, Any]: ...


class PassthroughMixin:
    # Required overrides
    _bearer_token_arg: str = ""

    # Optional overrides
    _base_url_arg: str = "base_url"
    _base_url_default: str | None = None
    _allowed_hosts_arg: str = "allowed_hosts"
    _default_headers_arg: str = "default_headers"

    # Auth header. Defaults to bearer-compatible; handlers using a custom
    # scheme (e.g. Shopify's `X-Shopify-Access-Token: <token>`) override
    # both attrs. The value from `_get_bearer_token()` is formatted into
    # `{token}` — the method name is retained for backwards compat but
    # now represents "the auth secret" regardless of scheme.
    _auth_header_name: str = "Authorization"
    _auth_header_format: str = "Bearer {token}"

    # Declarative auth mode surfaced to /capabilities. One handler instance
    # has exactly one auth mode, so this is a single string; the API
    # response still wraps it in a list because a future contract may
    # surface handlers supporting multiple configurations. Known values:
    # "bearer", "custom", "oauth_refresh". Handlers that use a non-bearer
    # header scheme or a refresh-aware mixin should set this explicitly —
    # don't infer it from _auth_header_format, since OAuth-refresh also
    # uses "Bearer {token}" but is a distinct mode.
    _auth_mode: str = "bearer"

    # Canonical sanity-check request for `test_passthrough()`. Handlers MUST
    # set this if they want the /passthrough/test endpoint to do anything
    # useful. `None` means "test endpoint returns 'not implemented'".
    _test_request: PassthroughRequest | None = None

    # Stamped on every upstream request so the upstream can identify our
    # traffic for support/debugging. See design §13 (q3).
    _upstream_marker_header: str = "X-Minds-Passthrough"

    # Hook: override when URL composition is more than "take a string"
    # (e.g. strapi composes from host+port).
    def _build_base_url(self) -> str | None:
        data = self._get_connection_data()
        value = data.get(self._base_url_arg) if self._base_url_arg else None
        if value:
            return str(value).rstrip("/")
        if self._base_url_default is not None:
            return self._base_url_default.rstrip("/")
        return None

    def _get_connection_data(self) -> dict[str, Any]:
        """Return the handler's stored connection_data dict.

        Handlers store this differently; we check the common attribute names
        so most handlers don't need to override.
        """
        for attr in ("connection_data", "_connection_data"):
            value = getattr(self, attr, None)
            if isinstance(value, dict):
                return value
        return {}

    def _get_bearer_token(self) -> str:
        if not self._bearer_token_arg:
            raise PassthroughConfigError("handler did not declare _bearer_token_arg")
        token = self._get_connection_data().get(self._bearer_token_arg)
        if not token:
            raise PassthroughConfigError(f"bearer token ('{self._bearer_token_arg}') is missing from connection_data")
        return str(token)

    def _resolve_url(self, path: str) -> tuple[str, str]:
        """Return ``(url, hostname)`` for the outgoing request.

        `path` is appended to the base URL verbatim. After joining we parse
        the result and compare the hostname against the allowlist — path
        injection tricks like ``@evil.com`` or ``//evil.com`` are rejected
        at the hostname-comparison step, not by string matching.
        """
        if not path.startswith("/"):
            raise PassthroughValidationError("path must start with '/'")
        base = self._build_base_url()
        if not base:
            raise PassthroughConfigError("base_url is not configured for this datasource")

        url = f"{base}{path}"
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise PassthroughValidationError(f"resolved URL is not valid: {url}")
        return url, parsed.hostname

    def _allowed_hosts(self, default_host: str) -> list[str]:
        data = self._get_connection_data()
        allowed = data.get(self._allowed_hosts_arg)
        if isinstance(allowed, list) and allowed:
            return [str(h) for h in allowed]
        return [default_host]

    def _check_host_allowed(self, hostname: str) -> None:
        allowlist = self._allowed_hosts(hostname)
        if allowlist == ["*"]:
            return
        if not _host_matches(hostname, allowlist):
            raise HostNotAllowedError(f"host '{hostname}' is not in the datasource allowlist")
        if _is_private_host(hostname):
            raise HostNotAllowedError(
                f"host '{hostname}' resolves to a private/loopback address; "
                "set allowed_hosts=['*'] to bypass this check (explicit "
                "listing is ignored for private IPs)"
            )

    def _build_outgoing_headers(self, caller_headers: dict[str, str], bearer: str) -> dict[str, str]:
        """Merge caller headers (filtered) + default_headers + Authorization."""
        out: dict[str, str] = {}
        data = self._get_connection_data()
        defaults = data.get(self._default_headers_arg) or {}
        if isinstance(defaults, dict):
            out.update({str(k): str(v) for k, v in defaults.items()})
        for name, value in (caller_headers or {}).items():
            if name.lower() in FORBIDDEN_REQUEST_HEADERS:
                continue
            if name.lower().startswith("proxy-"):
                continue
            out[name] = value
        out[self._auth_header_name] = self._auth_header_format.format(token=bearer)
        out[self._upstream_marker_header] = "1"
        return out

    def _secrets_for_scrub(self) -> list[str]:
        """Values that must not appear in the response returned to the caller."""
        secrets: list[str] = []
        try:
            secrets.append(self._get_bearer_token())
        except PassthroughConfigError:
            pass
        data = self._get_connection_data()
        defaults = data.get(self._default_headers_arg) or {}
        if isinstance(defaults, dict):
            for value in defaults.values():
                s = str(value)
                if len(s) >= 16:
                    secrets.append(s)
        return secrets

    def _scrub(self, text: str, secrets: list[str]) -> str:
        for s in secrets:
            if s:
                text = text.replace(s, REDACTED_SENTINEL)
        return text

    def _scrub_bytes(self, data: bytes, secrets: list[str]) -> bytes:
        """Byte-level secret scrub (spec §7.6).

        Replacing on raw bytes before decoding prevents U+FFFD substitutions
        from `errors="replace"` from fragmenting a secret and letting part of
        it survive the scrub.
        """
        sentinel = REDACTED_SENTINEL.encode("utf-8")
        for s in secrets:
            if s:
                data = data.replace(s.encode("utf-8"), sentinel)
        return data

    def _filter_response_headers(self, headers: dict[str, str], secrets: list[str]) -> dict[str, str]:
        filtered: dict[str, str] = {}
        for name, value in headers.items():
            if name.lower() in HOP_BY_HOP_RESPONSE_HEADERS:
                continue
            filtered[name] = self._scrub(str(value), secrets)
        return filtered

    def _read_capped_body(self, response: requests.Response) -> bytes:
        """Read the response body in chunks, abort if it exceeds the cap."""
        chunks: list[bytes] = []
        total = 0
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > PASSTHROUGH_MAX_RESPONSE_BYTES:
                    raise PassthroughValidationError(f"response body exceeded {PASSTHROUGH_MAX_RESPONSE_BYTES} bytes")
                chunks.append(chunk)
        finally:
            response.close()
        return b"".join(chunks)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def api_passthrough(self, req: PassthroughRequest) -> PassthroughResponse:
        method = (req.method or "").upper()
        if method not in ALLOWED_METHODS:
            raise PassthroughValidationError(f"method '{req.method}' is not allowed")

        connection_data = self._get_connection_data()
        allowed_methods_cfg = connection_data.get("allowed_methods")
        if allowed_methods_cfg is not None:
            if not isinstance(allowed_methods_cfg, list):
                raise PassthroughConfigError("'allowed_methods' must be a list of HTTP method strings")
            if not all(isinstance(m, str) for m in allowed_methods_cfg):
                raise PassthroughConfigError("'allowed_methods' must be a list of HTTP method strings")
            allowed_upper = {m.upper() for m in allowed_methods_cfg}
            unknown = sorted(allowed_upper - ALLOWED_METHODS)
            if unknown:
                raise PassthroughConfigError(
                    f"'allowed_methods' contains unsupported verbs: {unknown}. Allowed: {sorted(ALLOWED_METHODS)}"
                )
            if method not in allowed_upper:
                raise PassthroughValidationError(
                    f"method '{method}' is not permitted by this datasource",
                    error_code="method_not_allowed",
                    http_status=405,
                )

        request_bytes = 0
        if req.body is not None:
            # requests will serialize dict bodies to JSON; we cap on the
            # serialized length. For raw strings / bytes we cap directly.
            import json as _json

            if isinstance(req.body, (dict, list)):
                body_bytes_for_size = _json.dumps(req.body).encode("utf-8")
            elif isinstance(req.body, (bytes, bytearray)):
                body_bytes_for_size = bytes(req.body)
            else:
                body_bytes_for_size = str(req.body).encode("utf-8")
            if len(body_bytes_for_size) > PASSTHROUGH_MAX_REQUEST_BYTES:
                raise PassthroughValidationError(f"request body exceeded {PASSTHROUGH_MAX_REQUEST_BYTES} bytes")
            request_bytes = len(body_bytes_for_size)

        url, hostname = self._resolve_url(req.path)
        self._check_host_allowed(hostname)
        bearer = self._get_bearer_token()
        headers = self._build_outgoing_headers(req.headers or {}, bearer)

        request_kwargs: dict[str, Any] = {
            "headers": headers,
            "params": req.query or None,
            "timeout": PASSTHROUGH_TIMEOUT_SECONDS,
            "stream": True,
        }
        if req.body is not None:
            if isinstance(req.body, (dict, list)):
                request_kwargs["json"] = req.body
            else:
                request_kwargs["data"] = req.body

        datasource_name = getattr(self, "name", None) or "?"
        start = time.monotonic()
        response = requests.request(method, url, **request_kwargs)
        body_bytes = self._read_capped_body(response)
        duration_ms = int((time.monotonic() - start) * 1000)

        secrets = self._secrets_for_scrub()
        body_bytes = self._scrub_bytes(body_bytes, secrets)
        content_type = response.headers.get("Content-Type", "") or ""
        out_headers = self._filter_response_headers(dict(response.headers), secrets)

        body: Any
        if "application/json" in content_type.lower():
            try:
                text = body_bytes.decode("utf-8", errors="replace")
                import json as _json

                body = _json.loads(text) if text else None
            except ValueError:
                body = body_bytes.decode("utf-8", errors="replace")
        else:
            body = body_bytes.decode("utf-8", errors="replace")

        self._log_passthrough_call(
            method=method,
            path=req.path,
            datasource_name=datasource_name,
            upstream_status_code=response.status_code,
            request_bytes=request_bytes,
            response_bytes=len(body_bytes),
            duration_ms=duration_ms,
        )

        return PassthroughResponse(
            status_code=response.status_code,
            headers=out_headers,
            body=body,
            content_type=content_type.split(";", 1)[0].strip() or None,
        )

    def _log_passthrough_call(
        self,
        *,
        method: str,
        path: str,
        datasource_name: str,
        upstream_status_code: int,
        request_bytes: int,
        response_bytes: int,
        duration_ms: int,
    ) -> None:
        """Emit one audit line per passthrough call (spec §7.8).

        Never logs headers or bodies. user_id / org_id are pulled from the
        MindsDB request context when available; in test/dev invocations
        where the context is not populated, they are omitted.
        """
        fields: dict[str, Any] = {
            "method": method,
            "path": path,
            "datasource_name": datasource_name,
            "upstream_status_code": upstream_status_code,
            "request_bytes": request_bytes,
            "response_bytes": response_bytes,
            "duration_ms": duration_ms,
        }
        # TODO: org_id lives in Minds; when the passthrough is called via the
        # Minds gateway the org scope should be propagated and logged here.
        try:
            from mindsdb.utilities.context import context as _ctx

            user_id = getattr(_ctx, "user_id", None)
            company_id = getattr(_ctx, "company_id", None)
            if user_id is not None:
                fields["user_id"] = user_id
            if company_id is not None:
                fields["company_id"] = company_id
        except Exception:
            pass
        # DEBUG level per team decision: per-request audit logging at
        # info level happens in Minds at the HTTP layer. This log is
        # intended for mindsdb-side troubleshooting only.
        logger.debug("passthrough %s", fields)

    def test_passthrough(self) -> dict[str, Any]:
        """Run the handler's canonical sanity-check call (see §6.1a).

        Returns a structured dict the HTTP layer forwards to the caller:
            { "ok": bool, "status_code": int?, "host": str?, "latency_ms": int?,
              "error_code": str?, "message": str? }
        """
        if self._test_request is None:
            return {
                "ok": False,
                "error_code": "not_implemented",
                "message": "this handler does not define a passthrough test request",
            }

        start = time.monotonic()
        try:
            resp = self.api_passthrough(self._test_request)
        except HostNotAllowedError as e:
            return {"ok": False, "error_code": e.error_code, "message": str(e)}
        except PassthroughConfigError as e:
            return {"ok": False, "error_code": e.error_code, "message": str(e)}
        except PassthroughValidationError as e:
            return {"ok": False, "error_code": e.error_code, "message": str(e)}
        except requests.exceptions.Timeout as e:
            return {"ok": False, "error_code": "timeout", "message": str(e)}
        except requests.exceptions.ConnectionError as e:
            return {"ok": False, "error_code": "network", "message": str(e)}
        except Exception as e:  # noqa: BLE001
            logger.exception("passthrough test failed unexpectedly")
            return {"ok": False, "error_code": "unknown", "message": str(e)}

        latency_ms = int((time.monotonic() - start) * 1000)
        try:
            _, host = self._resolve_url(self._test_request.path)
        except Exception:
            host = None

        if 200 <= resp.status_code < 300:
            return {"ok": True, "status_code": resp.status_code, "host": host, "latency_ms": latency_ms}
        if resp.status_code in (401, 403):
            return {
                "ok": False,
                "status_code": resp.status_code,
                "host": host,
                "latency_ms": latency_ms,
                "error_code": "auth_failed",
                "message": "upstream rejected credentials; base URL and allowlist look correct",
            }
        return {
            "ok": False,
            "status_code": resp.status_code,
            "host": host,
            "latency_ms": latency_ms,
            "error_code": "upstream_error",
            "message": f"upstream returned {resp.status_code}",
        }
