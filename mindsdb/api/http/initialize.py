import os
import secrets
import mimetypes
import threading
import webbrowser

from pathlib import Path
from http import HTTPStatus


import requests
from flask import Flask, url_for, request, send_from_directory
from flask_compress import Compress
from flask_restx import Api
from werkzeug.exceptions import HTTPException
from packaging.version import Version, parse as parse_version

from mindsdb.__about__ import __version__ as mindsdb_version
from mindsdb.api.http.gui import update_static
from mindsdb.api.http.utils import http_error
from mindsdb.api.http.namespaces.agents import ns_conf as agents_ns
from mindsdb.api.http.namespaces.analysis import ns_conf as analysis_ns
from mindsdb.api.http.namespaces.auth import ns_conf as auth_ns
from mindsdb.api.http.namespaces.chatbots import ns_conf as chatbots_ns
from mindsdb.api.http.namespaces.jobs import ns_conf as jobs_ns
from mindsdb.api.http.namespaces.config import ns_conf as conf_ns
from mindsdb.api.http.namespaces.databases import ns_conf as databases_ns
from mindsdb.api.http.namespaces.default import ns_conf as default_ns, check_session_auth
from mindsdb.api.http.namespaces.file import ns_conf as file_ns
from mindsdb.api.http.namespaces.handlers import ns_conf as handlers_ns
from mindsdb.api.http.namespaces.integrations import ns_conf as integrations_ns
from mindsdb.api.http.namespaces.knowledge_bases import ns_conf as knowledge_bases_ns
from mindsdb.api.http.namespaces.models import ns_conf as models_ns
from mindsdb.api.http.namespaces.projects import ns_conf as projects_ns
from mindsdb.api.http.namespaces.sql import ns_conf as sql_ns
from mindsdb.api.http.namespaces.tab import ns_conf as tab_ns
from mindsdb.api.http.namespaces.tree import ns_conf as tree_ns
from mindsdb.api.http.namespaces.views import ns_conf as views_ns
from mindsdb.api.http.namespaces.util import ns_conf as utils_ns
from mindsdb.api.http.namespaces.webhooks import ns_conf as webhooks_ns
from mindsdb.interfaces.database.integrations import integration_controller
from mindsdb.interfaces.database.database import DatabaseController
from mindsdb.interfaces.file.file_controller import FileController
from mindsdb.interfaces.jobs.jobs_controller import JobsController
from mindsdb.interfaces.storage import db
from mindsdb.metrics.server import init_metrics
from mindsdb.utilities import log
from mindsdb.utilities.config import config, HTTP_AUTH_TYPE
from mindsdb.utilities.context import context as ctx
from mindsdb.utilities.json_encoder import ORJSONProvider
from mindsdb.utilities.ps import is_pid_listen_port, wait_func_is_true
from mindsdb.utilities.sentry import sentry_sdk  # noqa: F401
from mindsdb.utilities.otel import trace  # noqa: F401
from mindsdb.api.common.middleware import verify_pat
from mindsdb.utilities.constants import DEFAULT_COMPANY_ID, DEFAULT_USER_ID

logger = log.getLogger(__name__)


class _NoOpFlaskInstrumentor:
    def instrument_app(self, app):
        pass


class _NoOpRequestsInstrumentor:
    def instrument(self):
        pass


try:
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
except ImportError:
    logger.debug(
        "OpenTelemetry is not avaiable. Please run `pip install -r requirements/requirements-opentelemetry.txt` to use it."
    )
    FlaskInstrumentor = _NoOpFlaskInstrumentor
    RequestsInstrumentor = _NoOpRequestsInstrumentor


class Swagger_Api(Api):
    """
    This is a modification of the base Flask Restplus Api class due to the issue described here
    https://github.com/noirbizarre/flask-restplus/issues/223
    """

    @property
    def specs_url(self):
        return url_for(self.endpoint("specs"), _external=False)


def get_last_compatible_gui_version() -> Version | bool:
    logger.debug("Getting last compatible frontend...")
    try:
        res = requests.get(
            "https://mindsdb-web-builds.s3.amazonaws.com/compatible-config.json",
            timeout=5,
        )
    except (ConnectionError, requests.exceptions.ConnectionError) as e:
        logger.error(f"Is no connection. {e}")
        return False
    except Exception as e:
        logger.error(f"Is something wrong with getting compatible-config.json: {e}")
        return False

    if res.status_code != 200:
        logger.error(f"Cant get compatible-config.json: returned status code = {res.status_code}")
        return False

    try:
        versions = res.json()
    except Exception as e:
        logger.error(f"Cant decode compatible-config.json: {e}")
        return False

    current_mindsdb_lv = parse_version(mindsdb_version)

    try:
        gui_versions = {}
        max_mindsdb_lv = None
        max_gui_lv = None
        for el in versions["mindsdb"]:
            if el["mindsdb_version"] is None:
                gui_lv = parse_version(el["gui_version"])
            else:
                mindsdb_lv = parse_version(el["mindsdb_version"])
                gui_lv = parse_version(el["gui_version"])
                if mindsdb_lv.base_version not in gui_versions or gui_lv > gui_versions[mindsdb_lv.base_version]:
                    gui_versions[mindsdb_lv.base_version] = gui_lv
                if max_mindsdb_lv is None or max_mindsdb_lv < mindsdb_lv:
                    max_mindsdb_lv = mindsdb_lv
            if max_gui_lv is None or max_gui_lv < gui_lv:
                max_gui_lv = gui_lv

        all_mindsdb_lv = [parse_version(x) for x in gui_versions.keys()]
        all_mindsdb_lv.sort()

        if current_mindsdb_lv.base_version in gui_versions:
            gui_version_lv = gui_versions[current_mindsdb_lv.base_version]
        elif current_mindsdb_lv > all_mindsdb_lv[-1]:
            gui_version_lv = max_gui_lv
        else:
            lower_versions = {
                key: value for key, value in gui_versions.items() if parse_version(key) < current_mindsdb_lv
            }
            if len(lower_versions) == 0:
                gui_version_lv = gui_versions[all_mindsdb_lv[0].base_version]
            else:
                all_lower_versions = [parse_version(x) for x in lower_versions.keys()]
                gui_version_lv = gui_versions[all_lower_versions[-1].base_version]
    except Exception:
        logger.exception("Error in compatible-config.json structure")
        return False

    logger.debug(f"Last compatible frontend version: {gui_version_lv}.")
    return gui_version_lv


def get_current_gui_version() -> Version:
    logger.debug("Getting current frontend version...")
    static_path = Path(config["paths"]["static"])
    version_txt_path = static_path.joinpath("version.txt")

    current_gui_version = None
    if version_txt_path.is_file():
        with open(version_txt_path, "rt") as f:
            current_gui_version = f.readline()

    current_gui_lv = None if current_gui_version is None else parse_version(current_gui_version)
    logger.debug(f"Current frontend version: {current_gui_lv}.")

    return current_gui_lv


def initialize_static():
    last_gui_version_lv = get_last_compatible_gui_version()
    current_gui_version_lv = get_current_gui_version()
    required_gui_version = config["gui"].get("version")

    if required_gui_version is not None:
        required_gui_version_lv = parse_version(required_gui_version)
        success = True
        if current_gui_version_lv is None or required_gui_version_lv != current_gui_version_lv:
            success = update_static(required_gui_version_lv)
    else:
        if last_gui_version_lv is False:
            logger.debug(
                "The number of the latest version has not been determined, "
                f"so we will continue using the current version: {current_gui_version_lv}"
            )
            return False

        if current_gui_version_lv == last_gui_version_lv:
            logger.debug(f"The latest version is already in use: {current_gui_version_lv}")
            return True
        success = update_static(last_gui_version_lv)

    if db.session:
        db.session.close()
    return success


def initialize_app(is_restart: bool = False):
    static_root = config["paths"]["static"]
    logger.debug(f"Static route: {static_root}")
    init_static_thread = None
    if not is_restart:
        gui_exists = Path(static_root).joinpath("index.html").is_file()
        logger.debug(f"Does GUI already exist.. {'YES' if gui_exists else 'NO'}")

        if config["gui"]["autoupdate"] is True or (config["gui"]["open_on_start"] is True and gui_exists is False):
            logger.debug("Initializing static...")
            init_static_thread = threading.Thread(target=initialize_static, name="initialize_static")
            init_static_thread.start()
        else:
            logger.debug(f"Skip initializing static: config['gui']={config['gui']}, gui_exists={gui_exists}")

    app, api = initialize_flask()

    if not is_restart and config["gui"]["open_on_start"]:
        if init_static_thread is not None:
            init_static_thread.join()
        open_gui(init_static_thread)

    Compress(app)

    initialize_interfaces(app)

    if os.path.isabs(static_root) is False:
        static_root = os.path.join(os.getcwd(), static_root)
    static_root = Path(static_root)

    @app.route("/", defaults={"path": ""}, methods=["GET"])
    @app.route("/<path:path>", methods=["GET"])
    def root_index(path):
        if path.startswith("api/"):
            return http_error(
                HTTPStatus.NOT_FOUND,
                "Not found",
                "The endpoint you are trying to access does not exist on the server.",
            )

        try:
            # Ensure the requested path is within the static directory
            # https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.is_relative_to
            requested_path = (static_root / path).resolve()

            if not requested_path.is_relative_to(static_root.resolve()):
                return http_error(
                    HTTPStatus.FORBIDDEN,
                    "Forbidden",
                    "You are not allowed to access the requested resource.",
                )

            if requested_path.is_file():
                return send_from_directory(static_root, path)
            else:
                return send_from_directory(static_root, "index.html")

        except (ValueError, OSError):
            return http_error(
                HTTPStatus.BAD_REQUEST,
                "Bad Request",
                "Invalid path requested.",
            )

    protected_namespaces = [
        tab_ns,
        utils_ns,
        conf_ns,
        file_ns,
        sql_ns,
        analysis_ns,
        handlers_ns,
        tree_ns,
        projects_ns,
        databases_ns,
        views_ns,
        models_ns,
        chatbots_ns,
        agents_ns,
        jobs_ns,
        knowledge_bases_ns,
        integrations_ns,
    ]

    for ns in protected_namespaces:
        api.add_namespace(ns)
    api.add_namespace(default_ns)
    api.add_namespace(auth_ns)
    api.add_namespace(webhooks_ns)

    @api.errorhandler(Exception)
    def handle_exception(e):
        logger.error(f"http exception: {e}")
        # pass through HTTP errors
        # NOTE flask_restx require 'message', also it modyfies 'application/problem+json' to 'application/json'
        if isinstance(e, HTTPException):
            return (
                {"title": e.name, "detail": e.description, "message": e.description},
                e.code,
                {"Content-Type": "application/problem+json"},
            )
        return (
            {
                "title": getattr(type(e), "__name__") or "Unknown error",
                "detail": str(e),
                "message": str(e),
            },
            500,
            {"Content-Type": "application/problem+json"},
        )

    @app.teardown_appcontext
    def remove_session(*args, **kwargs):
        db.session.remove()

    @app.before_request
    def before_request():
        ctx.set_default()

        h = request.headers.get("Authorization")
        if not h or not h.startswith("Bearer "):
            bearer = None
        else:
            bearer = h.split(" ", 1)[1].strip() or None

        # region routes where auth is required
        http_auth_type = config["auth"]["http_auth_type"]
        if (
            config["auth"]["http_auth_enabled"] is True
            and any(request.path.startswith(f"/api{ns.path}") for ns in protected_namespaces)
            and (
                (http_auth_type == HTTP_AUTH_TYPE.SESSION and check_session_auth() is False)
                or (http_auth_type == HTTP_AUTH_TYPE.TOKEN and verify_pat(bearer) is False)
                or (
                    http_auth_type == HTTP_AUTH_TYPE.SESSION_OR_TOKEN
                    and check_session_auth() is False
                    and verify_pat(bearer) is False
                )
            )
        ):
            logger.debug(f"Auth failed for path {request.path}")
            return http_error(
                HTTPStatus.UNAUTHORIZED,
                "Unauthorized",
                "Authorization is required to complete the request",
            )
        # endregion

        company_id = request.headers.get("company-id")
        user_id = request.headers.get("user-id")
        user_class = request.headers.get("user-class")
        enforce_user_id = request.headers.get("enforce-user-id")

        if user_class is not None:
            try:
                user_class = int(user_class)
            except Exception as e:
                logger.error(f"Could not parse user_class: {user_class} | exception: {e}")
                user_class = 0
        else:
            user_class = 0

        ctx.company_id = company_id if company_id is not None else DEFAULT_COMPANY_ID
        ctx.user_id = user_id if user_id is not None else DEFAULT_USER_ID
        ctx.user_class = user_class
        if enforce_user_id is not None:
            ctx.enforce_user_id = enforce_user_id.lower() not in ("false", "0", "no", "")

    logger.debug("Done initializing app.")
    return app


def initialize_flask():
    logger.debug("Initializing flask...")
    # region required for windows https://github.com/mindsdb/mindsdb/issues/2526
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("text/javascript", ".js")
    # endregion

    static_path = os.path.join(config["paths"]["static"], "static/")
    if os.path.isabs(static_path) is False:
        static_path = os.path.join(os.getcwd(), static_path)
    kwargs = {"static_url_path": "/static", "static_folder": static_path}
    logger.debug(f"Static path: {static_path}")

    app = Flask(__name__, **kwargs)
    init_metrics(app)

    # Instrument Flask app and requests using either real or no-op instrumentors
    FlaskInstrumentor().instrument_app(app)
    RequestsInstrumentor().instrument()

    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 60
    app.config["SWAGGER_HOST"] = "http://localhost:8000/mindsdb"
    app.json = ORJSONProvider(app)

    http_auth_type = config["auth"]["http_auth_type"]
    authorizations = {}
    security = []

    if http_auth_type in (HTTP_AUTH_TYPE.SESSION, HTTP_AUTH_TYPE.SESSION_OR_TOKEN):
        app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
        app.config["SESSION_COOKIE_NAME"] = "session"
        app.config["PERMANENT_SESSION_LIFETIME"] = config["auth"]["http_permanent_session_lifetime"]
        authorizations["session"] = {"type": "apiKey", "in": "cookie", "name": "session"}
        security.append(["session"])

    if http_auth_type in (HTTP_AUTH_TYPE.TOKEN, HTTP_AUTH_TYPE.SESSION_OR_TOKEN):
        authorizations["bearer"] = {"type": "apiKey", "in": "header", "name": "Authorization"}
        security.append(["bearer"])

    logger.debug("Creating swagger API..")
    api = Swagger_Api(
        app,
        authorizations=authorizations,
        security=security,
        url_prefix=":8000",
        prefix="/api",
        doc="/doc/",
    )

    def __output_json_orjson(data, code, headers=None):
        from flask import current_app, make_response

        dumped = current_app.json.dumps(data)
        resp = make_response(dumped, code)
        if headers:
            resp.headers.extend(headers)
        resp.mimetype = "application/json"
        return resp

    api.representations["application/json"] = __output_json_orjson

    return app, api


def open_gui(init_static_thread):
    port = config["api"]["http"]["port"]
    host = config["api"]["http"]["host"]

    if host in ("", "0.0.0.0"):
        url = f"http://127.0.0.1:{port}/"
    else:
        url = f"http://{host}:{port}/"
    logger.info(f" - GUI available at {url}")

    pid = os.getpid()
    thread = threading.Thread(
        target=_open_webbrowser,
        args=(url, pid, port, init_static_thread, config["paths"]["static"]),
        daemon=True,
        name="open_webbrowser",
    )
    thread.start()


def initialize_interfaces(app):
    app.integration_controller = integration_controller
    app.database_controller = DatabaseController()
    app.file_controller = FileController()
    app.jobs_controller = JobsController()


def _open_webbrowser(url: str, pid: int, port: int, init_static_thread, static_folder):
    """Open webbrowser with url when http service is started.

    If some error then do nothing.
    """
    if init_static_thread is not None:
        init_static_thread.join()
    try:
        is_http_active = wait_func_is_true(func=is_pid_listen_port, timeout=15, pid=pid, port=port)
        if is_http_active:
            webbrowser.open(url)
    except Exception:
        logger.exception(f"Failed to open {url} in webbrowser with exception:")
    db.session.close()
