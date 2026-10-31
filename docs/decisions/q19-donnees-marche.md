# Données de marché (étape 2.5)

- **Statut :** en place, mesures du 31 octobre 2026 (samedi, or fermé)
- **Portée :** lecture seule, point public Deriv, sans jeton

## Fonctionnement

```
Deriv (point public)  ->  worker safetradev2-worker  ->  Redis  ->  API  ->  navigateur (SSE)
```

- **Une seule connexion** pour tout le serveur : les prix ne consomment ni un jeton ni une connexion par utilisateur. L'API ne parle jamais à Deriv pour les prix.
- **Server-Sent Events** plutôt que WebSocket : le flux va du serveur au navigateur uniquement, et il passe par la réécriture `/api` de Next.js avec le cookie de session (vérifié : ticks reçus au fil de l'eau). Aucune dépendance ajoutée.
- `GET /market/assets`, `GET /market/candles`, `GET /market/stream` : session obligatoire. Un flux dure 5 minutes au plus puis le navigateur se reconnecte, ce qui revalide la session. 5 flux au plus par utilisateur et par instance d'API.
- Actifs suivis : `SAFETRADE_MARKET_SYMBOLS`. Leur état, leur nom et leur précision viennent toujours de `active_symbols`, relu chaque minute.

## Statut d'un actif

Le backend calcule le statut, le front-end l'affiche. **Seul `live` autorisera un bot à trader** (règle à brancher en phase 3).

| Statut | Signification |
| --- | --- |
| `live` | Marché ouvert, tick reçu depuis moins de 30 s |
| `closed` | `exchange_is_open` à 0 |
| `suspended` | `is_trading_suspended` à 1 |
| `stale` | Marché ouvert mais aucun tick récent |
| `unavailable` | Le flux n'a pas relu les actifs depuis 3 minutes |

## Cohérence

- Marché fermé : Deriv refuse `ticks` avec `MarketIsClosed` et annonce la réouverture dans le message [mesuré]. Les bougies restent lisibles [mesuré].
- Ticks écartés : actif différent, cours ou date invalides, date déjà reçue.
- Trou de plus de 15 s : événement `gap` et bougies de l'actif relues en priorité.
- Flux muet plus de 30 s sur un marché ouvert, ou reprise refusée : réouverture.
- Bougies : ordre strict et plus-haut, plus-bas cohérents, sinon non enregistrées.
- Quatre intervalles (1, 5, 15 et 60 minutes), 500 bougies, un rafraîchissement toutes les 1,5 s : 40 appels par minute, sous les 176 du quota retenu.

## Mesures

Depuis le poste de développement, **pas depuis un serveur** :

| Mesure | Résultat |
| --- | --- |
| Actifs reçus en direct | 5 sur 5 ouverts ; l'or signalé `closed` |
| Rythme | 1 tick par seconde ; 1 toutes les 2 s sur `R_100` |
| Aller-retour de `time` | Médiane 342 ms, de 305 à 455 ms (20 essais) |
| Trois coupures provoquées | Flux repris en 1,85, 2,89 et 5,23 s, sans tick écarté |
| Flux SSE via le front-end | 58 ticks en 12 s |

L'âge d'un tick à réception n'est pas exploitable au-dessous de la seconde : `epoch` est arrondi à la seconde et l'horloge locale différait de 0,36 s. **La latence décisive pour l'hébergement reste à mesurer depuis les serveurs candidats** ([q12](q12-hebergement.md)).

## Limites

- Le flux est mono-instance : deux workers publieraient chaque tick en double.
- `stale` et `gap` n'ont pas été observés en réel, seulement sur faux broker.
- Les 24 heures sans coupure non récupérée relèvent de l'étape 2.6.
- Redis partage le pub/sub entre toutes ses bases numérotées : ne pas supposer l'isolation d'un test par numéro de base.
