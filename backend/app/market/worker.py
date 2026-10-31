"""Processus dédié au flux de marché : `python -m app.market.worker`."""

import asyncio
import logging

from redis.asyncio import Redis

from app.broker.deriv import PUBLIC_WS_URL, DerivConnection
from app.broker.quotas import QuotaManager, RedisQuotaStore
from app.config import get_settings
from app.market.feed import MarketFeed
from app.market.store import RedisMarketStore


async def public_url() -> str:
    return PUBLIC_WS_URL


async def main() -> None:
    settings = get_settings()
    if settings.redis_url is None:
        raise RuntimeError("SAFETRADE_REDIS_URL est obligatoire pour le flux de marché.")
    client = Redis.from_url(settings.redis_url.get_secret_value())
    connection = DerivConnection(
        public_url, QuotaManager(RedisQuotaStore(client)), scope="public", uses_otp=False
    )
    await MarketFeed(connection, RedisMarketStore(client), settings.market_symbols).run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
