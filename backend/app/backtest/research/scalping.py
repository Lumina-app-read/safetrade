"""
Recherche v3 : scalping sur Volatility 75 (1s), tick par tick.

Protocole : docs/decisions/recherche-scalping-protocole.md, écrit avant tout résultat.

    python -m app.backtest.research.scalping

Un signal au tick i est exécuté au tick i + délai ; une position à la fois. Trois produits Deriv,
avec leurs coûts lus sur devis démo : Rise/Fall, multiplicateur x100, accumulateur.
"""

import argparse
import json
import math
import random
import statistics
import time
from collections import deque
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

from app.backtest.research import protocol, ticks

ROOT = Path(__file__).resolve().parents[4]
REPORT = ROOT / "docs/decisions/recherche-scalping.md"
WORK = Path(".backtest/research")
SYMBOL = "1HZ75V"


def _epoch(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, tzinfo=UTC).timestamp())


START = _epoch(2026, 7, 11)
TRAIN_END = _epoch(2026, 7, 25)
STUDY_END = _epoch(2026, 8, 1)  # août à octobre 2026 réservé : jamais chargé

# Coûts lus sur devis du compte démo le 5 novembre 2026 (mise 10 USD).
RISE_FALL_GAIN = 0.883  # paiement 18,83 pour 10 : +0,883 de la mise si juste, -1 sinon
RISE_FALL_BREAK_EVEN = 1 / (1 + RISE_FALL_GAIN)
MULTIPLIER = 100
MULTIPLIER_RATE = 0.00039  # commission en fraction du notionnel
MULTIPLIER_STOP = 0.5  # stop à 50 % de la mise
ACCUMULATOR_BARRIERS = {0.01: 1.503, 0.02: 1.405, 0.03: 1.317, 0.04: 1.253, 0.05: 1.193}

DELAY = 1
DELAYS = (1, 2, 3)
HORIZONS = (1, 2, 3, 5, 10, 30, 60)
TRAIN_MIN = 1000
VALID_MIN = 300
TRAIN_P = 0.001
TRAIN_T = 3.5
VALID_P = 0.05
MIN_DAYS = 5
RANDOM_DRAWS = 2000
ACCU_HOLDS = (1, 2, 3, 5, 10, 20, 50)


# Signaux : une liste (indice du tick, sens), calculée sur les seuls ticks déjà reçus.

Signal = list[tuple[int, int]]


def _momentum(price: Sequence[float], sigma: float, n: int, z: float) -> Signal:
    limit = z * sigma * math.sqrt(n)
    return [
        (i, 1 if price[i] > price[i - n] else -1)
        for i in range(n, len(price))
        if abs(price[i] - price[i - n]) > limit
    ]


def _reversal(price: Sequence[float], sigma: float, n: int) -> Signal:
    return [(i, -d) for i, d in _momentum(price, sigma, n, 2.5)]


def _acceleration(price: Sequence[float], sigma: float) -> Signal:
    found = []
    for i in range(30, len(price)):
        fast, slow = price[i] - price[i - 5], price[i] - price[i - 30]
        if fast * slow > 0 and abs(fast) / 5 > 2 * abs(slow) / 30 and abs(fast) > sigma:
            found.append((i, 1 if fast > 0 else -1))
    return found


def _rolling_extremes(price: Sequence[float], n: int) -> tuple[list[float], list[float]]:
    """Plus haut et plus bas des n ticks avant i (i exclu), en temps linéaire."""
    highs: list[float] = [math.nan] * len(price)
    lows: list[float] = [math.nan] * len(price)
    up: deque[int] = deque()
    down: deque[int] = deque()
    for i in range(len(price)):
        if i >= n:
            highs[i] = price[up[0]]
            lows[i] = price[down[0]]
        while up and price[up[-1]] <= price[i]:
            up.pop()
        up.append(i)
        while down and price[down[-1]] >= price[i]:
            down.pop()
        down.append(i)
        while up[0] <= i - n:
            up.popleft()
        while down[0] <= i - n:
            down.popleft()
    return highs, lows


def _breakout(price: Sequence[float], n: int) -> Signal:
    highs, lows = _rolling_extremes(price, n)
    found = []
    for i in range(n, len(price)):
        if price[i] > highs[i]:
            found.append((i, 1))
        elif price[i] < lows[i]:
            found.append((i, -1))
    return found


def _streak(price: Sequence[float], k: int, follow: bool) -> Signal:
    found = []
    run = 0
    for i in range(1, len(price)):
        step = price[i] - price[i - 1]
        direction = 1 if step > 0 else -1 if step < 0 else 0
        run = run + direction if direction and run * direction > 0 else direction
        if abs(run) >= k:
            sign = 1 if run > 0 else -1
            found.append((i, sign if follow else -sign))
            run = 0  # une série ne donne qu'un signal
    return found


def rolling_std(price: Sequence[float], n: int) -> list[float]:
    """Écart type des n dernières variations, i compris."""
    result = [math.nan] * len(price)
    total = squares = 0.0
    window: deque[float] = deque()
    for i in range(1, len(price)):
        step = price[i] - price[i - 1]
        window.append(step)
        total += step
        squares += step * step
        if len(window) > n:
            old = window.popleft()
            total -= old
            squares -= old * old
        if len(window) == n:
            mean = total / n
            result[i] = math.sqrt(max(squares / n - mean * mean, 0.0))
    return result


def _consolidation(price: Sequence[float], quiet: float) -> Signal:
    spread = rolling_std(price, 60)
    return [
        (i, d)
        for i, d in _breakout(price, 60)
        if not math.isnan(spread[i - 1]) and spread[i - 1] <= quiet
    ]


def signal_makers(sigma: float, quiet: float) -> dict[str, Callable[[Sequence[float]], Signal]]:
    makers: dict[str, Callable[[Sequence[float]], Signal]] = {}
    for n in (5, 10, 30):
        for z in (1.0, 2.0):
            makers[f"momentum n={n} z={z:g}"] = partial(_momentum, sigma=sigma, n=n, z=z)
        makers[f"micro-retournement n={n}"] = partial(_reversal, sigma=sigma, n=n)
    makers["acceleration"] = partial(_acceleration, sigma=sigma)
    for n in (30, 60, 300):
        makers[f"cassure n={n}"] = partial(_breakout, n=n)
    for k in (3, 4, 5):
        makers[f"serie k={k} continuation"] = partial(_streak, k=k, follow=True)
        makers[f"serie k={k} retournement"] = partial(_streak, k=k, follow=False)
    makers["sortie de consolidation"] = partial(_consolidation, quiet=quiet)
    return makers


# Positions : une à la fois, entrée après le délai, sortie après l'horizon.


@dataclass(frozen=True)
class Position:
    entry: int
    exit: int
    direction: int
    move: float  # variation dans le sens du signal, en fraction du prix d'entrée


def positions_of(
    price: Sequence[float], signals: Signal, horizon: int, delay: int, start: int, end: int
) -> list[Position]:
    found = []
    free_from = 0
    for i, direction in signals:
        if i < start or i < free_from:
            continue
        entry, exit_ = i + delay, i + delay + horizon
        if exit_ >= end:
            break
        move = direction * (price[exit_] - price[entry]) / price[entry]
        found.append(Position(entry, exit_, direction, move))
        free_from = exit_ + 1
    return found


def rise_fall(p: Position) -> float:
    """Égalité perdue, comme chez Deriv pour Rise/Fall strict."""
    return RISE_FALL_GAIN if p.move > 0 else -1.0


def multiplier(p: Position, price: Sequence[float]) -> float:
    """En fraction de la mise : stop à 50 % vérifié à chaque tick, commission déduite."""
    entry = price[p.entry]
    for k in range(p.entry + 1, p.exit + 1):
        if MULTIPLIER * p.direction * (price[k] - entry) / entry <= -MULTIPLIER_STOP:
            return -MULTIPLIER_STOP - MULTIPLIER * MULTIPLIER_RATE
    return MULTIPLIER * p.move - MULTIPLIER * MULTIPLIER_RATE


def binomial_p(wins: int, n: int, rate: float) -> float:
    if n == 0:
        return 1.0
    z = (wins / n - rate) / math.sqrt(rate * (1 - rate) / n)
    return 0.5 * math.erfc(z / math.sqrt(2))


def consecutive_losses(values: Sequence[float]) -> int:
    longest = current = 0
    for v in values:
        current = current + 1 if v <= 0 else 0
        longest = max(longest, current)
    return longest


def summary(
    values: Sequence[float],
    signals: int,
    positions: Sequence[Position],
    minutes: float,
    cost: float,
) -> dict[str, Any]:
    stat = protocol.stats_of(values)
    return {
        **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in stat.__dict__.items()},
        "signals_per_minute": round(signals / minutes, 3),
        "positions_per_minute": round(len(positions) / minutes, 3),
        "rejected": round(1 - len(positions) / signals, 3) if signals else 0.0,
        "duration_s": round(statistics.fmean(p.exit - p.entry for p in positions), 1)
        if positions
        else 0,
        "max_losses": consecutive_losses(values),
        "cost_total": round(cost * len(values), 2),
    }


def random_p(moves: Sequence[float], product: Callable[[float], float], actual: float) -> float:
    generator = random.Random(20261105)  # noqa: S311
    better = 0
    for _ in range(RANDOM_DRAWS):
        drawn = [product(m if generator.random() < 0.5 else -m) for m in moves]
        better += statistics.fmean(drawn) >= actual
    return (better + 1) / (RANDOM_DRAWS + 1)


def _days_positive(values: Sequence[float], entries: Sequence[int], epochs: Sequence[int]) -> int:
    by_day: dict[int, float] = {}
    for v, e in zip(values, entries, strict=True):
        day = epochs[e] // 86400
        by_day[day] = by_day.get(day, 0.0) + v
    return sum(total > 0 for total in by_day.values())


# Travail d'un signal : entraînement et validation, deux produits, tous les horizons.


def _evaluate(job: tuple[str, str, float, float]) -> dict[str, Any]:
    name, directory, sigma, quiet = job
    data = ticks.load(ticks.path_of(Path(directory), SYMBOL), until=STUDY_END)
    price, epochs = data.price, data.epoch
    split = next(i for i, e in enumerate(epochs) if e >= TRAIN_END)
    signals = signal_makers(sigma, quiet)[name](price)
    train_minutes = (TRAIN_END - epochs[0]) / 60
    valid_minutes = (epochs[-1] - TRAIN_END) / 60
    train_signals = sum(1 for i, _ in signals if i < split)
    valid_signals = len(signals) - train_signals
    rows = []
    for horizon in HORIZONS:
        for delay_ in DELAYS:
            train = positions_of(price, signals, horizon, delay_, 0, split)
            valid = positions_of(price, signals, horizon, delay_, split, len(price))
            for product in ("rise_fall", "multiplicateur"):

                def value(p: Position, product: str = product) -> float:
                    return rise_fall(p) if product == "rise_fall" else multiplier(p, price)

                cost = 0.0 if product == "rise_fall" else MULTIPLIER * MULTIPLIER_RATE
                row: dict[str, Any] = {
                    "signal": name,
                    "horizon": horizon,
                    "delay": delay_,
                    "product": product,
                }
                for label, items, count, minutes in (
                    ("train", train, train_signals, train_minutes),
                    ("valid", valid, valid_signals, valid_minutes),
                ):
                    values = [value(p) for p in items]
                    block = summary(values, count, items, minutes, cost)
                    wins = sum(v > 0 for v in values)
                    block["p_rise_fall"] = binomial_p(wins, len(values), RISE_FALL_BREAK_EVEN)
                    block["days_positive"] = _days_positive(
                        values, [p.entry for p in items], epochs
                    )
                    block["gross_hit"] = (
                        round(sum(p.move > 0 for p in items) / len(items), 4) if items else 0
                    )
                    if label == "valid" and delay_ == DELAY and values:
                        moves = [p.move for p in items]
                        if product == "rise_fall":
                            block["random_p"] = random_p(
                                moves, lambda m: RISE_FALL_GAIN if m > 0 else -1.0, block["mean"]
                            )
                        else:
                            block["random_p"] = random_p(
                                moves,
                                lambda m: MULTIPLIER * m - MULTIPLIER * MULTIPLIER_RATE,
                                block["mean"],
                            )
                    row[label] = block
                rows.append(row)
    return {"signal": name, "rows": rows}


def train_pass(block: dict[str, Any], product: str) -> bool:
    if block["n"] < TRAIN_MIN or block["mean"] <= 0:
        return False
    if product == "rise_fall":
        return bool(block["p_rise_fall"] < TRAIN_P)
    return bool(block["t"] >= TRAIN_T)


def valid_pass(row: dict[str, Any], slower: dict[str, Any] | None) -> dict[str, bool]:
    v = row["valid"]
    significant = v["p_rise_fall"] < VALID_P if row["product"] == "rise_fall" else v["p"] < VALID_P
    return {
        "positions": v["n"] >= VALID_MIN,
        "positif": v["mean"] > 0,
        "significatif": bool(significant),
        "hasard": v.get("random_p", 1.0) < VALID_P,
        "jours": v["days_positive"] >= MIN_DAYS,
        "delai": slower is not None and slower["valid"]["mean"] > 0,
    }


# Prévisibilité : mesures descriptives.


def autocorrelation(values: Sequence[float], lag: int) -> float:
    mean = statistics.fmean(values)
    top = sum((values[i] - mean) * (values[i - lag] - mean) for i in range(lag, len(values)))
    bottom = sum((v - mean) ** 2 for v in values)
    return top / bottom if bottom else 0.0


def variance_ratio(price: Sequence[float], k: int) -> float:
    one = [price[i] - price[i - 1] for i in range(1, len(price))]
    many = [price[i] - price[i - k] for i in range(k, len(price), k)]
    return statistics.pvariance(many) / (k * statistics.pvariance(one))


def predictability(price: Sequence[float]) -> dict[str, Any]:
    steps = [price[i] - price[i - 1] for i in range(1, len(price))]
    sizes = [abs(s) for s in steps]
    up_after: dict[int, float] = {}
    for k in range(1, 6):
        hits = total = run = 0
        for i in range(1, len(steps)):
            prev = steps[i - 1]
            run = run + 1 if prev > 0 else 0
            if run >= k and steps[i] != 0:
                total += 1
                hits += steps[i] > 0
        up_after[k] = hits / total if total else 0.0
    return {
        "n": len(steps),
        "band": 1.96 / math.sqrt(len(steps)),
        "acf": [round(autocorrelation(steps, lag), 5) for lag in range(1, 11)],
        "acf_abs": [round(autocorrelation(sizes, lag), 5) for lag in range(1, 11)],
        "vr": {k: round(variance_ratio(price, k), 4) for k in (5, 10, 30, 60, 300)},
        "up_after_ups": {k: round(v, 4) for k, v in up_after.items()},
        "ties": round(sum(s == 0 for s in steps) / len(steps), 4),
        "sigma": statistics.pstdev(steps),
    }


# Accumulateurs : franchissement de la barrière, tick par tick.


def accumulators(
    price: Sequence[float], quiet_std: list[float], quiet: float, start: int, end: int
) -> dict[str, Any]:
    steps = [abs(price[i] - price[i - 1]) for i in range(1, len(price))]
    result = {}
    for rate, barrier in ACCUMULATOR_BARRIERS.items():
        knocked = [s >= barrier for s in steps]
        entry: dict[str, Any] = {"barrier": barrier, "knock_per_tick": {}}
        for label, condition in (("toujours", None), ("apres_calme", quiet)):
            starts = [
                i
                for i in range(max(start, 61), end - max(ACCU_HOLDS) - 1, 7)
                if condition is None or quiet_std[i] <= condition
            ]
            holds = {}
            for k in ACCU_HOLDS:
                survived = sum(not any(knocked[i : i + k]) for i in starts)
                share = survived / len(starts) if starts else 0.0
                holds[k] = {
                    "survival": round(share, 4),
                    "expectancy": round((1 + rate) ** k * share - 1, 4),
                    "n": len(starts),
                }
            entry[label] = holds
            per_tick = [knocked[i] for i in starts]
            entry["knock_per_tick"][label] = (
                round(sum(per_tick) / len(per_tick), 4) if per_tick else 0.0
            )
        result[str(rate)] = entry
    return result


def study(directory: Path, workers: int) -> dict[str, Any]:
    started = time.monotonic()
    data = ticks.load(ticks.path_of(directory, SYMBOL), until=STUDY_END)
    price, epochs = data.price, data.epoch
    split = next(i for i, e in enumerate(epochs) if e >= TRAIN_END)
    train_price = price[:split]
    sigma = statistics.pstdev(
        train_price[i] - train_price[i - 1] for i in range(1, len(train_price))
    )
    spread = rolling_std(price, 60)
    calm = sorted(s for s in spread[:split] if not math.isnan(s))
    quiet = calm[len(calm) // 5]
    names = list(signal_makers(sigma, quiet))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        evaluated = list(pool.map(_evaluate, [(n, str(directory), sigma, quiet) for n in names]))
    rows = [row for item in evaluated for row in item["rows"]]
    index = {(r["signal"], r["horizon"], r["delay"], r["product"]): r for r in rows}
    retained = []
    for row in rows:
        if row["delay"] != DELAY or not train_pass(row["train"], row["product"]):
            continue
        slower = index.get((row["signal"], row["horizon"], DELAY + 1, row["product"]))
        checks = valid_pass(row, slower)
        row["checks"] = checks
        row["passed"] = all(checks.values())
        retained.append(row)
    return {
        "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "data": {
            "ticks": len(price),
            "first": epochs[0],
            "last": epochs[-1],
            "train_ticks": split,
            "gaps": sum(1 for i in range(1, len(epochs)) if epochs[i] - epochs[i - 1] > 1),
        },
        "sigma": sigma,
        "quiet": quiet,
        "predictability": {
            "train": predictability(price[:split]),
            "valid": predictability(price[split:]),
        },
        "accumulators": {
            "train": accumulators(price, spread, quiet, 0, split),
            "valid": accumulators(price, spread, quiet, split, len(price)),
        },
        "tests": len([r for r in rows if r["delay"] == DELAY]),
        "rows": rows,
        "retained": [r for r in retained],
        "candidates": [
            f"{r['signal']}|{r['horizon']}|{r['product']}" for r in retained if r["passed"]
        ],
        "seconds": round(time.monotonic() - started),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Recherche v3 : scalping sur 1HZ75V.")
    parser.add_argument("--directory", type=Path, default=ticks.DATA_DIR)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)
    result = study(args.directory, args.workers)
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "scalping.json").write_text(json.dumps(result, indent=1, default=str))
    from app.backtest.research.scalping_report import render

    REPORT.write_text(render(result), encoding="utf-8", newline="\n")
    print(
        f"{result['tests']} tests, {len(result['retained'])} retenus à l'entraînement, "
        f"{len(result['candidates'])} candidats, {result['seconds']} s ; rapport écrit"
    )


if __name__ == "__main__":
    main()
