from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from csda_client.client import CsdaClient


@pytest.mark.with_earthdata_login
def test_open(client: CsdaClient) -> None:
    client.verify()


@pytest.mark.with_earthdata_login
def test_download(client: CsdaClient, tmp_path: Path) -> None:
    client.download(
        "planet",
        "PSScene-20160606_222940_0c74",
        "thumbnail",
        tmp_path / "thumbnail.jpg",
    )


@pytest.mark.with_earthdata_login
def test_profile(basic_auth_client: CsdaClient, earthdata_username: str) -> None:
    profile = basic_auth_client.profile(earthdata_username)
    assert profile.earthdata_username == earthdata_username


@pytest.mark.with_earthdata_login
def test_httpx_client_injection(
    earthdata_username: str, earthdata_password: SecretStr
) -> None:
    httpx_client = httpx.Client(verify=False)

    csda_client = CsdaClient(httpx_client=httpx_client)
    assert csda_client.client is httpx_client

    auth = httpx.BasicAuth(earthdata_username, earthdata_password.get_secret_value())
    csda_client = CsdaClient.open(auth=auth, httpx_client=httpx_client)
    assert csda_client.client is httpx_client
