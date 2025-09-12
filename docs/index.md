# csda-client

**csda-client** is a Python client for interacting with NASA's Commercial Satellite Data Acquisition (CSDA) APIs.

## Quickstart

Install **csda-client** via `pip`:

```shell
python -m pip install git+https://github.com/NASA-IMPACT/csda-client
```

!!! note

    **csda-client** is not yet available via [PyPI](https://pypi.org/), but we plan to publish it there [soon](https://github.com/NASA-IMPACT/csda-client/issues/44).

Then:

```python
from csda_client import CsdaClient
from httpx import BasicAuth

auth = BasicAuth(username="your-earthdata-username", password="your-earthdata-password")
client = CsdaClient.open(auth)
client.verify()
```

See our [search and download notebook](./examples/search-and-download.ipynb) for an example of finding and downloading data from the CSDA system.

## Authentication

We use [httpx authentication](https://www.python-httpx.org/advanced/authentication/) to verify your [Earthdata login](https://urs.earthdata.nasa.gov) credentials, which we use for CSDA API access.
You can use `BasicAuth` as demonstrated above, but we recommend setting up `.netrc` authentication to avoid putting your password in code.
To set up `.netrc`:

1. Follow the instructions [here](https://nsidc.org/data/user-resources/help-center/creating-netrc-file-earthdata-login)
2. Provide a `NetrcAuth` to `CsdaClient.open`:

    ```python
    from csda_client import CsdaClient
    from https import NetrcAuth

    client = CsdaClient.open(NetrcAuth())
    ```
