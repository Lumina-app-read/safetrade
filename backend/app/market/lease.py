"""
Bail de responsable : un seul worker collecte et publie les données de marché.

Le bail expire seul si son détenteur disparaît. Un worker gelé puis réveillé ne peut plus
rien publier : chaque écriture du flux vérifie le bail dans Redis, de façon atomique
(`RedisMarketStore`). Le renouvellement n'est donc qu'une détection rapide, pas la garantie.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger("safetrade.market")

LEASE_KEY = "market:leader"
LEASE_SECONDS = 15
RENEW_SECONDS = 5.0
STANDBY_SECONDS = 3.0

_RENEW = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
redis.call('EXPIRE', KEYS[1], ARGV[2])
return 1
"""

_RELEASE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
redis.call('DEL', KEYS[1])
return 1
"""


class LeadershipLostError(Exception):
    """Écriture refusée : ce worker n'est pas, ou plus, le responsable."""


class Lease:
    def __init__(self, client: Redis, owner: str, seconds: int = LEASE_SECONDS) -> None:
        self.owner = owner
        self._client = client
        self._seconds = seconds
        self._renew = client.register_script(_RENEW)
        self._release = client.register_script(_RELEASE)

    async def acquire(self) -> bool:
        return bool(await self._client.set(LEASE_KEY, self.owner, nx=True, ex=self._seconds))

    async def renew(self) -> bool:
        return bool(await self._renew(keys=[LEASE_KEY], args=[self.owner, self._seconds]))

    async def release(self) -> None:
        await self._release(keys=[LEASE_KEY], args=[self.owner])


async def lead_while_holding(
    lease: Lease,
    work: Callable[[], Awaitable[None]],
    *,
    renew_seconds: float = RENEW_SECONDS,
) -> None:
    """Exécute `work` tant que le bail est tenu ; rend la main dès qu'il est perdu."""
    task = asyncio.ensure_future(work())
    try:
        while not task.done():
            done, _ = await asyncio.wait({task}, timeout=renew_seconds)
            if done:
                break
            if not await lease.renew():
                logger.error("bail perdu", extra={"event": "market.lease_lost"})
                return
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        try:
            await lease.release()
        except RedisError:
            # Redis injoignable : le bail expirera seul.
            logger.warning("bail non libéré", extra={"event": "market.lease_not_released"})
    task.result()
