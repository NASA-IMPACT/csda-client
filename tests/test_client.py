from pathlib import Path

import pytest

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
def test_profile(client: CsdaClient, earthdata_username: str) -> None:
    profile = client.profile()
    assert profile.earthdata_username == earthdata_username
