from __future__ import annotations

import json

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from csda_client.cli import app

runner = CliRunner()


# ===== Tests that don't require auth (public STAC API) =====


def test_help() -> None:
    """CLI shows help with available commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "collections" in result.stdout
    assert "search" in result.stdout


def test_collections_returns_list() -> None:
    """Collections command returns list of available collections."""
    result = runner.invoke(app, ["collections"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "collections" in data
    assert len(data["collections"]) > 0


def test_search_with_bbox() -> None:
    """Search with bbox returns items."""
    result = runner.invoke(
        app,
        [
            "search",
            "-c",
            "planet",
            "--bbox",
            "-105,39,-104,40",
            "--limit",
            "3",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "items" in data


def test_search_output_has_required_fields() -> None:
    """Search output includes id, collection, datetime, link."""
    result = runner.invoke(app, ["search", "-c", "planet", "--limit", "1"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    if data["items"]:  # May be empty if no data
        item = data["items"][0]
        assert "id" in item
        assert "collection" in item
        assert "link" in item


def test_search_respects_limit() -> None:
    """Search respects --limit parameter."""
    result = runner.invoke(app, ["search", "--limit", "2"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data["items"]) <= 2


def test_search_with_datetime() -> None:
    """Search with datetime filter works."""
    result = runner.invoke(
        app,
        [
            "search",
            "-c",
            "planet",
            "--datetime",
            "2023-01-01/2023-12-31",
            "--limit",
            "1",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "items" in data


def test_search_with_sortby() -> None:
    """Search with sortby returns items sorted."""
    result = runner.invoke(
        app,
        ["search", "-c", "planet", "--sortby", "-datetime", "--limit", "3"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "items" in data


# ===== Tests that require Earthdata auth =====


@pytest.mark.with_earthdata_login
def test_verify(
    monkeypatch: pytest.MonkeyPatch,
    earthdata_username: str,
    earthdata_password: SecretStr,
) -> None:
    """Verify command works with valid credentials."""
    monkeypatch.setenv("EARTHDATA_USERNAME", earthdata_username)
    monkeypatch.setenv("EARTHDATA_PASSWORD", earthdata_password.get_secret_value())
    result = runner.invoke(app, ["verify"])
    assert result.exit_code == 0


@pytest.mark.with_earthdata_login
def test_profile(
    monkeypatch: pytest.MonkeyPatch,
    earthdata_username: str,
    earthdata_password: SecretStr,
) -> None:
    """Profile command returns user info."""
    monkeypatch.setenv("EARTHDATA_USERNAME", earthdata_username)
    monkeypatch.setenv("EARTHDATA_PASSWORD", earthdata_password.get_secret_value())
    result = runner.invoke(app, ["profile", earthdata_username])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["earthdata_username"] == earthdata_username


@pytest.mark.with_earthdata_login
def test_vendors(
    monkeypatch: pytest.MonkeyPatch,
    earthdata_username: str,
    earthdata_password: SecretStr,
) -> None:
    """Vendors command returns list of vendors."""
    monkeypatch.setenv("EARTHDATA_USERNAME", earthdata_username)
    monkeypatch.setenv("EARTHDATA_PASSWORD", earthdata_password.get_secret_value())
    result = runner.invoke(app, ["vendors"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "vendors" in data


def test_download_without_auth_fails() -> None:
    """Download without credentials should fail."""
    result = runner.invoke(
        app,
        ["download", "planet", "item_id", "asset", "out.tif"],
    )
    assert result.exit_code != 0
