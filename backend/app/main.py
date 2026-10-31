from collections import Counter

from fastapi import FastAPI
from pydantic import BaseModel
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.orm import sessionmaker

from app.admin.router import router as admin_router
from app.auth.mailer import LogMailer, Mailer
from app.auth.rate_limit import FailureCounter, MemoryFailureCounter, RedisFailureCounter
from app.auth.router import router as auth_router
from app.broker.deriv_rest import DerivRest
from app.broker.quotas import MemoryQuotaStore, QuotaManager, RedisQuotaStore
from app.config import Settings, get_settings
from app.db.session import get_engine
from app.deriv.router import router as deriv_router
from app.errors import install_error_handlers
from app.market.router import router as market_router
from app.market.store import MarketStore, RedisMarketStore
from app.trading.router import router as trading_router


class Health(BaseModel):
    status: str
    environment: str


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: sessionmaker | None = None,  # type: ignore[type-arg]
    mailer: Mailer | None = None,
    failures: FailureCounter | None = None,
    deriv: DerivRest | None = None,
    market: MarketStore | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    is_dev = settings.environment == "development"
    app = FastAPI(
        title="SafeTrade API",
        docs_url="/docs" if is_dev else None,
        redoc_url=None,
        openapi_url="/openapi.json" if is_dev else None,
    )
    app.state.settings = settings
    app.state.session_factory = session_factory or (
        sessionmaker(get_engine(), expire_on_commit=False) if settings.database_url else None
    )
    if mailer is None:
        if settings.environment not in ("development", "test"):
            # Aucun fournisseur d'e-mails choisi : jamais d'envoi simulé hors développement.
            raise RuntimeError("Aucun fournisseur d'e-mails configuré.")
        mailer = LogMailer()
    app.state.mailer = mailer
    if settings.encryption_key is None and settings.environment not in ("development", "test"):
        raise RuntimeError("SAFETRADE_ENCRYPTION_KEY est obligatoire hors développement.")
    if failures is None:
        if not settings.redis_url and settings.environment not in ("development", "test"):
            # Compteurs en mémoire = limite contournable avec plusieurs instances.
            raise RuntimeError("SAFETRADE_REDIS_URL est obligatoire hors développement.")
        failures = (
            RedisFailureCounter(Redis.from_url(settings.redis_url.get_secret_value()))
            if settings.redis_url
            else MemoryFailureCounter()
        )
    app.state.failures = failures
    if deriv is None and settings.deriv_app_id:
        store = (
            RedisQuotaStore(AsyncRedis.from_url(settings.redis_url.get_secret_value()))
            if settings.redis_url
            else MemoryQuotaStore()
        )
        deriv = DerivRest(
            settings.deriv_app_id,
            QuotaManager(store),
            real_account_enabled=settings.real_account_enabled,
        )
    app.state.deriv = deriv
    if market is None and settings.redis_url:
        market = RedisMarketStore(AsyncRedis.from_url(settings.redis_url.get_secret_value()))
    app.state.market = market
    app.state.market_streams = Counter()

    install_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(deriv_router)
    app.include_router(market_router)
    app.include_router(trading_router)

    @app.get("/health", response_model=Health, tags=["system"])
    def health() -> Health:
        return Health(status="ok", environment=settings.environment)

    return app


app = create_app()
