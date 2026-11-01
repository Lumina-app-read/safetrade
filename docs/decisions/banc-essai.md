# Banc d'essai de la stratégie (étape 3.6)

- **Statut :** banc en place, première mesure du 1er novembre 2026
- **Résultats complets :** [banc-essai-v1.md](banc-essai-v1.md), généré par le banc

## Conclusion

**La stratégie version 1 n'a montré aucun avantage. Elle ne doit pas être présentée comme rentable, et le compte réel reste fermé.**

| Mesure, 7 jours, 6 indices, mise de 1 USD | Stratégie | Sens tiré au sort |
| --- | --- | --- |
| Positions | 936 | 903 |
| Par position | -0,05 USD | -0,05 USD |
| Intervalle à 95 % | [-0,07 ; -0,04] | [-0,07 ; -0,03] |
| Réussite | 16,5 % | 18,1 % |
| Réussite d'équilibre | 25,4 % | 26,8 % |

- Le croisement de moyennes ne fait pas mieux qu'un tirage au sort : le signal n'apporte rien de mesurable.
- La perte correspond surtout aux frais : -0,02 USD par position avant frais, -0,05 USD après.
- L'optimisation n'a rien sauvé. Sur Volatility 100, le meilleur des 27 réglages passe de +0,03 USD à -0,11 USD sur la période de contrôle. C'est le comportement attendu d'un réglage ajusté au hasard.

## Marchés réels : même verdict

Mesure du 1er novembre 2026 sur 14 jours : bitcoin, ether, or, EUR/USD, GBP/USD et USD/JPY. Résultats complets : [banc-essai-marches-reels.md](banc-essai-marches-reels.md).

| Mesure, mise de 1 USD | Stratégie | Sens tiré au sort |
| --- | --- | --- |
| Positions | 972 | 961 |
| Par position | -0,06 USD | -0,05 USD |
| Intervalle à 95 % | [-0,08 ; -0,04] | [-0,07 ; -0,03] |
| Avant frais | -0,01 USD | -0,01 USD |
| Réussite | 15,2 % | 16,9 % |
| Réussite d'équilibre | 24,0 % | 25,4 % |

- Ici non plus, le signal ne fait pas mieux que le hasard, et la perte vient presque entièrement des frais.
- **Forex à ×100 : 87 à 96 % du temps bloqué** par le filtre, une bougie n'y valant que 1 % de la mise. Il a donc été testé à ×500, qui est aussi plus risqué.
- **Commissions de l'or et du forex supposées** : 0,02 USD, la plus basse observée, car ces marchés étaient fermés lors de la mesure. L'hypothèse avantage la stratégie : une commission réelle plus haute aggraverait le résultat. À remplacer par un devis à la réouverture.
- Le bitcoin ressort à peine différent de zéro, sur 66 positions seulement. Il ne faut pas en tirer de conclusion, et l'optimisation par actif y varie autant que le hasard.

Cette mesure juge **cette stratégie**, un croisement de moyennes mobiles sur des bougies d'une minute. Elle ne dit pas qu'aucune stratégie ne peut fonctionner sur ces marchés, ni que deux semaines suffisent à le prouver.

## Pourquoi ce résultat n'étonne pas

Les indices synthétiques de Deriv sont produits par un générateur aléatoire, non par un marché. Sur un cours sans mémoire, aucune règle d'entrée ni de sortie ne peut créer d'espérance positive : couper vite ou laisser courir change la forme des résultats, pas leur moyenne. Reste alors le coût de chaque position.

Ce raisonnement vaut pour les indices synthétiques. Il explique la mesure, il ne la remplace pas : toute autre stratégie devra repasser au banc.

## Ce que le banc a corrigé

Le filtre de marché plat utilisait un seuil en pourcentage du cours, pensé pour ×100. **Step Index 100 était bloqué 100 % du temps** : le bot aurait tourné sans jamais ouvrir de position. Le seuil vaut maintenant en argent : une bougie moyenne doit représenter au moins 2 % de la mise, multiplicateur compris. Le comportement à ×100 ne change pas.

## Méthode

- **Rejeu tick par tick** de `strategy.evaluate`, `quality.candles_refusal` et `exits.decide`, le code du moteur. À ×750, un stop peut être touché dans une bougie d'une minute : des bougies seules seraient trompeuses.
- **Broker simulé** : stop au premier tick qui le franchit et à ce cours, donc glissement réel sur un saut ; `stop_out` à la mise ; vente au tick suivant la décision ; ordre 15 secondes après la fin de la bougie.
- **Coûts** : commission lue sur un devis du compte démo.
- **Calibration** : la formule retrouve les niveaux mesurés chez Deriv (stop à -0,471 %, `stop_out` à -0,971 % sur Volatility 75, ×100). Les sorties simulées ont le profil des positions démo réelles : stop à -0,50 à -0,55 USD, plancher à -0,10 à -0,13 USD.
- **Contrôle hors échantillon** : 27 réglages essayés sur les 70 % les plus anciens, jugés sur les 30 % les plus récents.
- **Témoin** : mêmes règles, sens tiré au sort.
- **Verdict** : « positif » seulement si tout l'intervalle à 95 % est au-dessus de zéro, sur 30 positions au moins.

```bash
cd backend
python -m app.backtest.fetch --days 7 --symbols 1HZ100V stpRNG BOOM500 JD10 RB100 1HZ15V
python -m app.backtest.run --output ../docs/decisions/banc-essai-v1.md
```

Les ticks restent dans `backend/.backtest/`, hors de Git. `meta.json` s'y écrit à partir d'un devis du compte démo.

## Limites

- Une semaine seulement : un marché qui change de régime n'y figure pas. Les données de plus d'une semaine restent à télécharger.
- Mise de 1 USD : la commission arrondie au cent y pèse lourd.
- Commission fixe, relue une fois : elle a varié de 0,04 à 0,05 USD sur Volatility 100.
- Sans limites de session ni position multiple. La pause après pertes est appliquée.
- Écart de -0,02 USD avant frais, présent aussi avec le sens tiré au sort. Son origine n'est pas établie : petit glissement réel, ou biais du simulateur.
- Le filtre corrigé n'a pas encore tourné sur une session réelle de démo sans signal forcé.
