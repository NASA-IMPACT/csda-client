"""csda-client is a library for interacting with CSDA API services."""

from .client import PRODUCTION_URL, STAGING_URL, CsdaClient

__all__ = ["CsdaClient", "PRODUCTION_URL", "STAGING_URL"]
