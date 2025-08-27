from pathlib import Path

import pytest
from conftest import get_username_from_netrc

from csda_client.client import CsdaClient


@pytest.mark.with_earthdata_login
def test_open(netrc_client: CsdaClient) -> None:
    netrc_client.verify()


@pytest.mark.with_earthdata_login
def test_download(netrc_client: CsdaClient, tmp_path: Path) -> None:
    netrc_client.download(
        "planet",
        "PSScene-20160606_222940_0c74",
        "thumbnail",
        tmp_path / "thumbnail.jpg",
    )


@pytest.mark.with_earthdata_login
def test_profile_edl(basic_auth_client: CsdaClient, earthdata_username: str) -> None:
    profile = basic_auth_client.profile(earthdata_username)
    assert profile.earthdata_username == earthdata_username


@pytest.mark.with_earthdata_login
def test_profile_netrc(netrc_client: CsdaClient) -> None:
    username = get_username_from_netrc()
    assert username
    profile = netrc_client.profile(str(username))
    assert profile.earthdata_username == username
