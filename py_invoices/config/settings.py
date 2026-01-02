from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class InvoiceSettings(BaseSettings):
    backend: str = "memory"
    # database_url: str | None = None # For future SQL backends
    
    model_config = SettingsConfigDict(env_prefix="PY_INVOICES_")

@lru_cache
def get_settings() -> InvoiceSettings:
    return InvoiceSettings()
