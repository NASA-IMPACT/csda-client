---
name: csda
description: Search and download NASA CSDA (Commercial SmallSat Data Acquisition) satellite data
allowed-tools: Bash(csda *), Bash(uv run csda *)
---

# CSDA Satellite Data Skill

You have access to the `csda` CLI for searching and downloading commercial satellite data from NASA's CSDA program.

## Prerequisites

The `csda` CLI must be installed:
```bash
pip install csda-client
```

For download commands, set authentication:
```bash
export EARTHDATA_USERNAME="username"
export EARTHDATA_PASSWORD="password"
```

## Available Commands

### List Collections (Vendors)
```bash
csda collections [--pretty]
```
Returns available data vendors: planet, maxar, blacksky, airbus, capellaspace, etc.

### Search for Data
```bash
csda search [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `-c, --collection` | Filter by collection/vendor | `-c planet` |
| `--bbox` | Bounding box (minx,miny,maxx,maxy) | `--bbox -105.1,39.6,-104.8,39.9` |
| `--datetime` | Temporal filter | `--datetime 2024-01-01/2024-12-31` |
| `--filter` | CQL2 property filter | `--filter "eo:cloud_cover<25"` |
| `--sortby` | Sort field (prefix `-` for desc) | `--sortby -datetime` |
| `--limit` | Max items to return | `--limit 10` |
| `--intersects` | GeoJSON geometry file or inline | `--intersects area.geojson` |
| `--pretty` | Human-readable output | `--pretty` |
| `--map` | Include stac-map visualization URLs | `--map` |

### Download Asset
```bash
csda download <collection> <item_id> <asset_key> <output_path> [OPTIONS]
```
Requires authentication. Common asset keys: `thumbnail`, `ortho_visual`, `ortho_analytic_4b`

**Options:**
| Option | Description |
|--------|-------------|
| `--skip-quota-check` | Skip pre-download quota verification |
| `--show-quota` | Display quota before and after download |

By default, the download command checks if you have sufficient quota before downloading.

### Check Quota Usage
```bash
csda quota <username> [--pretty] [--human]
```
Shows quota limits, current usage, and remaining quota per vendor. Use `--human` for a formatted table view. Requires authentication.

### User Profile
```bash
csda profile <username> [--pretty]
```
Shows full user profile including grants and vendor access. Requires authentication.

### Verify Authentication
```bash
csda verify
```

### List Tasking Vendors
```bash
csda vendors [--pretty]
```

### List Vendor Products
```bash
csda products <vendor_id> [--pretty]
```

### Visualize on Map
```bash
csda map <stac_url>
```
Generates a stac-map URL and opens it in your browser.
Works with any STAC item or collection URL.

## Common Workflows

### "What [vendor] data is available over [area]?"
1. Convert area to bbox (minx,miny,maxx,maxy in WGS84)
2. Run search:
```bash
csda search -c planet --bbox -105.1,39.6,-104.8,39.9 --limit 10 --pretty
```

### "Find the latest image with low clouds"
```bash
csda search -c planet --bbox <bbox> --sortby -datetime --filter "eo:cloud_cover<20" --limit 1 --pretty
```

### "What collections are available?"
```bash
csda collections --pretty
```

### "Download thumbnail for item X"
```bash
csda download planet PSScene-20251119_183303_62_24c6 thumbnail ./thumbnail.jpg
```

### "Check my download quota"
```bash
csda quota <username> --human
```
Shows a table with quota limits, usage, and remaining quota for each vendor.

### "Download with quota tracking"
```bash
csda download planet PSScene-123 ortho_visual ./image.tif --show-quota
```
Shows quota before and after the download completes.

### "Download without quota check"
```bash
csda download planet PSScene-123 ortho_visual ./image.tif --skip-quota-check
```
Bypasses pre-download quota verification for faster downloads.

### "Show me search results on a map"
```bash
csda search -c planet --bbox -105.1,39.6,-104.8,39.9 --limit 3 --map --pretty
```
Each result includes a `map` field with a stac-map visualization URL.

### "Visualize this collection/item on a map"
```bash
csda map https://csdap.earthdata.nasa.gov/stac/collections/planet
```
Opens an interactive map in the browser showing the STAC item/collection footprint.

## Output Format

All commands output JSON by default. Use `--pretty` for formatted output.

Search results include:
- `id`: Item identifier
- `collection`: Vendor/collection name
- `datetime`: Acquisition time
- `bbox`: Bounding box
- `cloud_cover`: Cloud cover percentage (if available)
- `link`: Direct link to STAC item
- `map`: stac-map visualization URL (when `--map` flag is used)

## Tips

- Bbox format is `minx,miny,maxx,maxy` (west,south,east,north) in WGS84 degrees
- Use `--sortby -datetime` for newest first, `--sortby datetime` for oldest first
- CQL2 filters: `eo:cloud_cover<25`, `gsd<1.0`, combine with `AND`/`OR`
- Search is public (no auth), download requires Earthdata credentials
