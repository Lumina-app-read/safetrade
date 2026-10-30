# Q14. Isolation complète de l'environnement Docker

- **Statut :** décidé
- **Date :** 30 octobre 2026

## Décision du propriétaire

Le poste de développement héberge d'autres projets Docker (MUYUEXCHANGE, MUYUSTORE, une ancienne version de SafeTrade). SafeTrade V2 a sa propre infrastructure, sans rien réutiliser ni modifier.

**Règle absolue :** ne jamais supprimer, réinitialiser, renommer ni modifier un conteneur, une base, un volume ou un réseau qui n'appartient pas à SafeTrade V2.

## Noms retenus

| Élément | Nom |
| --- | --- |
| Projet Compose | `safetradev2` |
| Base PostgreSQL | `safetradev2` (utilisateur `safetradev2`) |
| Conteneurs | `safetradev2-postgres`, `safetradev2-redis`, `safetradev2-backend`, `safetradev2-frontend` |
| Images | `safetradev2-backend:dev`, `safetradev2-frontend:dev` |
| Réseau | `safetradev2-network` |
| Volumes | `safetradev2-postgres-data`, `safetradev2-redis-data` |

## Ports hôte

Relevé du 30 octobre 2026, avant le premier démarrage : 6379 (Memurai), 8000 (`safetrade-api`, ancien projet), 5433 (`muyustore-postgres`), 55432 (`safetrade-pg`) et 55433 (`muyuexchange-guard-test-pg`) sont pris ou réservés par des conteneurs arrêtés.

| Service | Port hôte (127.0.0.1) | Port interne |
| --- | --- | --- |
| PostgreSQL | 15432 | 5432 |
| Redis | 16379 | 6379 |
| API | 18000 | 8000 |
| Front-end | 13000 | 3000 |

Les conteneurs communiquent entre eux sur les ports standard, par le réseau `safetradev2-network`.

## Contrôle

Avant chaque changement de ports : `netstat -ano | findstr LISTENING` et `docker ps -a --format "{{.Names}} {{.Ports}}"`. Après chaque démarrage, l'état des conteneurs, volumes et réseaux des autres projets doit être identique à celui d'avant (vérifié le 30 octobre 2026).
