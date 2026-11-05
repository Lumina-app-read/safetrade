"""
Recherche v2 : existe-t-il des conditions de marché où le prix est prévisible au-delà des coûts ?

Protocole : docs/decisions/recherche-conditions-protocole.md, écrit avant tout résultat.

    python -m app.backtest.research.conditions

Étude d'événements : à chaque clôture de bougie, un signal donne un sens ; le résultat est le
mouvement dans ce sens, de l'ouverture de la minute suivante à la clôture de `h` bougies plus
tard, moins la commission mesurée. Les événements ne se chevauchent pas. Le résultat est lu par
condition de marché, sur trois plis de validation glissante. Août à octobre 2026 n'est jamais lu.
"""

import argparse
import json
import math
import random
import statistics
import time
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.backtest.research import candles, indicators, protocol
from app.backtest.research.families import Config, Exit
from app.backtest.research.indicators import MINUTE, Frame, Series
from app.backtest.research.protocol import CLASSES, STUDIED
from app.backtest.research.simulate import MAX_ENTRY_DELAY, run

ROOT = Path(__file__).resolve().parents[4]
REPORT = ROOT / "docs/decisions/recherche-conditions.md"
WORK = Path(".backtest/research")


def _epoch(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, tzinfo=UTC).timestamp())


# Août à octobre 2026 est réservé au test final : rien n'est chargé à partir de cette date.
STUDY_END = _epoch(2026, 8, 1)
FOLDS: tuple[tuple[int, int], ...] = (
    (_epoch(2026, 2, 1), _epoch(2026, 4, 1)),
    (_epoch(2026, 4, 1), _epoch(2026, 6, 1)),
    (_epoch(2026, 6, 1), STUDY_END),
)
TIMEFRAMES = (15, 60)
HORIZONS = (4, 16)
SIGNALS = ("momentum", "acceleration", "exces", "cassure_compression", "alignement")
REGIMES = {"tendance": 3, "volatilite": 3, "cout": 3, "seance": 4}
SESSION_HOURS = (7, 13, 21)  # 0-7 h, 7-13 h, 13-21 h, 21-24 h UTC

TRAIN_MIN_EVENTS = 150
TRAIN_MIN_T = 3.0
OOS_MIN_FOLDS = 2
OOS_MIN_EVENTS = 100
OOS_MIN_T = 2.0
MIN_POSITIVE_MARKETS = 0.6
RANDOM_DRAWS = 2000
ALPHA = 0.05
STOP_ATR = 2.0
BP = 10_000  # résultats en points de base du notionnel


# Signaux.


def _signals(frame: Frame) -> dict[str, list[tuple[int, int]]]:
    close = frame.close
    width = indicators.atr(frame, 14)
    mean, spread = indicators.sma_std(close, 20)
    upper = indicators.ema(close, 200)  # unité 4 fois plus longue : moyenne sur 50 de cette unité
    found: dict[str, list[tuple[int, int]]] = {name: [] for name in SIGNALS}
    bands: Series = [
        None if m is None or s is None or m == 0 else 4 * s / m
        for m, s in zip(mean, spread, strict=True)
    ]
    for i in range(120, len(frame)):
        a = width[i]
        if a is None or a <= 0:
            continue
        move8 = close[i] - close[i - 8]
        if abs(move8) > 1.5 * a * math.sqrt(8):
            found["momentum"].append((i, 1 if move8 > 0 else -1))
        move4, move16 = close[i] - close[i - 4], close[i] - close[i - 16]
        if move4 * move16 > 0 and abs(move4) / 4 > abs(move16) / 16 and abs(move4) > a:
            found["acceleration"].append((i, 1 if move4 > 0 else -1))
        m, s = mean[i], spread[i]
        if m is not None and s is not None and s > 0 and abs(close[i] - m) > 2.5 * s:
            found["exces"].append((i, -1 if close[i] > m else 1))
        history = [w for w in bands[i - 100 : i] if w is not None]
        current = bands[i - 1]
        if current is not None and len(history) >= 80:
            rank = sum(w <= current for w in history) / len(history)
            if rank <= 0.2:
                if close[i] > max(frame.high[i - 20 : i]):
                    found["cassure_compression"].append((i, 1))
                elif close[i] < min(frame.low[i - 20 : i]):
                    found["cassure_compression"].append((i, -1))
        trend = upper[i]
        if trend is not None and abs(move4) > a:
            direction = 1 if move4 > 0 else -1
            if (close[i] - trend) * direction > 0:
                found["alignement"].append((i, direction))
    return found


@dataclass(frozen=True)
class Event:
    epoch: int  # clôture de la bougie du signal
    gross: float  # mouvement dans le sens du signal, fraction du notionnel, avant commission
    features: tuple[float, float, float, int]  # tendance, volatilité, coût, séance


def _features(frame: Frame, rate: float) -> list[tuple[float, float, float, int] | None]:
    short = indicators.atr(frame, 14)
    long = indicators.atr(frame, 100)
    straight = indicators.efficiency(frame.close, 20)
    result: list[tuple[float, float, float, int] | None] = []
    for i in range(len(frame)):
        a, b, e = short[i], long[i], straight[i]
        if a is None or b is None or e is None or a <= 0 or b <= 0:
            result.append(None)
            continue
        hour = datetime.fromtimestamp(frame.epoch[i] + frame.minutes * MINUTE, UTC).hour
        session = bisect_right(SESSION_HOURS, hour)
        result.append((e, a / b, rate / (a / frame.close[i]), session))
    return result


def events_of(
    bars: candles.Bars, frame: Frame, signals: list[tuple[int, int]], horizon: int, rate: float
) -> list[Event]:
    """Un événement à la fois : le suivant attend la sortie du précédent."""
    features = _features(frame, rate)
    found: list[Event] = []
    free_from = 0
    for index, direction in signals:
        exit_index = index + horizon
        if index < free_from or exit_index >= len(frame):
            continue
        start = frame.next_minute[index]
        ready = frame.epoch[index] + frame.minutes * MINUTE
        feature = features[index]
        if start >= len(bars) or bars.epoch[start] - ready > MAX_ENTRY_DELAY or feature is None:
            continue
        entry = bars.open[start]
        gross = direction * (frame.close[exit_index] - entry) / entry
        found.append(Event(frame.epoch[index], gross, feature))
        free_from = exit_index + 1
    return found


def _market(job: tuple[str, str]) -> tuple[str, dict[str, Any]]:
    symbol, directory = job
    bars = candles.load(candles.path_of(Path(directory), symbol), until=STUDY_END)
    rate = protocol.rate_of(symbol)
    result: dict[str, Any] = {"events": {}, "bars": {}}
    for minutes in TIMEFRAMES:
        frame = indicators.resample(bars, minutes)
        signals = _signals(frame)
        for name in SIGNALS:
            for horizon in HORIZONS:
                result["events"][(name, minutes, horizon)] = events_of(
                    bars, frame, signals[name], horizon, rate
                )
        # Caractéristiques de chaque bougie : les seuils des régimes en sont tirés.
        result["bars"][minutes] = [
            (frame.epoch[i], f) for i, f in enumerate(_features(frame, rate)) if f is not None
        ]
    return symbol, result


# Régimes : terciles calculés sur l'entraînement d'un pli, par marché et par unité.


def thresholds(
    rows: Sequence[tuple[int, tuple[float, float, float, int]]], until: int
) -> list[tuple[float, float]]:
    values: list[list[float]] = [[], [], []]
    for epoch, feature in rows:
        if epoch >= until:
            break
        for k in range(3):
            values[k].append(feature[k])
    cuts = []
    for column in values:
        ordered = sorted(column)
        cuts.append((ordered[len(ordered) // 3], ordered[2 * len(ordered) // 3]))
    return cuts


def regime_of(
    feature: tuple[float, float, float, int], cuts: list[tuple[float, float]], kind: str
) -> int:
    if kind == "seance":
        return feature[3]
    k = ("tendance", "volatilite", "cout").index(kind)
    low, high = cuts[k]
    return 0 if feature[k] < low else 1 if feature[k] < high else 2


@dataclass(frozen=True)
class Cell:
    signal: str
    minutes: int
    horizon: int
    klass: str
    regime: str | None
    value: int | None

    @property
    def key(self) -> str:
        condition = f"{self.regime}={self.value}" if self.regime else "toutes"
        return f"{self.signal}|{self.minutes}|{self.horizon}|{self.klass}|{condition}"


def all_cells() -> list[Cell]:
    cells = []
    for signal in SIGNALS:
        for minutes in TIMEFRAMES:
            for horizon in HORIZONS:
                for klass in CLASSES:
                    cells.append(Cell(signal, minutes, horizon, klass, None, None))
                    for regime, count in REGIMES.items():
                        for value in range(count):
                            cells.append(Cell(signal, minutes, horizon, klass, regime, value))
    return cells


Selected = dict[str, list[tuple[Event, float]]]  # marché : (événement, coût) retenus


def gather(
    cell: Cell,
    found: dict[str, dict[str, Any]],
    cuts: dict[tuple[str, int], list[tuple[float, float]]],
    start: int,
    end: int,
) -> Selected:
    picked: Selected = {}
    for symbol in CLASSES[cell.klass]:
        rate = protocol.rate_of(symbol)
        rows = []
        for event in found[symbol]["events"][(cell.signal, cell.minutes, cell.horizon)]:
            if not start <= event.epoch < end:
                continue
            if (
                cell.regime
                and regime_of(event.features, cuts[(symbol, cell.minutes)], cell.regime)
                != cell.value
            ):
                continue
            rows.append((event, rate))
        picked[symbol] = rows
    return picked


def net_values(picked: Selected, cost: float = 1.0) -> list[float]:
    return [(e.gross - cost * rate) * BP for rows in picked.values() for e, rate in rows]


def share_positive(picked: Selected, cost: float = 1.0) -> float:
    means = [
        statistics.fmean((e.gross - cost * rate) for e, rate in rows)
        for rows in picked.values()
        if rows
    ]
    return sum(m > 0 for m in means) / len(means) if means else 0.0


def random_p(picked: Selected, draws: int = RANDOM_DRAWS, seed: int = 20261105) -> float:
    """Part des tirages du sens au hasard qui font au moins aussi bien, coûts compris."""
    rows = [(e.gross, rate) for r in picked.values() for e, rate in r]
    if not rows:
        return 1.0
    actual = statistics.fmean(g - c for g, c in rows)
    generator = random.Random(seed)  # noqa: S311
    better = 0
    for _ in range(draws):
        mean = statistics.fmean((g if generator.random() < 0.5 else -g) - c for g, c in rows)
        better += mean >= actual
    return (better + 1) / (draws + 1)


def break_even(picked: Selected) -> float | None:
    """Multiple des coûts mesurés qui annule le résultat : au-dessous de 1, perte."""
    rows = [(e.gross, rate) for r in picked.values() for e, rate in r]
    if not rows:
        return None
    gross = statistics.fmean(g for g, _ in rows)
    cost = statistics.fmean(c for _, c in rows)
    return gross / cost if cost > 0 else None


def view(values: Sequence[float]) -> dict[str, Any]:
    stat = protocol.stats_of(values)
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in stat.__dict__.items()}


def study(directory: Path, workers: int) -> dict[str, Any]:
    started = time.monotonic()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        found = dict(pool.map(_market, [(s, str(directory)) for s in STUDIED]))
    cells = all_cells()
    folds_cuts = [
        {(s, m): thresholds(found[s]["bars"][m], train_end) for s in STUDIED for m in TIMEFRAMES}
        for train_end, _ in FOLDS
    ]
    rows = []
    for cell in cells:
        entry: dict[str, Any] = {"cell": cell.key, "folds": []}
        for (train_end, valid_end), cuts in zip(FOLDS, folds_cuts, strict=True):
            train = gather(cell, found, cuts, 0, train_end)
            values = net_values(train)
            stat = protocol.stats_of(values)
            markets = len(CLASSES[cell.klass])
            chosen = (
                stat.n >= TRAIN_MIN_EVENTS
                and stat.mean > 0
                and stat.t >= TRAIN_MIN_T
                and (markets == 1 or share_positive(train) >= MIN_POSITIVE_MARKETS)
            )
            fold: dict[str, Any] = {"train": view(values), "chosen": chosen}
            if chosen:
                valid = gather(cell, found, cuts, train_end, valid_end)
                fold["valid"] = view(net_values(valid))
                fold["_valid"] = valid
            entry["folds"].append(fold)
        rows.append(entry)

    candidates = []
    for entry in rows:
        kept = [f for f in entry["folds"] if f["chosen"]]
        entry["chosen_folds"] = len(kept)
        if not kept:
            continue
        pooled: Selected = defaultdict(list)
        for fold in kept:
            for symbol, items in fold.pop("_valid").items():
                pooled[symbol].extend(items)
        values = net_values(pooled)
        stat = protocol.stats_of(values)
        checks = {
            "plis": len(kept) >= OOS_MIN_FOLDS,
            "evenements": stat.n >= OOS_MIN_EVENTS,
            "positif": stat.mean > 0,
            "t": stat.t >= OOS_MIN_T,
            "chaque_pli": all(f["valid"]["mean"] > 0 for f in kept if f["valid"]["n"]),
            "hasard": random_p(pooled) < ALPHA,
            "couts_x1_5": statistics.fmean(net_values(pooled, 1.5)) > 0 if values else False,
            "marches": share_positive(pooled) >= MIN_POSITIVE_MARKETS
            or len(CLASSES[entry["cell"].split("|")[3]]) == 1,
        }
        entry["oos"] = view(values)
        entry["oos_gross"] = view([e.gross * BP for r in pooled.values() for e, _ in r])
        entry["oos_cost_x2"] = view(net_values(pooled, 2.0))
        entry["oos_break_even"] = break_even(pooled)
        entry["oos_random_p"] = random_p(pooled) if values else 1.0
        entry["oos_markets"] = {s: view(net_values({s: r})) for s, r in pooled.items()}
        entry["checks"] = checks
        entry["passed"] = all(checks.values())
        if entry["passed"]:
            candidates.append(entry["cell"])
    for entry in rows:
        for fold in entry["folds"]:
            fold.pop("_valid", None)

    simulations = {key: simulate_cell(key, directory) for key in candidates}
    reference = landscape(directory, workers)
    return {
        "landscape": reference,
        "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "study_end": STUDY_END,
        "folds": FOLDS,
        "cells": len(cells),
        "rows": rows,
        "candidates": candidates,
        "simulations": simulations,
        "costs": cost_map(found),
        "seconds": round(time.monotonic() - started),
    }


# Simulation complète, avec stop, des cellules qui passent toutes les étapes.


def simulate_cell(key: str, directory: Path) -> dict[str, Any]:
    signal, minutes_text, horizon_text, klass, condition = key.split("|")
    minutes, horizon = int(minutes_text), int(horizon_text)
    regime, value = (None, None) if condition == "toutes" else condition.split("=")
    config = Config("conditions", minutes, (), Exit(STOP_ATR, hold=horizon))
    multipliers = json.loads((directory / "multipliers.json").read_text())
    by_market: dict[str, list[float]] = {}
    for symbol in CLASSES[klass]:
        bars = candles.load(candles.path_of(directory, symbol), until=STUDY_END)
        frame = indicators.resample(bars, minutes)
        width = indicators.atr(frame, 14)
        rate = protocol.rate_of(symbol)
        features = _features(frame, rate)
        values: list[float] = []
        for train_end, valid_end in FOLDS:
            cuts = thresholds(
                [(frame.epoch[i], f) for i, f in enumerate(features) if f is not None], train_end
            )
            signals = [
                (i, d)
                for i, d in _signals(frame)[signal]
                if features[i] is not None
                and (regime is None or regime_of(features[i], cuts, regime) == int(value or 0))  # type: ignore[arg-type]
            ]
            trades = run(bars, frame, width, signals, config, multipliers[symbol], since=train_end)
            values += [t.net_r(rate) for t in trades if t.opened_at < valid_end]
        by_market[symbol] = values
    pooled = [v for values in by_market.values() for v in values]
    stat = protocol.stats_of(pooled)
    return {
        "r": view(pooled),
        "passed": stat.n > 0 and stat.ci_low > 0,
        "markets": {s: view(v) for s, v in by_market.items()},
    }


# Référence descriptive : chaque signal en stratégie complète, sans condition. Ne sert à aucune
# sélection ; montre ce que donnent les signaux avec stop, frais et comparaison au hasard.

LANDSCAPE_DRAWS = 20


def _landscape_market(job: tuple[str, str, list[int]]) -> tuple[str, dict[str, Any]]:
    symbol, directory, multipliers = job
    bars = candles.load(candles.path_of(Path(directory), symbol), until=STUDY_END)
    rate = protocol.rate_of(symbol)
    first = FOLDS[0][0]
    result: dict[str, Any] = {}
    for minutes in TIMEFRAMES:
        frame = indicators.resample(bars, minutes)
        width = indicators.atr(frame, 14)
        signals = _signals(frame)
        for name in SIGNALS:
            for horizon in HORIZONS:
                config = Config("conditions", minutes, (), Exit(STOP_ATR, hold=horizon))
                trades = run(bars, frame, width, signals[name], config, multipliers)
                train = [t for t in trades if t.opened_at < first]
                oos = [t for t in trades if t.opened_at >= first]
                draws = []
                for seed in range(LANDSCAPE_DRAWS):
                    drawn = run(
                        bars, frame, width, signals[name], config, multipliers,
                        since=first, draw=random.Random(seed),  # noqa: S311
                    )  # fmt: skip
                    draws.append([t.net_r(rate) for t in drawn])
                result[f"{name}|{minutes}|{horizon}"] = {
                    "train": [t.net_r(rate) for t in train],
                    "oos": [(t.opened_at, t.net_r(rate), t.gross_r, t.fee_r * rate) for t in oos],
                    "draws": draws,
                }
    return symbol, result


def landscape(directory: Path, workers: int) -> dict[str, Any]:
    multipliers = json.loads((directory / "multipliers.json").read_text())
    jobs = [(s, str(directory), multipliers[s]) for s in STUDIED]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        found = dict(pool.map(_landscape_market, jobs))
    table = {}
    for key in found[STUDIED[0]]:
        oos = [row for s in STUDIED for row in found[s][key]["oos"]]
        values = [v for _, v, _, _ in oos]
        draws = [
            statistics.fmean(v)
            if (v := [x for s in STUDIED for x in found[s][key]["draws"][i]])
            else 0.0
            for i in range(LANDSCAPE_DRAWS)
        ]
        stat = protocol.stats_of(values)
        by_fold = [sum(v for e, v, _, _ in oos if a <= e < b) for a, b in FOLDS]
        gross = statistics.fmean(g for _, _, g, _ in oos) if oos else 0.0
        fee = statistics.fmean(c for _, _, _, c in oos) if oos else 0.0
        table[key] = {
            "train": view([v for s in STUDIED for v in found[s][key]["train"]]),
            "oos": view(values),
            "cost_x2": view([v - c for _, v, _, c in oos]),
            "break_even": gross / fee if fee > 0 else None,
            "random_mean": statistics.fmean(draws),
            "random_p": (sum(d >= stat.mean for d in draws) + 1) / (len(draws) + 1),
            "folds_positive": sum(total > 0 for total in by_fold),
            "markets": {
                s: round(statistics.fmean(v for _, v, _, _ in found[s][key]["oos"]), 3)
                if found[s][key]["oos"]
                else None
                for s in STUDIED
            },
        }
    return table


# Carte des coûts : la commission face au mouvement disponible.


def cost_map(found: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Médiane du rapport commission ÷ (ATR 14 ÷ cours) en 1 heure, par séance."""
    result = {}
    for symbol in STUDIED:
        rows = found[symbol]["bars"][60]
        ratios = [f[2] for _, f in rows]
        by_session: defaultdict[int, list[float]] = defaultdict(list)
        for _, f in rows:
            by_session[f[3]].append(f[2])
        result[symbol] = {
            "median": statistics.median(ratios),
            "sessions": {str(k): statistics.median(v) for k, v in sorted(by_session.items())},
            "cheap_share": sum(r < 0.1 for r in ratios) / len(ratios),
        }
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Recherche v2 : conditions de marché.")
    parser.add_argument("--directory", type=Path, default=candles.DATA_DIR)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)
    result = study(args.directory, args.workers)
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "conditions.json").write_text(json.dumps(result, indent=1, default=str))
    from app.backtest.research.conditions_report import render

    REPORT.write_text(render(result), encoding="utf-8", newline="\n")
    print(
        f"{result['cells']} cellules, {len(result['candidates'])} candidates, "
        f"{result['seconds']} s ; rapport écrit"
    )


if __name__ == "__main__":
    main()
