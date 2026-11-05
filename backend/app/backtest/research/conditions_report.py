"""Rapport de la recherche v2, régénéré par `python -m app.backtest.research.conditions`."""

# Lignes de tableau Markdown : une ligne de code par ligne du rapport.
# ruff: noqa: E501

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from app.backtest.research import protocol

SIGNALS = {
    "momentum": "Momentum",
    "acceleration": "Accélération",
    "exces": "Excès, sens inverse",
    "cassure_compression": "Cassure après compression",
    "alignement": "Alignement d'unités",
}
CLASSES = {"crypto": "Crypto", "metaux": "Métaux", "forex": "Forex", "ensemble": "Ensemble"}
REGIMES = {
    "tendance": ("tendance faible", "tendance moyenne", "tendance forte"),
    "volatilite": ("volatilité en baisse", "volatilité stable", "volatilité en hausse"),
    "cout": ("coût bas", "coût moyen", "coût élevé"),
    "seance": ("0-7 h UTC", "7-13 h UTC", "13-21 h UTC", "21-24 h UTC"),
}
CHECKS = {
    "plis": "retenue dans moins de deux plis",
    "evenements": "moins de 100 événements hors échantillon",
    "positif": "négative hors échantillon",
    "t": "statistique t hors échantillon sous 2",
    "chaque_pli": "négative dans au moins un pli",
    "hasard": "pas meilleure que le sens tiré au sort",
    "couts_x1_5": "négative à 1,5 fois les coûts",
    "marches": "moins de 60 % des marchés positifs",
}


def _f(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "sans objet"
    return f"{value:+.{digits}f}".replace(".", ",")


def _n(value: float | None, digits: int = 2) -> str:
    return "sans objet" if value is None else f"{value:.{digits}f}".replace(".", ",")


def _pct(value: float | None) -> str:
    return "sans objet" if value is None else f"{value * 100:.0f} %"


def _date(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%d/%m/%Y")


def label(key: str) -> str:
    signal, minutes, horizon, klass, condition = key.split("|")
    if condition == "toutes":
        where = "toutes conditions"
    else:
        regime, value = condition.split("=")
        where = REGIMES[regime][int(value)]
    return (
        f"{SIGNALS[signal]}, {minutes} min, sortie à {horizon} bougies, {CLASSES[klass]}, {where}"
    )


def render(result: dict[str, Any]) -> str:
    rows = result["rows"]
    tried = [r for r in rows if r["chosen_folds"]]
    passed = [r for r in tried if r.get("passed")]
    simulations = result["simulations"]
    kept = [k for k, s in simulations.items() if s["passed"]]
    folds = result["folds"]
    lines = [
        "# Recherche v2 : conditions de marché",
        "",
        f"- **Généré le :** {datetime.now(UTC).strftime('%d/%m/%Y %H:%M')} UTC par `python -m app.backtest.research.conditions`",
        "- **Protocole :** `recherche-conditions-protocole.md`, validé dans Git avant tout résultat de cette phase (commit 3573fad)",
        "- **Nature :** étude et simulation sur l'historique de Deriv. Aucun résultat de démo, aucun ordre passé.",
        f"- **Période réservée :** rien n'est lu à partir du {_date(result['study_end'])} : août à octobre 2026 reste intact.",
        "",
        "## Conclusion",
        "",
    ]
    if not kept:
        lines.append(
            f"**Aucune condition de marché ne donne un avantage fiable après frais.** Sur {result['cells']} cellules "
            f"(5 signaux, 2 unités de temps, 2 horizons, 4 classes de marchés, 14 conditions), {len(tried)} ont passé "
            f"le filtre d'entraînement d'au moins un pli, {len(passed)} ont passé toutes les étapes hors échantillon"
            + (
                ", et aucune n'a gardé une espérance sûrement positive une fois simulée avec un stop."
                if passed
                else "."
            )
        )
        lines += [
            "",
            "Le test réservé n'est donc pas ouvert, et aucune piste n'est proposée pour le compte démo.",
            "",
            "Dans le tableau de référence, le sens tiré au sort fait aussi bien que chaque signal : les signaux ne portent pas d'information sur le sens du mouvement suivant, et la perte par position correspond pour l'essentiel aux frais. Le forex est le plus pénalisé : la commission y vaut 18 à 28 % du mouvement d'une heure.",
            "",
            "**Phase démo :** non lancée, faute de candidate. Si une hypothèse passait un jour toutes les étapes puis le test réservé, elle tournerait sur le compte démo avec le moteur existant, sans rien changer au module de risque, et le journal des décisions servirait à comparer historique, simulation et démo : délai entre signal et exécution, prix reçu face au prix théorique, commission facturée, positions refusées et coupures de connexion.",
        ]
    else:
        lines.append(
            f"**{len(kept)} piste(s) passent toutes les étapes** et méritent le test réservé puis une période en démo. "
            "Aucune n'est une stratégie rentable : ce sont des hypothèses à confirmer."
        )
    lines += [
        "",
        "Le moteur d'exécution et le module de risque n'ont pas été touchés : stop obligatoire, plafonds, limites de pertes, anti-doublon, arrêt d'urgence, aucune hausse de mise après une perte.",
        "",
        "## Pourquoi : la commission face au mouvement disponible",
        "",
        "Rapport médian entre la commission mesurée et le mouvement moyen d'une bougie d'une heure (ATR 14 ÷ cours). À 0,25, une position doit capter un quart du mouvement d'une heure avant d'être rentable.",
        "",
        "| Marché | Médiane | 0-7 h | 7-13 h | 13-21 h | 21-24 h | Heures où le coût reste sous 10 % du mouvement |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for symbol, item in result["costs"].items():
        sessions = [item["sessions"].get(str(k)) for k in range(4)]
        lines.append(
            f"| {symbol} | {_n(item['median'])} | "
            + " | ".join(_n(v) for v in sessions)
            + f" | {_pct(item['cheap_share'])} |"
        )
    lines += [
        "",
        "## Méthode",
        "",
        "- **Approches :** cinq signaux (momentum, accélération, excès en sens inverse, cassure après compression de volatilité, alignement avec l'unité quatre fois plus longue), chacun lu seul et sous une condition de marché à la fois : tendance, volatilité, coût relatif, séance. Les quatre conditions répondent aux pistes demandées : régimes, filtrage par volatilité et par coût, liquidité par séance.",
        "- **Mesure :** mouvement dans le sens du signal, de l'ouverture de la minute suivante à la clôture de 4 ou 16 bougies plus tard, moins la commission mesurée. Événements sans chevauchement. Résultats en points de base (pb) du notionnel.",
        "- **Validation glissante :** "
        + " ; ".join(
            f"entraînement jusqu'au {_date(a)}, validation jusqu'au {_date(b)}" for a, b in folds
        )
        + ". Seuils des conditions calculés sur l'entraînement de chaque pli.",
        "- **Sélection :** entraînement d'un pli : au moins 150 événements, moyenne nette positive, t ≥ 3, 60 % des marchés positifs. Hors échantillon : retenue dans au moins 2 plis, 100 événements, moyenne positive, t ≥ 2, positive dans chaque pli, mieux que 2 000 tirages du sens au hasard (p < 5 %), positive à 1,5 fois les coûts, 60 % des marchés positifs. Puis simulation avec stop de 2 ATR : intervalle de confiance à 95 % au-dessus de zéro.",
        "",
        "## Entraînement : les cellules retenues dans au moins un pli",
        "",
        "| Cellule | Plis | Entraînement (dernier pli) : événements, moyenne nette, t | Hors échantillon : événements, moyenne nette [IC 95 %], t | Avant frais | Coûts doublés | Frais qui annulent | Sens au hasard (p) | Décision |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in sorted(tried, key=lambda r: -(r.get("oos") or {}).get("t", -99))[:40]:
        train = next(f["train"] for f in reversed(row["folds"]) if f["chosen"])
        oos = row["oos"]
        failed = [CHECKS[k] for k, ok in row["checks"].items() if not ok]
        decision = "passe" if row["passed"] else failed[0]
        lines.append(
            f"| {label(row['cell'])} | {row['chosen_folds']} | {train['n']}, {_f(train['mean'])} pb, {_n(train['t'])} | "
            f"{oos['n']}, {_f(oos['mean'])} pb [{_f(oos['ci_low'])} ; {_f(oos['ci_high'])}], {_n(oos['t'])} | "
            f"{_f(row['oos_gross']['mean'])} pb | {_f(row['oos_cost_x2']['mean'])} pb | {_n(row['oos_break_even'])} fois | "
            f"{_n(row['oos_random_p'], 3)} | {decision} |"
        )
    if len(tried) > 40:
        lines.append(
            f"\n{len(tried) - 40} autres cellules, moins bonnes hors échantillon, sont dans `backend/.backtest/research/conditions.json`."
        )
    reasons = Counter(
        next(CHECKS[k] for k, ok in r["checks"].items() if not ok) for r in tried if not r["passed"]
    )
    lines += [
        "",
        "## Rejets",
        "",
        f"{result['cells'] - len(tried)} cellules n'ont passé l'entraînement d'aucun pli. Pour les autres, premier motif de rejet :",
        "",
    ]
    lines += [f"- {reason} : {count}" for reason, count in reasons.most_common()] or ["- aucune"]
    if tried:
        best = max(tried, key=lambda r: r["oos"]["t"])
        lines += [
            "",
            f"Détail par marché, hors échantillon, de la meilleure cellule ({label(best['cell'])}) :",
            "",
            "| Marché | Événements | Réussite | Gain moyen | Perte moyenne | Moyenne nette | Profit factor | Drawdown | Total |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for symbol, m in best["oos_markets"].items():
            lines.append(
                f"| {symbol} | {m['n']} | {_pct(m['win_rate'])} | {_f(m['avg_win'])} pb | {_f(m['avg_loss'])} pb | {_f(m['mean'])} pb | "
                f"{_n(m['profit_factor'])} | {_n(m['max_drawdown'], 0)} pb | {_f(m['total'], 0)} pb |"
            )
    reference = result.get("landscape") or {}
    if reference:
        lines += [
            "",
            "## Référence : les signaux en stratégie complète, sans condition",
            "",
            "Descriptif, sans aucune sélection : chaque signal simulé avec le stop obligatoire de 2 ATR, la sortie au temps de l'horizon, une position à la fois et les multiplicateurs de Deriv, sur les dix marchés. Entraînement : avant le 1er février 2026. Hors échantillon : du 1er février au 1er août 2026. Résultats nets de frais, en R (1 R = la perte prévue par le stop).",
            "",
            "| Signal | Entraînement : positions, espérance | Hors échantillon : positions | Réussite | Gain moyen | Perte moyenne | Espérance [IC 95 %] | Profit factor | Drawdown | Total | Sens au hasard | p | Coûts doublés | Frais qui annulent | Plis positifs |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for key, item in reference.items():
            name, minutes, horizon = key.split("|")
            t, o = item["train"], item["oos"]
            lines.append(
                f"| {SIGNALS[name]}, {minutes} min, {horizon} bougies | {t['n']}, {_f(t['mean'], 3)} R | {o['n']} | {_pct(o['win_rate'])} | "
                f"{_f(o['avg_win'], 2)} R | {_f(o['avg_loss'], 2)} R | {_f(o['mean'], 3)} R [{_f(o['ci_low'], 3)} ; {_f(o['ci_high'], 3)}] | "
                f"{_n(o['profit_factor'])} | {_n(o['max_drawdown'], 1)} R | {_f(o['total'], 1)} R | {_f(item['random_mean'], 3)} R | "
                f"{_n(item['random_p'], 2)} | {_f(item['cost_x2']['mean'], 3)} R | {_n(item['break_even'])} fois | {item['folds_positive']} sur 3 |"
            )
        markets = list(next(iter(reference.values()))["markets"])
        lines += [
            "",
            "Espérance hors échantillon par marché, en R :",
            "",
            "| Signal | " + " | ".join(markets) + " |",
            "| --- | " + " | ".join("---" for _ in markets) + " |",
        ]
        for key, item in reference.items():
            name, minutes, horizon = key.split("|")
            lines.append(
                f"| {SIGNALS[name]}, {minutes} min, {horizon} | "
                + " | ".join(_f(item["markets"][m], 2) for m in markets)
                + " |"
            )
        positive = [k for k, item in reference.items() if item["oos"]["ci_low"] > 0]
        lines += [
            "",
            f"Signaux dont l'espérance hors échantillon est sûrement positive (intervalle à 95 % au-dessus de zéro) : {len(positive)} sur {len(reference)}.",
        ]
    if simulations:
        lines += [
            "",
            "## Simulation avec stop",
            "",
            "| Cellule | Positions | Espérance nette [IC 95 %] | Profit factor | Drawdown | Décision |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for key, s in simulations.items():
            r = s["r"]
            lines.append(
                f"| {label(key)} | {r['n']} | {_f(r['mean'], 3)} R [{_f(r['ci_low'], 3)} ; {_f(r['ci_high'], 3)}] | {_n(r['profit_factor'])} | {_n(r['max_drawdown'], 1)} R | {'piste' if s['passed'] else 'rejetée'} |"
            )
    lines += [
        "",
        "## Limites",
        "",
        f"- {result['cells']} cellules testées sur chaque pli : sous l'hypothèse d'aucun avantage, quelques-unes passent l'entraînement par hasard. Les étapes hors échantillon, le tirage au sort et les plis successifs servent à les écarter.",
        "- Juin et juillet 2026 avaient déjà servi de validation à la première campagne, et cette approche a été choisie après en avoir vu les résultats. Seule la période réservée est entièrement vierge.",
        "- Le tableau de référence a été ajouté après la première exécution, pour donner les indicateurs complets demandés ; il est descriptif et ne sert à aucune sélection.",
        "- Une seule année d'historique, six mois hors échantillon : un avantage faible, inférieur à quelques points de base, ne peut pas être distingué du hasard.",
        "- Coûts : commissions mesurées sur devis démo le 4 novembre 2026 ; elles peuvent changer. Glissement non compté dans l'étude d'événements (sortie au temps), compté à 5 % de R au stop dans la simulation.",
        "",
        "## Reproduire",
        "",
        "```bash",
        "python -m app.backtest.research.candles --end 2026-11-01 --days 365 --symbols <marché>   # une fois",
        "python -m app.backtest.research.candles --end 2026-11-01 --repair",
        "python -m app.backtest.research.conditions",
        "```",
        "",
        f"Durée de calcul : {result['seconds']} s. Commissions utilisées : "
        + ", ".join(
            f"{s} {protocol.rate_of(s) * 100:.4f} %".replace(".", ",") for s in protocol.STUDIED
        )
        + ".",
        "",
    ]
    return "\n".join(lines)
