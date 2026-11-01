# Banc d'essai, marchés réels

Rapport généré le 01/11/2026 par `app.backtest.run`.

Rejeu tick par tick du code du moteur, mise de 1 USD, frais compris. Réglages choisis sur
les 70 % les plus anciens, puis jugés sur les 30 % les plus récents, jamais vus.
**Ce rapport ne présente aucune stratégie comme rentable.**

## Contrôle, hors de l'échantillon d'optimisation

Résultat par position, en USD, avec son intervalle de confiance à 95 %.

| Actif | Positions | Réussite | Équilibre | Net | Par position | Avant frais | Intervalle | Baisse max. | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cryBTCUSD | 51 | 15,7 % | 10,1 % | +3,71 | +0,07 | +0,10 | [-0,07 ; +0,22] | -3,24 | Non concluant |
| cryETHUSD | 50 | 14,0 % | 19,7 % | -3,30 | -0,07 | +0,02 | [-0,21 ; +0,07] | -6,61 | Non concluant |
| frxEURUSD | 63 | 11,1 % | 14,7 % | -2,11 | -0,03 | -0,01 | [-0,12 ; +0,05] | -2,48 | Non concluant |
| frxGBPUSD | 78 | 46,2 % | 57,5 % | -2,03 | -0,03 | -0,01 | [-0,05 ; +0,00] | -2,76 | Non concluant |
| frxUSDJPY | 26 | 3,8 % | 6,2 % | -1,40 | -0,05 | -0,03 | [-0,24 ; +0,13] | -1,91 | Échantillon insuffisant |
| frxXAUUSD | 11 | 18,2 % | 6,0 % | +2,32 | +0,21 | +0,23 | [-0,20 ; +0,63] | -0,84 | Échantillon insuffisant |

## Ce que le signal apporte

Mêmes règles sur la période de contrôle, sens de chaque position tiré au sort.

| Actif | Positions | Réussite | Équilibre | Net | Par position | Avant frais | Intervalle | Baisse max. | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cryBTCUSD | 38 | 26,3 % | 12,7 % | +5,99 | +0,16 | +0,19 | [-0,02 ; +0,33] | -1,13 | Non concluant |
| cryETHUSD | 62 | 11,3 % | 19,2 % | -5,18 | -0,08 | +0,01 | [-0,19 ; +0,02] | -6,47 | Non concluant |
| frxEURUSD | 52 | 15,4 % | 11,4 % | +2,21 | +0,04 | +0,06 | [-0,07 ; +0,16] | -1,44 | Non concluant |
| frxGBPUSD | 69 | 44,9 % | 62,6 % | -2,79 | -0,04 | -0,02 | [-0,07 ; -0,01] | -3,40 | Négatif |
| frxUSDJPY | 46 | 0,0 % | 100,0 % | -5,91 | -0,13 | -0,11 | [-0,17 ; -0,09] | -5,91 | Négatif |
| frxXAUUSD | 10 | 0,0 % | 100,0 % | -1,06 | -0,11 | -0,09 | [-0,11 ; -0,10] | -1,06 | Échantillon insuffisant |

## Réglages actuels du moteur, sur la période de contrôle

| Actif | Positions | Réussite | Équilibre | Net | Par position | Avant frais | Intervalle | Baisse max. | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cryBTCUSD | 18 | 27,8 % | 19,7 % | +0,99 | +0,06 | +0,08 | [-0,10 ; +0,21] | -1,07 | Échantillon insuffisant |
| cryETHUSD | 69 | 20,3 % | 30,1 % | -5,06 | -0,07 | +0,02 | [-0,17 ; +0,02] | -6,48 | Non concluant |
| frxEURUSD | 76 | 17,1 % | 26,7 % | -3,52 | -0,05 | -0,03 | [-0,09 ; +0,00] | -3,81 | Non concluant |
| frxGBPUSD | 59 | 23,7 % | 27,1 % | -1,01 | -0,02 | +0,00 | [-0,08 ; +0,05] | -2,34 | Non concluant |
| frxUSDJPY | 71 | 15,5 % | 24,4 % | -3,55 | -0,05 | -0,03 | [-0,11 ; +0,01] | -4,30 | Non concluant |
| frxXAUUSD | 44 | 13,6 % | 28,5 % | -3,32 | -0,08 | -0,06 | [-0,14 ; -0,01] | -3,73 | Négatif |

## Réglages actuels du moteur, sur tout l'historique

Ces réglages n'ont pas été choisis sur ces données : tout l'historique compte, sans
biais d'optimisation. C'est le plus grand échantillon de ce rapport.

| Actif | Positions | Réussite | Équilibre | Net | Par position | Avant frais | Intervalle | Baisse max. | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cryBTCUSD | 66 | 16,7 % | 17,7 % | -0,61 | -0,01 | +0,02 | [-0,12 ; +0,10] | -4,74 | Non concluant |
| cryETHUSD | 298 | 14,1 % | 29,7 % | -31,78 | -0,11 | -0,02 | [-0,14 ; -0,07] | -31,78 | Négatif |
| frxEURUSD | 153 | 17,6 % | 21,9 % | -3,79 | -0,02 | -0,00 | [-0,07 ; +0,02] | -5,63 | Non concluant |
| frxGBPUSD | 170 | 15,9 % | 23,6 % | -7,46 | -0,04 | -0,02 | [-0,08 ; -0,01] | -7,46 | Négatif |
| frxUSDJPY | 170 | 13,5 % | 19,0 % | -6,67 | -0,04 | -0,02 | [-0,09 ; +0,01] | -9,33 | Non concluant |
| frxXAUUSD | 115 | 15,7 % | 24,4 % | -5,22 | -0,05 | -0,03 | [-0,09 ; -0,01] | -5,69 | Négatif |
| **Ensemble** | 972 | 15,2 % | 24,0 % | -55,53 | -0,06 | -0,01 | [-0,08 ; -0,04] | -56,31 | Négatif |

Mêmes règles, sens de chaque position tiré au sort.

| Actif | Positions | Réussite | Équilibre | Net | Par position | Avant frais | Intervalle | Baisse max. | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cryBTCUSD | 110 | 23,6 % | 25,8 % | -1,65 | -0,02 | +0,01 | [-0,09 ; +0,06] | -3,08 | Non concluant |
| cryETHUSD | 289 | 12,5 % | 27,6 % | -32,96 | -0,11 | -0,02 | [-0,15 ; -0,07] | -33,59 | Négatif |
| frxEURUSD | 153 | 17,0 % | 21,9 % | -4,29 | -0,03 | -0,01 | [-0,07 ; +0,01] | -5,78 | Non concluant |
| frxGBPUSD | 139 | 18,7 % | 21,5 % | -2,15 | -0,02 | +0,00 | [-0,06 ; +0,03] | -5,09 | Non concluant |
| frxUSDJPY | 180 | 19,4 % | 26,0 % | -6,66 | -0,04 | -0,02 | [-0,08 ; +0,00] | -9,38 | Non concluant |
| frxXAUUSD | 90 | 14,4 % | 22,7 % | -3,98 | -0,04 | -0,02 | [-0,09 ; +0,00] | -4,46 | Non concluant |
| **Ensemble** | 961 | 16,9 % | 25,4 % | -51,69 | -0,05 | -0,01 | [-0,07 ; -0,03] | -52,82 | Négatif |

## Optimisation

Le meilleur réglage de la première période, parmi 27 essayés, et sa chute hors échantillon.

| Actif | Stop | Activation | Fraction | Par position, optimisé | Contrôle |
| --- | --- | --- | --- | --- | --- |
| cryBTCUSD | 50 % | 2.0 R | 0.7 | +0,03 | +0,07 |
| cryETHUSD | 100 % | 1.0 R | 0.7 | -0,05 | -0,07 |
| frxEURUSD | 100 % | 1.0 R | 0.7 | +0,05 | -0,03 |
| frxGBPUSD | 25 % | 0.5 R | 0.3 | -0,01 | -0,03 |
| frxUSDJPY | 100 % | 2.0 R | 0.7 | +0,08 | -0,05 |
| frxXAUUSD | 100 % | 2.0 R | 0.7 | +0,01 | +0,21 |

## Données

| Actif | Ticks | Du | Au | Multiplicateur | Commission | Sorties sur le contrôle |
| --- | --- | --- | --- | --- | --- | --- |
| cryBTCUSD | 1206506 | 18/10/2026 | 01/11/2026 | 100 | 0,03 (devis) | floor 40, ratchet 8, stop 3 |
| cryETHUSD | 1206510 | 18/10/2026 | 01/11/2026 | 100 | 0,09 (devis) | floor 37, ratchet 7, stop_out 6 |
| frxEURUSD | 840932 | 19/10/2026 | 30/10/2026 | 500 | 0,02 (hypothèse) | floor 54, ratchet 7, stop_out 2 |
| frxGBPUSD | 840235 | 19/10/2026 | 30/10/2026 | 500 | 0,02 (hypothèse) | floor 34, ratchet 36, stop 8 |
| frxUSDJPY | 840253 | 19/10/2026 | 30/10/2026 | 500 | 0,02 (hypothèse) | floor 24, ratchet 1, stop_out 1 |
| frxXAUUSD | 808038 | 19/10/2026 | 30/10/2026 | 100 | 0,02 (hypothèse) | floor 9, ratchet 2 |
