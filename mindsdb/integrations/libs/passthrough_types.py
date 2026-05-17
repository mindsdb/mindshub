"""
Request/response dataclasses and error types for the REST passthrough path.

These are the payloads exchanged between the HTTP layer and
`PassthroughMixin`. They are intentionally framework-agnostic so the
mixin can be unit-tested without Flask.
"""

from dataclasses import dataclass, field
from typing import Any


ALLOWED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})

# Hop-by-hop and auth-related headers that must never come from the caller.
FORBIDDEN_REQUEST_HEADERS = frozenset(
    h.lower()
    for h in (
        "authorization",
        "host",
        "cookie",
        "content-length",
        "connection",
    )
)

# Hop-by-hop response headers stripped before returning to the caller.
HOP_BY_HOP_RESPONSE_HEADERS = frozenset(
    h.lower()
    for h in (
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",
    )
)


@dataclass
class PassthroughRequest:
    method: str
    path: str
    query: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: Any = None


@dataclass
class PassthroughResponse:
    status_code: int
    headers: dict[str, str]
    body: Any
    content_type: str | None = None


class PassthroughError(Exception):
    """Base class for passthrough failures that should not be leaked as 500s."""

    error_code: str = "passthrough_error"
    http_status: int = 400

    def __init__(self, message: str, *, error_code: str | None = None, http_status: int | None = None):
        super().__init__(message)
        if error_code is not None:
            self.error_code = error_code
        if http_status is not None:
            self.http_status = http_status


class PassthroughConfigError(PassthroughError):
    error_code = "config_error"
    http_status = 500


class HostNotAllowedError(PassthroughError):
    error_code = "host_not_allowed"
    http_status = 400


class PassthroughValidationError(PassthroughError):
    error_code = "invalid_request"
    http_status = 400


class PassthroughNotSupportedError(PassthroughError):
    """Raised when a handler does not implement the mixin."""

    error_code = "passthrough_not_supported"
    http_status = 501
