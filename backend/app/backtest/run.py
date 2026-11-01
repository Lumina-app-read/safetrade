"""
Rapport du banc d'essai : réglages choisis sur 70 % de l'historique, jugés sur les 30 % suivants.

    python -m app.backtest.run --output ../docs/decisions/banc-essai-v1.md

`.backtest/meta.json` donne, par actif, le multiplicateur, la commission et le stop minimum lus
sur un devis du compte démo, par exemple :
`{"stpRNG": {"multiplier": 750, "commission": 0.02, "stop_min": 0.1}}`.
"""

import argparse
import json
from datetime import UTC, datetime
from multiprocessing import Pool
from pathlib import Path
from typing import Any

from app.backtest.engine import Params, Trade
from app.backtest.fetch import DATA_DIR, path_of
from app.backtest.report import Summary, WalkForward, summarize, walk_forward

VERDICTS = {
    "positive": "Positif",
    "negative": "Négatif",
    "inconclusive": "Non concluant",
    "insufficient": "Échantillon insuffisant",
}


def load_ticks(path: Path) -> tuple[list[int], list[float]]:
    """Ligne coupée ou tick déjà vu : écartés. Les ticks sont déjà en ordre chronologique."""
    times: list[int] = []
    prices: list[float] = []
    for row in path.read_text(encoding="ascii").splitlines():
        epoch, _, price = row.partition(",")
        if not price or not epoch.isdigit():
            continue
        moment = int(epoch)
        if times and moment <= times[-1]:
            continue
        times.append(moment)
        prices.append(float(price))
    return times, prices


def study(job: tuple[str, Path, dict[str, Any]]) -> dict[str, Any]:
    symbol, directory, meta = job
    times, prices = load_ticks(path_of(directory, symbol))
    base = Params(
        multiplier=meta["multiplier"], commission=meta["commission"], stop_minimum=meta["stop_min"]
    )
    return {
        "symbol": symbol,
        "ticks": len(times),
        "first": times[0],
        "last": times[-1],
        "result": walk_forward(times, prices, base),
    }


def day(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%d/%m/%Y")


def money(value: float) -> str:
    return f"{value:+.2f}".replace(".", ",")


def percent(value: float) -> str:
    return f"{value:.1%}".replace(".", ",").replace("%", " %")


HEADER = (
    "| Actif | Positions | Réussite | Équilibre | Net | Par position | Avant frais | Intervalle "
    "| Baisse max. | Verdict |"
)
RULE = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"


def line(label: str, item: Summary, commission: float) -> str:
    rate = "n.d." if item.breakeven_win_rate is None else percent(item.breakeven_win_rate)
    gross = money(item.expectancy + commission) if item.trades else "n.d."
    return (
        f"| {label} | {item.trades} | {percent(item.win_rate)} | {rate} | {money(item.net)} | "
        f"{money(item.expectancy)} | {gross} | [{money(item.low)} ; {money(item.high)}] | "
        f"{money(-item.max_drawdown)} | {VERDICTS[item.verdict]} |"
    )


def whole_lines(studies: list[dict[str, Any]], field: str) -> list[str]:
    """Une ligne par actif, puis l'ensemble, frais moyens pondérés par le nombre de positions."""
    lines = []
    pooled: list[Trade] = []
    fees = 0.0
    for item in studies:
        trades: list[Trade] = getattr(item["result"], field)
        commission = item["result"].chosen.commission
        lines.append(line(item["symbol"], summarize(trades), commission))
        pooled += trades
        fees += commission * len(trades)
    return [*lines, line("**Ensemble**", summarize(pooled), fees / max(len(pooled), 1))]


def render(studies: list[dict[str, Any]]) -> str:
    rows = [
        "# Banc d'essai, stratégie version 1",
        "",
        f"Rapport généré le {datetime.now(UTC).strftime('%d/%m/%Y')} par `app.backtest.run`.",
        "",
        "Rejeu tick par tick du code du moteur, mise de 1 USD, frais compris. Réglages choisis sur",
        "les 70 % les plus anciens, puis jugés sur les 30 % les plus récents, jamais vus.",
        "**Ce rapport ne présente aucune stratégie comme rentable.**",
        "",
        "## Contrôle, hors de l'échantillon d'optimisation",
        "",
        "Résultat par position, en USD, avec son intervalle de confiance à 95 %.",
        "",
        HEADER,
        RULE,
    ]
    results: list[tuple[str, WalkForward]] = [(s["symbol"], s["result"]) for s in studies]
    rows += [line(symbol, result.test, result.chosen.commission) for symbol, result in results]
    rows += [
        "",
        "## Ce que le signal apporte",
        "",
        "Mêmes règles sur la période de contrôle, sens de chaque position tiré au sort.",
        "",
        HEADER,
        RULE,
    ]
    rows += [
        line(symbol, result.test_random, result.chosen.commission) for symbol, result in results
    ]
    rows += [
        "",
        "## Réglages actuels du moteur, sur la période de contrôle",
        "",
        HEADER,
        RULE,
    ]
    rows += [
        line(symbol, result.test_default, result.chosen.commission) for symbol, result in results
    ]
    rows += [
        "",
        "## Réglages actuels du moteur, sur tout l'historique",
        "",
        "Ces réglages n'ont pas été choisis sur ces données : les 7 jours comptent, sans biais",
        "d'optimisation. C'est le plus grand échantillon de ce rapport.",
        "",
        HEADER,
        RULE,
    ]
    rows += whole_lines(studies, "whole")
    rows += [
        "",
        "Mêmes règles, sens de chaque position tiré au sort.",
        "",
        HEADER,
        RULE,
    ]
    rows += whole_lines(studies, "whole_random")
    rows += [
        "",
        "## Optimisation",
        "",
        "Le meilleur réglage de la première période, parmi "
        f"{results[0][1].candidates} essayés, et sa chute hors échantillon.",
        "",
        "| Actif | Stop | Activation | Fraction | Par position, optimisé | Contrôle |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for symbol, result in results:
        chosen = result.chosen
        rows.append(
            f"| {symbol} | {chosen.stop_loss_pct:.0f} % | {chosen.activation_r} R | "
            f"{chosen.locked_fraction} | {money(result.train.expectancy)} | "
            f"{money(result.test.expectancy)} |"
        )
    rows += [
        "",
        "## Données",
        "",
        "| Actif | Ticks | Du | Au | Sorties sur le contrôle |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in studies:
        reasons = ", ".join(f"{k} {v}" for k, v in sorted(item["result"].test.reasons.items()))
        rows.append(
            f"| {item['symbol']} | {item['ticks']} | {day(item['first'])} | {day(item['last'])} | "
            f"{reasons or 'aucune'} |"
        )
    return "\n".join(rows) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.backtest.run")
    parser.add_argument("--directory", type=Path, default=DATA_DIR)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--symbols", nargs="*")
    args = parser.parse_args()
    meta = json.loads((args.directory / "meta.json").read_text(encoding="utf-8"))
    symbols = args.symbols or sorted(meta)
    jobs = [(symbol, args.directory, meta[symbol]) for symbol in symbols]
    with Pool() as pool:
        studies = pool.map(study, jobs)
    args.output.write_text(render(studies), encoding="utf-8", newline="\n")
    print(args.output)


if __name__ == "__main__":
    main()
