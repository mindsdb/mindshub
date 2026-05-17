---
title: REST API
sidebarTitle: REST API
---

This documentation describes the integration of MindsDB with generic REST APIs using bearer-token authentication.
The integration allows MindsDB to forward HTTP requests to any REST API using stored credentials via the passthrough endpoint — no SQL table mapping required.

### Prerequisites

Before proceeding, ensure the following prerequisites are met:

1. Install MindsDB locally via [Docker](https://docs.mindsdb.com/setup/self-hosted/docker) or [Docker Desktop](https://docs.mindsdb.com/setup/self-hosted/docker-desktop).
2. Obtain a bearer token (API key, personal access token, etc.) for the target REST API.

## Connection

Establish a connection to a REST API from MindsDB by executing the following SQL command:

```sql
CREATE DATABASE my_api
WITH ENGINE = 'rest_api',
PARAMETERS = {
    "base_url": "https://api.example.com",
    "bearer_token": "your_token_here"
};
```

Required connection parameters include the following:

* `base_url`: The base URL of the REST API (e.g. `https://api.example.com`). All passthrough request paths are appended to this URL.
* `bearer_token`: The bearer token used for authentication. Injected as `Authorization: Bearer <token>` on every request.

Optional connection parameters include the following:

* `default_headers`: A JSON object of static headers added to every request (e.g. `{"Accept": "application/json"}`).
* `allowed_hosts`: A list of allowed hostnames for passthrough requests. Defaults to the hostname of `base_url`. Use `["*"]` to disable host containment.
* `test_path`: The path used by the `/passthrough/test` endpoint to verify connectivity. Defaults to `/`.

### Examples

Connect to the HubSpot API:

```sql
CREATE DATABASE my_hubspot
WITH ENGINE = 'rest_api',
PARAMETERS = {
    "base_url": "https://api.hubapi.com",
    "bearer_token": "pat-eu1-..."
};
```

Connect to a custom internal API with default headers:

```sql
CREATE DATABASE my_internal_api
WITH ENGINE = 'rest_api',
PARAMETERS = {
    "base_url": "https://internal.example.com/api/v2",
    "bearer_token": "sk-...",
    "default_headers": {"Accept": "application/json", "X-Team": "data"},
    "test_path": "/health"
};
```

Connect to an API with multiple allowed hosts:

```sql
CREATE DATABASE my_multi_region_api
WITH ENGINE = 'rest_api',
PARAMETERS = {
    "base_url": "https://api.example.com",
    "bearer_token": "your_token",
    "allowed_hosts": ["api.example.com", "api.eu.example.com"]
};
```

## Usage

This handler is **passthrough-only** — it does not expose SQL tables. All interaction is through the REST passthrough endpoint.

### Passthrough Requests

Send HTTP requests to the upstream API through MindsDB:

```
POST /api/integrations/my_api/passthrough
```

```json
{
    "method": "GET",
    "path": "/v1/users",
    "query": {"limit": "10"},
    "headers": {"Accept": "application/json"}
}
```

The response wraps the upstream HTTP response:

```json
{
    "status_code": 200,
    "headers": {"content-type": "application/json"},
    "body": {"results": [...]},
    "content_type": "application/json"
}
```

Supported HTTP methods: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`.

### Testing the Connection

Verify that the base URL, token, and host allowlist are configured correctly:

```
POST /api/integrations/my_api/passthrough/test
```

Returns:

```json
{"ok": true, "status_code": 200, "host": "api.example.com", "latency_ms": 140}
```

Or on failure:

```json
{"ok": false, "error_code": "auth_failed", "message": "upstream rejected credentials; base URL and allowlist look correct"}
```

## Security

- **Credentials are never exposed.** The bearer token is stored in MindsDB and injected at request time. It is never returned to the caller.
- **Host containment.** Requests are restricted to hostnames in the allowlist (defaults to the `base_url` host). Private/loopback IP addresses are rejected by default.
- **Header filtering.** Callers cannot override `Authorization`, `Host`, `Cookie`, or `Proxy-*` headers.
- **Response scrubbing.** If the upstream API echoes the token in responses, it is replaced with `[REDACTED_API_KEY]` before returning to the caller.
- **Size limits.** Request bodies are capped at 1 MB, response bodies at 10 MB (configurable via environment variables).

## Troubleshooting

<Warning>
`base_url is not configured`

* **Symptoms**: Passthrough requests fail with a configuration error.
* **Checklist**:
    1. Ensure `base_url` is provided in the connection parameters.
    2. The URL must include the scheme (`https://`).
</Warning>

<Warning>
`host 'X' is not in the datasource allowlist`

* **Symptoms**: Passthrough requests to a valid URL are rejected.
* **Checklist**:
    1. The request path may resolve to a different hostname than `base_url`.
    2. Add the hostname to `allowed_hosts` in the connection parameters.
    3. Use `["*"]` to disable host containment (not recommended for production).
</Warning>

<Warning>
`upstream rejected credentials (401/403)`

* **Symptoms**: The `/passthrough/test` endpoint returns `error_code: "auth_failed"`.
* **Checklist**:
    1. Verify the bearer token is valid and not expired.
    2. Check that the token has the required scopes/permissions for the API endpoints you are calling.
</Warning>
