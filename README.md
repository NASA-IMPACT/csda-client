# CSDA client

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/nasa-impact/csda-client/ci.yaml?style=for-the-badge)](https://github.com/NASA-IMPACT/csda-client/actions/workflows/ci.yaml)

An API client for [CSDA](https://csdap.earthdata.nasa.gov/).

## Usage

```shell
python -m pip install git+https://github.com/nasa-impact/csda-client
```

See our [docs](https://nasa-impact.github.io/csda-client) for more.

## Issues

Please open [Github issues](https://github.com/NASA-IMPACT/csda-client/issues) with any bug reports, feature requests, and questions.

## Development

Get [uv](https://docs.astral.sh/uv/getting-started/installation/).
Then:

```sh
git clone git@github.com:NASA-IMPACT/csda-client.git
cd csda-client
uv sync
```

### Tests

Many of our tests run requests against the production system, which requires an [Earthdata login](https://urs.earthdata.nasa.gov/).
These are skipped by default.
To enable them, create a `.env` file with the following values:

```env
EARTHDATA_USERNAME=your-user-name
EARTHDATA_PASSWORD=your-password
```

We also allow `.netrc` authentication, so set that up per [these instructions](https://nsidc.org/data/user-resources/help-center/creating-netrc-file-earthdata-login)
Then:

```sh
uv run pytest --with-earthdata-login
```

### Documentation

To build and serve the documentation:

```sh
uv run mkdocs serve
```

They'll be available on <http://127.0.0.1:8000/csda-client/>.

## License

MIT
