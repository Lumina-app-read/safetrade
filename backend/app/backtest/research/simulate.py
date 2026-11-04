"""
Simulation d'une stratégie sur les bougies d'une minute, résultats exprimés en R.

1 R est la perte prévue par le stop. Travailler en R rend les marchés comparables et garantit une
mise constante : aucune règle ne fait grossir une position après une perte.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass

from app.backtest.research.candles import Bars
from app.backtest.research.families import Config, Signals
from app.backtest.research.indicators import MINUTE, Frame, Series

# Mesuré en démo : 0 à 12 % du stop. Appliqué à chaque sortie au stop.
STOP_SLIPPAGE_R = 0.05
# Deriv : le stop doit rester entre ces fractions de la mise.
STOP_MIN_STAKE = 0.10
STOP_MAX_STAKE = 0.90
# Signal trop ancien pour être exécuté, par exemple à la réouverture du lundi.
MAX_ENTRY_DELAY = 15 * MINUTE


@dataclass(frozen=True)
class Trade:
    opened_at: int
    closed_at: int
    direction: int
    gross_r: float  # avant commission, glissement compris
    fee_r: float  # commission pour un taux de 1, en R : 1 / distance du stop
    reason: str

    def net_r(self, rate: float) -> float:
        return self.gross_r - rate * self.fee_r


def tradable(stop_pct: float, multipliers: Sequence[int]) -> bool:
    return any(STOP_MIN_STAKE <= stop_pct * m <= STOP_MAX_STAKE for m in multipliers)


def _follow(
    bars: Bars, start: int, sign: int, stop_pct: float, config: Config, width: float
) -> tuple[int, float, str] | None:
    """Sortie de la position : indice, cours, motif. None si l'historique s'arrête avant."""
    leave = config.exit
    entry = bars.open[start]
    stop = entry * (1 - sign * stop_pct)
    target = None if leave.target is None else entry + sign * leave.target * width
    limit = None
    if leave.hold is not None:
        limit = bars.epoch[start] + leave.hold * config.minutes * MINUTE
    best = entry
    for index in range(start, len(bars)):
        if limit is not None and bars.epoch[index] >= limit:
            return index, bars.open[index], "temps"
        opening, high, low = bars.open[index], bars.high[index], bars.low[index]
        worst = low if sign > 0 else high
        if (opening - stop) * sign <= 0:
            return index, opening, "stop"  # saut de cours : sortie au-delà du stop
        if (worst - stop) * sign <= 0:
            return index, stop, "stop"  # prudence : le stop passe avant l'objectif
        if target is not None and ((high if sign > 0 else low) - target) * sign >= 0:
            return index, target, "objectif"
        if leave.trail is not None:
            close = bars.close[index]
            best = max(best, close) if sign > 0 else min(best, close)
            trailed = best - sign * leave.trail * width
            stop = max(stop, trailed) if sign > 0 else min(stop, trailed)
    return None


def run(
    bars: Bars,
    frame: Frame,
    width: Series,
    signals: Signals,
    config: Config,
    multipliers: Sequence[int],
    *,
    since: int = 0,
    draw: random.Random | None = None,
) -> list[Trade]:
    """
    Une position à la fois. `since` : première date d'entrée admise. `draw` : sens tiré au sort
    à chaque signal, pour la référence aléatoire.
    """
    trades: list[Trade] = []
    free_from = 0
    for index, direction in signals:
        start = frame.next_minute[index]
        if start >= len(bars) or start < free_from:
            continue
        ready_at = frame.epoch[index] + frame.minutes * MINUTE
        if bars.epoch[start] < since or bars.epoch[start] - ready_at > MAX_ENTRY_DELAY:
            continue
        distance = width[index]
        if distance is None or distance <= 0:
            continue
        entry = bars.open[start]
        stop_pct = config.exit.stop * distance / entry
        if not tradable(stop_pct, multipliers):
            continue
        sign = direction if draw is None else draw.choice((1, -1))
        outcome = _follow(bars, start, sign, stop_pct, config, distance)
        if outcome is None:
            break  # position encore ouverte en fin d'historique : aucun résultat à inventer
        end, price, reason = outcome
        gross = sign * (price - entry) / entry / stop_pct
        if reason == "stop":
            gross -= STOP_SLIPPAGE_R
        trades.append(Trade(bars.epoch[start], bars.epoch[end], sign, gross, 1 / stop_pct, reason))
        free_from = end + 1
    return trades
