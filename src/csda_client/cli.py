from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Optional

import typer
from httpx import BasicAuth, NetRCAuth
from pystac_client import Client as StacClient

from csda_client import PRODUCTION_URL, STAGING_URL, CsdaClient
from csda_client.models import QuotaUnit

app = typer.Typer(help="CSDA CLI - Search and download satellite data from NASA CSDA")


def get_stac_url(prod: bool = False) -> str:
    """Get the STAC API URL."""
    return f"{PRODUCTION_URL}/stac/" if prod else f"{STAGING_URL}/stac/"


def get_auth() -> BasicAuth | NetRCAuth | None:
    """Get authentication from environment or netrc."""
    username = os.environ.get("EARTHDATA_USERNAME")
    password = os.environ.get("EARTHDATA_PASSWORD")

    if username and password:
        return BasicAuth(username, password)

    # Try netrc
    try:
        return NetRCAuth()
    except Exception:
        return None


def get_authenticated_client(prod: bool = False) -> CsdaClient:
    """Get an authenticated CsdaClient."""
    auth = get_auth()
    if auth is None:
        typer.echo(
            "Error: No credentials found. Set EARTHDATA_USERNAME and EARTHDATA_PASSWORD "
            "environment variables or configure ~/.netrc",
            err=True,
        )
        raise typer.Exit(1)

    url = PRODUCTION_URL if prod else STAGING_URL
    return CsdaClient.open(auth, url)


STAC_MAP_BASE_URL = "https://developmentseed.org/stac-map/"


def get_stac_map_url(stac_url: str) -> str:
    """Generate a stac-map visualization URL for a STAC item or collection."""
    from urllib.parse import quote

    return f"{STAC_MAP_BASE_URL}?href={quote(stac_url, safe='')}"


def format_item_summary(item: dict, include_map: bool = False) -> dict:
    """Format a STAC item as a summary with essential fields."""
    properties = item.get("properties", {})
    links = item.get("links", [])

    # Find self link
    self_link = next(
        (link["href"] for link in links if link.get("rel") == "self"), None
    )

    result = {
        "id": item.get("id"),
        "collection": item.get("collection"),
        "datetime": properties.get("datetime"),
        "bbox": item.get("bbox"),
        "cloud_cover": properties.get("eo:cloud_cover"),
        "link": self_link,
    }

    if include_map and self_link:
        result["map"] = get_stac_map_url(self_link)

    return result


def format_size(bytes_value: float) -> str:
    """Format bytes as human-readable size."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(bytes_value) < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def format_area(sq_km: float) -> str:
    """Format area as human-readable string."""
    if sq_km >= 1_000_000:
        return f"{sq_km / 1_000_000:.2f} M sq km"
    elif sq_km >= 1000:
        return f"{sq_km / 1000:.2f} K sq km"
    else:
        return f"{sq_km:.1f} sq km"


def format_quota_value(value: float, unit: QuotaUnit) -> str:
    """Format a quota value based on its unit type."""
    if unit == QuotaUnit.filesize:
        return format_size(value)
    else:
        return format_area(value)


@app.command()
def collections(
    prod: Annotated[
        bool, typer.Option("--prod", help="Use production environment")
    ] = False,
    pretty: Annotated[
        bool, typer.Option("--pretty", help="Pretty print JSON output")
    ] = False,
) -> None:
    """List available STAC collections (vendors/datasets)."""
    stac_url = get_stac_url(prod)
    client = StacClient.open(stac_url)

    # Use collection_search().collections_as_dicts() to avoid parsing errors
    # with some collections that have invalid STAC metadata
    collections_list = []
    for collection in client.collection_search().collections_as_dicts():
        collections_list.append(
            {
                "id": collection.get("id"),
                "title": collection.get("title"),
                "description": collection.get("description"),
            }
        )

    output = {"collections": collections_list}
    indent = 2 if pretty else None
    typer.echo(json.dumps(output, indent=indent))


@app.command()
def search(
    collection: Annotated[
        Optional[list[str]],
        typer.Option("-c", "--collection", help="Collection ID(s) to search"),
    ] = None,
    bbox: Annotated[
        Optional[str],
        typer.Option("--bbox", help="Bounding box: minx,miny,maxx,maxy"),
    ] = None,
    intersects: Annotated[
        Optional[str],
        typer.Option(
            "--intersects", help="GeoJSON geometry (file path or inline JSON)"
        ),
    ] = None,
    datetime: Annotated[
        Optional[str],
        typer.Option(
            "--datetime", help="Datetime filter: YYYY-MM-DD or YYYY-MM-DD/YYYY-MM-DD"
        ),
    ] = None,
    filter: Annotated[
        Optional[str],
        typer.Option(
            "--filter", help="CQL2 filter expression (e.g., eo:cloud_cover<25)"
        ),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum items to return")] = 10,
    sortby: Annotated[
        Optional[str],
        typer.Option(
            "--sortby",
            help="Sort field (prefix with - for descending, e.g., -datetime)",
        ),
    ] = None,
    prod: Annotated[
        bool, typer.Option("--prod", help="Use production environment")
    ] = False,
    pretty: Annotated[
        bool, typer.Option("--pretty", help="Pretty print JSON output")
    ] = False,
    map_urls: Annotated[
        bool, typer.Option("--map", help="Include stac-map visualization URLs")
    ] = False,
) -> None:
    """Search for STAC items with spatial/temporal/property filters."""
    stac_url = get_stac_url(prod)
    client = StacClient.open(stac_url)

    # Parse bbox
    bbox_list = None
    if bbox:
        try:
            bbox_list = [float(x.strip()) for x in bbox.split(",")]
            if len(bbox_list) != 4:
                raise ValueError("bbox must have 4 values")
        except ValueError as e:
            typer.echo(f"Error parsing bbox: {e}", err=True)
            raise typer.Exit(1)

    # Parse intersects (GeoJSON)
    intersects_geom = None
    if intersects:
        try:
            # Check if it's a file path
            if Path(intersects).exists():
                with open(intersects) as f:
                    intersects_geom = json.load(f)
            else:
                intersects_geom = json.loads(intersects)
        except (json.JSONDecodeError, OSError) as e:
            typer.echo(f"Error parsing intersects geometry: {e}", err=True)
            raise typer.Exit(1)

    # Parse sortby
    sortby_list = None
    if sortby:
        if sortby.startswith("-"):
            sortby_list = [{"field": sortby[1:], "direction": "desc"}]
        else:
            sortby_list = [{"field": sortby, "direction": "asc"}]

    # Build search kwargs
    search_kwargs: dict = {
        "max_items": limit,
    }

    if collection:
        search_kwargs["collections"] = collection
    if bbox_list:
        search_kwargs["bbox"] = bbox_list
    if intersects_geom:
        search_kwargs["intersects"] = intersects_geom
    if datetime:
        search_kwargs["datetime"] = datetime
    if filter:
        # CQL2 filter - pystac-client supports this via filter parameter
        search_kwargs["filter"] = filter
        search_kwargs["filter_lang"] = "cql2-text"
    if sortby_list:
        search_kwargs["sortby"] = sortby_list

    # Execute search
    try:
        search_result = client.search(**search_kwargs)
        # Use items_as_dicts() to avoid parsing errors with items
        # that have invalid STAC metadata (e.g., missing 'type' attribute)
        items = list(search_result.items_as_dicts())
    except Exception as e:
        typer.echo(f"Search error: {e}", err=True)
        raise typer.Exit(1)

    # Format output
    items_summary = [format_item_summary(item, include_map=map_urls) for item in items]
    output = {
        "matched": search_result.matched()
        if hasattr(search_result, "matched")
        else None,
        "returned": len(items_summary),
        "items": items_summary,
    }

    indent = 2 if pretty else None
    typer.echo(json.dumps(output, indent=indent, default=str))


@app.command()
def download(
    collection_id: Annotated[str, typer.Argument(help="STAC collection ID")],
    item_id: Annotated[str, typer.Argument(help="STAC item ID")],
    asset_key: Annotated[str, typer.Argument(help="Asset key to download")],
    output_path: Annotated[str, typer.Argument(help="Output file path")],
    prod: Annotated[
        bool, typer.Option("--prod", help="Use production environment")
    ] = False,
    skip_quota_check: Annotated[
        bool,
        typer.Option("--skip-quota-check", help="Skip pre-download quota verification"),
    ] = False,
    show_quota: Annotated[
        bool, typer.Option("--show-quota", help="Show quota before and after download")
    ] = False,
) -> None:
    """Download a STAC item asset.

    By default, checks quota availability before downloading.
    Use --skip-quota-check to bypass this verification.
    """
    from httpx import HTTPStatusError

    with get_authenticated_client(prod) as client:
        # Get username for quota checks
        try:
            username = client.get_username()
        except Exception as e:
            typer.echo(f"Error: Could not determine username: {e}", err=True)
            raise typer.Exit(1)

        # Pre-download quota check
        vendor_usage_before = None
        if not skip_quota_check or show_quota:
            try:
                has_quota, vendor_usage_before = client.check_quota_available(
                    username, collection_id
                )

                if not skip_quota_check and vendor_usage_before is not None:
                    if not has_quota:
                        typer.echo(
                            f"Error: Insufficient quota for {collection_id}. "
                            f"Remaining: {format_quota_value(vendor_usage_before.remaining, vendor_usage_before.quota_unit)}",
                            err=True,
                        )
                        typer.echo(
                            "Use --skip-quota-check to attempt download anyway.",
                            err=True,
                        )
                        raise typer.Exit(1)

                if show_quota and vendor_usage_before:
                    typer.echo(
                        f"Quota before download - "
                        f"Used: {format_quota_value(vendor_usage_before.used, vendor_usage_before.quota_unit)}, "
                        f"Remaining: {format_quota_value(vendor_usage_before.remaining, vendor_usage_before.quota_unit)}",
                        err=True,
                    )
            except HTTPStatusError as e:
                if not skip_quota_check:
                    typer.echo(f"Warning: Could not check quota: {e}", err=True)

        # Perform download
        try:
            client.download(collection_id, item_id, asset_key, Path(output_path))
        except HTTPStatusError as e:
            if e.response.status_code == 403:
                error_body = e.response.text
                if "quota" in error_body.lower() or "exceeded" in error_body.lower():
                    typer.echo(
                        f"Error: Download failed - quota exceeded for {collection_id}",
                        err=True,
                    )
                    typer.echo(
                        f"Check your quota with: csda quota {username}",
                        err=True,
                    )
                else:
                    typer.echo(f"Error: Access denied (403): {error_body}", err=True)
                raise typer.Exit(1)
            else:
                typer.echo(f"Download error: {e}", err=True)
                raise typer.Exit(1)
        except Exception as e:
            typer.echo(f"Download error: {e}", err=True)
            raise typer.Exit(1)

        # Post-download quota display
        if show_quota:
            try:
                _, vendor_usage_after = client.check_quota_available(
                    username, collection_id
                )
                if vendor_usage_after:
                    typer.echo(
                        f"Quota after download - "
                        f"Used: {format_quota_value(vendor_usage_after.used, vendor_usage_after.quota_unit)}, "
                        f"Remaining: {format_quota_value(vendor_usage_after.remaining, vendor_usage_after.quota_unit)}",
                        err=True,
                    )
            except Exception:
                pass  # Non-critical, don't fail the download

        typer.echo(json.dumps({"status": "success", "path": output_path}))


@app.command()
def verify(
    prod: Annotated[
        bool, typer.Option("--prod", help="Use production environment")
    ] = False,
    pretty: Annotated[
        bool, typer.Option("--pretty", help="Pretty print JSON output")
    ] = False,
) -> None:
    """Verify authentication is working."""
    with get_authenticated_client(prod) as client:
        result = client.verify()
        indent = 2 if pretty else None
        typer.echo(json.dumps(result, indent=indent, default=str))


@app.command()
def profile(
    username: Annotated[str, typer.Argument(help="Earthdata username")],
    prod: Annotated[
        bool, typer.Option("--prod", help="Use production environment")
    ] = False,
    pretty: Annotated[
        bool, typer.Option("--pretty", help="Pretty print JSON output")
    ] = False,
) -> None:
    """Get user profile with quotas and permissions."""
    with get_authenticated_client(prod) as client:
        result = client.profile(username)
        indent = 2 if pretty else None
        typer.echo(
            json.dumps(result.model_dump(mode="json"), indent=indent, default=str)
        )


@app.command()
def quota(
    username: Annotated[str, typer.Argument(help="Earthdata username")],
    prod: Annotated[
        bool, typer.Option("--prod", help="Use production environment")
    ] = False,
    pretty: Annotated[
        bool, typer.Option("--pretty", help="Pretty print JSON output")
    ] = False,
    human_readable: Annotated[
        bool, typer.Option("--human", "-H", help="Human-readable table format")
    ] = False,
) -> None:
    """Check download quota usage for a user.

    Shows quota limits, current usage, and remaining quota for each vendor.
    """
    with get_authenticated_client(prod) as client:
        try:
            summary = client.get_quota_summary(username)

            if human_readable:
                typer.echo(f"\nQuota Summary for {username}\n")
                typer.echo("-" * 75)
                typer.echo(
                    f"{'Vendor':<20} {'Quota':<15} {'Used':<15} "
                    f"{'Remaining':<15} {'%Used':<8}"
                )
                typer.echo("-" * 75)

                for v in summary.vendors:
                    status = "" if v.approved else " (not approved)"

                    quota_str = format_quota_value(v.quota, v.quota_unit)
                    used_str = format_quota_value(v.used, v.quota_unit)
                    remaining_str = format_quota_value(v.remaining, v.quota_unit)
                    pct_str = f"{v.percentage_used:.1f}%"

                    typer.echo(
                        f"{v.vendor:<20} {quota_str:<15} {used_str:<15} "
                        f"{remaining_str:<15} {pct_str:<8}{status}"
                    )

                typer.echo("-" * 75)
            else:
                indent = 2 if pretty else None
                typer.echo(
                    json.dumps(
                        summary.model_dump(mode="json"), indent=indent, default=str
                    )
                )
        except Exception as e:
            typer.echo(f"Error fetching quota: {e}", err=True)
            raise typer.Exit(1)


@app.command()
def vendors(
    prod: Annotated[
        bool, typer.Option("--prod", help="Use production environment")
    ] = False,
    pretty: Annotated[
        bool, typer.Option("--pretty", help="Pretty print JSON output")
    ] = False,
) -> None:
    """List available tasking vendors."""
    with get_authenticated_client(prod) as client:
        vendors_list = [v.model_dump(mode="json") for v in client.vendors()]
        output = {"vendors": vendors_list}
        indent = 2 if pretty else None
        typer.echo(json.dumps(output, indent=indent, default=str))


@app.command()
def products(
    vendor_id: Annotated[int, typer.Argument(help="Vendor ID")],
    prod: Annotated[
        bool, typer.Option("--prod", help="Use production environment")
    ] = False,
    pretty: Annotated[
        bool, typer.Option("--pretty", help="Pretty print JSON output")
    ] = False,
) -> None:
    """List products for a vendor."""
    with get_authenticated_client(prod) as client:
        products_list = [p.model_dump(mode="json") for p in client.products(vendor_id)]
        output = {"products": products_list}
        indent = 2 if pretty else None
        typer.echo(json.dumps(output, indent=indent, default=str))


@app.command()
def map(
    stac_url: Annotated[str, typer.Argument(help="STAC item or collection URL")],
) -> None:
    """Generate a stac-map visualization URL for a STAC item or collection.

    Opens the URL in your browser if possible.

    Examples:
        csda map https://csdap.earthdata.nasa.gov/stac/collections/planet
        csda map https://csdap.earthdata.nasa.gov/stac/collections/planet/items/PSScene-123
    """
    map_url = get_stac_map_url(stac_url)
    typer.echo(map_url)

    # Try to open in browser
    try:
        import webbrowser

        webbrowser.open(map_url)
    except Exception:
        pass  # Silently fail if browser can't be opened


@app.command("install-skill")
def install_skill(
    global_install: Annotated[
        bool,
        typer.Option("--global", "-g", help="Install to ~/.claude/skills (user-wide)"),
    ] = False,
) -> None:
    """Install the CSDA skill for Claude Code.

    By default, installs to .claude/skills/ in the current directory.
    Use --global to install to ~/.claude/skills/ for user-wide access.
    """
    from importlib.resources import files

    # Determine destination
    if global_install:
        dest_dir = Path.home() / ".claude" / "skills"
    else:
        dest_dir = Path.cwd() / ".claude" / "skills"

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / "csda.md"

    # Get the skill file from package resources
    skill_source = files("csda_client.skills").joinpath("csda.md")
    with skill_source.open("r") as src:
        content = src.read()

    dest_file.write_text(content)
    typer.echo(f"Installed CSDA skill to {dest_file}")
    typer.echo("\nUsage: Type /csda in Claude Code to use the skill.")


@app.command("show-skill")
def show_skill() -> None:
    """Print the CSDA skill file contents."""
    from importlib.resources import files

    skill_source = files("csda_client.skills").joinpath("csda.md")
    with skill_source.open("r") as src:
        typer.echo(src.read())


if __name__ == "__main__":
    app()
