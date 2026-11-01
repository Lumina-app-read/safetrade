"""
Mesures d'un backtest et séparation entre optimisation et contrôle (q18).

Un résultat n'est dit positif que hors de l'échantillon d'optimisation, frais compris, et si
même le bas de l'intervalle de confiance à 95 % reste au-dessus de zéro.
"""

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from itertools import product

from app.backtest.engine import Params, Trade, simulate

TRAIN_SHARE = 0.7
# 1,96 écart-type : intervalle à 95 % de la moyenne par position.
Z_95 = 1.96
MIN_TRADES = 30


@dataclass(frozen=True)
class Summary:
    trades: int
    win_rate: float
    net: float
    expectancy: float
    low: float
    high: float
    average_win: float
    average_loss: float
    breakeven_win_rate: float | None
    profit_factor: float | None
    max_drawdown: float
    reasons: dict[str, int]

    @property
    def verdict(self) -> str:
        if self.trades < MIN_TRADES:
            return "insufficient"
        if self.low > 0:
            return "positive"
        return "negative" if self.high < 0 else "inconclusive"


def summarize(trades: Sequence[Trade]) -> Summary:
    nets = [trade.net for trade in trades]
    count = len(nets)
    if count == 0:
        return Summary(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, None, None, 0.0, {})
    wins = [net for net in nets if net > 0]
    losses = [-net for net in nets if net <= 0]
    mean = sum(nets) / count
    variance = sum((net - mean) ** 2 for net in nets) / max(count - 1, 1)
    margin = Z_95 * math.sqrt(variance / count)
    average_win = sum(wins) / len(wins) if wins else 0.0
    average_loss = sum(losses) / len(losses) if losses else 0.0
    # q18 : perte moyenne / (gain moyen + perte moyenne).
    total = average_win + average_loss
    balance = peak = worst = 0.0
    for net in nets:
        balance += net
        peak = max(peak, balance)
        worst = max(worst, peak - balance)
    return Summary(
        trades=count,
        win_rate=len(wins) / count,
        net=sum(nets),
        expectancy=mean,
        low=mean - margin,
        high=mean + margin,
        average_win=average_win,
        average_loss=average_loss,
        breakeven_win_rate=average_loss / total if total else None,
        profit_factor=sum(wins) / sum(losses) if losses and sum(losses) > 0 else None,
        max_drawdown=worst,
        reasons=dict(Counter(trade.reason for trade in trades)),
    )


@dataclass(frozen=True)
class WalkForward:
    chosen: Params
    train: Summary
    test: Summary
    test_default: Summary
    test_random: Summary
    candidates: int
    # Réglages du moteur sur tout l'historique : ils n'ont pas été choisis sur ces données.
    whole: list[Trade]
    whole_random: list[Trade]


def split(times: Sequence[int]) -> int:
    """Coupure dans le temps : le contrôle porte toujours sur la période la plus récente."""
    return int(len(times) * TRAIN_SHARE)


def grid(base: Params) -> list[Params]:
    return [
        replace(base, stop_loss_pct=stop, activation_r=activation, locked_fraction=locked)
        for stop, activation, locked in product(
            (25.0, 50.0, 100.0), (0.5, 1.0, 2.0), (0.3, 0.5, 0.7)
        )
    ]


def walk_forward(times: Sequence[int], prices: Sequence[float], base: Params) -> WalkForward:
    """
    Choisit les réglages sur la première période seulement, puis les juge sur la seconde. La
    période de contrôle reprend les bougies nécessaires à l'indicateur, sans les trader deux fois.
    """
    cut = split(times)
    train_times, train_prices = times[:cut], prices[:cut]
    test_times, test_prices = times[cut:], prices[cut:]
    candidates = grid(base)
    scored = [
        (summarize(simulate(train_times, train_prices, params)), params) for params in candidates
    ]
    eligible = [item for item in scored if item[0].trades >= MIN_TRADES] or scored
    train, chosen = max(eligible, key=lambda item: item[0].expectancy)
    return WalkForward(
        chosen=chosen,
        train=train,
        test=summarize(simulate(test_times, test_prices, chosen)),
        test_default=summarize(simulate(test_times, test_prices, base)),
        test_random=summarize(
            simulate(test_times, test_prices, replace(chosen, random_direction=True))
        ),
        candidates=len(candidates),
        whole=simulate(times, prices, base),
        whole_random=simulate(times, prices, replace(base, random_direction=True)),
    )
