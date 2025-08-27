from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any, Iterator, Literal
from urllib.parse import parse_qs, urljoin, urlparse

from httpx import Auth, BasicAuth, Client, NetRCAuth, Response
from pystac import Item

from .models import Profile

logger = logging.getLogger(__name__)

Method = Literal["GET"] | Literal["POST"]

STAGING_URL = "https://csdap-staging.ds.io"
PRODUCTION_URL = "https://csdap.earthdata.nasa.gov"


class AuthError(Exception):
    """A custom exception that we raise when something bad happens during authentication."""


def earthdata_auth() -> Auth:
    """Resolve auth from either environment variables or .netrc."""
    username = os.getenv("EARTHDATA_USERNAME")
    password = os.getenv("EARTHDATA_PASSWORD")

    if username and password:
        return BasicAuth(username, password)

    return NetRCAuth()


class CsdaClient:
    """A client for interacting with CSDA services."""

    @classmethod
    def open(cls, auth: Auth | None = None, url: str = PRODUCTION_URL) -> CsdaClient:
        """Opens and logs in a CSDA client."""
        if auth is None:
            auth = earthdata_auth()

        client = CsdaClient(url)
        client.login(auth)
        return client

    def __init__(self, url: str = PRODUCTION_URL) -> None:
        """Creates a new, un-logged-in CSDA client.

        Use `login` to get an auth token.
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
        """Verifies the currently logged in user, returning the response."""
        response = self.request(path="/api/v1/auth/verify", method="GET")
        return response.json()

    def profile(self, username: str) -> Profile:
        response = self.request(
            path=f"/signup/api/users/{username}/",
            method="GET",
        )
        return Profile.model_validate(response.json())

    def download_item(self, item: Item, asset_key: str, path: Path) -> None:
        """Downloads a single asset from a STAC item to a local file."""
        if item.collection_id:
            self.download(item.collection_id, item.id, asset_key, path)
        else:
            raise ValueError("Cannot download an item without a collection id")

    def download(
        self, collection_id: str, item_id: str, asset_key: str, path: Path
    ) -> None:
        """Downloads an asset."""
        request_path = f"/api/v2/download/{collection_id}/{item_id}/{asset_key}"
        with self.stream(method="GET", path=request_path) as response:
            with open(path, "wb") as f:
                for chunk in response.iter_bytes(1024 * 8):
                    if chunk:
                        f.write(chunk)

    def get_url(self, path: str) -> str:
        """Builds a full URL from a path."""
        return urljoin(self.url, path)

    def login(self, auth: Auth) -> None:
        """Log in this client with authentication.

        The retrieved token is saved in the session headers.
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
                f"got {response.status_code}"
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
        """Sends a request and returns its response."""
        response = self.client.request(
            method=method,
            url=self.get_url(path),
            params=params,
            data=data,
            follow_redirects=follow_redirects,
            auth=auth,
            json=json,
        )
        if raise_for_status:
            response.raise_for_status()
        return response

    @contextmanager
    def stream(self, method: Method, path: str) -> Iterator[Response]:
        """Streams a response.

        This method raises an error on an unsuccessful request.
        """
        with self.client.stream(
            method=method, url=self.get_url(path), follow_redirects=True
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
