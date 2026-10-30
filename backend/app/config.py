from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration lue dans les variables d'environnement (préfixe SAFETRADE_)."""

    model_config = SettingsConfigDict(env_prefix="SAFETRADE_", extra="ignore")

    environment: Literal["development", "test", "staging", "production"] = "development"
    # Interrupteur du compte réel : reste désactivé jusqu'à la phase 8.
    real_account_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
