# Vérifications à faire à l'étape 2.1

- **Statut :** en grande partie vérifié le 31 octobre 2026 ; le reste exige un compte démo
- **Date :** 30 octobre 2026

Vérifié à l'étape 2.1 (détails : [deriv.md](deriv.md)) :

- [x] Bitcoin disponible (`cryBTCUSD`, ouvert). Or disponible (`frxXAUUSD`), fermé pendant la mesure du samedi.
- [x] Multiplicateurs disponibles sur synthétiques, Bitcoin et or ; ordres limites acceptés (`stop_loss`, `take_profit`) sur V75 et Bitcoin.
- [x] Portées OAuth : `trade`, `account_manage`, `application_read`, `payment`.
- [x] Durée du jeton OAuth : lire `expires_in` (30 jours dans l'exemple) ; aucun jeton de renouvellement.
- [x] Champs de prix : `buy_price`, `bid_price`, `profit`, `sell_price`.

Reste à vérifier sur un compte démo (étapes 2.3 et 3.4) :

- [ ] Portées exactes d'un PAT.
- [ ] Portée nécessaire pour lister les comptes, avec `trade` seul.
- [ ] `bid_price` inclut-il déjà la commission ? Valeur de `profit` juste après l'achat.
- [ ] `sell` juste après l'ouverture : délai éventuel, `is_valid_to_sell`.
- [ ] Glissement réel du stop loss par rapport au montant demandé.
- [ ] Bornes de `validation_params` sur l'or, marché ouvert.
- [ ] Limites de connexions WebSocket simultanées et code d'erreur de dépassement.

Source : [section 21](../spec/21-decisions.md), parties « À vérifier à l'étape 2.1 » et « Conséquences sur le cahier des charges ».
