"""
Banc d'essai : rejoue le vrai code de décision sur des ticks historiques, tick par tick.

Stratégie (`strategy.evaluate`), bougies (`quality.candles_refusal`) et sorties
(`exits.decide`) sont ceux du moteur. Seul le broker est simulé :

- le gain suit la formule mesurée : mise, fois multiplicateur, fois variation, moins commission ;
- un stop se déclenche au premier tick qui le franchit, à ce cours : un saut de cours donne donc
  un vrai glissement, plafonné à la mise par le `stop_out` ;
- une vente décidée à un tick s'exécute au tick suivant.

Limites : 1 position à la fois, pas de limite de session, commission fixe mesurée sur un devis.
Aucune fonction ici ne lit un tick postérieur à l'instant simulé.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache

from app.market.quality import candles_refusal
from app.market.store import Data
from app.trading import exits, strategy

MINUTE = strategy.GRANULARITY


@dataclass(frozen=True)
class Params:
    multiplier: int
    commission: float
    stop_minimum: float
    stake: float = 1.0
    stop_loss_pct: float = 50.0
    activation_r: float = 1.0
    locked_fraction: float = 0.5
    max_consecutive_losses: int = 3
    pause_minutes: int = 15
    # Temps entre la fin d'une bougie et l'ordre : le flux relit les bougies toutes les 30 s.
    entry_delay_seconds: int = 15
    # Même nombre d'entrées, sens tiré au sort : mesure ce que le signal apporte vraiment.
    random_direction: bool = False
    seed: int = 1


@dataclass(frozen=True)
class Trade:
    opened_at: int
    closed_at: int
    direction: str
    net: float
    peak: float
    reason: str


def candles_of(times: Sequence[int], prices: Sequence[float]) -> list[Data]:
    """Bougies d'une minute : une bougie n'existe que si un tick est tombé dans sa période."""
    candles: list[Data] = []
    for epoch, price in zip(times, prices, strict=True):
        start = epoch - epoch % MINUTE
        if candles and candles[-1]["epoch"] == start:
            last = candles[-1]
            last["high"] = max(last["high"], price)
            last["low"] = min(last["low"], price)
            last["close"] = price
        else:
            candles.append(
                {"epoch": start, "open": price, "high": price, "low": price, "close": price}
            )
    return candles


def cents(value: float) -> int:
    return round(value * 100)


@lru_cache(maxsize=200_000)
def _decide(
    profit: int,
    peak: int,
    commission: int,
    risk: int,
    stop: int,
    minimum: int,
    activation: float,
    locked: float,
) -> tuple[str, int | None]:
    """Décision du moteur, en centimes : Deriv arrondit au cent, le cache évite les doublons."""
    action = exits.decide(
        exits.PositionView(
            Decimal(profit) / 100,
            Decimal(peak) / 100,
            Decimal(commission) / 100,
            Decimal(risk) / 100,
            Decimal(stop) / 100,
            Decimal(minimum) / 100,
        ),
        exits.ExitParams(Decimal(str(activation)), Decimal(str(locked))),
    )
    level = cents(float(action.stop_loss)) if action.stop_loss is not None else None
    return action.kind, level


def _signal(
    candles: Sequence[Data], closed: int, now: int, draw: random.Random, params: Params
) -> str | None:
    """Direction à prendre à la clôture de la bougie `closed - 1`, ou None."""
    window = candles[max(0, closed - strategy.NEEDED_CANDLES) : closed]
    if candles_refusal(window, MINUTE, now, strategy.NEEDED_CANDLES):
        return None
    direction = strategy.evaluate(window, params.multiplier).direction
    if direction and params.random_direction:
        return draw.choice(("up", "down"))
    return direction


def simulate(times: Sequence[int], prices: Sequence[float], params: Params) -> list[Trade]:
    candles = candles_of(times, prices)
    draw = random.Random(params.seed)  # noqa: S311 : tirage reproductible, sans usage de sécurité
    risk = cents(params.stake * params.stop_loss_pct / 100)
    stake = cents(params.stake)
    commission = cents(params.commission)
    minimum = max(cents(params.stop_minimum), commission + 1)
    trades: list[Trade] = []

    closed = 0  # bougies closes à l'instant simulé
    decided = -1  # dernière bougie étudiée : une décision par bougie close
    losses = 0
    paused_until = 0
    index = 0
    last = len(times) - 1
    while index < last:
        now = times[index]
        while closed < len(candles) and candles[closed]["epoch"] + MINUTE <= now:
            closed += 1
        ready = (
            closed > 0 and now >= candles[closed - 1]["epoch"] + MINUTE + params.entry_delay_seconds
        )
        if not ready or closed - 1 == decided or now < paused_until:
            index += 1
            continue
        decided = closed - 1
        direction = _signal(candles, closed, now, draw, params)
        if direction is None:
            index += 1
            continue

        # L'ordre part au tick suivant ; le cours d'entrée est celui de ce tick.
        index += 1
        entry = prices[index]
        opened_at = times[index]
        sign = 1 if direction == "up" else -1
        stop = risk
        peak = 0
        selling = False
        net = -commission
        reason = "end_of_data"
        while index < last:
            index += 1
            move = sign * (prices[index] - entry) / entry
            profit = cents(params.stake * params.multiplier * move) - commission
            peak = max(peak, profit)
            if profit <= -stake:
                net, reason = -stake, "stop_out"
                break
            if profit <= -stop:
                net, reason = profit, "stop" if stop == risk else "floor"
                break
            if selling:
                net, reason = profit, "ratchet"
                break
            kind, level = _decide(
                profit,
                peak,
                commission,
                risk,
                stop,
                minimum,
                params.activation_r,
                params.locked_fraction,
            )
            if kind == "sell":
                selling = True
            elif kind == "tighten" and level is not None:
                stop = level
            net = profit
        if reason == "end_of_data":
            break  # position encore ouverte en fin d'historique : aucun résultat à inventer
        trades.append(Trade(opened_at, times[index], direction, net / 100, peak / 100, reason))
        losses = losses + 1 if net < 0 else 0
        if losses >= params.max_consecutive_losses:
            paused_until = times[index] + params.pause_minutes * 60
            losses = 0
    return trades
