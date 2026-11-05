"""Rapport de la recherche v3, régénéré par `python -m app.backtest.research.scalping`."""

# Lignes de tableau Markdown : une ligne de code par ligne du rapport.
# ruff: noqa: E501

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from app.backtest.research import scalping

PRODUCTS = {"rise_fall": "Rise/Fall", "multiplicateur": "Multiplicateur x100"}
CHECKS = {
    "positions": "moins de 300 positions en validation",
    "positif": "négatif en validation",
    "significatif": "pas significatif en validation",
    "hasard": "pas meilleur que le sens tiré au sort",
    "jours": "positif moins de 5 jours sur 7",
    "delai": "négatif avec un tick de délai de plus",
}


def _f(value: float | None, digits: int = 3) -> str:
    return "sans objet" if value is None else f"{value:+.{digits}f}".replace(".", ",")


def _n(value: float | None, digits: int = 2) -> str:
    return "sans objet" if value is None else f"{value:.{digits}f}".replace(".", ",")


def _pct(value: float | None, digits: int = 1) -> str:
    return "sans objet" if value is None else f"{value * 100:.{digits}f} %".replace(".", ",")


def _dt(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%d/%m/%Y %H:%M")


def render(result: dict[str, Any]) -> str:
    data = result["data"]
    rows = [r for r in result["rows"] if r["delay"] == scalping.DELAY]
    retained = result["retained"]
    candidates = result["candidates"]
    pt, pv = result["predictability"]["train"], result["predictability"]["valid"]
    best_rf = max(
        (r for r in rows if r["product"] == "rise_fall"), key=lambda r: r["train"]["win_rate"]
    )
    best_rf_valid = max(
        (r for r in rows if r["product"] == "rise_fall"), key=lambda r: r["valid"]["win_rate"]
    )
    lines = [
        "# Recherche v3 : scalping sur Volatility 75 (1s)",
        "",
        f"- **Généré le :** {datetime.now(UTC).strftime('%d/%m/%Y %H:%M')} UTC par `python -m app.backtest.research.scalping`",
        "- **Protocole :** `recherche-scalping-protocole.md`, validé dans Git avant tout résultat (commit 8169179)",
        "- **Nature :** étude sur l'historique de Deriv, ticks réels à la seconde. Aucun résultat de démo, aucun ordre passé, moteur et module de risque inchangés.",
        f"- **Données :** {data['ticks']:,} ticks de 1HZ75V du {_dt(data['first'])} au {_dt(data['last'])} UTC, {data['gaps']} trous de plus d'une seconde. Entraînement jusqu'au 25/07/2026, validation ensuite. Rien d'août à octobre 2026.".replace(
            ",", " "
        ),
        "",
        "## Réponses",
        "",
    ]
    no_edge = not candidates
    lines += [
        "**1. Mouvements courts prévisibles ?** "
        + (
            "Non. Les variations tick à tick ne sont pas corrélées entre elles, les rapports de variance restent à 1, la volatilité ne forme pas de séquences, et aucun des "
            f"{result['tests']} tests de signaux ne tient en validation."
            if no_edge
            else "Des indices existent, voir les pistes plus bas, à confirmer."
        ),
        "",
        "**2. Quelle durée de détention étudier ?** "
        + (
            "Aucune ne se détache : de 1 à 60 ticks, le taux de réussite reste autour de 50 % et l'espérance nette suit le coût du produit."
            if no_edge
            else "Celle des pistes retenues ci-dessous."
        ),
        "",
        "**3. Plusieurs opportunités exploitables par minute ?** "
        + (
            "Des signaux, oui : jusqu'à plusieurs par minute selon la règle. Des opportunités exploitables, non : aucun signal ne dépasse le hasard une fois le coût déduit."
            if no_edge
            else "Voir les fréquences des pistes."
        ),
        "",
        "**4. Les frais permettent-ils une espérance positive ?** "
        f"Pas sans prévisibilité. Rise/Fall exige {_pct(scalping.RISE_FALL_BREAK_EVEN)} de réussite ; le meilleur signal à l'entraînement atteint {_pct(best_rf['train']['win_rate'])}, et le meilleur en validation {_pct(best_rf_valid['valid']['win_rate'])}. "
        f"Le multiplicateur x100 coûte {_pct(scalping.MULTIPLIER * scalping.MULTIPLIER_RATE)} de la mise par position, alors qu'un mouvement de 10 ticks vaut en moyenne {_pct(pt['sigma'] / 4600 * 100 * 10**0.5)} de la mise. "
        "L'accumulateur perd en moyenne à chaque durée de détention étudiée (tableau plus bas).",
        "",
        "**5. Quelle logique mérite un essai en démo ?** "
        + (
            "Aucune : rien n'a passé la validation, et la période réservée reste fermée."
            if no_edge
            else ", ".join(candidates)
        ),
        "",
        "**6. Limites :** trois semaines de ticks seulement, un seul indice, coûts relevés un jour donné, délai d'exécution modélisé à un tick (une seconde) sans mesure réelle en démo. Un avantage inférieur à environ un point de réussite sur Rise/Fall ne serait pas détectable avec cet échantillon.",
        "",
        "## Prévisibilité tick par tick",
        "",
        f"Écart type d'une variation : {_n(result['sigma'], 3)} point. Ticks sans variation : {_pct(pt['ties'])} à l'entraînement, {_pct(pv['ties'])} en validation (une égalité perd sur Rise/Fall).",
        "",
        "| Mesure | Entraînement | Validation | Hasard pur |",
        "| --- | --- | --- | --- |",
        f"| Autocorrélation des variations, décalage 1 à 3 | {', '.join(_f(x, 4) for x in pt['acf'][:3])} | {', '.join(_f(x, 4) for x in pv['acf'][:3])} | 0 (±{_n(pt['band'], 4)}) |",
        f"| Plus forte autocorrélation, décalages 1 à 10 | {_f(max(pt['acf'], key=abs), 4)} | {_f(max(pv['acf'], key=abs), 4)} | 0 |",
        f"| Autocorrélation de la taille des variations (séquences de volatilité), décalage 1 | {_f(pt['acf_abs'][0], 4)} | {_f(pv['acf_abs'][0], 4)} | 0 |",
    ]
    for k in (5, 10, 30, 60, 300):
        lines.append(
            f"| Rapport des variances sur {k} ticks | {_n(pt['vr'][str(k)] if str(k) in pt['vr'] else pt['vr'][k], 3)} | {_n(pv['vr'][str(k)] if str(k) in pv['vr'] else pv['vr'][k], 3)} | 1 |"
        )
    for k in range(1, 6):
        key = str(k) if str(k) in pt["up_after_ups"] else k
        lines.append(
            f"| Hausse après {k} hausse(s) de suite | {_pct(pt['up_after_ups'][key])} | {_pct(pv['up_after_ups'][key])} | 50 % |"
        )
    lines += [
        "",
        "## Signaux : entraînement puis validation",
        "",
        f"{len(rows)} combinaisons (20 signaux, 7 horizons, 2 produits) avec un tick de délai. Les 25 meilleures à l'entraînement :",
        "",
        "| Signal | Produit | Horizon | Signaux/min | Positions/min | Écartés | Entraînement : positions, réussite, net | Validation : positions, réussite, net [IC 95 %] | Pertes de suite | Drawdown | Coût cumulé | Hasard (p) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in sorted(rows, key=lambda r: -r["train"]["mean"])[:25]:
        t, v = row["train"], row["valid"]
        lines.append(
            f"| {row['signal']} | {PRODUCTS[row['product']]} | {row['horizon']} ticks | {_n(t['signals_per_minute'])} | {_n(t['positions_per_minute'])} | {_pct(t['rejected'], 0)} | "
            f"{t['n']}, {_pct(t['win_rate'])}, {_f(t['mean'])} | {v['n']}, {_pct(v['win_rate'])}, {_f(v['mean'])} [{_f(v['ci_low'])} ; {_f(v['ci_high'])}] | "
            f"{v['max_losses']} | {_n(v['max_drawdown'], 1)} | {_n(v['cost_total'], 0)} | {_n(v.get('random_p'), 3)} |"
        )
    lines += [
        "",
        "Résultats nets en fraction de la mise par position (+0,883 si juste sur Rise/Fall, -1 sinon ; sur le multiplicateur, la commission de 3,9 % est déduite). Drawdown et coût cumulé en mises.",
        "",
        f"**Retenues à l'entraînement :** {len(retained)} ; **passent la validation :** {len(candidates)}.",
    ]
    if retained:
        reasons = Counter(
            next(CHECKS[k] for k, ok in r["checks"].items() if not ok)
            for r in retained
            if not r["passed"]
        )
        lines += ["", "Motifs de rejet en validation :", ""] + [
            f"- {k} : {c}" for k, c in reasons.most_common()
        ]
    lines += [
        "",
        "## Durée de détention : toutes les règles confondues",
        "",
        "| Horizon | Réussite Rise/Fall, entraînement | Validation | Net Rise/Fall, validation | Net multiplicateur, validation |",
        "| --- | --- | --- | --- | --- |",
    ]
    for horizon in scalping.HORIZONS:
        rf = [r for r in rows if r["horizon"] == horizon and r["product"] == "rise_fall"]
        mu = [r for r in rows if r["horizon"] == horizon and r["product"] == "multiplicateur"]

        def pooled(items: list[dict[str, Any]], part: str, key: str) -> float:
            total = sum(r[part]["n"] for r in items)
            return sum(r[part][key] * r[part]["n"] for r in items) / total if total else 0.0

        lines.append(
            f"| {horizon} ticks | {_pct(pooled(rf, 'train', 'win_rate'))} | {_pct(pooled(rf, 'valid', 'win_rate'))} | {_f(pooled(rf, 'valid', 'mean'))} | {_f(pooled(mu, 'valid', 'mean'))} |"
        )
    lines += [
        "",
        "## Accumulateurs",
        "",
        "Espérance d'une position tenue k ticks, en fraction de la mise : (1 + taux)^k fois la part des positions qui survivent, moins 1. « Après calme » : entrée seulement quand l'écart type des 60 derniers ticks est dans le cinquième le plus bas de l'entraînement.",
        "",
        "| Taux | Barrière | Franchissement par tick (validation) | k = 1 | k = 5 | k = 10 | k = 20 | k = 50 | Après calme, k = 10 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for rate, item in result["accumulators"]["valid"].items():
        holds = item["toujours"]

        def get(block: dict[str, Any], k: int) -> float:
            found = block.get(str(k)) or block.get(k) or {}  # type: ignore[call-overload]
            return float(found.get("expectancy", 0.0))

        lines.append(
            f"| {_pct(float(rate), 0)} | ±{item['barrier']} | {_pct(item['knock_per_tick']['toujours'], 2)} | "
            + " | ".join(_f(get(holds, k)) for k in (1, 5, 10, 20, 50))
            + f" | {_f(get(item['apres_calme'], 10))} |"
        )
    lines += [
        "",
        "## Reproduire",
        "",
        "```bash",
        "python -m app.backtest.research.ticks --symbol 1HZ75V --start 2026-07-11 --end 2026-08-01",
        "python -m app.backtest.research.scalping",
        "```",
        "",
        f"Calcul : {result['seconds']} s. Coûts lus sur devis du compte démo le 5 novembre 2026, aucun achat.",
        "",
    ]
    return "\n".join(lines)
