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
- [x] Portée nécessaire pour lister les comptes : `trade` [doc]. Connexion démo, solde et reconnexion avec nouvel OTP vérifiés le 31 octobre 2026.
- [x] `bid_price` et `profit` incluent la commission.
- [x] `sell` juste après l'ouverture : refus possible tant que l'entry tick manque, moins de 2 s.
- [ ] Glissement du stop loss sur un grand échantillon (0,03 USD observé sur 0,25).
- [ ] Stop loss minimal demandé en cours de position, en gain.
- [ ] Cause du `RateLimit` isolé sur `proposal_open_contract`.
- [x] `stop_loss` et `take_profit` fonctionnent sur les multiplicateurs.
- [x] Exécution avec SafeTrade déconnecté : 3 sur 3. La réconciliation automatique reste à coder (étape 3.4).
- [x] `contract_update` : déplacement accepté, une fois par seconde ; stop loss en zone de gain refusé.
- [x] Pas de trailing stop natif ; répartition Deriv et moteur dans [q18](q18-sorties-dynamiques.md).
- [x] `statement` donne les champs d'appariement. Reste à le coder (étape 3.4).
- [ ] Bornes de `validation_params` sur l'or, marché ouvert.
- [ ] Limites de connexions WebSocket simultanées et code d'erreur de dépassement.

Source : [section 21](../spec/21-decisions.md), parties « À vérifier à l'étape 2.1 » et « Conséquences sur le cahier des charges ».
