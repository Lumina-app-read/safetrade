"""
Quotas d'appels Deriv, centralisés et partagés entre tous les bots (docs/decisions/deriv.md).

Limites distinctes pour REST et WebSocket, par groupe d'appels. Les compteurs vivent dans
Redis : toutes les instances voient le même budget, notamment celui de l'adresse IP du
serveur, commun à tous les utilisateurs. Marge de sécurité : 80 % des limites officielles,
indicatives et modifiables par Deriv.
"""

import asyncio
import enum
import random
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, cast

from redis.asyncio import Redis


@dataclass(frozen=True)
class Window:
    seconds: int
    limit: int


class Priority(enum.IntEnum):
    """Une sortie de position passe avant une entrée quand le budget se resserre."""

    NORMAL = 0
    PROTECTIVE = 1


class Quota(enum.StrEnum):
    WS_TRADING = "ws_trading"
    WS_ACCOUNT = "ws_account"
    WS_REPORTS = "ws_reports"
    WS_OTHER = "ws_other"
    REST_USER = "rest_user"
    REST_IP = "rest_ip"


MINUTE = 60
HOUR = 3600

# Limite officielle multipliée par 0,8.
WINDOWS: dict[Quota, tuple[Window, ...]] = {
    Quota.WS_TRADING: (Window(MINUTE, 288), Window(HOUR, 11520)),
    Quota.WS_ACCOUNT: (Window(MINUTE, 80), Window(HOUR, 1600)),
    Quota.WS_REPORTS: (Window(MINUTE, 24), Window(HOUR, 1200)),
    Quota.WS_OTHER: (Window(MINUTE, 176), Window(HOUR, 11520)),
    Quota.REST_USER: (Window(MINUTE, 64),),
    Quota.REST_IP: (Window(MINUTE, 240), Window(600, 800)),
}

# Plafond interne des entrées (section 21) : le reste du budget est réservé aux sorties.
ENTRY_MINUTE_LIMIT = 120

_GROUPS: dict[str, Quota] = {
    "proposal": Quota.WS_TRADING,
    "proposal_open_contract": Quota.WS_TRADING,
    "buy": Quota.WS_TRADING,
    "sell": Quota.WS_TRADING,
    "balance": Quota.WS_ACCOUNT,
    "statement": Quota.WS_ACCOUNT,
    "portfolio": Quota.WS_REPORTS,
    "profit_table": Quota.WS_REPORTS,
}

_PROTECTIVE = frozenset({"sell", "contract_update"})


def quota_for(call: str) -> Quota | None:
    """Groupe d'un appel WebSocket ; None pour `ping`, hors budget."""
    if call == "ping":
        return None
    return _GROUPS.get(call, Quota.WS_OTHER)


def priority_for(call: str) -> Priority:
    return Priority.PROTECTIVE if call in _PROTECTIVE else Priority.NORMAL


def windows_for(quota: Quota, priority: Priority) -> tuple[Window, ...]:
    windows = WINDOWS[quota]
    if quota is Quota.WS_TRADING and priority is Priority.NORMAL:
        return (Window(MINUTE, ENTRY_MINUTE_LIMIT), *windows[1:])
    return windows


class QuotaStore(Protocol):
    async def acquire(self, key: str, windows: tuple[Window, ...]) -> float:
        """Réserve un appel. Renvoie 0 si accordé, sinon le délai d'attente en secondes."""
        ...


class MemoryQuotaStore:
    """Journal glissant en mémoire : tests et développement sans Redis."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._events: dict[str, list[float]] = defaultdict(list)
        self._clock = clock

    async def acquire(self, key: str, windows: tuple[Window, ...]) -> float:
        now = self._clock()
        horizon = max(w.seconds for w in windows)
        events = [t for t in self._events[key] if t > now - horizon]
        self._events[key] = events
        wait = 0.0
        for window in windows:
            recent = [t for t in events if t > now - window.seconds]
            if len(recent) >= window.limit:
                wait = max(wait, recent[len(recent) - window.limit] + window.seconds - now)
        if wait == 0:
            events.append(now)
        return wait


# Journal glissant atomique. L'heure vient de Redis : horloge commune à toutes les instances.
_ACQUIRE = """
local key = KEYS[1]
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000
local horizon = 0
for i = 1, #ARGV - 1, 2 do horizon = math.max(horizon, tonumber(ARGV[i])) end
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - horizon)
local wait = 0
for i = 1, #ARGV - 1, 2 do
  local seconds, limit = tonumber(ARGV[i]), tonumber(ARGV[i + 1])
  local count = redis.call('ZCOUNT', key, '(' .. (now - seconds), '+inf')
  if count >= limit then
    local rows = redis.call('ZRANGEBYSCORE', key, '(' .. (now - seconds), '+inf',
                            'WITHSCORES', 'LIMIT', count - limit, 1)
    wait = math.max(wait, tonumber(rows[2]) + seconds - now)
  end
end
if wait == 0 then
  redis.call('ZADD', key, now, ARGV[#ARGV])
  redis.call('EXPIRE', key, math.ceil(horizon) + 1)
end
return tostring(wait)
"""


class RedisQuotaStore:
    def __init__(self, client: Redis) -> None:
        self._acquire = client.register_script(_ACQUIRE)

    async def acquire(self, key: str, windows: tuple[Window, ...]) -> float:
        args: list[str | int] = [v for w in windows for v in (w.seconds, w.limit)]
        result = await self._acquire(keys=[f"quota:{key}"], args=[*args, uuid.uuid4().hex])
        return float(cast("bytes | str", result))


class QuotaManager:
    """Attend qu'un appel soit autorisé. `scope` : compte Deriv, utilisateur ou « server »."""

    def __init__(self, store: QuotaStore) -> None:
        self._store = store

    async def wait(self, quota: Quota, scope: str, priority: Priority = Priority.NORMAL) -> None:
        windows = windows_for(quota, priority)
        while (delay := await self._store.acquire(f"{quota}:{scope}", windows)) > 0:
            # Variation aléatoire : les bots en attente ne repartent pas tous au même instant.
            await asyncio.sleep(delay + random.uniform(0, 0.25))  # noqa: S311


class Backoff:
    """Attente exponentielle avec jitter total : 1 s, 2 s, 4 s... plafonnée."""

    def __init__(self, base: float = 1.0, cap: float = 60.0) -> None:
        self.base = base
        self.cap = cap
        self.attempt = 0

    def next_delay(self) -> float:
        ceiling = min(self.cap, self.base * 2**self.attempt)
        self.attempt += 1
        # Jamais zéro : pas de reconnexion en boucle serrée.
        return random.uniform(ceiling / 2, ceiling)  # noqa: S311

    def reset(self) -> None:
        self.attempt = 0
