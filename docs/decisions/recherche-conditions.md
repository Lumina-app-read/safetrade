# Recherche v2 : conditions de marché

- **Généré le :** 05/11/2026 10:06 UTC par `python -m app.backtest.research.conditions`
- **Protocole :** `recherche-conditions-protocole.md`, validé dans Git avant tout résultat de cette phase (commit 3573fad)
- **Nature :** étude et simulation sur l'historique de Deriv. Aucun résultat de démo, aucun ordre passé.
- **Période réservée :** rien n'est lu à partir du 01/08/2026 : août à octobre 2026 reste intact.

## Conclusion

**Aucune condition de marché ne donne un avantage fiable après frais.** Sur 1120 cellules (5 signaux, 2 unités de temps, 2 horizons, 4 classes de marchés, 14 conditions), 1 ont passé le filtre d'entraînement d'au moins un pli, 0 ont passé toutes les étapes hors échantillon.

Le test réservé n'est donc pas ouvert, et aucune piste n'est proposée pour le compte démo.

Dans le tableau de référence, le sens tiré au sort fait aussi bien que chaque signal : les signaux ne portent pas d'information sur le sens du mouvement suivant, et la perte par position correspond pour l'essentiel aux frais. Le forex est le plus pénalisé : la commission y vaut 18 à 28 % du mouvement d'une heure.

**Phase démo :** non lancée, faute de candidate. Si une hypothèse passait un jour toutes les étapes puis le test réservé, elle tournerait sur le compte démo avec le moteur existant, sans rien changer au module de risque, et le journal des décisions servirait à comparer historique, simulation et démo : délai entre signal et exécution, prix reçu face au prix théorique, commission facturée, positions refusées et coupures de connexion.

Le moteur d'exécution et le module de risque n'ont pas été touchés : stop obligatoire, plafonds, limites de pertes, anti-doublon, arrêt d'urgence, aucune hausse de mise après une perte.

## Pourquoi : la commission face au mouvement disponible

Rapport médian entre la commission mesurée et le mouvement moyen d'une bougie d'une heure (ATR 14 ÷ cours). À 0,25, une position doit capter un quart du mouvement d'une heure avant d'être rentable.

| Marché | Médiane | 0-7 h | 7-13 h | 13-21 h | 21-24 h | Heures où le coût reste sous 10 % du mouvement |
| --- | --- | --- | --- | --- | --- | --- |
| cryBTCUSD | 0,05 | 0,05 | 0,06 | 0,05 | 0,05 | 90 % |
| cryETHUSD | 0,11 | 0,10 | 0,12 | 0,10 | 0,10 | 44 % |
| frxXAUUSD | 0,03 | 0,03 | 0,03 | 0,03 | 0,03 | 100 % |
| frxXAGUSD | 0,06 | 0,06 | 0,07 | 0,06 | 0,06 | 95 % |
| frxEURUSD | 0,26 | 0,29 | 0,28 | 0,22 | 0,25 | 1 % |
| frxGBPUSD | 0,18 | 0,21 | 0,20 | 0,15 | 0,18 | 3 % |
| frxUSDJPY | 0,27 | 0,29 | 0,27 | 0,25 | 0,30 | 2 % |
| frxAUDUSD | 0,28 | 0,29 | 0,29 | 0,25 | 0,29 | 0 % |
| frxUSDCAD | 0,28 | 0,31 | 0,32 | 0,24 | 0,26 | 0 % |
| frxEURJPY | 0,26 | 0,29 | 0,26 | 0,25 | 0,29 | 1 % |

## Méthode

- **Approches :** cinq signaux (momentum, accélération, excès en sens inverse, cassure après compression de volatilité, alignement avec l'unité quatre fois plus longue), chacun lu seul et sous une condition de marché à la fois : tendance, volatilité, coût relatif, séance. Les quatre conditions répondent aux pistes demandées : régimes, filtrage par volatilité et par coût, liquidité par séance.
- **Mesure :** mouvement dans le sens du signal, de l'ouverture de la minute suivante à la clôture de 4 ou 16 bougies plus tard, moins la commission mesurée. Événements sans chevauchement. Résultats en points de base (pb) du notionnel.
- **Validation glissante :** entraînement jusqu'au 01/02/2026, validation jusqu'au 01/04/2026 ; entraînement jusqu'au 01/04/2026, validation jusqu'au 01/06/2026 ; entraînement jusqu'au 01/06/2026, validation jusqu'au 01/08/2026. Seuils des conditions calculés sur l'entraînement de chaque pli.
- **Sélection :** entraînement d'un pli : au moins 150 événements, moyenne nette positive, t ≥ 3, 60 % des marchés positifs. Hors échantillon : retenue dans au moins 2 plis, 100 événements, moyenne positive, t ≥ 2, positive dans chaque pli, mieux que 2 000 tirages du sens au hasard (p < 5 %), positive à 1,5 fois les coûts, 60 % des marchés positifs. Puis simulation avec stop de 2 ATR : intervalle de confiance à 95 % au-dessus de zéro.

## Entraînement : les cellules retenues dans au moins un pli

| Cellule | Plis | Entraînement (dernier pli) : événements, moyenne nette, t | Hors échantillon : événements, moyenne nette [IC 95 %], t | Avant frais | Coûts doublés | Frais qui annulent | Sens au hasard (p) | Décision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Alignement d'unités, 60 min, sortie à 16 bougies, Ensemble, volatilité stable | 1 | 363, +33,6 pb, 3,23 | 166, -10,8 pb [-35,0 ; +13,4], -0,88 | -7,1 pb | -14,5 pb | -1,90 fois | 0,714 | retenue dans moins de deux plis |

## Rejets

1119 cellules n'ont passé l'entraînement d'aucun pli. Pour les autres, premier motif de rejet :

- retenue dans moins de deux plis : 1

Détail par marché, hors échantillon, de la meilleure cellule (Alignement d'unités, 60 min, sortie à 16 bougies, Ensemble, volatilité stable) :

| Marché | Événements | Réussite | Gain moyen | Perte moyenne | Moyenne nette | Profit factor | Drawdown | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cryBTCUSD | 24 | 33 % | +143,4 pb | -99,6 pb | -18,6 pb | 0,72 | 1314 pb | -447 pb |
| cryETHUSD | 24 | 50 % | +222,6 pb | -137,5 pb | +42,6 pb | 1,62 | 1134 pb | +1022 pb |
| frxXAUUSD | 18 | 50 % | +88,7 pb | -104,5 pb | -7,9 pb | 0,85 | 695 pb | -142 pb |
| frxXAGUSD | 14 | 36 % | +251,5 pb | -323,1 pb | -117,9 pb | 0,43 | 2061 pb | -1651 pb |
| frxEURUSD | 14 | 71 % | +18,0 pb | -20,1 pb | +7,1 pb | 2,23 | 40 pb | +99 pb |
| frxGBPUSD | 21 | 43 % | +11,8 pb | -28,3 pb | -11,1 pb | 0,31 | 245 pb | -233 pb |
| frxUSDJPY | 6 | 33 % | +2,8 pb | -47,6 pb | -30,8 pb | 0,03 | 187 pb | -185 pb |
| frxAUDUSD | 16 | 50 % | +28,4 pb | -43,1 pb | -7,3 pb | 0,66 | 282 pb | -117 pb |
| frxUSDCAD | 17 | 53 % | +19,0 pb | -19,9 pb | +0,7 pb | 1,08 | 64 pb | +12 pb |
| frxEURJPY | 12 | 67 % | +11,9 pb | -61,9 pb | -12,7 pb | 0,38 | 230 pb | -152 pb |

## Référence : les signaux en stratégie complète, sans condition

Descriptif, sans aucune sélection : chaque signal simulé avec le stop obligatoire de 2 ATR, la sortie au temps de l'horizon, une position à la fois et les multiplicateurs de Deriv, sur les dix marchés. Entraînement : avant le 1er février 2026. Hors échantillon : du 1er février au 1er août 2026. Résultats nets de frais, en R (1 R = la perte prévue par le stop).

| Signal | Entraînement : positions, espérance | Hors échantillon : positions | Réussite | Gain moyen | Perte moyenne | Espérance [IC 95 %] | Profit factor | Drawdown | Total | Sens au hasard | p | Coûts doublés | Frais qui annulent | Plis positifs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Momentum, 15 min, 4 bougies | 345, -0,153 R | 788 | 36 % | +0,59 R | -0,63 R | -0,196 R [-0,250 ; -0,142] | 0,52 | 163,3 R | -154,6 R | -0,189 R | 0,71 | -0,385 R | -0,04 fois | 0 sur 3 |
| Momentum, 15 min, 16 bougies | 292, -0,096 R | 693 | 36 % | +1,17 R | -0,97 R | -0,198 R [-0,306 ; -0,091] | 0,68 | 156,2 R | -137,4 R | -0,182 R | 0,62 | -0,388 R | -0,05 fois | 0 sur 3 |
| Accélération, 15 min, 4 bougies | 6252, -0,223 R | 13145 | 34 % | +0,58 R | -0,66 R | -0,238 R [-0,251 ; -0,224] | 0,46 | 3126,3 R | -3123,2 R | -0,219 R | 1,00 | -0,458 R | -0,08 fois | 0 sur 3 |
| Accélération, 15 min, 16 bougies | 3605, -0,216 R | 7691 | 34 % | +1,26 R | -1,05 R | -0,256 R [-0,288 ; -0,225] | 0,63 | 2008,2 R | -1970,0 R | -0,230 R | 1,00 | -0,476 R | -0,16 fois | 0 sur 3 |
| Excès, sens inverse, 15 min, 4 bougies | 1550, -0,202 R | 3350 | 41 % | +0,56 R | -0,73 R | -0,205 R [-0,233 ; -0,177] | 0,53 | 692,0 R | -686,6 R | -0,207 R | 0,48 | -0,410 R | -0,00 fois | 0 sur 3 |
| Excès, sens inverse, 15 min, 16 bougies | 1462, -0,197 R | 3159 | 40 % | +1,01 R | -1,06 R | -0,237 R [-0,280 ; -0,194] | 0,63 | 751,8 R | -748,7 R | -0,217 R | 0,86 | -0,442 R | -0,16 fois | 0 sur 3 |
| Cassure après compression, 15 min, 4 bougies | 1051, -0,299 R | 2164 | 34 % | +0,67 R | -0,75 R | -0,267 R [-0,306 ; -0,227] | 0,46 | 576,9 R | -576,8 R | -0,241 R | 0,86 | -0,509 R | -0,10 fois | 0 sur 3 |
| Cassure après compression, 15 min, 16 bougies | 993, -0,309 R | 2053 | 34 % | +1,40 R | -1,10 R | -0,255 R [-0,320 ; -0,190] | 0,65 | 548,0 R | -523,4 R | -0,256 R | 0,57 | -0,495 R | -0,06 fois | 0 sur 3 |
| Alignement d'unités, 15 min, 4 bougies | 5184, -0,213 R | 10926 | 35 % | +0,58 R | -0,65 R | -0,222 R [-0,237 ; -0,207] | 0,47 | 2430,5 R | -2428,2 R | -0,215 R | 0,81 | -0,439 R | -0,03 fois | 0 sur 3 |
| Alignement d'unités, 15 min, 16 bougies | 3051, -0,212 R | 6456 | 34 % | +1,27 R | -1,04 R | -0,246 R [-0,280 ; -0,212] | 0,64 | 1611,1 R | -1588,3 R | -0,220 R | 1,00 | -0,462 R | -0,14 fois | 0 sur 3 |
| Momentum, 60 min, 4 bougies | 69, +0,063 R | 144 | 38 % | +0,36 R | -0,49 R | -0,166 R [-0,252 ; -0,079] | 0,45 | 26,1 R | -23,9 R | -0,129 R | 0,81 | -0,260 R | -0,76 fois | 0 sur 3 |
| Momentum, 60 min, 16 bougies | 59, +0,219 R | 117 | 40 % | +0,76 R | -0,81 R | -0,178 R [-0,347 ; -0,010] | 0,63 | 23,5 R | -20,9 R | -0,168 R | 0,62 | -0,275 R | -0,85 fois | 0 sur 3 |
| Accélération, 60 min, 4 bougies | 1090, -0,129 R | 2342 | 40 % | +0,62 R | -0,58 R | -0,102 R [-0,136 ; -0,068] | 0,71 | 249,3 R | -239,1 R | -0,115 R | 0,24 | -0,220 R | 0,13 fois | 0 sur 3 |
| Accélération, 60 min, 16 bougies | 672, -0,133 R | 1416 | 40 % | +1,15 R | -0,96 R | -0,115 R [-0,182 ; -0,048] | 0,80 | 186,0 R | -162,7 R | -0,128 R | 0,38 | -0,232 R | 0,02 fois | 0 sur 3 |
| Excès, sens inverse, 60 min, 4 bougies | 293, -0,138 R | 651 | 42 % | +0,56 R | -0,66 R | -0,153 R [-0,212 ; -0,093] | 0,60 | 101,1 R | -99,5 R | -0,121 R | 0,86 | -0,266 R | -0,35 fois | 0 sur 3 |
| Excès, sens inverse, 60 min, 16 bougies | 275, -0,229 R | 617 | 41 % | +0,98 R | -0,95 R | -0,156 R [-0,246 ; -0,066] | 0,72 | 97,6 R | -96,3 R | -0,138 R | 0,62 | -0,269 R | -0,39 fois | 0 sur 3 |
| Cassure après compression, 60 min, 4 bougies | 188, -0,165 R | 457 | 40 % | +0,56 R | -0,63 R | -0,154 R [-0,222 ; -0,085] | 0,59 | 76,1 R | -70,2 R | -0,152 R | 0,57 | -0,280 R | -0,22 fois | 0 sur 3 |
| Cassure après compression, 60 min, 16 bougies | 175, -0,073 R | 433 | 40 % | +1,25 R | -0,97 R | -0,089 R [-0,220 ; +0,041] | 0,85 | 59,0 R | -38,7 R | -0,144 R | 0,24 | -0,215 R | 0,29 fois | 1 sur 3 |
| Alignement d'unités, 60 min, 4 bougies | 848, -0,110 R | 1983 | 40 % | +0,57 R | -0,57 R | -0,112 R [-0,146 ; -0,078] | 0,67 | 229,5 R | -222,5 R | -0,123 R | 0,24 | -0,229 R | 0,04 fois | 0 sur 3 |
| Alignement d'unités, 60 min, 16 bougies | 525, -0,072 R | 1205 | 38 % | +1,15 R | -0,96 R | -0,146 R [-0,217 ; -0,075] | 0,75 | 185,9 R | -175,6 R | -0,122 R | 0,76 | -0,262 R | -0,25 fois | 0 sur 3 |

Espérance hors échantillon par marché, en R :

| Signal | cryBTCUSD | cryETHUSD | frxXAUUSD | frxXAGUSD | frxEURUSD | frxGBPUSD | frxUSDJPY | frxAUDUSD | frxUSDCAD | frxEURJPY |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Momentum, 15 min, 4 | -0,03 | -0,19 | -0,07 | +0,10 | -0,27 | -0,09 | -0,24 | -0,31 | -0,35 | -0,16 |
| Momentum, 15 min, 16 | +0,27 | -0,26 | -0,05 | -0,15 | -0,37 | -0,09 | -0,05 | -0,47 | -0,33 | -0,24 |
| Accélération, 15 min, 4 | -0,07 | -0,15 | -0,01 | -0,07 | -0,30 | -0,23 | -0,44 | -0,32 | -0,38 | -0,29 |
| Accélération, 15 min, 16 | -0,08 | -0,14 | +0,01 | -0,05 | -0,33 | -0,28 | -0,46 | -0,37 | -0,46 | -0,30 |
| Excès, sens inverse, 15 min, 4 | -0,08 | -0,19 | -0,05 | -0,06 | -0,24 | -0,13 | -0,33 | -0,27 | -0,32 | -0,30 |
| Excès, sens inverse, 15 min, 16 | -0,08 | -0,22 | -0,09 | -0,16 | -0,35 | -0,18 | -0,36 | -0,31 | -0,31 | -0,30 |
| Cassure après compression, 15 min, 4 | -0,07 | -0,17 | -0,00 | -0,10 | -0,41 | -0,36 | -0,50 | -0,33 | -0,35 | -0,37 |
| Cassure après compression, 15 min, 16 | -0,12 | -0,08 | -0,05 | -0,12 | -0,35 | -0,36 | -0,51 | -0,35 | -0,23 | -0,38 |
| Alignement d'unités, 15 min, 4 | -0,08 | -0,14 | -0,01 | -0,05 | -0,29 | -0,23 | -0,39 | -0,28 | -0,34 | -0,30 |
| Alignement d'unités, 15 min, 16 | -0,06 | -0,14 | -0,06 | +0,07 | -0,31 | -0,31 | -0,41 | -0,40 | -0,38 | -0,31 |
| Momentum, 60 min, 4 | sans objet | sans objet | -0,15 | sans objet | -0,33 | -0,27 | -0,03 | -0,28 | -0,06 | +0,04 |
| Momentum, 60 min, 16 | sans objet | sans objet | -0,07 | sans objet | -0,22 | -0,10 | -0,56 | -0,15 | +0,07 | -0,15 |
| Accélération, 60 min, 4 | -0,03 | -0,18 | +0,03 | sans objet | -0,12 | -0,04 | -0,14 | -0,12 | -0,19 | -0,08 |
| Accélération, 60 min, 16 | +0,01 | -0,07 | +0,12 | sans objet | -0,22 | -0,03 | -0,17 | -0,17 | -0,19 | -0,08 |
| Excès, sens inverse, 60 min, 4 | -0,21 | -0,44 | -0,07 | sans objet | -0,11 | +0,01 | -0,28 | -0,12 | -0,14 | -0,28 |
| Excès, sens inverse, 60 min, 16 | -0,19 | -0,42 | -0,30 | sans objet | -0,12 | -0,05 | -0,27 | -0,04 | -0,17 | -0,21 |
| Cassure après compression, 60 min, 4 | -0,20 | +0,26 | +0,03 | sans objet | -0,19 | -0,29 | -0,19 | -0,10 | -0,24 | -0,08 |
| Cassure après compression, 60 min, 16 | -0,03 | +0,62 | +0,05 | sans objet | -0,23 | -0,10 | -0,16 | -0,15 | -0,11 | -0,04 |
| Alignement d'unités, 60 min, 4 | -0,05 | +0,02 | -0,01 | sans objet | -0,15 | -0,08 | -0,14 | -0,09 | -0,15 | -0,15 |
| Alignement d'unités, 60 min, 16 | -0,15 | +0,16 | +0,02 | sans objet | -0,26 | -0,17 | -0,13 | -0,18 | -0,07 | -0,17 |

Signaux dont l'espérance hors échantillon est sûrement positive (intervalle à 95 % au-dessus de zéro) : 0 sur 20.

## Limites

- 1120 cellules testées sur chaque pli : sous l'hypothèse d'aucun avantage, quelques-unes passent l'entraînement par hasard. Les étapes hors échantillon, le tirage au sort et les plis successifs servent à les écarter.
- Juin et juillet 2026 avaient déjà servi de validation à la première campagne, et cette approche a été choisie après en avoir vu les résultats. Seule la période réservée est entièrement vierge.
- Le tableau de référence a été ajouté après la première exécution, pour donner les indicateurs complets demandés ; il est descriptif et ne sert à aucune sélection.
- Une seule année d'historique, six mois hors échantillon : un avantage faible, inférieur à quelques points de base, ne peut pas être distingué du hasard.
- Coûts : commissions mesurées sur devis démo le 4 novembre 2026 ; elles peuvent changer. Glissement non compté dans l'étude d'événements (sortie au temps), compté à 5 % de R au stop dans la simulation.

## Reproduire

```bash
python -m app.backtest.research.candles --end 2026-11-01 --days 365 --symbols <marché>   # une fois
python -m app.backtest.research.candles --end 2026-11-01 --repair
python -m app.backtest.research.conditions
```

Durée de calcul : 139 s. Commissions utilisées : cryBTCUSD 0,0326 %, cryETHUSD 0,0882 %, frxXAUUSD 0,0120 %, frxXAGUSD 0,0600 %, frxEURUSD 0,0240 %, frxGBPUSD 0,0204 %, frxUSDJPY 0,0292 %, frxAUDUSD 0,0400 %, frxUSDCAD 0,0212 %, frxEURJPY 0,0250 %.
