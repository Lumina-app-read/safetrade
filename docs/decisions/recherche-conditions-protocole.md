# Recherche v2 : conditions de marché exploitables, protocole

- **Statut :** écrit le 5 novembre 2026, **avant tout résultat de cette phase**
- **Rôle :** règles fixées à l'avance ; elles ne changent pas après avoir vu les chiffres. Toute entorse serait notée dans le rapport.
- **Point de départ :** `recherche-strategies.md` (312 réglages, aucun avantage, 15 réglages sur 15 négatifs en validation).

## Audit de la première campagne

| Point vérifié | Constat |
| --- | --- |
| Données | 12 fichiers complets, 4 novembre 2025 à 30 octobre ou 1er novembre 2026 ; aucun doublon, aucune inversion d'ordre, aucune bougie incohérente. Un défaut du téléchargement (pages hors historique remplacées par les dernières bougies) a été corrigé avant tout calcul. |
| Découpage | Entraînement jusqu'au 3 mai 2026, validation jusqu'au 1er août, test ensuite ; l'exploration ne lit jamais la période de test. |
| Entrée et sortie | Entrée à l'ouverture de la minute qui suit la clôture du signal ; stop avant objectif dans une même minute ; saut de cours au cours d'ouverture. Vérifié par un calcul à la main. |
| Commissions | Mesurées sur devis démo, proportionnelles au notionnel ; en R : taux ÷ distance du stop. Vérifié à la main (0,264 R sur EUR/USD pour un stop de 2 ATR en 15 minutes). |
| Écart de cours | Les bougies de Deriv sont en prix moyen ; sur les multiplicateurs, Deriv facture la commission et n'ajoute pas d'écart à l'ouverture. Le glissement est compté à 5 % de R sur chaque stop. |
| Biais prudent | Le simulateur place la commission au-delà du stop ; chez Deriv, le stop porte sur le résultat net. Les pertes au stop sont donc légèrement surestimées, de la commission au plus. |
| Limites | 76 à 294 positions par couple en validation : erreur type d'environ 0,1 R, avantage détectable seulement au-delà de 0,2 R. Le meilleur réglage parmi 13 à 48 est choisi à l'entraînement (« malédiction du gagnant »), puis corrigé par la validation. La référence aléatoire n'était calculée qu'au test, jamais atteint. Une seule année de données. |
| **Constat central** | La commission pèse lourd face au mouvement attendu : 0,26 R par position sur EUR/USD avec un stop de 2 ATR en 15 minutes. Une stratégie doit gagner plus d'un quart de son risque en moyenne avant d'être rentable. |

## Changement d'approche

On ne cherche plus le meilleur réglage d'une stratégie complète. On mesure d'abord **s'il existe des conditions où le mouvement des prix est prévisible au-delà des coûts**, par une étude d'événements :

1. À chaque clôture de bougie, un signal donne un sens (ou rien).
2. Le résultat est le mouvement du prix, dans ce sens, de l'ouverture de la minute suivante à la clôture de `h` bougies plus tard, **moins la commission mesurée** du marché, en fraction du notionnel. Les événements ne se chevauchent pas.
3. Le résultat est regardé **par condition de marché** (régime). Une condition n'est retenue que si elle reste positive hors échantillon, sur plusieurs périodes et plusieurs marchés.
4. Seules les conditions qui passent ces étapes sont simulées comme stratégies complètes, avec stop obligatoire, puis comparées au hasard.

Cette approche répond directement au constat central : elle montre où le coût dépasse le mouvement disponible.

## Signaux (fixés ici)

| Signal | Règle, sur bougies closes |
| --- | --- |
| Momentum | Variation sur 8 bougies supérieure à 1,5 × ATR × √8, dans son sens |
| Accélération | Variation sur 4 bougies de même sens que sur 16 bougies, et plus rapide par bougie |
| Excès | Écart à la moyenne sur 20 bougies supérieur à 2,5 écarts types, sens inverse |
| Cassure après compression | Clôture au-delà du plus haut ou du plus bas de 20 bougies, alors que la largeur de bande est dans le cinquième le plus bas des 100 dernières bougies |
| Alignement d'unités | Momentum sur 4 bougies dans le sens de la tendance de l'unité 4 fois plus longue (cours au-dessus ou au-dessous de sa moyenne sur 50) |

Unités de temps : 15 minutes et 1 heure. Horizons : 4 et 16 bougies.

## Conditions de marché (régimes)

Seuils calculés **sur l'entraînement de chaque pli seulement** (terciles), puis appliqués tels quels :

| Régime | Mesure |
| --- | --- |
| Tendance | Rapport d'efficacité de Kaufman sur 20 bougies : faible, moyen, fort |
| Volatilité | ATR 14 ÷ ATR 100 : en baisse, stable, en hausse |
| Coût | Commission ÷ (ATR 14 ÷ cours) : bon marché, moyen, cher |
| Séance (forex et métaux) | Heure UTC : 0-7 h, 7-13 h, 13-21 h, 21-24 h |

Une cellule = un signal, une unité, un horizon, une classe de marchés (crypto, métaux, forex, ensemble) et au plus une condition (ou aucune). Environ 1 100 cellules : beaucoup de tests, d'où des seuils stricts.

## Périodes

- **Étude :** 4 novembre 2025 au 1er août 2026. **Août à octobre 2026 reste réservé** : le code de cette phase refuse de charger une bougie postérieure au 1er août 2026 (vérifié par un test).
- **Validation glissante, trois plis :** entraînement depuis le début jusqu'au 1er février, 1er avril, 1er juin ; validation sur les deux mois suivants (février-mars, avril-mai, juin-juillet). Six mois hors échantillon au total.
- **Limite connue :** juin-juillet a déjà servi de validation à la première campagne, et cette nouvelle approche a été choisie après en avoir vu les résultats. Le rapport le signale ; le test réservé reste la seule mesure vierge.

## Règles de sélection

1. **Entraînement d'un pli :** au moins 150 événements, résultat net moyen positif, statistique t d'au moins 3, au moins 60 % des marchés positifs pour une classe de plusieurs marchés.
2. **Hors échantillon, sur les plis où la cellule a été retenue :** retenue dans au moins deux plis sur trois ; au moins 100 événements hors échantillon ; moyenne nette positive, t d'au moins 2 ; positive dans chacun des plis où elle a été retenue ; mieux que le sens tiré au sort (2 000 tirages, p < 5 %) ; toujours positive à 1,5 fois les coûts ; au moins 60 % des marchés positifs.
3. **Simulation complète** des cellules retenues : stop obligatoire de 2 ATR, sortie au temps de l'horizon, une position à la fois, multiplicateurs de Deriv, sur les mêmes périodes hors échantillon. Gardée seulement si son espérance nette reste positive avec un intervalle de confiance à 95 % au-dessus de zéro.

Une cellule qui passe tout devient une **piste pour le test réservé puis le compte démo**, jamais une stratégie déclarée rentable. Si aucune ne passe, le test réservé n'est pas ouvert.

## Indicateurs

Pour chaque cellule retenue à l'entraînement et chaque marché : nombre d'événements, taux de réussite, gain moyen, perte moyenne, résultat net moyen et total, profit factor, drawdown, intervalle de confiance, résultat avant frais, à 1,5 et 2 fois les frais, frais qui annulent le résultat, comparaison au sens tiré au sort, résultat par pli. Une carte des coûts par marché, séance et volatilité montre où le coût dépasse le mouvement disponible.

## Ce que ce protocole interdit

- Lire, même pour un contrôle, une bougie d'août à octobre 2026 pendant cette phase.
- Changer un signal, un seuil ou un horizon après avoir vu un résultat hors échantillon.
- Modifier le moteur, le module de risque, les limites ou le stop obligatoire ; augmenter un multiplicateur pour passer un filtre de frais ; toute martingale.
- Présenter un résultat d'étude ou de simulation comme un résultat de démo.
