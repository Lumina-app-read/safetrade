# Q6. Positions ouvertes à l'expiration de l'abonnement

- **Statut :** décidé
- **Date :** 30 octobre 2026

## Question

À l'expiration, laisser les positions ouvertes se clôturer ou les clôturer immédiatement ?

## Décision

Les laisser se clôturer sous leur protection (gain net ou stop loss), puis arrêter le bot.

## Conséquences

- À l'expiration, le backend bloque toute nouvelle position ; le moteur continue de surveiller les positions déjà ouvertes jusqu'à leur clôture, puis passe le bot à l'état « Arrêté ».

Source : [section 21](../spec/21-decisions.md) ; question 6 de la [section 18](../spec/18-questions-ouvertes.md).
