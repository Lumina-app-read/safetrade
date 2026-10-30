# Intégration Deriv : note technique (étape 2.1)

- **Statut :** décisions du propriétaire intégrées (voir la fin) ; vérifications sur compte démo en attente
- **Date :** 31 octobre 2026
- **Sources :** documentation officielle consultée ce jour, schémas JSON officiels (`developers.deriv.com/schemas/`), et mesures en lecture seule sur le point WebSocket public, sans compte et sans aucun achat.

Légende : **[doc]** écrit dans la documentation, **[mesuré]** observé sur l'API publique le 31 octobre 2026, **[à vérifier]** nécessite un compte démo. Cette note complète la section 21 et la corrige sur les points signalés.

## Corrections de la section 21

| Point | Section 21 | Réalité |
| --- | --- | --- |
| Durée du jeton OAuth | 3 600 s dans l'exemple | 2 592 000 s (30 jours) dans l'exemple actuel. Lire `expires_in`, ne jamais coder la durée en dur [doc] |
| Jeton de renouvellement | À vérifier | **Il n'existe pas** pour les applications tierces [doc] |
| Mise minimale (section 7 : 0,35 USD) | 0,35 à 50 | **1,00 USD** en multiplicateurs, maximum 500 [mesuré] |
| Gain net minimal (section 7) | 0,05 à 5 | Plus de seuil fixe ([q18](q18-sorties-dynamiques.md)). `take_profit` minimum 0,10 USD chez Deriv [mesuré] |
| Calcul du spread | Écart achat et rachat | En multiplicateurs, le coût visible est la **commission** ; voir plus bas |

## Accès et authentification

- REST : `https://api.derivws.com`. WebSocket : `wss://api.derivws.com/trading/v1/options/ws/{public|demo|real}` [doc].
- `POST /trading/v1/options/accounts/{accountId}/otp` avec `Authorization: Bearer` renvoie une adresse WebSocket contenant l'OTP. **L'OTP vaut 120 secondes et chaque adresse ne sert qu'une fois** : en demander une nouvelle à chaque reconnexion [doc].
- OAuth 2.0 avec PKCE : `https://auth.deriv.com/oauth2/auth`, puis `https://auth.deriv.com/oauth2/token` depuis le backend. `state` obligatoire, `code_challenge_method=S256`, adresse de redirection enregistrée à l'identique [doc].
- Portées disponibles : `trade`, `account_manage`, `application_read`, `payment` [doc]. **SafeTrade demande uniquement `trade`** ; `payment` et `account_manage` ne doivent jamais être demandés.
- PAT : en-tête `Deriv-App-ID` obligatoire sur REST, sinon erreur 401 [doc]. Portées des PAT non documentées [à vérifier].

### Conséquence : pas de renouvellement silencieux

À l'expiration du jeton (ou sur un 401), l'utilisateur doit se réautoriser. Le bot ne peut pas le faire seul. Donc :

1. stocker la date d'expiration et prévenir l'utilisateur plusieurs jours avant ;
2. à l'expiration : plus de nouvelle position, état « Erreur », alerte. Les positions ouvertes restent protégées par le stop loss posé chez Deriv.

### Conséquence : révocation

La documentation ne décrit aucun point de révocation de jeton. « Révocable en un clic » (section 5) signifie donc que SafeTrade efface le jeton de son côté ; la révocation chez Deriv reste à faire par l'utilisateur dans son espace Deriv, et l'interface doit le dire.

## Contrat retenu : multiplicateurs (hypothèse de travail)

`MULTUP` et `MULTDOWN` sont le meilleur choix pour la première version. Ils respectent la décision [q03](q03-stop-loss.md) : stop loss posé à l'ouverture, vente possible avant l'échéance, et les deux sens de marché.

- `limit_order` accepte `stop_loss` et `take_profit` à l'ouverture, et `contract_update` les modifie ensuite [doc, mesuré].
- **Ces ordres sont exécutés chez Deriv** : la protection reste active si SafeTrade tombe. Le stop loss ne doit donc pas être simulé par le moteur.
- Un `stop_out` existe toujours : la perte maximale est la mise [mesuré].
- Si l'option `cancellation` est active, la vente peut être restreinte : le moteur ne l'utilise pas [à vérifier].

| Actif | Multiplicateurs | État le 31 octobre | Multiplicateurs proposés | Commission pour 1 USD à ×100 |
| --- | --- | --- | --- | --- |
| Volatility 75 (1s), `1HZ75V` | Oui, sans échéance pratique | Ouvert | 50 à 500 | 0,03 USD |
| Volatility 100, `R_100` | Oui | Ouvert | 40 à 400 | Non mesurée |
| Bitcoin, `cryBTCUSD` | Oui, échéance à 7 jours environ | Ouvert | 100 à 800 | 0,09 USD |
| Or, `frxXAUUSD` | Oui | Fermé (samedi) | Non mesurés | Non mesurée |

89 symboles actifs : 46 synthétiques, 25 forex, 12 indices, 4 matières premières, 2 cryptomonnaies. Liste à lire avec `active_symbols` (champs `underlying_symbol`, `exchange_is_open`, `is_trading_suspended`), jamais écrite en dur [mesuré]. Bornes à lire dans `validation_params` de chaque `proposal`, car Deriv les fixe par contrat [mesuré].

## Coût réel d'une position

Mesuré sur `1HZ75V`, mise 1 USD, ×100, cours 4906,61 : commission 0,03 USD ; stop loss de 0,50 USD au cours 4883,50 (-0,471 %) ; `stop_out` au cours 4858,97 (-0,971 %). Cela confirme la formule :

```
résultat ≈ mise × multiplicateur × variation du cours - commission
```

- La position **démarre à -0,03 USD** sur V75 et à -0,09 USD sur Bitcoin.
- Gain net : champ `profit` de `proposal_open_contract` (`bid_price` moins `buy_price`) [doc]. Que `bid_price` inclue déjà la commission : [à vérifier].

### Rentabilité

Les définitions (mise, commission, gain brut, gain net, perte nette) et le calcul des seuils sont fixés dans [q18](q18-sorties-dynamiques.md). Exemple de l'ordre de grandeur : sortir systématiquement à +0,10 USD avec un stop loss de 0,50 USD exigerait 83,3 % de réussite. Le propriétaire a écarté cette logique ; aucune stratégie n'est présentée comme rentable sans backtest solide, frais compris.

## Exécution des ordres

- **Toujours acheter par identifiant de `proposal`** (`buy` + `price` maximum) : une proposition ne s'achète qu'une fois, alors qu'un achat par paramètres répété peut ouvrir un second contrat [doc]. C'est le premier rempart anti-doublon.
- Vente : `sell` + `contract_id` + `price` (`0` pour vendre au marché) ; réponse `sold_for`, `balance_after`, `transaction_id` [doc]. Vérifier `is_valid_to_sell` et `validation_error` avant [doc].
- Suivi : abonnement `proposal_open_contract`, à arrêter dès que `is_sold` vaut 1 [doc].
- Réconciliation : `portfolio` pour les positions ouvertes. **Pas de recherche par identifiant de requête** : pour un achat dont la réponse est perdue, lire `statement` (type `buy`, depuis juste avant l'envoi) et apparier application, montant, shortcode et heure [doc].

## Connexion et limites

- Une seule connexion WebSocket par compte, réponses appariées avec `req_id`, `ping` toutes les 30 s, reconnexion avec attente exponentielle et variation aléatoire [doc].
- WebSocket, budgets partagés : voir [q01](q01-produit-deriv.md), limites confirmées sans changement [doc]. `ping` : 10 par seconde, hors budget [doc].
- REST : 80 requêtes par minute par utilisateur, et **par adresse IP : 300 par minute et 1 000 sur 10 minutes** [doc]. Codes d'erreur de dépassement non documentés : lire le champ `error` [doc].
- Limites indicatives, modifiables à tout moment par Deriv [doc].

### Conséquence : limite par adresse IP

Tous les bots partagent l'adresse du serveur. Après un redémarrage, 300 bots demanderaient 300 OTP d'un coup, juste à la limite, et 1 000 sur 10 minutes est vite atteint avec des reconnexions. Les reconnexions doivent être **étalées dans le temps** par une file commune, et l'étape 2.2 doit le prévoir. Si l'adresse est bloquée, tous les utilisateurs sont touchés.

## Données de marché

- `ticks`, `ticks_history` (`style: candles`, `granularity` en secondes), `trading_times` et `contracts_for` répondent sans authentification sur le point public [mesuré].
- Le point public peut donc alimenter l'analyse sans jeton, avec une connexion partagée par actif plutôt qu'une par utilisateur.

## Reste à vérifier sur compte démo

Voir [verifications-etape-2-1.md](verifications-etape-2-1.md).

## Décisions du propriétaire (31 octobre 2026)

- Multiplicateurs : contrat retenu pour la première version.
- Pas d'objectif de gain universel : sorties dynamiques, voir [q18](q18-sorties-dynamiques.md). La section 7 ne fixe plus de gain net de clôture.
- Achats : uniquement par identifiant de proposition. Après un délai dépassé ou une réponse perdue, lire `statement` avant toute nouvelle tentative.
- OAuth : utiliser `expires_in` tel que renvoyé, alertes avant expiration, passage automatique en état sûr.
- Limites : REST et WebSocket distincts, quotas par groupe, centralisés entre les bots, reconnexion progressive avec attente exponentielle et jitter.
- **Règle absolue : aucun ordre réel, aucun accès à des fonds réels et aucune mise en production sans validation explicite du propriétaire.**
