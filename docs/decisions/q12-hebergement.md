# Q12. Hébergement

- **Statut :** hypothèse (à confirmer)
- **Date :** 30 octobre 2026

## Question

Quel hébergement (fournisseur cloud, région) ?

## Décision

- Serveur cloud sous Docker.
- Région européenne en hypothèse.
- Latence vers Deriv mesurée à l'étape 2.5.
- Fournisseur choisi selon le budget du propriétaire.

## Conséquences

- Le code reste indépendant du fournisseur (Docker Compose, configuration par variables d'environnement).
- Bloque le déploiement de préproduction (étape 7.1), pas le développement local.

## Reste à faire

- Choisir le fournisseur d'hébergement et confirmer la région.

Source : [section 21](../spec/21-decisions.md) ; question 12 de la [section 18](../spec/18-questions-ouvertes.md).
