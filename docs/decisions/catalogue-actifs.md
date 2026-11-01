# Catalogue des actifs, barre de trading et lien partenaire

Demande du propriétaire du 31 octobre 2026.

## Catalogue

- La liste vient de `active_symbols`, jamais écrite en dur : tous les actifs du marché `synthetic_index`, plus `SAFETRADE_MARKET_SYMBOLS` (les actifs par défaut).
- Relevé du 31 octobre 2026 : 46 indices synthétiques (Volatility 13, Crash et Boom 14, Jump 5, Step 5, Range Break 2, paniers 5, Bull et Bear 2).
- 44 proposent les multiplicateurs. **Bear Market et Bull Market n'en proposent pas** : ils s'affichent, mais le bot les refuse (`trading.no_multipliers`). Cette information vient de `contracts_for`, lu pour un actif par seconde, puis toutes les 6 heures.

## Multiplicateurs

- **Deriv n'accepte que cinq valeurs par actif, différentes d'un actif à l'autre** : 40 à 400 sur Volatility 100, 750 à 7500 sur Step Index 100. Le réglage du client ne peut donc pas s'appliquer partout.
- `risk.multiplier_for` : le plus proche du réglage sans le dépasser, sinon le plus petit proposé. La valeur utilisée est écrite sur la position avant l'envoi, et le client la voit avant de démarrer (`GET /trading/multiplier`).
- Sur Step Index 100, le ×100 demandé devient ×750 : à mise égale, la position est 7,5 fois plus exposée. La perte reste bornée par le stop loss et la mise.
- **`contracts_for` fait foi ; un devis sur le point public, non.** Mesuré le 1er novembre 2026 sur le compte démo : 39 actifs ouverts acceptés et aucun refus avec les listes de `contracts_for`. Le point public, lui, a répondu `400, 1000, 2000, 3000, 4000` pour Volatility 15 et 30 (1s) et Range Break, alors que le compte démo refuse ×400 sur trois d'entre eux. Un devis ne vaut donc preuve que sur un compte connecté.

## Charge

| Donnée | Portée | Coût |
| --- | --- | --- |
| Ticks | Tout le catalogue, une connexion | Mesuré avec 43 flux : 4 % de processeur, moins de 0,2 s de retard, aucun trou |
| Bougies | Actifs par défaut et actifs demandés | 3,5 appels par minute et par actif, 120 par minute au plus |
| Flux vers le navigateur | Actifs de la barre du client, plus celui de son bot | Maximum 60 |

- Relire les bougies de tout le catalogue prendrait trop de temps pour `candles_refusal`. Un actif n'est donc suivi que s'il est **demandé** : lecture de `/market/candles` ou bot en analyse (`store.demand`, 150 secondes de validité).
- Les bougies les plus en retard passent d'abord (`next_candles`) : 30 s pour les bougies d'une minute. Environ 34 actifs peuvent être suivis ensemble avant que les relectures prennent du retard.
- Bougies absentes : `/market/candles` répond `refreshing: true` et le graphique relit toutes les 1,5 s.

## Barre du client

- `users.market_watchlist` : liste et ordre choisis par le client (`GET` et `PUT /market/watchlist`). Vide : actifs par défaut.
- Décision du propriétaire du 31 octobre 2026 : **tout actif compatible est autorisé par défaut** (`trading_settings.all_symbols`). Le client peut encore restreindre à une liste dans ses paramètres (section 7).
- Crash, Boom et Jump bougent par à-coups : le sélecteur le signale. Aucune stratégie n'est calibrée pour eux. Essai réel en démo le 1er novembre 2026, signal forcé, un contrat de 1 USD fictif par indice : ouverture, clôture et arrêt corrects sur Step Index 100 (×750), Boom 500 (×100), Boom 50 (×500), Jump 10 (×100), Jump 75 (×75), Volatility 15 (1s) (×300), Volatility 30 (1s) (×140) et Range Break 100 (×100). Ce n'est ni un backtest ni une preuve de rentabilité.

## Lien partenaire Deriv

- `site_settings`, clé `deriv_signup_url`, modifié dans Administration, Réglages (`settings.write`), journal `admin.site_settings`.
- Lu sans session par `GET /site/config`, car la page d'accueil en a besoin.
- Adresse `https` sans identifiants, sinon `admin.invalid_url`. Vide : l'invitation disparaît du site.
- Affichée sur la page de trading, le tableau de bord, la page d'accueil et après l'inscription, seulement pour qui n'a pas connecté de compte Deriv.
- Lien marqué `sponsored`, avec une mention de partenariat : un visiteur doit savoir que SafeTrade peut être rémunéré.

## Saisie des codes

`CodeInput` (`components/ui/code-input.tsx`) : une case par caractère. Un code collé remplit toutes les cases depuis la première, où que soit le curseur. Le remplissage automatique du téléphone suit le même chemin. Le code à 6 chiffres part seul dès la dernière case ; après un refus, les cases se vident. Utilisé pour la double authentification, les codes de secours et le code de parrainage.
