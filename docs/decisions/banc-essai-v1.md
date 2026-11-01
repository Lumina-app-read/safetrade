# Banc d'essai, stratégie version 1

Rapport généré le 01/11/2026 par `app.backtest.run`.

Rejeu tick par tick du code du moteur, mise de 1 USD, frais compris. Réglages choisis sur
les 70 % les plus anciens, puis jugés sur les 30 % les plus récents, jamais vus.
**Ce rapport ne présente aucune stratégie comme rentable.**

## Contrôle, hors de l'échantillon d'optimisation

Résultat par position, en USD, avec son intervalle de confiance à 95 %.

| Actif | Positions | Réussite | Équilibre | Net | Par position | Avant frais | Intervalle | Baisse max. | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1HZ100V | 84 | 2,4 % | 10,4 % | -8,92 | -0,11 | -0,06 | [-0,16 ; -0,05] | -9,82 | Négatif |
| 1HZ15V | 17 | 11,8 % | 5,8 % | +1,76 | +0,10 | +0,12 | [-0,17 ; +0,38] | -1,32 | Échantillon insuffisant |
| BOOM500 | 7 | 42,9 % | 18,5 % | +1,61 | +0,23 | +0,25 | [-0,27 ; +0,73] | -0,35 | Échantillon insuffisant |
| JD10 | 29 | 51,7 % | 50,4 % | +0,10 | +0,00 | +0,02 | [-0,05 ; +0,05] | -0,58 | Échantillon insuffisant |
| RB100 | 13 | 69,2 % | 42,8 % | +1,79 | +0,14 | +0,16 | [-0,04 ; +0,32] | -0,38 | Échantillon insuffisant |
| stpRNG | 67 | 20,9 % | 23,7 % | -1,35 | -0,02 | -0,00 | [-0,11 ; +0,07] | -3,13 | Non concluant |

## Ce que le signal apporte

Mêmes règles sur la période de contrôle, sens de chaque position tiré au sort.

| Actif | Positions | Réussite | Équilibre | Net | Par position | Avant frais | Intervalle | Baisse max. | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1HZ100V | 83 | 1,2 % | 9,4 % | -9,24 | -0,11 | -0,06 | [-0,16 ; -0,07] | -9,24 | Négatif |
| 1HZ15V | 25 | 12,0 % | 6,2 % | +2,36 | +0,09 | +0,11 | [-0,12 ; +0,31] | -1,62 | Échantillon insuffisant |
| BOOM500 | 6 | 50,0 % | 19,5 % | +1,91 | +0,32 | +0,34 | [-0,34 ; +0,98] | -0,25 | Échantillon insuffisant |
| JD10 | 22 | 50,0 % | 53,6 % | -0,23 | -0,01 | +0,01 | [-0,08 ; +0,06] | -0,90 | Échantillon insuffisant |
| RB100 | 19 | 52,6 % | 55,6 % | -0,24 | -0,01 | +0,01 | [-0,13 ; +0,11] | -0,98 | Échantillon insuffisant |
| stpRNG | 69 | 18,8 % | 29,7 % | -4,54 | -0,07 | -0,05 | [-0,15 ; +0,01] | -4,94 | Non concluant |

## Réglages actuels du moteur, sur la période de contrôle

| Actif | Positions | Réussite | Équilibre | Net | Par position | Avant frais | Intervalle | Baisse max. | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1HZ100V | 108 | 13,9 % | 31,9 % | -11,14 | -0,10 | -0,05 | [-0,15 ; -0,05] | -12,09 | Négatif |
| 1HZ15V | 67 | 14,9 % | 27,2 % | -4,32 | -0,06 | -0,04 | [-0,12 ; -0,01] | -5,35 | Négatif |
| BOOM500 | 6 | 33,3 % | 15,9 % | +1,32 | +0,22 | +0,24 | [-0,39 ; +0,83] | -0,60 | Échantillon insuffisant |
| JD10 | 9 | 11,1 % | 25,1 % | -0,79 | -0,09 | -0,07 | [-0,25 ; +0,07] | -1,01 | Échantillon insuffisant |
| RB100 | 8 | 25,0 % | 40,2 % | -0,69 | -0,09 | -0,07 | [-0,29 ; +0,12] | -1,12 | Échantillon insuffisant |
| stpRNG | 58 | 13,8 % | 16,1 % | -1,17 | -0,02 | -0,00 | [-0,12 ; +0,08] | -2,68 | Non concluant |

## Réglages actuels du moteur, sur tout l'historique

Ces réglages n'ont pas été choisis sur ces données : les 7 jours comptent, sans biais
d'optimisation. C'est le plus grand échantillon de ce rapport.

| Actif | Positions | Réussite | Équilibre | Net | Par position | Avant frais | Intervalle | Baisse max. | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1HZ100V | 321 | 16,2 % | 29,1 % | -27,01 | -0,08 | -0,03 | [-0,12 ; -0,05] | -28,25 | Négatif |
| 1HZ15V | 214 | 15,4 % | 22,7 % | -8,56 | -0,04 | -0,02 | [-0,07 ; -0,01] | -9,49 | Négatif |
| BOOM500 | 80 | 21,2 % | 26,9 % | -2,73 | -0,03 | -0,01 | [-0,10 ; +0,03] | -4,05 | Non concluant |
| JD10 | 36 | 13,9 % | 21,7 % | -1,66 | -0,05 | -0,03 | [-0,12 ; +0,03] | -3,07 | Non concluant |
| RB100 | 19 | 47,4 % | 45,2 % | +0,35 | +0,02 | +0,04 | [-0,21 ; +0,25] | -2,51 | Échantillon insuffisant |
| stpRNG | 266 | 14,3 % | 21,3 % | -11,36 | -0,04 | -0,02 | [-0,07 ; -0,01] | -12,87 | Négatif |
| **Ensemble** | 936 | 16,5 % | 25,4 % | -50,97 | -0,05 | -0,02 | [-0,07 ; -0,04] | -52,77 | Négatif |

Mêmes règles, sens de chaque position tiré au sort.

| Actif | Positions | Réussite | Équilibre | Net | Par position | Avant frais | Intervalle | Baisse max. | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1HZ100V | 304 | 21,1 % | 29,1 % | -15,17 | -0,05 | +0,00 | [-0,09 ; -0,01] | -15,17 | Négatif |
| 1HZ15V | 233 | 15,0 % | 25,2 % | -12,16 | -0,05 | -0,03 | [-0,08 ; -0,02] | -13,49 | Négatif |
| BOOM500 | 66 | 19,7 % | 29,1 % | -4,69 | -0,07 | -0,05 | [-0,17 ; +0,03] | -7,92 | Non concluant |
| JD10 | 20 | 35,0 % | 31,7 % | +0,41 | +0,02 | +0,04 | [-0,13 ; +0,17] | -1,22 | Échantillon insuffisant |
| RB100 | 38 | 21,1 % | 47,2 % | -5,86 | -0,15 | -0,13 | [-0,25 ; -0,06] | -5,86 | Négatif |
| stpRNG | 242 | 14,9 % | 21,3 % | -9,59 | -0,04 | -0,02 | [-0,08 ; -0,00] | -9,87 | Négatif |
| **Ensemble** | 903 | 18,1 % | 26,8 % | -47,06 | -0,05 | -0,02 | [-0,07 ; -0,03] | -47,15 | Négatif |

## Optimisation

Le meilleur réglage de la première période, parmi 27 essayés, et sa chute hors échantillon.

| Actif | Stop | Activation | Fraction | Par position, optimisé | Contrôle |
| --- | --- | --- | --- | --- | --- |
| 1HZ100V | 100 % | 2.0 R | 0.5 | +0,03 | -0,11 |
| 1HZ15V | 100 % | 2.0 R | 0.7 | +0,02 | +0,10 |
| BOOM500 | 25 % | 1.0 R | 0.5 | +0,00 | +0,23 |
| JD10 | 25 % | 0.5 R | 0.7 | -0,03 | +0,00 |
| RB100 | 25 % | 0.5 R | 0.7 | +0,02 | +0,14 |
| stpRNG | 100 % | 0.5 R | 0.7 | -0,01 | -0,02 |

## Données

| Actif | Ticks | Du | Au | Sorties sur le contrôle |
| --- | --- | --- | --- | --- |
| 1HZ100V | 605581 | 25/10/2026 | 01/11/2026 | floor 79, ratchet 2, stop_out 3 |
| 1HZ15V | 604794 | 25/10/2026 | 01/11/2026 | floor 15, ratchet 2 |
| BOOM500 | 604794 | 25/10/2026 | 01/11/2026 | floor 2, ratchet 3, stop 2 |
| JD10 | 605492 | 25/10/2026 | 01/11/2026 | floor 12, ratchet 15, stop 2 |
| RB100 | 604705 | 25/10/2026 | 01/11/2026 | floor 2, ratchet 9, stop 2 |
| stpRNG | 604794 | 25/10/2026 | 01/11/2026 | floor 49, ratchet 14, stop_out 4 |
