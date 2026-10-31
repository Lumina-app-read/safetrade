"""
Contrôle de santé du conteneur : `python -m app.market.health`.

Il répond à une seule question : redémarrer ce worker serait-il utile ? Il exige Redis
joignable, un signal de vie récent et, chez le responsable, des rapports du flux récents.
Il ignore volontairement Deriv et les marchés : une coupure chez Deriv ou l'or fermé le
week-end ne sont pas des pannes du worker. Ces états sont suivis par `monitor:feed`, les
alertes et le statut de chaque actif.

Peu d'imports : ce processus court est relancé à chaque contrôle.
"""

import asyncio
import json
import os
import socket
import sys
import time
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

Data = dict[str, Any]

PRESENCE_KEY = "monitor:worker:{host}"
FEED_KEY = "monitor:feed"
PRESENCE_MAX_AGE_SECONDS = 20.0
FEED_REPORT_MAX_AGE_SECONDS = 30.0
REDIS_TIMEOUT_SECONDS = 2.0


def presence_key(host: str) -> str:
    return PRESENCE_KEY.format(host=host)


def diagnose(presence: Data | None, feed: Data | None, now: float) -> str | None:
    """Motif de mauvaise santé, ou None. Le signal de vie peut manquer au tout début."""
    if presence is None:
        return "worker.absent"
    if now - presence["at"] > PRESENCE_MAX_AGE_SECONDS:
        return "worker.stalled"
    if presence["role"] != "leader":
        return None
    # Nouveau responsable : son premier rapport peut suivre l'ancien de quelques secondes.
    if now - presence["since"] <= FEED_REPORT_MAX_AGE_SECONDS:
        return None
    if feed is None or now - feed["reported_at"] > FEED_REPORT_MAX_AGE_SECONDS:
        return "feed.stalled"
    return None


async def check(url: str, host: str) -> str | None:
    client = Redis.from_url(
        url,
        socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
        socket_timeout=REDIS_TIMEOUT_SECONDS,
    )
    try:
        presence, feed = await client.mget([presence_key(host), FEED_KEY])
    except (RedisError, OSError):
        return "redis.unreachable"
    finally:
        await client.aclose()
    return diagnose(
        json.loads(presence) if presence else None,
        json.loads(feed) if feed else None,
        time.time(),
    )


def main() -> int:
    url = os.environ.get("SAFETRADE_REDIS_URL")
    if not url:
        print("redis.not_configured")
        return 1
    problem = asyncio.run(check(url, socket.gethostname()))
    if problem:
        # Visible dans `docker inspect` : le diagnostic dit quoi regarder.
        print(problem)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
