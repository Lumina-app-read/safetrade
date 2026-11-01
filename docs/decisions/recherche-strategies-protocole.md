# Recherche de stratégies : protocole

- **Statut :** écrit le 1er novembre 2026, **avant tout résultat**
- **Rôle :** ce document fixe les règles à l'avance. Il ne change pas après avoir vu les chiffres. Toute entorse serait notée dans le rapport.

## Question

Existe-t-il une stratégie dont le résultat reste positif après frais, sur des données qui n'ont servi à rien d'autre ? Le résultat attendu par défaut est **non**. Le rapport le dira si c'est le cas.

## Données

- Bougies d'une minute de Deriv, en date de fin du 1er novembre 2026, sur un an au plus. Le forex s'arrête où Deriv s'arrête, entre 6 et 12 mois.
- **Marchés étudiés :** BTC, ETH, or, argent, EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, EUR/JPY.
- **Classes :** crypto, métaux, forex, et l'ensemble.
- **Témoins négatifs :** Volatility 100 et Step Index 100. Ces indices sont aléatoires : un avantage solide sur eux signalerait un défaut de la méthode. Ils ne sont jamais sélectionnés.

## Découpage dans le temps

Mêmes dates pour tous, calculées sur la période commune à tous les marchés :

| Période | Part | Usage |
| --- | --- | --- |
| Entraînement | 50 % | Choisir les réglages |
| Validation | 25 % | Décider qui passe au test |
| Test | 25 % | Une seule ouverture, stratégies figées |

La crypto a plus d'historique : ce qui précède la période commune compte dans l'entraînement.

**Garantie technique :** la phase d'exploration ne charge pas les bougies de test. La liste des stratégies retenues est écrite dans un fichier, **validée dans Git avant l'ouverture du test**. L'historique Git prouve donc l'ordre des opérations.

## Familles

Les réglages essayés sont fixés dans le code (`families.py`). Unités de temps : 15 minutes et 1 heure. Toutes les valeurs sont calculées sur des bougies closes.

| Famille | Principe |
| --- | --- |
| Tendance | Croisement de moyennes, dans le sens de la tendance de l'unité supérieure |
| Momentum | Forte variation mesurée en volatilité, confirmée par la position du cours |
| Retournement | Écart extrême à la moyenne, confirmé par le RSI |
| Cassure | Plus haut ou plus bas de N bougies, avec volatilité en hausse |
| Volatilité | Compression de volatilité, puis sortie de bande |
| Combinée | Tendance de fond, repli au RSI, filtre d'efficacité du mouvement |

## Simulation

- **Entrée** à l'ouverture de la bougie d'une minute qui suit la clôture du signal.
- **Stop** obligatoire, en multiple de la volatilité (ATR). Le risque d'une position vaut 1 R.
- **Dans une même minute, si le stop et l'objectif sont touchés, le stop passe d'abord** : c'est l'hypothèse la plus prudente.
- **Saut de cours** : sortie au cours d'ouverture, donc au-delà du stop.
- **Glissement** : 5 % de R sur chaque sortie au stop (mesuré en démo : 0 à 12 %).
- **Mise constante**, sans aucune augmentation après une perte.
- **Une position à la fois par marché et par stratégie.**
- **Limites de Deriv** : position écartée si aucun multiplicateur proposé ne donne un stop entre 10 % et 90 % de la mise.

## Coûts

La commission est proportionnelle à la position. Taux mesurés sur un devis du compte démo, mise de 50 USD :

| Marché | Taux |
| --- | --- |
| BTC | 0,034 % |
| ETH | 0,087 % |
| Volatility 100 | 0,051 % |
| Step Index 100 | 0,0016 % |

**Or, argent et forex : fermés au moment de la mesure.** Taux supposé : 0,005 %, à remplacer par un devis à la réouverture. Pour ne pas dépendre de cette hypothèse, le rapport donne pour chaque stratégie le **coût maximal supportable**, en taux de commission.

## Sélection, sur entraînement et validation seulement

Pour chaque couple famille et classe :

1. **Entraînement :** on garde le réglage de meilleure statistique t, s'il a au moins 100 positions et une espérance nette positive. Un seul réglage par couple.
2. **Validation :** ce réglage devient candidat s'il a au moins 50 positions, une espérance nette positive et une statistique t d'au moins 1,65. Pour une classe de plusieurs marchés, au moins 60 % d'entre eux doivent être positifs.

## Verdict, sur le test seulement

Une stratégie **mérite une validation supplémentaire** si toutes ces conditions sont réunies :

1. Espérance nette positive, avec une valeur p inférieure à 5 % divisée par le nombre de candidats (correction de Bonferroni).
2. Mieux que le sens tiré au sort : valeur p de moins de 5 % sur 200 tirages.
3. Toujours positive avec des coûts doublés.
4. Au moins deux tiers de la période de test positifs, sur trois sous-périodes.
5. Pour une classe de plusieurs marchés, au moins 60 % des marchés positifs.

Même alors, il s'agira d'une piste à confirmer en démo, jamais d'une stratégie déclarée rentable.

## Ce que le protocole interdit

- Rouvrir le test pour changer une stratégie. Si cela arrive, le test est brûlé et il faut de nouvelles données.
- Présenter un résultat d'entraînement ou de validation comme une preuve.
- Modifier le module de risque, les limites ou le stop obligatoire. Rien ici ne touche au moteur.
- Présenter une simulation comme un résultat obtenu en démo.
