# Q3. Stop loss obligatoire

- **Statut :** décidé
- **Date :** 30 octobre 2026

## Question

Le stop loss obligatoire par trade est-il accepté ?

## Décision

- Oui, toujours obligatoire.
- Contrats à perte limitée à la mise : le plafond de mise tient lieu de stop loss.
- Contrats qui acceptent un ordre limite : le stop loss est posé à l'ouverture.
- Le moteur ne traite que des contrats qui permettent la vente avant l'échéance.

## Conséquences

- Le module de risque (étape 3.2) refuse tout ordre sans protection de perte.
- La liste des contrats éligibles dépend de la vérification `contracts_for` de l'étape 2.1.

Source : [section 21](../spec/21-decisions.md) ; question 3 de la [section 18](../spec/18-questions-ouvertes.md).
