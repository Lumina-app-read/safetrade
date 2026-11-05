# Recherche de stratégies : résultats

- **Généré le :** 05/11/2026 09:34 UTC, par `python -m app.backtest.research.run --stage test`
- **Protocole :** `recherche-strategies-protocole.md`, validé dans Git avant tout résultat
- **Sélection figée :** `recherche-strategies-selection.json`, écrite le 2026-11-05 et validée dans Git avant l'ouverture du test
- **Nature des résultats :** **simulation sur l'historique de Deriv**. Aucun résultat obtenu en démo n'est présenté ici, aucun ordre n'a été passé.

## Conclusion

**Aucune stratégie n'a franchi la validation : aucune n'a été ouverte sur la période de test.**

Sur 312 réglages répartis en six familles et quatre classes de marchés, aucun n'a présenté sur la validation une espérance positive après frais assez solide (statistique t d'au moins 1,65, au moins 50 positions, au moins 60 % des marchés positifs). Aucune stratégie de ce document ne peut être présentée comme ayant un avantage statistique.

Sur 15 réglages retenus à l'entraînement, 15 deviennent négatifs en validation, quand on les applique à des mois qu'ils n'ont pas vus. C'est la marque d'un avantage apparent produit par le hasard de l'échantillon, pas d'un avantage réel.

Le module de risque reste inchangé et indépendant de la stratégie : stop loss obligatoire, plafonds d'exposition et de pertes, réconciliation, anti-doublon, arrêt d'urgence, aucune hausse de mise après une perte.

## Données

| Marché | Début | Fin | Commission par position |
| --- | --- | --- | --- |
| cryBTCUSD | 04/11/2025 | 01/11/2026 | 0,0326 % du notionnel, mesurée |
| cryETHUSD | 04/11/2025 | 01/11/2026 | 0,0882 % du notionnel, mesurée |
| frxXAUUSD | 04/11/2025 | 30/10/2026 | 0,0120 % du notionnel, mesurée |
| frxXAGUSD | 04/11/2025 | 30/10/2026 | 0,0600 % du notionnel, mesurée |
| frxEURUSD | 04/11/2025 | 30/10/2026 | 0,0240 % du notionnel, mesurée |
| frxGBPUSD | 04/11/2025 | 30/10/2026 | 0,0204 % du notionnel, mesurée |
| frxUSDJPY | 04/11/2025 | 30/10/2026 | 0,0292 % du notionnel, mesurée |
| frxAUDUSD | 04/11/2025 | 30/10/2026 | 0,0400 % du notionnel, mesurée |
| frxUSDCAD | 04/11/2025 | 30/10/2026 | 0,0212 % du notionnel, mesurée |
| frxEURJPY | 04/11/2025 | 30/10/2026 | 0,0250 % du notionnel, mesurée |
| 1HZ100V | 05/11/2025 | 01/11/2026 | 0,0510 % du notionnel, mesurée |
| stpRNG | 04/11/2025 | 01/11/2026 | 0,0017 % du notionnel, mesurée |

Période commune découpée aux mêmes dates : entraînement jusqu'au 03/05/2026, validation jusqu'au 01/08/2026, test jusqu'au 30/10/2026. La crypto garde son historique antérieur dans l'entraînement.

Hypothèses : entrée à l'ouverture de la minute qui suit la clôture du signal, stop avant objectif dans une même minute, sortie au cours d'ouverture en cas de saut, glissement de 5 % du risque à chaque stop, mise constante, une position à la fois, position écartée si aucun multiplicateur de Deriv ne place le stop entre 10 % et 90 % de la mise. Résultats en R : 1 R est la perte prévue par le stop.

## Tableau comparatif : entraînement et validation

Un réglage par couple, choisi sur l'entraînement seulement (meilleure statistique t, au moins 100 positions, espérance positive).

| Famille | Classe | Réglage retenu | Entraînement : positions, espérance, t | Validation : positions, espérance, t | Candidat |
| --- | --- | --- | --- | --- | --- |
| Cassure | Crypto | 15 min, canal=20,expansion=1,3, stop 2,0 ATR, suivi 3,0 ATR | 105, +0,200 R, 1,09 | 93, -0,221 R, -1,49 | non |
| Cassure | Métaux | 15 min, canal=55,expansion=1,0, stop 2,0 ATR, suivi 3,0 ATR | 164, +0,150 R, 1,00 | 110, -0,161 R, -1,30 | non |
| Cassure | Forex | 60 min, canal=55,expansion=1,3, stop 1,5 ATR, objectif 3,0 ATR, 24 bougies max | 105, +0,013 R, 0,10 | 76, -0,184 R, -1,30 | non |
| Cassure | Ensemble | 60 min, canal=55,expansion=1,3, stop 1,5 ATR, objectif 3,0 ATR, 24 bougies max | 117, +0,012 R, 0,10 | 78, -0,185 R, -1,34 | non |
| Combinée | Crypto | 15 min, repli=35,efficacite=0,2, stop 1,5 ATR, objectif 3,0 ATR, 24 bougies max | 125, +0,056 R, 0,46 | 76, -0,012 R, -0,07 | non |
| Combinée | Métaux | 15 min, repli=45,efficacite=0,2, stop 1,5 ATR, objectif 3,0 ATR, 24 bougies max | 143, +0,070 R, 0,60 | 80, -0,121 R, -0,75 | non |
| Combinée | Forex | aucun | aucun réglage positif (meilleur t : 1,18) | sans objet | non |
| Combinée | Ensemble | 15 min, repli=35,efficacite=0,35, stop 2,5 ATR, objectif 3,0 ATR, 24 bougies max | 189, +0,040 R, 0,57 | 130, -0,378 R, -4,29 | non |
| Momentum | Crypto | aucun | aucun réglage positif (meilleur t : 1,51) | sans objet | non |
| Momentum | Métaux | aucun | aucun réglage positif (meilleur t : 1,32) | sans objet | non |
| Momentum | Forex | 60 min, periode=4,seuil=1,5, stop 2,5 ATR, objectif 3,0 ATR, 24 bougies max | 160, +0,076 R, 1,03 | 97, -0,126 R, -1,29 | non |
| Momentum | Ensemble | 60 min, periode=4,seuil=1,5, stop 2,5 ATR, objectif 3,0 ATR, 24 bougies max | 169, +0,077 R, 1,06 | 99, -0,122 R, -1,26 | non |
| Retournement | Crypto | 15 min, ecart=2,0, stop 2,5 ATR, objectif 1,0 ATR, 8 bougies max | 192, +0,003 R, 0,07 | 150, -0,114 R, -2,39 | non |
| Retournement | Métaux | 15 min, ecart=3,0, stop 1,5 ATR, objectif 2,0 ATR, 8 bougies max | 125, +0,224 R, 2,34 | 80, -0,076 R, -0,67 | non |
| Retournement | Forex | aucun | aucun réglage positif (meilleur t : -1,48) | sans objet | non |
| Retournement | Ensemble | aucun | aucun réglage positif (meilleur t : -1,39) | sans objet | non |
| Tendance | Crypto | 15 min, rapide=10,lente=30, stop 3,0 ATR, suivi 5,0 ATR | 181, +0,091 R, 0,67 | 120, -0,059 R, -0,40 | non |
| Tendance | Métaux | 15 min, rapide=10,lente=30, stop 2,0 ATR, suivi 5,0 ATR | 213, +0,457 R, 2,25 | 126, -0,125 R, -0,62 | non |
| Tendance | Forex | aucun | aucun réglage positif (meilleur t : 0,34) | sans objet | non |
| Tendance | Ensemble | 60 min, rapide=10,lente=30, stop 2,0 ATR, suivi 3,0 ATR | 312, +0,118 R, 1,12 | 195, -0,314 R, -4,06 | non |
| Volatilité | Crypto | aucun | aucun réglage positif (meilleur t : 1,08) | sans objet | non |
| Volatilité | Métaux | 15 min, quantile=0,2, stop 1,5 ATR, objectif 3,0 ATR, 8 bougies max | 435, +0,095 R, 1,48 | 294, -0,089 R, -1,23 | non |
| Volatilité | Forex | aucun | aucun réglage positif (meilleur t : -0,52) | sans objet | non |
| Volatilité | Ensemble | aucun | aucun réglage positif (meilleur t : -0,77) | sans objet | non |
## Reproduire

```bash
python -m app.backtest.research.candles --end 2026-11-01 --days 365 --symbols <marché>
python -m app.backtest.research.run --stage explore
python -m app.backtest.research.run --stage test
```

Les bougies restent dans `backend/.backtest/candles/`, hors Git ; les multiplicateurs lus chez Deriv sont dans la sélection.
