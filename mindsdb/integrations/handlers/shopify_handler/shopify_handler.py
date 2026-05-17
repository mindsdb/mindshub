import json

import shopify
import requests
import pandas as pd

from mindsdb.integrations.handlers.shopify_handler.shopify_tables import (
    ProductsTable,
    ProductVariantsTable,
    CustomersTable,
    OrdersTable,
    MarketingEventsTable,
    InventoryItemsTable,
    StaffMembersTable,
    GiftCardsTable,
)
from mindsdb.integrations.libs.api_handler import MetaAPIHandler
from mindsdb.integrations.libs.passthrough import PassthroughMixin
from mindsdb.integrations.libs.passthrough_types import PassthroughRequest
from mindsdb.integrations.libs.response import (
    HandlerStatusResponse as StatusResponse,
    HandlerResponse as Response,
    RESPONSE_TYPE,
)

from mindsdb.utilities import log
from mindsdb.integrations.libs.api_handler_exceptions import (
    InvalidNativeQuery,
    ConnectionFailed,
    MissingConnectionParams,
)

from .connection_args import connection_args

logger = log.getLogger(__name__)


class ShopifyHandler(MetaAPIHandler, PassthroughMixin):
    """
    The Shopify handler implementation.
    """

    name = "shopify"

    # REST passthrough configuration. Shopify sends the Admin API token in
    # `X-Shopify-Access-Token`, not `Authorization: Bearer`, so we override
    # the default auth header. v1 requires the caller to pre-supply the
    # access token in connection_data — the existing client_id/client_secret
    # OAuth dance runs inside `connect()` and isn't surfaced to the mixin.
    _bearer_token_arg = "access_token"
    _auth_header_name = "X-Shopify-Access-Token"
    _auth_header_format = "{token}"
    _auth_mode = "custom"
    _base_url_default = None
    # Version-less path — Shopify redirects this to the current stable
    # Admin API version, so the probe survives quarterly API releases.
    _test_request = PassthroughRequest(method="GET", path="/admin/shop.json")

    def _build_base_url(self) -> str | None:
        data = self._get_connection_data()
        shop = data.get("shop_url")
        if not shop:
            return None
        shop = str(shop)
        if not shop.startswith(("http://", "https://")):
            shop = f"https://{shop}"
        return shop.rstrip("/")

    def __init__(self, name: str, **kwargs):
        """
        Initialize the handler.
        Args:
            name (str): name of particular handler instance
            **kwargs: arbitrary keyword arguments.
        """
        super().__init__(name)

        if kwargs.get("connection_data") is None:
            raise MissingConnectionParams("Incomplete parameters passed to Shopify Handler")

        connection_data = kwargs.get("connection_data", {})

        required_args = [arg_name for arg_name, arg_meta in connection_args.items() if arg_meta.get("required") is True]
        missed_args = set(required_args) - set(connection_data)
        if missed_args:
            raise MissingConnectionParams(
                f"Required parameters are not found in the connection data: {', '.join(list(missed_args))}"
            )

        self.connection_data = connection_data
        self.kwargs = kwargs

        self.connection = None
        self.is_connected = False

        self._register_table("products", ProductsTable(self))
        self._register_table("customers", CustomersTable(self))
        self._register_table("orders", OrdersTable(self))
        self._register_table("product_variants", ProductVariantsTable(self))
        self._register_table("marketing_events", MarketingEventsTable(self))
        self._register_table("inventory_items", InventoryItemsTable(self))
        self._register_table("staff_members", StaffMembersTable(self))
        self._register_table("gift_cards", GiftCardsTable(self))

    def connect(self):
        """
        Set up the connection required by the handler.
        Returns
        -------
        StatusResponse
            connection object
        """
        if self.is_connected is True:
            return self.connection

        shop_url = self.connection_data["shop_url"]
        client_id = self.connection_data["client_id"]
        client_secret = self.connection_data["client_secret"]

        response = requests.post(
            f"https://{shop_url}/admin/oauth/access_token",
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
        access_token = result.get("access_token")
        if not access_token:
            raise ConnectionFailed("Unable to get an access token")

        api_session = shopify.Session(shop_url, "2025-10", access_token)

        self.connection = api_session
        self.is_connected = True

        return self.connection

    def check_connection(self) -> StatusResponse:
        """
        Check connection to the handler.
        Returns:
            HandlerStatusResponse
        """

        response = StatusResponse(False)

        try:
            api_session = self.connect()
            shopify.ShopifyResource.activate_session(api_session)
            shopify.Shop.current()
            response.success = True
        except Exception as e:
            logger.error("Error connecting to Shopify!")
            response.error_message = str(e)

        self.is_connected = response.success

        return response

    def native_query(self, query: str) -> Response:
        """process a raw query

        Args:
            query (str): query in a native format (graphql)
        Returns:
            Response: The query result.
        """
        api_session = self.connect()
        shopify.ShopifyResource.activate_session(api_session)
        try:
            result = shopify.GraphQL().execute(query)
        except Exception as e:
            raise InvalidNativeQuery(f"An error occurred when executing the query: {e}")

        try:
            result = json.loads(result)
            data = result.get("data")
            df = pd.DataFrame(data)
        except Exception as e:
            raise InvalidNativeQuery(f"An error occurred when parsing the query result into a DataFrame: {e}")

        return Response(RESPONSE_TYPE.TABLE, data_frame=df)
