from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class InvoiceSettings(BaseSettings):
    backend: Literal["memory", "sqlite", "postgres", "mysql", "files"] = "memory"
    database_url: str | None = None
    database_echo: bool = False

    # Files backend settings
    file_format: Literal["json", "xml", "md"] = "md"

    template_dir: str | None = None
    output_dir: str = "output"

    # Path for files backend data
    storage_path: str = "./data"

    # HTTP API: every request must send this key in the X-API-Key header.
    # Without it the API refuses all data requests.
    api_key: SecretStr | None = None
    # Browser origins allowed to call the API (CORS); empty allows none.
    cors_origins: list[str] = []

    model_config = SettingsConfigDict(env_prefix="INVOICES_", env_file=".env", extra="ignore")

    @classmethod
    def load(cls, base: Path) -> InvoiceSettings:
        """Settings from the environment and `base`/.env, relative paths resolved against `base`.

        A CLI run passes its working directory (`--cwd`), so the store, templates and output
        directory are the same wherever the process was started.
        """
        settings = cls(_env_file=base / ".env")
        return settings.model_copy(
            update={
                "storage_path": str(base / settings.storage_path),
                "output_dir": str(base / settings.output_dir),
                "template_dir": str(base / settings.template_dir)
                if settings.template_dir
                else None,
            }
        )


@lru_cache
def get_settings() -> InvoiceSettings:
    return InvoiceSettings()
