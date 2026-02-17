from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any, Iterator, Literal
from urllib.parse import parse_qs, urljoin, urlparse

from httpx import Auth, Client, HTTPStatusError, Response
from pystac import Item
from stapi_pydantic import Order, OrderPayload

from .models import (
    CreateTaskingProposal,
    DownloadSummaryItem,
    OrderParameters,
    Product,
    Profile,
    QuotaSummary,
    QuotaUnit,
    TaskingProposal,
    Vendor,
    VendorQuotaUsage,
)

logger = logging.getLogger(__name__)

Method = Literal["GET"] | Literal["POST"]
"""The HTTP methods supported by CSDA endpoints."""

STAGING_URL = "https://csdap-staging.ds.io"
PRODUCTION_URL = "https://csdap.earthdata.nasa.gov"
"""The CSDA service url."""


class AuthError(Exception):
    """A custom exception that we raise when something bad happens during authentication."""


class CsdaClient:
    """
    A client for logging into and interacting with CSDA API services.

    A `CsdaClient` can be used as a context manager:

    ```python
    >>> with CsdaClient.open(NetrcAuth()) as client:
    ...     client.verify()
    ...
    >>> # The underlying http connection has been closed.
    ```
    """

    @classmethod
    def open(cls, auth: Auth, url: str = PRODUCTION_URL) -> CsdaClient:
        """Opens and logs in a CSDA client.

        Args:
            auth: A [`httpx.Auth`](https://www.python-httpx.org/advanced/authentication/) that will be used for [Earthdata login](https://urs.earthdata.nasa.gov).
                We recommend either `BasicAuth` or `NetrcAuth`.
            url: The CSDA instance to use for queries.

        Returns:
            A logged-in client.
        """
        client = CsdaClient(url)
        client.login(auth)
        return client

    def __init__(self, url: str = PRODUCTION_URL) -> None:
        """Creates a new, un-logged-in CSDA client.

        Once you've created a client, use [login][csda_client.CsdaClient.login] to get an auth token.

        Args:
            url: The CSDA instance to use for queries.

        Returns:
            An un-logged-in client.
        """
        self.client = Client()
        self.url = url

    def __enter__(self) -> CsdaClient:
        return self

    def __exit__(
        self,
        exc_type: type[Exception] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.client.close()

    def verify(self) -> str:
        """Verifies the currently logged in user, returning the response.

        Returns:
            The string response from the authentication verification.
        """
        response = self.request(path="/api/v1/auth/verify", method="GET")
        return response.json()

    def profile(self, username: str) -> Profile:
        """Returns a user's [profile][csda_client.models.Profile].

        Args:
            username: A Earthdata Login username

        Returns:
            That user's CSDA profile
        """
        response = self.request(
            path=f"/signup/api/users/{username}/",
            method="GET",
        )
        return Profile.model_validate(response.json())

    def download_item(self, item: Item, asset_key: str, path: Path) -> None:
        """Downloads a single asset from a STAC item to a local file.

        Args:
            item: A [pystac.Item][]
            asset_key: The item's asset key that you would like to download
            path: The file to which the asset will be saved
        """
        if item.collection_id:
            self.download(item.collection_id, item.id, asset_key, path)
        else:
            raise ValueError("Cannot download an item without a collection id")

    def download(
        self, collection_id: str, item_id: str, asset_key: str, path: Path
    ) -> None:
        """Downloads an asset.

        Args:
            collection_id: The STAC collection id
            item_id: The STAC item id
            asset_key: The asset key
            path: The file to which the asset will be saved
        """
        request_path = f"/api/v2/download/{collection_id}/{item_id}/{asset_key}"
        with self.stream(method="GET", path=request_path) as response:
            with open(path, "wb") as f:
                for chunk in response.iter_bytes(1024 * 8):
                    if chunk:
                        f.write(chunk)

    def download_summary(
        self, username: str | None = None
    ) -> list[DownloadSummaryItem]:
        """Fetches download usage summary.

        Args:
            username: Optional username filter. If not provided, returns entries
                      for the authenticated user.

        Returns:
            List of download summary items showing usage per provider.
        """
        params = {}
        if username:
            params["username"] = username
        response = self.request(
            method="GET",
            path="/api/v1/download/summary",
            params=params if params else None,
        )
        return [DownloadSummaryItem.model_validate(item) for item in response.json()]

    def get_username(self) -> str:
        """Get the authenticated user's username.

        Retrieves the username from the download summary endpoint. Falls back
        to parsing the verify response if no download history exists.

        Returns:
            The authenticated user's username.

        Raises:
            ValueError: If the username cannot be determined.
        """
        summary = self.download_summary()
        if summary:
            return summary[0].username
        # Fallback: parse from verify response
        verify_result = self.verify()
        if isinstance(verify_result, str) and verify_result.startswith("Hello "):
            return verify_result.split(",")[0].replace("Hello ", "").strip()
        raise ValueError("Could not determine username from authentication")

    def get_quota_summary(self, username: str) -> QuotaSummary:
        """Gets a combined quota summary with limits and current usage.

        This method combines data from the profile endpoint (quota limits)
        and the download summary endpoint (current usage) to produce a
        unified view of quota status per vendor.

        Args:
            username: The Earthdata username to check.

        Returns:
            A QuotaSummary with usage details for each vendor.
        """
        profile = self.profile(username)
        summary_items = self.download_summary(username)

        usage_by_provider: dict[str, DownloadSummaryItem] = {
            item.provider: item for item in summary_items
        }

        vendor_usages = []
        for vendor in profile.vendors:
            usage_item = usage_by_provider.get(vendor.slug)

            if vendor.quota_unit == QuotaUnit.area:
                used = float(usage_item.area) if usage_item else 0.0
            else:
                used = float(usage_item.filesize) if usage_item else 0.0

            remaining = max(0.0, vendor.quota - used)
            percentage = (used / vendor.quota * 100) if vendor.quota > 0 else 0.0

            vendor_usages.append(
                VendorQuotaUsage(
                    vendor=vendor.vendor,
                    slug=vendor.slug,
                    quota=vendor.quota,
                    quota_unit=vendor.quota_unit,
                    used=used,
                    remaining=remaining,
                    percentage_used=percentage,
                    approved=vendor.approved,
                    expiration_date=vendor.expiration_date,
                )
            )

        return QuotaSummary(username=username, vendors=vendor_usages)

    def check_quota_available(
        self, username: str, collection_id: str
    ) -> tuple[bool, VendorQuotaUsage | None]:
        """Checks if user has quota available for a given collection.

        Args:
            username: The Earthdata username.
            collection_id: The STAC collection ID (maps to vendor slug).

        Returns:
            Tuple of (has_quota, vendor_usage) where vendor_usage is None
            if the vendor is not found in user's profile.
        """
        quota_summary = self.get_quota_summary(username)

        for vendor in quota_summary.vendors:
            if vendor.slug == collection_id or collection_id.startswith(vendor.slug):
                has_remaining = vendor.remaining > 0 and vendor.approved
                return (has_remaining, vendor)

        return (True, None)

    def vendors(self) -> Iterator[Vendor]:
        """Iterates over all vendors.

        Returns:
            An iterator over all vendors in the CSDA system that you have permissions to see
        """
        response = self.request(method="GET", path="/signup/vendors/api/vendors/")
        for value in response.json():
            yield Vendor.model_validate(value)

    def products(self, vendor_id: int) -> Iterator[Product]:
        """Iterates over all products for a given vendor id.

        Args:
            vendor_id: The id of the vendor

        Returns:
            An iterator over all products that belong to the provided vendor.
        """
        response = self.request(
            method="GET", path=f"/signup/vendors/api/products/?vendor={vendor_id}"
        )
        for value in response.json():
            yield Product.model_validate(value)

    def create_tasking_proposal(
        self, tasking_proposal: CreateTaskingProposal, submit: bool
    ) -> TaskingProposal:
        """Creates a new tasking proposal.

        Args:
            tasking_proposal: The tasking proposal to create
            submit: Whether to submit the tasking proposal, or only save it as a draft

        Returns:
            The created tasking proposal
        """
        path = "/signup/tasking/api/proposals"
        if submit:
            path += "?submit=true"
        response = self.request(
            method="POST",
            path=path,
            json=tasking_proposal.model_dump(mode="json"),
        )
        return TaskingProposal.model_validate(response.json())

    def get_tasking_order_parameters(self, product_id: str) -> OrderParameters:
        """Returns the tasking order parameters for a given STAPI product.

        Args:
            product_id: The STAPI product id

        Returns:
            That product's order parameters
        """
        path = f"/api/v1/stapi/products/{product_id}/order-parameters"
        response = self.request(method="GET", path=path)
        return OrderParameters.model_validate(response.json())

    def create_tasking_request(
        self, product_id: str, order_payload: OrderPayload
    ) -> Order:
        """Creates a new tasking request.

        Args:
            product_id: The STAPI product id
            order_payload: The parameters that will be used to create the order

        Returns:
            The created order
        """
        path = f"/api/v1/stapi/products/{product_id}/orders"
        response = self.request(
            method="POST", path=path, json=order_payload.model_dump(mode="json")
        )
        return Order.model_validate(response.json())

    def _get_url(self, path: str) -> str:
        return urljoin(self.url, path)

    def login(self, auth: Auth) -> None:
        """Log in this client with authentication.

        The retrieved token is saved in the session headers.

        Args:
            auth: The `httpx.Auth` to use for logging in. This is usually either `BasicAuth` or `NetrcAuth`.
        """
        response = self._request_auth(
            "",
            method="GET",
            params={"redirect_uri": self.url},
            follow_redirects=False,
            raise_for_status=False,
        )
        if response.status_code not in (302, 307):
            raise AuthError(
                f"Expected API to respond with a redirect, got {response.status_code}"
            )

        edl_url = response.headers.get("Location", "")
        redirect_path = urlparse(edl_url).path
        if not redirect_path.startswith("/oauth/authorize"):
            raise AuthError(
                f"Expected redirect to /oauth/authorize, got {redirect_path}"
            )

        logger.debug("Authenticating with Earthdata Login...")
        response = self.client.request(url=edl_url, method="GET", auth=auth)
        if response.status_code not in (302, 307):
            raise AuthError(
                "Expected Earthdata Login to respond with a redirect, "
                f"got {response.status_code}: {response.text}"
            )

        querystring = parse_qs(urlparse(response.headers["Location"]).query)
        if (
            querystring.get("error")
            and response.status_code == 302
            and "resolution_url" in response.text
        ):
            start = response.text.find("resolution_url") + len("resolution_url") + 1
            end = response.text.find('"', start)
            raise AuthError(
                "\n".join(
                    [
                        "Authorization required for this application,",
                        "please authorize by visiting the resolution url",
                        response.text[start:end],
                    ]
                )
            )

        if querystring.get("error"):
            raise AuthError(querystring["error_msg"])

        logger.debug("Exchanging authorization code for access token...")
        code = querystring["code"]
        response = self._request_auth("token", method="POST", data={"code": code})
        token = response.json()["access_token"]

        self.client.headers["Authorization"] = f"Bearer {token}"

    def request(
        self,
        method: Method,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        follow_redirects: bool = False,
        auth: Auth | None = None,
        json: dict[str, Any] | None = None,
        raise_for_status: bool = True,
    ) -> Response:
        """Sends a request and returns its response.

        Args:
            method: The HTTP method to use for the request.
            path: The path to make the request, relative to the url provided on client instantiation
            params: Any URL parameters to add to the request
            data: Any data to include in the request body
            follow_redirects: Whether to follow redirects
            auth: A custom auth to use for the request
            json: Any JSON data to include in the request body
            raise_for_status: Whether to raise an exception if the request is not successful

        Returns:
            The response

        Raises:
            HTTPStatusError: Raise if `raise_for_status` is true and the request is not successful
        """
        response = self.client.request(
            method=method,
            url=self._get_url(path),
            params=params,
            data=data,
            follow_redirects=follow_redirects,
            auth=auth,
            json=json,
        )
        if raise_for_status:
            try:
                response.raise_for_status()
            except HTTPStatusError as e:
                logger.error(f"HTTP status error ({e}): {response.text}")
                raise e
        return response

    @contextmanager
    def stream(self, method: Method, path: str) -> Iterator[Response]:
        """Streams a response.

        This method raises an error on an unsuccessful request.

        Args:
            method: The method to use for the streaming request
            path: The path to stream

        Returns:
            A streaming response
        """
        with self.client.stream(
            method=method, url=self._get_url(path), follow_redirects=True
        ) as response:
            response.raise_for_status()
            yield response

    def _request_auth(
        self,
        path: str,
        method: Method,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        follow_redirects: bool = False,
        raise_for_status: bool = True,
    ) -> Response:
        """Sends a request to an auth endpoint."""
        return self.request(
            path=f"/api/v1/auth/{path}",
            method=method,
            params=params,
            data=data,
            follow_redirects=follow_redirects,
            raise_for_status=raise_for_status,
        )
