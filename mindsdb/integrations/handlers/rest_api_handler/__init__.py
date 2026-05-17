from mindsdb.integrations.libs.const import HANDLER_TYPE, HANDLER_SUPPORT_LEVEL

from .__about__ import __version__ as version, __description__ as description
from .connection_args import connection_args, connection_args_example

try:
    from .rest_api_handler import RestApiHandler as Handler

    import_error = None
except Exception as e:
    Handler = None
    import_error = e

title = "REST API"
name = "rest_api"
type = HANDLER_TYPE.DATA
icon_path = "icon.svg"
support_level = HANDLER_SUPPORT_LEVEL.MINDSDB

__all__ = [
    "Handler",
    "version",
    "name",
    "type",
    "support_level",
    "title",
    "description",
    "import_error",
    "icon_path",
    "connection_args",
    "connection_args_example",
]
