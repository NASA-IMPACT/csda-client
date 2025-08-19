import os
from typing import Any, Iterator

import pytest
from httpx import BasicAuth, NetRCAuth
from pydantic import SecretStr
from pytest import Config, Parser

from csda_client import CsdaClient


@pytest.fixture(scope="session")
def earthdata_username() -> str:
    try:
        return os.environ["EARTHDATA_USERNAME"]
    except KeyError:
        pytest.skip("EARTHDATA_USERNAME is not set")


@pytest.fixture(scope="session")
def earthdata_password() -> SecretStr:
    try:
        return SecretStr(os.environ["EARTHDATA_PASSWORD"])
    except KeyError:
        pytest.skip("EARTHDATA_PASSWORD is not set")


@pytest.fixture(scope="session")
def basic_auth_client(
    earthdata_username: str, earthdata_password: SecretStr
) -> Iterator[CsdaClient]:
    with CsdaClient.open(
        BasicAuth(earthdata_username, earthdata_password.get_secret_value())
    ) as client:
        yield client


@pytest.fixture(scope="session")
def client() -> Iterator[CsdaClient]:
    with CsdaClient.open(NetRCAuth()) as client:
        yield client


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--with-earthdata-login",
        action="store_true",
        default=False,
        help="run tests that require an Earthdata login",
    )


def pytest_configure(config: Config) -> None:
    config.addinivalue_line(
        "markers",
        "with_earthdata_login: marks tests as requiring Earthdata login, "
        "and disables them by default (enable with --with-earthdata-login)",
    )


def pytest_collection_modifyitems(config: Config, items: Any) -> None:
    if config.getoption("--with-earthdata-login"):
        return
    skip_earthdata_login = pytest.mark.skip(reason="need --with-earthdata-login to run")
    for item in items:
        if "with_earthdata_login" in item.keywords:
            item.add_marker(skip_earthdata_login)
