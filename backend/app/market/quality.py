"""
Contrôle des données avant toute décision : fonctions pures, sans réseau.

Une ouverture de position exige un actif `live`, un tick très récent, des bougies à jour et
continues. Le moindre doute se traduit par un refus : ne pas trader ne coûte rien.
"""

import itertools
from collections.abc import Sequence
from dataclasses import dataclass

from app.market.store import Data, MarketStore, asset_status

# Plus strict que STALE_SECONDS, qui ne sert qu'à l'affichage.
MAX_TICK_AGE_SECONDS = 5.0
MAX_FUTURE_SECONDS = 5.0
# Après un trou, attendre que les bougies relues et le flux soient de nouveau stables.
GAP_COOLDOWN_SECONDS = 60.0


@dataclass(frozen=True)
class MarketSnapshot:
    status: str
    tick: Data | None
    candles: Sequence[Data]
    granularity: int
    candles_updated_at: float
    multiplier_range: Sequence[int] = ()


async def read_snapshot(
    store: MarketStore, symbol: str, granularity: int, now: float
) -> MarketSnapshot:
    """Vue d'un actif pour le moteur. Un actif absent est `unavailable`, jamais supposé sain."""
    state = await store.get_assets()
    ticks = await store.get_ticks([symbol])
    stored = await store.get_candles(symbol, granularity)
    asset = next((a for a in (state or {}).get("assets", []) if a["symbol"] == symbol), None)
    status = "unavailable"
    if state is not None and asset is not None:
        status = asset_status(asset, ticks.get(symbol), state["updated_at"], now)
    return MarketSnapshot(
        status=status,
        tick=ticks.get(symbol),
        candles=(stored or {}).get("candles", []),
        granularity=granularity,
        candles_updated_at=(stored or {}).get("updated_at", 0.0),
        multiplier_range=(asset or {}).get("multiplier_range") or (),
    )


def closed_candles(candles: Sequence[Data], granularity: int, now: float) -> list[Data]:
    """La dernière bougie est encore en formation : aucune décision ne repose dessus."""
    return [c for c in candles if c["epoch"] + granularity <= now]


def candles_refusal(
    candles: Sequence[Data], granularity: int, now: float, needed: int
) -> str | None:
    closed = closed_candles(candles, granularity, now)[-needed:]
    if len(closed) < needed:
        return "market.candles_missing"
    # Une période de retard tolérée : la rotation des relectures prend moins d'une minute.
    if now - (closed[-1]["epoch"] + granularity) >= 2 * granularity:
        return "market.candles_stale"
    epochs = [c["epoch"] for c in closed]
    if any(b - a != granularity for a, b in itertools.pairwise(epochs)):
        return "market.candles_gap"
    return None


def entry_refusal(snapshot: MarketSnapshot, now: float, needed_candles: int) -> str | None:
    """Motif de refus d'une ouverture de position, ou None si les données sont saines."""
    if snapshot.status != "live":
        return f"market.{snapshot.status}"
    tick = snapshot.tick
    if tick is None:
        return "market.no_tick"
    if tick["epoch"] > now + MAX_FUTURE_SECONDS:
        return "market.tick_from_future"
    # Date de Deriv et date de réception : un vieux tick rejoué reste un vieux tick.
    if now - min(tick["epoch"], tick["received_at"]) > MAX_TICK_AGE_SECONDS:
        return "market.tick_stale"
    gap = tick.get("last_gap_epoch")
    if gap is not None:
        if now - gap < GAP_COOLDOWN_SECONDS:
            return "market.recent_gap"
        if snapshot.candles_updated_at <= gap:
            return "market.gap_not_repaired"
    return candles_refusal(snapshot.candles, snapshot.granularity, now, needed_candles)
