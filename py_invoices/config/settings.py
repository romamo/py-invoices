from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class InvoiceSettings(BaseSettings):
    backend: Literal["memory", "sqlite", "postgres", "mysql", "files"] = "memory"
    database_url: str | None = None
    database_echo: bool = False

    # Files backend settings
    file_format: Literal["json", "xml", "md"] = "md"

    template_dir: str | None = None
    output_dir: str = "output"

    model_config = SettingsConfigDict(env_prefix="INVOICES_")

@lru_cache
def get_settings() -> InvoiceSettings:
    return InvoiceSettings()
