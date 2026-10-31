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
- Actifs suivis : `SAFETRADE_MARKET_SYMBOLS`, plus tous les indices synthétiques ([catalogue-actifs.md](catalogue-actifs.md)). Leur état, leur nom et leur précision viennent toujours de `active_symbols`, relu chaque minute.

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
- Quatre intervalles (1, 5, 15 et 60 minutes), 500 bougies, une relecture toutes les 0,5 s au plus : 120 appels par minute, sous les 176 du quota retenu. Seuls les actifs demandés sont relus.

## Un seul worker actif

Exigence du propriétaire du 31 octobre 2026.

- Bail Redis de 15 s (`market:leader`), renouvelé toutes les 5 s, libéré à l'arrêt propre (`app/market/lease.py`).
- **La garantie vient de l'écriture, pas du renouvellement** : chaque écriture du flux vérifie le bail dans le même script Lua. Un worker gelé puis réveillé ne peut plus rien publier.
- Les autres instances attendent, puis prennent le relais. Une boucle tombée arrête tout le flux de ce worker.
- `RedisMarketStore` sans `owner` est en lecture seule : l'API ne peut rien écrire.

## Données autorisant une décision

`app/market/quality.py`, fonctions pures. `entry_refusal` renvoie un motif de refus ; le moteur l'appelle avant toute ouverture.

| Contrôle | Refus |
| --- | --- |
| Statut différent de `live` | `market.stale`, `market.closed`, `market.suspended`, `market.unavailable` |
| Aucun tick, tick daté du futur | `market.no_tick`, `market.tick_from_future` |
| Tick de plus de 5 s, date Deriv et date de réception confondues | `market.tick_stale` |
| Trou de moins de 60 s, ou bougies non relues depuis | `market.recent_gap`, `market.gap_not_repaired` |
| Bougies manquantes, en retard, non continues | `market.candles_missing`, `market.candles_stale`, `market.candles_gap` |

Chaque tick porte `epoch` (Deriv), `received_at` (réception) et `last_gap_epoch`. La bougie en formation n'entre jamais dans une décision (`closed_candles`).

## Surveillance

- Journaux JSON (`app/logs.py`), champ `event` stable.
- `monitor:feed`, publié toutes les 5 s même sans connexion : connexion, reconnexions, ticks reçus et écartés, trous, erreurs Deriv par code, latence, écart d'horloge, actifs silencieux.
- `GET /admin/monitoring/market`, permission `monitoring.read`.
- Alertes `market.feed_disconnected` (60 s), `market.symbols_silent`, `market.deriv_errors` : journal de niveau ERROR et liste `monitor:alerts`, levée puis fin.
- Présence de chaque instance dans `monitor:worker:{hôte}`, lue par le contrôle de santé Docker.

## Santé du worker

Le contrôle (`app/market/health.py`) répond à une question : redémarrer ce worker serait-il utile ? Il remplace le contrôle HTTP de l'API hérité de l'image.

| État | Résultat | Où le suivre |
| --- | --- | --- |
| Redis injoignable | `redis.unreachable`, en échec | Contrôle Docker |
| Signal de vie absent ou de plus de 20 s | `worker.absent`, `worker.stalled` | Contrôle Docker |
| Responsable sans rapport du flux depuis 30 s | `feed.stalled` | Contrôle Docker |
| Instance en attente | Sain | Rôle dans `monitor:worker` |
| Deriv coupé, reconnexion | **Sain** | `monitor:feed`, alertes |
| Marché fermé | **Sain** | Statut de l'actif |

Trois échecs de suite, à 30 s d'intervalle, sont nécessaires : une coupure brève ne déclenche rien, une vraie panne est signalée en 90 s environ. Coût mesuré d'un contrôle : 0,69 s de CPU et 36 Mo, soit 2,3 % d'un cœur en moyenne, contre 0,65 % pour le worker. Le délai de démarrage est de 20 s et un nouveau responsable dispose de 30 s pour son premier rapport.

L'état `unhealthy` ne redémarre pas le conteneur avec Docker Compose. `restart: unless-stopped` couvre l'arrêt du processus.

**Échec de CI du 31 octobre :** `docker compose up --wait` refuse un conteneur dont le contrôle est désactivé (`container has no healthcheck configured`), alors que Compose 5.5.1 sur le poste l'accepte. Ne jamais désactiver ce contrôle.

**Limite :** aucune alerte ne quitte encore le serveur, faute de fournisseur d'e-mails (q15), et un worker mort ne peut pas s'alerter lui-même. Il faudra une sonde externe au déploiement.

## Essais réels de santé et de relais

| Scénario | Résultat |
| --- | --- |
| Commande de la CI, images reconstruites | 5 conteneurs sains, `/health` et front-end répondent |
| Deux workers pendant 20 s | 73 ticks, 0 doublon |
| Arrêt propre du responsable | Relais en 1,2 s |
| Arrêt brutal, bail non libéré | Relais à l'expiration du bail, environ 13 s |
| Deriv injoignable 80 s | Worker sain, alerte `market.feed_disconnected` levée |
| Redis en pause 20 s | 1 échec isolé, worker resté sain |
| Worker gelé 75 s | `unhealthy` (`worker.absent`), puis sain après reprise |
| Écritures du worker dégelé | Refusées (`LeadershipLostError`) tant qu'il n'a pas repris le bail |

Mesures faites à 15 s d'intervalle, avant le passage à 30 s pour réduire la charge.

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

- `stale` et `gap` n'ont pas été observés en réel, seulement sur faux broker.
- **Test de stabilité de 24 heures : non exécuté, donc non validé.** Il reste dû à l'étape 2.6.
- Redis partage le pub/sub entre toutes ses bases numérotées : ne pas supposer l'isolation d'un test par numéro de base.
