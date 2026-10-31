# Catalogue des actifs, barre de trading et lien partenaire

Demande du propriétaire du 31 octobre 2026.

## Catalogue

- La liste vient de `active_symbols`, jamais écrite en dur : tous les actifs du marché `synthetic_index`, plus `SAFETRADE_MARKET_SYMBOLS` (les actifs par défaut).
- Relevé du 31 octobre 2026 : 46 indices synthétiques (Volatility 13, Crash et Boom 14, Jump 5, Step 5, Range Break 2, paniers 5, Bull et Bear 2).
- 44 proposent les multiplicateurs. **Bear Market et Bull Market n'en proposent pas** : ils s'affichent, mais le bot les refuse (`trading.no_multipliers`). Cette information vient de `contracts_for`, lu pour un actif par seconde, puis toutes les 6 heures.

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
- Afficher un actif n'autorise pas le bot à le trader : `allowed_symbols` reste une autorisation explicite, dans les paramètres.
- Crash, Boom et Jump bougent par à-coups : le sélecteur le signale. Aucune stratégie n'est calibrée pour eux, et le bot n'y a pas été essayé en démo. Les plages de multiplicateurs varient par actif et sont lues dans chaque `proposal`.

## Lien partenaire Deriv

- `site_settings`, clé `deriv_signup_url`, modifié dans Administration, Réglages (`settings.write`), journal `admin.site_settings`.
- Lu sans session par `GET /site/config`, car la page d'accueil en a besoin.
- Adresse `https` sans identifiants, sinon `admin.invalid_url`. Vide : l'invitation disparaît du site.
- Affichée sur la page de trading, le tableau de bord, la page d'accueil et après l'inscription, seulement pour qui n'a pas connecté de compte Deriv.
- Lien marqué `sponsored`, avec une mention de partenariat : un visiteur doit savoir que SafeTrade peut être rémunéré.

## Saisie des codes

`CodeInput` (`components/ui/code-input.tsx`) : une case par caractère. Un code collé remplit toutes les cases depuis la première, où que soit le curseur. Le remplissage automatique du téléphone suit le même chemin. Le code à 6 chiffres part seul dès la dernière case ; après un refus, les cases se vident. Utilisé pour la double authentification, les codes de secours et le code de parrainage.
