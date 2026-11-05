# Recherche v3 : scalping sur Volatility 75 (1s), protocole

- **Statut :** écrit le 5 novembre 2026, **avant tout résultat de cette étude**
- **Rôle :** règles fixées à l'avance ; elles ne changent pas après avoir vu les chiffres.

## Périmètre des campagnes précédentes

| Campagne | Instruments | Données | Contrat simulé |
| --- | --- | --- | --- |
| Banc d'essai v1 (`banc-essai.md`) | Volatility 100 (1s), Step Index, Boom 500, Jump 10, Range Break 100, Volatility 15 (1s) | ticks, 7 jours | multiplicateurs, stratégie de moyennes mobiles d'une minute |
| Banc marchés réels | bitcoin, ether, or, EUR/USD, GBP/USD, USD/JPY | ticks, 14 jours | multiplicateurs |
| Recherches v1 et v2 | bitcoin, ether, or, argent, six paires forex | bougies d'une minute, un an | multiplicateurs |

**Volatility 75 (1s) n'a jamais été étudié.** Aucune étude tick par tick du scalping n'a été faite ; seuls les multiplicateurs ont été simulés. Les résultats précédents ne sont pas transposés ici.

## Données

- Ticks de 1HZ75V, un par seconde, point public de Deriv, du 11 juillet au 1er août 2026 exclu (`app/backtest/research/ticks.py`). **Rien d'août à octobre 2026.**
- **Entraînement :** 11 au 25 juillet (14 jours). **Validation :** 25 juillet au 1er août (7 jours), lue une seule fois, signaux figés.
- Deriv présente ses indices synthétiques comme produits par un générateur aléatoire à volatilité constante : en théorie, aucun mouvement n'y est prévisible. L'étude vérifie ce point sur les données, sans le supposer.

## Coûts mesurés sur devis du compte démo, le 5 novembre 2026

| Produit | Coût |
| --- | --- |
| Multiplicateurs (×50 à ×500) | commission de 0,039 % du notionnel, soit 3,9 % de la mise à ×100 |
| Rise/Fall, 1 à 10 ticks et 15 à 60 secondes | paiement de 18,83 pour 10 : il faut **53,1 % de positions gagnantes** pour ne rien perdre ; une égalité perd |
| Accumulateurs, 1 à 5 % par tick | barrière à ±1,50 point (1 %) à ±1,19 point (5 %) autour de chaque tick, perte de la mise au premier franchissement |

## Mesures de prévisibilité (descriptives)

Sur l'entraînement puis sur la validation : autocorrélation des variations tick à tick (décalages 1 à 10), rapport des variances (5, 10, 30, 60 et 300 ticks), autocorrélation de la valeur absolue des variations (séquences de volatilité), probabilité de hausse après 1 à 5 hausses de suite.

## Signaux (fixés ici)

| Signal | Règle, sur les ticks déjà reçus |
| --- | --- |
| Momentum | variation sur n ticks (5, 10, 30) supérieure à z × σ × √n (z = 1 ou 2), dans son sens |
| Micro-retournement | variation sur n ticks (5, 10, 30) supérieure à 2,5 × σ × √n, sens inverse |
| Accélération | variation sur 5 ticks deux fois plus rapide par tick que sur 30, de même sens |
| Cassure courte | prix au-delà du plus haut ou du plus bas des n ticks précédents (30, 60, 300) |
| Série | k ticks de même sens à la suite (3, 4, 5), continuation ou retournement |
| Sortie de consolidation | cassure de 60 ticks quand l'écart type des 60 derniers ticks est dans le cinquième le plus bas de l'entraînement |

σ : écart type des variations tick à tick, mesuré sur l'entraînement.

**Exécution :** un signal au tick i est exécuté au tick i + 1 (délai d'achat d'environ une seconde) ; sensibilité à 2 et 3 ticks. Horizons : 1, 2, 3, 5, 10, 30 et 60 ticks. Une position à la fois.

## Résultat par produit

- **Rise/Fall :** gagnée si le prix de sortie est strictement au-delà du prix d'entrée dans le sens du signal ; +0,883 de la mise, sinon -1.
- **Multiplicateur ×100 :** 100 × variation relative, moins 3,9 % de la mise ; stop à 50 % de la mise vérifié à chaque tick.
- **Accumulateur :** pour chaque taux, probabilité de franchir la barrière à chaque tick, et espérance d'une position tenue k ticks (1 à 50) ; signaux étudiés : faible variation récente, sortie de consolidation.

## Sélection et verdict

1. **Entraînement :** au moins 1 000 positions ; Rise/Fall : taux de réussite au-dessus de 53,1 % avec p < 0,001 ; multiplicateur : moyenne nette positive, t ≥ 3,5 ; accumulateur : espérance positive, t ≥ 3,5.
2. **Validation, signaux figés :** au moins 300 positions ; même critère avec p < 5 % ; mieux que le sens tiré au sort (2 000 tirages) ; positif dans au moins 5 jours sur 7 ; toujours positif avec un tick de délai de plus.
3. Une règle qui passe tout devient une **piste pour le compte démo**, jamais une stratégie rentable ; la période réservée reste fermée.

## Indicateurs par signal

Signaux par minute, positions exécutables, taux de signaux écartés (position déjà ouverte), durée moyenne, taux de réussite, gains et pertes moyens, résultat net par position, pertes consécutives maximales, drawdown, coût cumulé.

## Interdits

Lire août à octobre 2026 ; changer un signal, un horizon ou un seuil après la validation ; toucher au moteur, au module de risque ou aux protections ; toute martingale ; présenter une simulation comme un résultat de démo.
