# Vérifications à faire à l'étape 2.1

- **Statut :** non confirmé à ce jour
- **Date :** 30 octobre 2026

Points de la documentation officielle Deriv qui restent à vérifier, sur un compte démo :

- [ ] Disponibilité de l'or et du Bitcoin dans la liste des actifs d'un compte (appel `active_symbols`). Chaque actif n'accepte que certains types de contrats.
- [ ] Types de contrats autorisant la vente anticipée et les ordres limites pour chaque actif retenu (appel `contracts_for`).
- [ ] Étendues (scopes) exactes des jetons PAT et OAuth (une page officielle cite par exemple `trade` et `account_manage`).
- [ ] Durée de vie des jetons OAuth et du jeton de renouvellement.
- [ ] Champs exacts du prix d'achat et du prix de rachat, pour le calcul du spread et du gain net (voir [q01](q01-produit-deriv.md)).

Source : [section 21](../spec/21-decisions.md), parties « À vérifier à l'étape 2.1 » et « Conséquences sur le cahier des charges ».
