from functools import lru_cache

from sqlalchemy import Engine, create_engine

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if url is None:
        raise RuntimeError("SAFETRADE_DATABASE_URL n'est pas défini.")
    return create_engine(url.get_secret_value(), pool_pre_ping=True)
