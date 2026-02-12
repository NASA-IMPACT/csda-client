from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Optional

import typer
from httpx import BasicAuth, NetRCAuth
from pystac_client import Client as StacClient

from csda_client import PRODUCTION_URL, STAGING_URL, CsdaClient

app = typer.Typer(help="CSDA CLI - Search and download satellite data from NASA CSDA")


def get_stac_url(staging: bool = False) -> str:
    """Get the STAC API URL."""
    return f"{STAGING_URL}/stac/" if staging else f"{PRODUCTION_URL}/stac/"


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


def get_authenticated_client(staging: bool = False) -> CsdaClient:
    """Get an authenticated CsdaClient."""
    auth = get_auth()
    if auth is None:
        typer.echo(
            "Error: No credentials found. Set EARTHDATA_USERNAME and EARTHDATA_PASSWORD "
            "environment variables or configure ~/.netrc",
            err=True,
        )
        raise typer.Exit(1)

    url = STAGING_URL if staging else PRODUCTION_URL
    return CsdaClient.open(auth, url)


def format_item_summary(item: dict) -> dict:
    """Format a STAC item as a summary with essential fields."""
    properties = item.get("properties", {})
    links = item.get("links", [])

    # Find self link
    self_link = next(
        (link["href"] for link in links if link.get("rel") == "self"), None
    )

    return {
        "id": item.get("id"),
        "collection": item.get("collection"),
        "datetime": properties.get("datetime"),
        "bbox": item.get("bbox"),
        "cloud_cover": properties.get("eo:cloud_cover"),
        "link": self_link,
    }


@app.command()
def collections(
    staging: Annotated[
        bool, typer.Option("--staging", help="Use staging environment")
    ] = False,
    pretty: Annotated[
        bool, typer.Option("--pretty", help="Pretty print JSON output")
    ] = False,
) -> None:
    """List available STAC collections (vendors/datasets)."""
    stac_url = get_stac_url(staging)
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
    staging: Annotated[
        bool, typer.Option("--staging", help="Use staging environment")
    ] = False,
    pretty: Annotated[
        bool, typer.Option("--pretty", help="Pretty print JSON output")
    ] = False,
) -> None:
    """Search for STAC items with spatial/temporal/property filters."""
    stac_url = get_stac_url(staging)
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
        items = list(search_result.items())
    except Exception as e:
        typer.echo(f"Search error: {e}", err=True)
        raise typer.Exit(1)

    # Format output
    items_summary = [format_item_summary(item.to_dict()) for item in items]
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
    staging: Annotated[
        bool, typer.Option("--staging", help="Use staging environment")
    ] = False,
) -> None:
    """Download a STAC item asset."""
    with get_authenticated_client(staging) as client:
        try:
            client.download(collection_id, item_id, asset_key, Path(output_path))
            typer.echo(json.dumps({"status": "success", "path": output_path}))
        except Exception as e:
            typer.echo(f"Download error: {e}", err=True)
            raise typer.Exit(1)


@app.command()
def verify(
    staging: Annotated[
        bool, typer.Option("--staging", help="Use staging environment")
    ] = False,
    pretty: Annotated[
        bool, typer.Option("--pretty", help="Pretty print JSON output")
    ] = False,
) -> None:
    """Verify authentication is working."""
    with get_authenticated_client(staging) as client:
        result = client.verify()
        indent = 2 if pretty else None
        typer.echo(json.dumps(result, indent=indent, default=str))


@app.command()
def profile(
    username: Annotated[str, typer.Argument(help="Earthdata username")],
    staging: Annotated[
        bool, typer.Option("--staging", help="Use staging environment")
    ] = False,
    pretty: Annotated[
        bool, typer.Option("--pretty", help="Pretty print JSON output")
    ] = False,
) -> None:
    """Get user profile with quotas and permissions."""
    with get_authenticated_client(staging) as client:
        result = client.profile(username)
        indent = 2 if pretty else None
        typer.echo(
            json.dumps(result.model_dump(mode="json"), indent=indent, default=str)
        )


@app.command()
def vendors(
    staging: Annotated[
        bool, typer.Option("--staging", help="Use staging environment")
    ] = False,
    pretty: Annotated[
        bool, typer.Option("--pretty", help="Pretty print JSON output")
    ] = False,
) -> None:
    """List available tasking vendors."""
    with get_authenticated_client(staging) as client:
        vendors_list = [v.model_dump(mode="json") for v in client.vendors()]
        output = {"vendors": vendors_list}
        indent = 2 if pretty else None
        typer.echo(json.dumps(output, indent=indent, default=str))


@app.command()
def products(
    vendor_id: Annotated[int, typer.Argument(help="Vendor ID")],
    staging: Annotated[
        bool, typer.Option("--staging", help="Use staging environment")
    ] = False,
    pretty: Annotated[
        bool, typer.Option("--pretty", help="Pretty print JSON output")
    ] = False,
) -> None:
    """List products for a vendor."""
    with get_authenticated_client(staging) as client:
        products_list = [p.model_dump(mode="json") for p in client.products(vendor_id)]
        output = {"products": products_list}
        indent = 2 if pretty else None
        typer.echo(json.dumps(output, indent=indent, default=str))


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
