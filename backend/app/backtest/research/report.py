"""Rapport de recherche en Markdown, régénéré par `run.py --stage test`, jamais écrit à la main."""

# Lignes de tableau Markdown : une ligne de code par ligne du rapport, plus lisible coupée nulle part.
# ruff: noqa: E501

from datetime import UTC, datetime
from typing import Any

from app.backtest.research import protocol

FAMILIES = {
    "tendance": "Tendance",
    "momentum": "Momentum",
    "retournement": "Retournement",
    "cassure": "Cassure",
    "volatilite": "Volatilité",
    "combinee": "Combinée",
}
CLASSES = {"crypto": "Crypto", "metaux": "Métaux", "forex": "Forex", "ensemble": "Ensemble"}


def _r(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "sans objet"
    text = f"{value:+.{digits}f}".replace(".", ",")
    return text.replace("+", "+") if value else text.replace("+", "")


def _n(value: float | None, digits: int = 2) -> str:
    return "sans objet" if value is None else f"{value:.{digits}f}".replace(".", ",")


def _pct(value: float | None, digits: int = 0) -> str:
    return "sans objet" if value is None else f"{value * 100:.{digits}f} %".replace(".", ",")


def _date(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%d/%m/%Y")


def _label(key: str | None) -> str:
    if not key:
        return "aucun"
    _, minutes, options, stop, target, hold, trail = key.split("|")
    parts = [f"{minutes} min", options or "défaut", f"stop {stop[1:]} ATR"]
    if target != "tNone":
        parts.append(f"objectif {target[1:]} ATR")
    if hold != "hNone":
        parts.append(f"{hold[1:]} bougies max")
    if trail != "rNone":
        parts.append(f"suivi {trail[1:]} ATR")
    return ", ".join(parts).replace(".", ",")


def render(selection: dict[str, Any], tested: list[dict[str, Any]]) -> str:
    split = selection["split_epochs"]
    rows = selection["rows"]
    lines = [
        "# Recherche de stratégies : résultats",
        "",
        f"- **Généré le :** {datetime.now(UTC).strftime('%d/%m/%Y %H:%M')} UTC, par `python -m app.backtest.research.run --stage test`",
        "- **Protocole :** `recherche-strategies-protocole.md`, validé dans Git avant tout résultat",
        f"- **Sélection figée :** `recherche-strategies-selection.json`, écrite le {selection['written_at'][:10]} et validée dans Git avant l'ouverture du test",
        "- **Nature des résultats :** **simulation sur l'historique de Deriv**. Aucun résultat obtenu en démo n'est présenté ici, aucun ordre n'a été passé.",
        "",
        "## Conclusion",
        "",
    ]
    passed = [t for t in tested if t["passed"]]
    if not tested:
        lines += [
            "**Aucune stratégie n'a franchi la validation : aucune n'a été ouverte sur la période de test.**",
            "",
            f"Sur {selection['configs_tried']} réglages répartis en six familles et quatre classes de marchés, "
            "aucun n'a présenté sur la validation une espérance positive après frais assez solide "
            "(statistique t d'au moins 1,65, au moins 50 positions, au moins 60 % des marchés positifs). "
            "Aucune stratégie de ce document ne peut être présentée comme ayant un avantage statistique.",
        ]
    elif not passed:
        lines += [
            f"**Aucune stratégie n'a d'avantage statistique robuste après frais.** {len(tested)} candidat(s) "
            "issus de la validation ont été ouverts une seule fois sur le test ; aucun ne remplit toutes les conditions du verdict.",
        ]
    else:
        lines += [
            f"**{len(passed)} piste(s) méritent une validation supplémentaire en démo**, et rien de plus : "
            "un résultat simulé n'est pas une preuve de rentabilité. Toutes les autres pistes sont écartées.",
        ]
    lines += [
        "",
        "Le module de risque reste inchangé et indépendant de la stratégie : stop loss obligatoire, plafonds "
        "d'exposition et de pertes, réconciliation, anti-doublon, arrêt d'urgence, aucune hausse de mise après une perte.",
        "",
        "## Données",
        "",
        "| Marché | Début | Fin | Commission par position |",
        "| --- | --- | --- | --- |",
    ]
    for symbol, (first, last) in selection["spans"].items():
        rate = protocol.rate_of(symbol)
        source = "mesurée" if symbol in protocol.RATES else "supposée"
        lines.append(
            f"| {symbol} | {_date(first)} | {_date(last)} | {_pct(rate, 4)} du notionnel, {source} |"
        )
    lines += [
        "",
        f"Période commune découpée aux mêmes dates : entraînement jusqu'au {_date(split['train_end'])}, "
        f"validation jusqu'au {_date(split['valid_end'])}, test jusqu'au {_date(split['end'])}. "
        "La crypto garde son historique antérieur dans l'entraînement.",
        "",
        "Hypothèses : entrée à l'ouverture de la minute qui suit la clôture du signal, stop avant objectif dans une même minute, "
        "sortie au cours d'ouverture en cas de saut, glissement de 5 % du risque à chaque stop, mise constante, "
        "une position à la fois, position écartée si aucun multiplicateur de Deriv ne place le stop entre 10 % et 90 % de la mise. "
        "Résultats en R : 1 R est la perte prévue par le stop.",
        "",
        "## Tableau comparatif : entraînement et validation",
        "",
        "Un réglage par couple, choisi sur l'entraînement seulement (meilleure statistique t, au moins 100 positions, espérance positive).",
        "",
        "| Famille | Classe | Réglage retenu | Entraînement : positions, espérance, t | Validation : positions, espérance, t | Candidat |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        train, valid = row.get("train"), row.get("valid")
        train_text = (
            f"{train['n']}, {_r(train['mean'])} R, {_n(train['t'])}"
            if train
            else (f"aucun réglage positif (meilleur t : {_n(row['train_best_any']['t'])})")
        )
        valid_text = (
            f"{valid['n']}, {_r(valid['mean'])} R, {_n(valid['t'])}" if valid else "sans objet"
        )
        lines.append(
            f"| {FAMILIES[row['family']]} | {CLASSES[row['class']]} | {_label(row['chosen'])} | {train_text} | {valid_text} | "
            f"{'oui' if row.get('candidate') else 'non'} |"
        )
    if tested:
        lines += [
            "",
            "## Test : une seule ouverture",
            "",
            "| Famille, classe | Positions | Réussite | Gain moyen | Perte moyenne | Espérance nette [IC 95 %] | Profit factor | Drawdown max | Total net | Sharpe | Tirage au sort | p hasard | Coûts doublés | Coût max supportable | Verdict |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for item in tested:
            s = item["test"]
            lines.append(
                f"| {FAMILIES[item['family']]}, {CLASSES[item['class']]} | {s['n']} | {_pct(s['win_rate'])} | {_r(s['avg_win'])} R | "
                f"{_r(s['avg_loss'])} R | {_r(s['mean'])} R [{_r(s['ci_low'])} ; {_r(s['ci_high'])}] | {_n(s['profit_factor'])} | "
                f"{_n(s['max_drawdown'], 1)} R | {_r(s['total'], 1)} R | {_n(item['sharpe'])} | {_r(item['random_mean'])} R | "
                f"{_n(item['p_random'], 3)} | {_r(item['doubled_cost']['mean'])} R | {_pct(item['max_cost'], 4)} | "
                f"{'retenue pour la démo' if item['passed'] else 'écartée'} |"
            )
        lines += [
            "",
            "Détail des conditions du verdict, par marché, par tiers de volatilité et sur les témoins :",
            "",
        ]
        for item in tested:
            v = item["verdict"]
            lines += [
                f"### {FAMILIES[item['family']]}, {CLASSES[item['class']]} : {_label(item['config'])}",
                "",
                f"- Significative après correction de Bonferroni : {'oui' if v['significant'] else 'non'} (p = {_n(item['test']['p'], 4)})",
                f"- Meilleure que le sens tiré au sort : {'oui' if v['beats_random'] else 'non'}",
                f"- Positive à coûts doublés : {'oui' if v['survives_double_cost'] else 'non'}",
                f"- Sous-périodes positives : {item['subperiods_positive']} sur 3",
                f"- Marchés positifs : {_pct(item['markets_positive'])}",
                f"- Avant frais : {_r(item['gross']['mean'])} R par position",
                "- Par tiers de volatilité (faible, moyenne, forte) : "
                + ", ".join(f"{_r(x)} R" for x in item["volatility_terciles"]),
                "- Par marché : "
                + ", ".join(
                    f"{s} {_r(m['mean'])} R ({m['n']})" for s, m in item["by_market"].items()
                ),
                "- Témoins aléatoires : "
                + ", ".join(
                    f"{s} {_r(m['mean'])} R ({m['n']})" for s, m in item["controls"].items()
                ),
                "",
            ]
    lines += [
        "## Reproduire",
        "",
        "```bash",
        "python -m app.backtest.research.candles --end 2026-11-01 --days 365 --symbols <marché>",
        "python -m app.backtest.research.run --stage explore",
        "python -m app.backtest.research.run --stage test",
        "```",
        "",
        "Les bougies restent dans `backend/.backtest/candles/`, hors Git ; les multiplicateurs lus chez Deriv sont dans la sélection.",
        "",
    ]
    return "\n".join(lines)
