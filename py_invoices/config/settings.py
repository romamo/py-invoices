"""Settings configuration for py-invoices using Pydantic Settings."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class InvoiceSettings(BaseSettings):
    """Configuration for py-invoices.

    Settings can be loaded from:
    - Environment variables (prefixed with INVOICES_)
    - .env file in the current directory
    - Programmatically via constructor

    Example:
        >>> # From environment variables
        >>> import os
        >>> os.environ["INVOICES_BACKEND"] = "sqlite"
        >>> os.environ["INVOICES_DATABASE_URL"] = "sqlite:///invoices.db"
        >>> settings = InvoiceSettings()

        >>> # Programmatically
        >>> settings = InvoiceSettings(
        ...     backend="sqlite",
        ...     database_url="sqlite:///invoices.db"
        ... )
    """

    model_config = SettingsConfigDict(
        env_prefix="INVOICES_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Backend configuration
    backend: Literal["memory", "sqlite", "postgres"] = "memory"
    database_url: str | None = None
    database_echo: bool = False

    # PDF configuration
    template_dir: str | None = None
    output_dir: str = "output"
