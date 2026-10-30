# SafeTrade

SaaS de trading semi-automatique connecté à l'API Options de Deriv : le moteur analyse le marché, ouvre et clôture les positions dans les limites de risque fixées par l'utilisateur. SafeTrade ne détient jamais les fonds et ne promet aucun gain.

> Le trading comporte un risque de perte en capital.

## Stack

| Couche | Technologies |
| --- | --- |
| Backend | Python, FastAPI, SQLAlchemy, Alembic |
| Données | PostgreSQL, Redis |
| Front-end | Next.js (TypeScript), Tailwind CSS, Lucide |
| Infrastructure | Docker Compose, GitHub Actions |

## Démarrage

```bash
cp infra/.env.example infra/.env   # puis renseigner le mot de passe et la clé de chiffrement
docker compose -f infra/docker-compose.yml --env-file infra/.env up -d --build --wait
```

- Site : http://127.0.0.1:13000
- API : http://127.0.0.1:18000/health

Commandes de développement, de test, de lint et de vérification des types : voir [CLAUDE.md](CLAUDE.md).

## Organisation

| Dossier | Contenu |
| --- | --- |
| `backend/` | API, authentification, double authentification, migrations, tests |
| `frontend/` | Application Next.js, composants, thèmes, traductions FR et EN |
| `infra/` | Docker Compose (environnement isolé `safetradev2`) |
| `docs/spec/` | Cahier des charges, une section par fichier |
| `docs/decisions/` | Décisions d'architecture et points en attente |
| `docs/maquettes/` | Maquettes de référence |

## Sécurité

Aucun secret n'est versionné : les valeurs réelles vivent dans `infra/.env` (ignoré par Git). Pour signaler une vulnérabilité, contacter l'équipe en privé plutôt qu'ouvrir une issue publique.
