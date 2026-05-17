from collections import OrderedDict

from mindsdb.integrations.libs.const import HANDLER_CONNECTION_ARG_TYPE as ARG_TYPE

connection_args = OrderedDict(
    base_url={
        "type": ARG_TYPE.STR,
        "description": "Base URL of the REST API (e.g. https://api.example.com)",
        "required": True,
        "label": "Base URL",
    },
    bearer_token={
        "type": ARG_TYPE.PWD,
        "description": "Bearer token injected as Authorization: Bearer <token>",
        "required": True,
        "label": "Bearer Token",
        "secret": True,
    },
    default_headers={
        "type": ARG_TYPE.DICT,
        "description": 'Static headers added to every request (e.g. {"Accept": "application/json"})',
        "required": False,
        "label": "Default Headers",
    },
    allowed_hosts={
        "type": ARG_TYPE.LIST,
        "description": 'Allowed hostnames for passthrough requests. Defaults to the base_url host. Use ["*"] to disable containment.',
        "required": False,
        "label": "Allowed Hosts",
    },
    test_path={
        "type": ARG_TYPE.STR,
        "description": "Path used by the /passthrough/test endpoint. Defaults to /",
        "required": False,
        "label": "Test Path",
    },
)

connection_args_example = OrderedDict(
    base_url="https://api.example.com",
    bearer_token="your_token_here",
    default_headers={"Accept": "application/json"},
    allowed_hosts=["api.example.com"],
)
