from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration lue dans les variables d'environnement (préfixe SAFETRADE_)."""

    model_config = SettingsConfigDict(env_prefix="SAFETRADE_", extra="ignore")

    environment: Literal["development", "test", "staging", "production"] = "development"
    # Interrupteur du compte réel : reste désactivé jusqu'à la phase 8.
    real_account_enabled: bool = False
    # Exemple : postgresql+psycopg://utilisateur:motdepasse@hote:5432/safetradev2.
    # SecretStr : l'adresse contient le mot de passe, jamais affichée dans un journal.
    database_url: SecretStr | None = None
    redis_url: SecretStr | None = None

    # Adresse publique du front-end, pour les liens envoyés par e-mail.
    public_app_url: str = "http://127.0.0.1:13000"
    # Origines autorisées à appeler l'API avec des cookies (contrôle anti-CSRF).
    allowed_origins: list[str] = ["http://127.0.0.1:13000", "http://localhost:13000"]

    # Sessions courtes : expiration après inactivité, et durée maximale absolue.
    session_idle_minutes: int = 30
    session_absolute_hours: int = 12
    # Cookie Secure obligatoire, sauf développement local en HTTP (désactivé explicitement).
    session_cookie_secure: bool = True
    email_verification_hours: int = 24

    # Protection contre le brute force (fenêtre glissante de 15 minutes).
    login_max_failures_per_email: int = 5
    login_max_failures_per_ip: int = 20
    login_failure_window_seconds: int = 15 * 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
