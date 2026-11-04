"""
Recherche de stratégies, en deux phases séparées.

    python -m app.backtest.research.run --stage explore
    git add docs/decisions/recherche-strategies-selection.json && git commit
    python -m app.backtest.research.run --stage test

`explore` ne charge jamais une bougie de la période de test et écrit la sélection. `test` refuse
de tourner tant que cette sélection n'est pas validée dans Git, sans modification : l'historique
Git prouve que les stratégies ont été figées avant d'ouvrir le test.
"""

import argparse
import json
import shutil
import statistics
import subprocess
import time
from array import array
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.backtest.research import candles, protocol
from app.backtest.research.families import Config, all_configs, signals_of
from app.backtest.research.indicators import Frame, Series, atr, resample
from app.backtest.research.protocol import CLASSES, CONTROLS, STUDIED, Split, Stats
from app.backtest.research.report import render
from app.backtest.research.simulate import Trade, run

ROOT = Path(__file__).resolve().parents[4]
SELECTION = ROOT / "docs/decisions/recherche-strategies-selection.json"
REPORT = ROOT / "docs/decisions/recherche-strategies.md"
WORK = Path(".backtest/research")
CONFIGS = {config.key: config for config in all_configs()}


def _span(path: Path) -> tuple[int, int]:
    lines = path.read_text(encoding="ascii").split()
    return int(lines[0].split(",")[0]), int(lines[-1].split(",")[0])


def _multipliers(directory: Path) -> dict[str, list[int]]:
    data: dict[str, list[int]] = json.loads((directory / "multipliers.json").read_text())
    return data


class Market:
    """Bougies, unités de temps et signaux d'un marché, calculés une fois par processus."""

    def __init__(self, bars: candles.Bars) -> None:
        self.bars = bars
        self.frames: dict[int, tuple[Frame, Series]] = {}
        self.signals: dict[tuple[str, int, tuple[tuple[str, float], ...]], Any] = {}

    def trades(self, config: Config, multipliers: list[int], **options: Any) -> list[Trade]:
        if config.minutes not in self.frames:
            frame = resample(self.bars, config.minutes)
            self.frames[config.minutes] = (frame, atr(frame, 14))
        frame, width = self.frames[config.minutes]
        key = (config.family, config.minutes, config.options)
        if key not in self.signals:
            self.signals[key] = signals_of(config, frame)
        return run(self.bars, frame, width, self.signals[key], config, multipliers, **options)


Columns = dict[str, tuple["array[float]", "array[float]"]]


def _explore_market(job: tuple[str, str, int, int, list[int]]) -> tuple[str, dict[str, Columns]]:
    """Résultats bruts et coûts par période, en colonnes compactes : rien d'autre ne sort."""
    symbol, directory, train_end, valid_end, multipliers = job
    market = Market(candles.load(candles.path_of(Path(directory), symbol), until=valid_end))
    found: dict[str, Columns] = {}
    for key, config in CONFIGS.items():
        columns: Columns = {p: (array("d"), array("d")) for p in ("train", "valid")}
        for trade in market.trades(config, multipliers):
            gross, fee = columns["train" if trade.opened_at < train_end else "valid"]
            gross.append(trade.gross_r)
            fee.append(trade.fee_r)
        found[key] = columns
    return symbol, found


def _test_market(
    job: tuple[str, str, int, list[int], list[str]],
) -> tuple[str, dict[str, tuple[list[Trade], list[list[Trade]]]]]:
    symbol, directory, since, multipliers, keys = job
    market = Market(candles.load(candles.path_of(Path(directory), symbol)))
    result = {}
    for key in keys:
        config = CONFIGS[key]
        real = market.trades(config, multipliers, since=since)
        draws = [
            market.trades(config, multipliers, since=since, draw=seed) for seed in protocol.seeds()
        ]
        result[key] = (real, draws)
    return symbol, result


def _pooled(
    found: dict[str, dict[str, Columns]], markets: tuple[str, ...], key: str, period: str
) -> tuple[Stats, dict[str, list[float]]]:
    by_market = {}
    for symbol in markets:
        gross, fee = found[symbol][key][period]
        rate = protocol.rate_of(symbol)
        by_market[symbol] = [g - rate * f for g, f in zip(gross, fee, strict=True)]
    values = [v for s in markets for v in by_market[s]]
    return protocol.stats_of(values), by_market


def _stat_view(stat: Stats) -> dict[str, Any]:
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in stat.__dict__.items()}


def explore(directory: Path, workers: int) -> None:
    spans = {s: _span(candles.path_of(directory, s)) for s in (*STUDIED, *CONTROLS)}
    split = protocol.split_of({s: spans[s] for s in STUDIED})
    multipliers = _multipliers(directory)
    jobs = [(s, str(directory), split.train_end, split.valid_end, multipliers[s]) for s in STUDIED]
    started = time.monotonic()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        found = dict(pool.map(_explore_market, jobs))

    rows = []
    candidates = []
    for family in sorted({c.family for c in CONFIGS.values()}):
        keys = [k for k, c in CONFIGS.items() if c.family == family]
        for name, markets in CLASSES.items():
            train = {k: _pooled(found, markets, k, "train") for k in keys}
            chosen = protocol.choose_on_train(train)
            row: dict[str, Any] = {
                "family": family,
                "class": name,
                "configs": len(keys),
                "chosen": chosen,
            }
            if chosen is not None:
                valid, by_market = _pooled(found, markets, chosen, "valid")
                passed = protocol.passes_validation(valid, by_market, len(markets))
                row.update(
                    train=_stat_view(train[chosen][0]),
                    valid=_stat_view(valid),
                    valid_markets_positive=round(protocol.markets_positive(by_market), 2),
                    candidate=passed,
                )
                if passed:
                    candidates.append({"family": family, "class": name, "config": chosen})
            best = max(train.values(), key=lambda item: item[0].t)[0]
            row["train_best_any"] = _stat_view(best)
            rows.append(row)

    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "explore.json").write_text(
        json.dumps({"split": split.__dict__, "rows": rows}, indent=1)
    )
    SELECTION.write_text(
        json.dumps(
            {
                "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "split": {
                    k: datetime.fromtimestamp(v, UTC).isoformat() for k, v in split.__dict__.items()
                },
                "split_epochs": split.__dict__,
                "spans": {s: list(v) for s, v in spans.items()},
                "multipliers": multipliers,
                "configs_tried": len(CONFIGS),
                "candidates": candidates,
                "rows": rows,
            },
            indent=1,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    elapsed = time.monotonic() - started
    print(f"exploration : {len(rows)} couples, {len(candidates)} candidats, {elapsed:.0f} s")


def _committed(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    # Commandes fixes, sans entrée extérieure : seul le chemin de la sélection est passé à Git.
    git = shutil.which("git") or "git"
    tracked = subprocess.run(  # noqa: S603
        [git, "ls-files", "--error-unmatch", relative], cwd=ROOT, capture_output=True, check=False
    )
    clean = subprocess.run(  # noqa: S603
        [git, "diff", "--quiet", "HEAD", "--", relative], cwd=ROOT, check=False
    )
    return tracked.returncode == 0 and clean.returncode == 0


def test(directory: Path, workers: int) -> None:
    if not _committed(SELECTION):
        raise SystemExit(
            "La sélection doit être validée dans Git, sans modification, avant le test."
        )
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    split = Split(**selection["split_epochs"])
    multipliers = selection["multipliers"]
    candidates = selection["candidates"]
    keys = sorted({c["config"] for c in candidates})
    results: dict[str, dict[str, tuple[list[Trade], list[list[Trade]]]]] = {}
    if keys:
        jobs = [
            (s, str(directory), split.valid_end, multipliers[s], keys)
            for s in (*STUDIED, *CONTROLS)
        ]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = dict(pool.map(_test_market, jobs))

    tested = []
    for candidate in candidates:
        key, markets = candidate["config"], CLASSES[candidate["class"]]
        real = {s: results[s][key][0] for s in markets}
        pairs = [
            (t, v) for s in markets for t, v in zip(real[s], protocol.net(real[s], s), strict=True)
        ]
        values = [v for _, v in pairs]
        stat = protocol.stats_of(values)
        doubled = protocol.stats_of(
            [v for s in markets for v in protocol.net(real[s], s, cost=2.0)]
        )
        gross = protocol.stats_of([t.gross_r for s in markets for t in real[s]])
        draws = []
        for index in range(protocol.RANDOM_DRAWS):
            drawn = [v for s in markets for v in protocol.net(results[s][key][1][index], s)]
            draws.append(statistics.fmean(drawn) if drawn else 0.0)
        p_random = protocol.random_p_value(stat.mean, draws)
        by_market = {s: protocol.net(real[s], s) for s in markets}
        share = protocol.markets_positive(by_market)
        subs = protocol.subperiods_positive(pairs, split.valid_end, split.end)
        decision = protocol.verdict(
            stat, p_random, doubled, subs, share, len(markets), len(candidates)
        )
        controls = {
            s: _stat_view(protocol.stats_of(protocol.net(results[s][key][0], s))) for s in CONTROLS
        }
        tested.append(
            {
                **candidate,
                "test": _stat_view(stat),
                "gross": _stat_view(gross),
                "doubled_cost": _stat_view(doubled),
                "sharpe": protocol.sharpe(pairs),
                "random_mean": statistics.fmean(draws),
                "p_random": p_random,
                "markets_positive": share,
                "by_market": {s: _stat_view(protocol.stats_of(v)) for s, v in by_market.items()},
                "subperiods_positive": subs,
                "volatility_terciles": protocol.volatility_terciles(pairs),
                "max_cost": protocol.max_cost([t for s in markets for t in real[s]]),
                "controls": controls,
                "verdict": decision.__dict__,
                "passed": decision.passed,
            }
        )
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "test.json").write_text(json.dumps(tested, indent=1))
    REPORT.write_text(render(selection, tested), encoding="utf-8", newline="\n")
    kept = sum(t["passed"] for t in tested)
    print(f"test : {len(tested)} candidats, {kept} retenus ; rapport écrit")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Recherche de stratégies, protocole pré-enregistré."
    )
    parser.add_argument("--stage", choices=("explore", "test"), required=True)
    parser.add_argument("--directory", type=Path, default=candles.DATA_DIR)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)
    (explore if args.stage == "explore" else test)(args.directory, args.workers)


if __name__ == "__main__":
    main()
