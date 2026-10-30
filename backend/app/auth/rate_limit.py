"""Compteurs d'échecs pour la protection contre le brute force (section 14)."""

import time
from typing import Protocol

from redis import Redis


class FailureCounter(Protocol):
    def count(self, key: str) -> int: ...
    def add(self, key: str, window_seconds: int) -> int: ...
    def reset(self, key: str) -> None: ...


class RedisFailureCounter:
    """Compteur partagé entre toutes les instances de l'API."""

    def __init__(self, client: Redis) -> None:
        self._redis = client

    def count(self, key: str) -> int:
        value = self._redis.get(f"fail:{key}")
        return int(value) if value is not None else 0  # type: ignore[arg-type]

    def add(self, key: str, window_seconds: int) -> int:
        pipe = self._redis.pipeline()
        pipe.incr(f"fail:{key}")
        pipe.expire(f"fail:{key}", window_seconds)
        return int(pipe.execute()[0])

    def reset(self, key: str) -> None:
        self._redis.delete(f"fail:{key}")


class MemoryFailureCounter:
    """Compteur en mémoire, pour les tests et le développement sans Redis."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[int, float]] = {}

    def count(self, key: str) -> int:
        value, expires = self._data.get(key, (0, 0.0))
        return value if expires > time.monotonic() else 0

    def add(self, key: str, window_seconds: int) -> int:
        value = self.count(key) + 1
        self._data[key] = (value, time.monotonic() + window_seconds)
        return value

    def reset(self, key: str) -> None:
        self._data.pop(key, None)
