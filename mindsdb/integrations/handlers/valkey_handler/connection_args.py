from collections import OrderedDict

from mindsdb.integrations.libs.const import HANDLER_CONNECTION_ARG_TYPE as ARG_TYPE

connection_args = OrderedDict(
    host={
        "type": ARG_TYPE.STR,
        "description": "Valkey server hostname",
        "required": False,
    },
    port={
        "type": ARG_TYPE.INT,
        "description": "Valkey server port",
        "required": False,
    },
    password={
        "type": ARG_TYPE.PWD,
        "description": "Valkey authentication password",
        "required": False,
        "secret": True,
    },
    db={
        "type": ARG_TYPE.INT,
        "description": "Valkey database number (0-15)",
        "required": False,
    },
    vector_dimension={
        "type": ARG_TYPE.INT,
        "description": "Default vector dimension for new indexes",
        "required": False,
    },
    distance_metric={
        "type": ARG_TYPE.STR,
        "description": "Distance metric: COSINE, L2, or IP",
        "required": False,
    },
    prefix={
        "type": ARG_TYPE.STR,
        "description": "Key prefix for document hashes",
        "required": False,
    },
    use_tls={
        "type": ARG_TYPE.BOOL,
        "description": "Enable TLS/SSL connection (required for AWS ElastiCache, MemoryDB)",
        "required": False,
    },
    request_timeout={
        "type": ARG_TYPE.INT,
        "description": "Request timeout in milliseconds (default: 5000)",
        "required": False,
    },
)

connection_args_example = OrderedDict(
    host="localhost",
    port=6379,
    vector_dimension=384,
    distance_metric="COSINE",
)
