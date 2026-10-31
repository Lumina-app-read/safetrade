"""
Processus du flux de marché : `python -m app.market.worker`.

Plusieurs instances peuvent tourner, par exemple pendant un déploiement : une seule tient le
bail et collecte, les autres attendent et prennent le relais. Chaque instance signale sa
présence, ce qui alimente le contrôle de santé du conteneur.
"""

import asyncio
import json
import logging
import signal
import socket
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.broker.deriv import PUBLIC_WS_URL, DerivConnection
from app.broker.quotas import QuotaManager, RedisQuotaStore
from app.config import Settings, get_settings
from app.logs import configure_json_logs
from app.market.feed import MarketFeed
from app.market.health import presence_key
from app.market.lease import STANDBY_SECONDS, LeadershipLostError, Lease, lead_while_holding
from app.market.store import RedisMarketStore

logger = logging.getLogger("safetrade.market")

PRESENCE_SECONDS = 5.0
PRESENCE_TTL = 30


async def public_url() -> str:
    return PUBLIC_WS_URL


async def signal_presence(client: Redis, role: dict[str, Any]) -> None:
    key = presence_key(socket.gethostname())
    while True:
        try:
            await client.set(key, json.dumps({**role, "at": time.time()}), ex=PRESENCE_TTL)
        except RedisError:
            logger.warning("Redis injoignable", extra={"event": "market.redis_down"})
        await asyncio.sleep(PRESENCE_SECONDS)


async def collect(client: Redis, settings: Settings, owner: str) -> None:
    connection = DerivConnection(
        public_url, QuotaManager(RedisQuotaStore(client)), scope="public", uses_otp=False
    )
    store = RedisMarketStore(client, owner)
    await MarketFeed(connection, store, settings.market_symbols).run()


async def supervise(
    lease: Lease, work: Callable[[], Awaitable[None]], role: dict[str, Any]
) -> None:
    while True:
        try:
            if await lease.acquire():
                role.update(role="leader", since=time.time())
                logger.info(
                    "responsable du flux", extra={"event": "market.leader", "owner": lease.owner}
                )
                await lead_while_holding(lease, work)
        except (LeadershipLostError, RedisError) as exc:
            logger.warning(
                "collecte interrompue",
                extra={"event": "market.collect_stopped", "reason": type(exc).__name__},
            )
        role.update(role="standby", since=time.time())
        await asyncio.sleep(STANDBY_SECONDS)


async def serve(client: Redis, lease: Lease, work: Callable[[], Awaitable[None]]) -> None:
    """
    Annulable : le bail est libéré avant la fin, et le remplaçant prend le relais sans attendre.
    Pas de `gather` ici : il se terminerait dès la première annulation, avant ce nettoyage.
    """
    role: dict[str, Any] = {"owner": lease.owner, "role": "standby", "since": time.time()}
    presence = asyncio.create_task(signal_presence(client, role))
    try:
        await supervise(lease, work, role)
    finally:
        presence.cancel()
        await asyncio.gather(presence, return_exceptions=True)


async def main() -> None:
    settings = get_settings()
    if settings.redis_url is None:
        raise RuntimeError("SAFETRADE_REDIS_URL est obligatoire pour le flux de marché.")
    client = Redis.from_url(settings.redis_url.get_secret_value())
    owner = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
    lease = Lease(client, owner)
    work = asyncio.create_task(serve(client, lease, lambda: collect(client, settings, owner)))
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, work.cancel)
    try:
        await work
    except asyncio.CancelledError:
        logger.info("arrêt demandé", extra={"event": "market.stopped", "owner": owner})


if __name__ == "__main__":
    configure_json_logs()
    asyncio.run(main())
