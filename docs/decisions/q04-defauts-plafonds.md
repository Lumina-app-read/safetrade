# Q4. Valeurs par défaut et plafonds

- **Statut :** décidé
- **Date :** 30 octobre 2026

## Question

Les valeurs par défaut et plafonds de la section 7 sont-ils validés ?

## Décision

Le tableau « Valeurs par défaut et plafonds » de la [section 7](../spec/07-risques.md) est adopté tel quel : défauts démo et réel, plage client, plafond administrateur.

## Corrections de l'étape 2.1

Mesurées sur l'API Deriv ([deriv.md](deriv.md)), elles priment sur le tableau de la section 7 :

- Mise par trade : minimum **1 USD** en multiplicateurs, et non 0,35 USD.
- `take_profit` Deriv : minimum 0,10 USD ; `stop_loss` : minimum 0,10 USD, maximum la mise.

Les bornes réelles se lisent dans `validation_params` de chaque `proposal`.

Le gain net minimal de clôture n'est plus un seuil imposé : voir [q18](q18-sorties-dynamiques.md).

## Conséquences

- Ces valeurs alimentent le paramétrage initial des étapes 3.2, 3.3, 5.5 et 8.1.
- Les plafonds restent modifiables par l'administrateur ; chaque modification est versionnée.

Source : [section 21](../spec/21-decisions.md) ; question 4 de la [section 18](../spec/18-questions-ouvertes.md).
