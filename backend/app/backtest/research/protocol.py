"""
Règles du protocole (docs/decisions/recherche-strategies-protocole.md), traduites en calcul.

Tout ce qui décide d'une sélection ou d'un verdict est ici, à un seul endroit, fixé avant de
voir les données de test.
"""

import math
import random
import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from app.backtest.research.simulate import Trade

DAY = 86400

CLASSES: dict[str, tuple[str, ...]] = {
    "crypto": ("cryBTCUSD", "cryETHUSD"),
    "metaux": ("frxXAUUSD", "frxXAGUSD"),
    "forex": ("frxEURUSD", "frxGBPUSD", "frxUSDJPY", "frxAUDUSD", "frxUSDCAD", "frxEURJPY"),
}
CLASSES["ensemble"] = tuple(s for markets in CLASSES.values() for s in markets)
CONTROLS = ("1HZ100V", "stpRNG")
STUDIED = CLASSES["ensemble"]

# Commission en fraction du notionnel, lue sur un devis du compte démo le 4 novembre 2026 (mise
# de 50 USD, plus petit multiplicateur proposé), avant tout résultat : elle remplace le taux
# supposé du protocole pour le forex et les métaux (voir le rapport de recherche).
RATES: dict[str, float] = {
    "cryBTCUSD": 0.000326,
    "cryETHUSD": 0.000882,
    "frxXAUUSD": 0.00012,
    "frxXAGUSD": 0.0006,
    "frxEURUSD": 0.00024,
    "frxGBPUSD": 0.000204,
    "frxUSDJPY": 0.000292,
    "frxAUDUSD": 0.0004,
    "frxUSDCAD": 0.000212,
    "frxEURJPY": 0.00025,
    "1HZ100V": 0.00051,
    "stpRNG": 0.0000165,
}
# Marché sans devis : jamais utilisé pour les marchés étudiés.
ASSUMED_RATE = 0.00005

TRAIN_SHARE = 0.5
VALID_SHARE = 0.25
TRAIN_MIN_TRADES = 100
VALID_MIN_TRADES = 50
VALID_MIN_T = 1.65
MIN_POSITIVE_MARKETS = 0.6
RANDOM_DRAWS = 200
ALPHA = 0.05
SUBPERIODS = 3


def rate_of(symbol: str) -> float:
    return RATES.get(symbol, ASSUMED_RATE)


@dataclass(frozen=True)
class Split:
    """Dates communes : entraînement avant `train_end`, validation avant `valid_end`, puis test."""

    common_start: int
    train_end: int
    valid_end: int
    end: int

    def period(self, epoch: int) -> str:
        if epoch < self.train_end:
            return "train"
        if epoch < self.valid_end:
            return "valid"
        return "test"


def split_of(spans: dict[str, tuple[int, int]]) -> Split:
    start = max(first for first, _ in spans.values())
    end = min(last for _, last in spans.values())
    span = end - start
    return Split(
        start,
        start + int(span * TRAIN_SHARE),
        start + int(span * (TRAIN_SHARE + VALID_SHARE)),
        end,
    )


def net(trades: Sequence[Trade], symbol: str, cost: float = 1.0) -> list[float]:
    rate = rate_of(symbol) * cost
    return [t.net_r(rate) for t in trades]


@dataclass(frozen=True)
class Stats:
    n: int
    mean: float
    t: float
    p: float  # unilatérale : probabilité d'une moyenne au moins aussi bonne sans avantage
    ci_low: float
    ci_high: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float | None
    total: float
    max_drawdown: float

    @property
    def positive(self) -> bool:
        return self.n > 0 and self.mean > 0


def _normal_tail(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2))


def stats_of(values: Sequence[float]) -> Stats:
    n = len(values)
    if n == 0:
        return Stats(0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, None, 0.0, 0.0)
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if n > 1 else 0.0
    t = mean / sd * math.sqrt(n) if sd > 0 else 0.0
    half = 1.96 * sd / math.sqrt(n) if n > 1 else 0.0
    wins = [v for v in values if v > 0]
    losses = [v for v in values if v <= 0]
    gross_loss = -sum(losses)
    peak = equity = drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return Stats(
        n=n,
        mean=mean,
        t=t,
        p=_normal_tail(t),
        ci_low=mean - half,
        ci_high=mean + half,
        win_rate=len(wins) / n,
        avg_win=statistics.fmean(wins) if wins else 0.0,
        avg_loss=statistics.fmean(losses) if losses else 0.0,
        profit_factor=sum(wins) / gross_loss if gross_loss > 0 else None,
        total=sum(values),
        max_drawdown=drawdown,
    )


def sharpe(trades: Sequence[tuple[Trade, float]]) -> float | None:
    """Sharpe annualisé sur les résultats journaliers en R (365 jours : la crypto ne ferme pas)."""
    days: defaultdict[int, float] = defaultdict(float)
    for trade, value in trades:
        days[trade.closed_at // DAY] += value
    if len(days) < 20:
        return None
    first, last = min(days), max(days)
    series = [days.get(day, 0.0) for day in range(first, last + 1)]
    sd = statistics.stdev(series)
    return statistics.fmean(series) / sd * math.sqrt(365) if sd > 0 else None


def max_cost(trades: Sequence[Trade]) -> float | None:
    """Taux de commission qui annulerait l'espérance : au-delà, la stratégie perd."""
    if not trades:
        return None
    gross = statistics.fmean(t.gross_r for t in trades)
    fee = statistics.fmean(t.fee_r for t in trades)
    return gross / fee if gross > 0 and fee > 0 else 0.0


def markets_positive(by_market: dict[str, list[float]]) -> float:
    active = [values for values in by_market.values() if values]
    if not active:
        return 0.0
    return sum(statistics.fmean(v) > 0 for v in active) / len(active)


def subperiods_positive(trades: Sequence[tuple[Trade, float]], start: int, end: int) -> int:
    width = (end - start) / SUBPERIODS
    sums = [0.0] * SUBPERIODS
    counts = [0] * SUBPERIODS
    for trade, value in trades:
        index = min(SUBPERIODS - 1, max(0, int((trade.opened_at - start) / width)))
        sums[index] += value
        counts[index] += 1
    return sum(1 for s, c in zip(sums, counts, strict=True) if c and s > 0)


def volatility_terciles(trades: Sequence[tuple[Trade, float]]) -> list[float | None]:
    """Espérance par tiers de volatilité : la distance du stop suit l'ATR, donc 1 / fee_r."""
    if len(trades) < 30:
        return [None, None, None]
    ordered = sorted(trades, key=lambda item: 1 / item[0].fee_r)
    size = len(ordered) // 3
    parts = [ordered[:size], ordered[size : 2 * size], ordered[2 * size :]]
    return [statistics.fmean(v for _, v in part) if part else None for part in parts]


def random_p_value(actual: float, draws: Sequence[float]) -> float:
    """Part des tirages au sort du sens qui font au moins aussi bien : 1 tirage ajouté (Laplace)."""
    better = sum(1 for value in draws if value >= actual)
    return (better + 1) / (len(draws) + 1)


def seeds(count: int = RANDOM_DRAWS, base: int = 20261101) -> list[random.Random]:
    return [random.Random(base + index) for index in range(count)]  # noqa: S311


def choose_on_train(
    pooled: dict[str, tuple[Stats, dict[str, list[float]]]],
) -> str | None:
    """Meilleure statistique t parmi les réglages assez fournis et positifs ; un seul."""
    eligible = [
        (stat.t, key)
        for key, (stat, _) in pooled.items()
        if stat.n >= TRAIN_MIN_TRADES and stat.mean > 0
    ]
    return max(eligible)[1] if eligible else None


def passes_validation(stat: Stats, by_market: dict[str, list[float]], markets: int) -> bool:
    if stat.n < VALID_MIN_TRADES or stat.mean <= 0 or stat.t < VALID_MIN_T:
        return False
    return markets == 1 or markets_positive(by_market) >= MIN_POSITIVE_MARKETS


@dataclass(frozen=True)
class Verdict:
    significant: bool
    beats_random: bool
    survives_double_cost: bool
    subperiods_ok: bool
    markets_ok: bool

    @property
    def passed(self) -> bool:
        return (
            self.significant
            and self.beats_random
            and self.survives_double_cost
            and self.subperiods_ok
            and self.markets_ok
        )


def verdict(
    stat: Stats,
    p_random: float,
    doubled: Stats,
    positive_subperiods: int,
    share_positive: float,
    markets: int,
    candidates: int,
) -> Verdict:
    return Verdict(
        significant=stat.mean > 0 and stat.p < ALPHA / max(candidates, 1),
        beats_random=p_random < ALPHA,
        survives_double_cost=doubled.mean > 0,
        subperiods_ok=positive_subperiods >= 2,
        markets_ok=markets == 1 or share_positive >= MIN_POSITIVE_MARKETS,
    )
