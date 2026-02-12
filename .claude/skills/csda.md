---
name: csda
description: Search and download NASA CSDA (Commercial SmallSat Data Acquisition) satellite data
tools:
  - Bash
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

### Download Asset
```bash
csda download <collection> <item_id> <asset_key> <output_path>
```
Requires authentication. Common asset keys: `thumbnail`, `ortho_visual`, `ortho_analytic_4b`

### User Profile & Quotas
```bash
csda profile <username> [--pretty]
```
Shows download quotas per vendor. Requires authentication.

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
csda profile <username> --pretty
```

## Output Format

All commands output JSON by default. Use `--pretty` for formatted output.

Search results include:
- `id`: Item identifier
- `collection`: Vendor/collection name
- `datetime`: Acquisition time
- `bbox`: Bounding box
- `cloud_cover`: Cloud cover percentage (if available)
- `link`: Direct link to STAC item

## Tips

- Bbox format is `minx,miny,maxx,maxy` (west,south,east,north) in WGS84 degrees
- Use `--sortby -datetime` for newest first, `--sortby datetime` for oldest first
- CQL2 filters: `eo:cloud_cover<25`, `gsd<1.0`, combine with `AND`/`OR`
- Search is public (no auth), download requires Earthdata credentials
