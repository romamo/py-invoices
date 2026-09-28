"""API key authentication."""

import secrets

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from py_invoices.config import InvoiceSettings, get_settings

API_KEY_HEADER = "X-API-Key"

_api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def get_api_settings() -> InvoiceSettings:
    return get_settings()


def require_api_key(
    provided: str | None = Security(_api_key_header),
    settings: InvoiceSettings = Depends(get_api_settings),
) -> None:
    """Reject the request unless it carries the configured API key."""
    if settings.api_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key not configured; set INVOICES_API_KEY on the server",
        )
    expected = settings.api_key.get_secret_value().encode()
    if provided is None or not secrets.compare_digest(provided.encode(), expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing or invalid {API_KEY_HEADER} header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
