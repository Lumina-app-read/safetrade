# SafeTrade : règles permanentes

SaaS de trading semi-automatique branché sur l'API Options de Deriv. SafeTrade ne détient jamais les fonds et ne promet aucun gain.

Au début de chaque session : lire ce fichier, puis uniquement la section du cahier des charges concernée dans `docs/spec/` et les notes utiles de `docs/decisions/`.

## Stack

| Couche | Choix |
| --- | --- |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy et Alembic |
| Base de données | PostgreSQL |
| Cache, files, verrous | Redis ; worker dédié (ARQ ou Celery) |
| Front-end | Next.js (React) avec TypeScript strict, Tailwind CSS, icônes Lucide |
| Temps réel | WebSocket (ou Server-Sent Events) du backend vers le front-end |
| Infrastructure | Docker Compose, reverse proxy HTTPS |

Organisation : `backend/`, `frontend/`, `infra/`, `docs/spec/` (cahier découpé, ne jamais modifier ; fins de ligne CRLF conservées), `docs/decisions/`.

## Règle d'or

Le backend est la seule source de vérité. Le front-end envoie des demandes et affiche les réponses, il ne décide jamais. Toute règle (limites de risque, droits, état du bot, abonnement, expiration) est appliquée et vérifiée côté serveur. Le front-end ne simule jamais un succès : il attend la confirmation du backend.

## Sécurité : liste de contrôle (section 14)

- [ ] Toute entrée est revalidée côté serveur (schémas Pydantic stricts) ; requêtes SQL paramétrées uniquement.
- [ ] Contrôle d'accès vérifié à chaque requête ; un client ne voit que ses propres données ; rôles administrateur au moindre privilège.
- [ ] Mots de passe hachés en Argon2id ; politique de mot de passe robuste.
- [ ] TOTP proposé aux clients, obligatoire pour les administrateurs et pour activer le compte réel.
- [ ] Sessions courtes avec renouvellement ; cookies HttpOnly, Secure, SameSite ; sessions actives listées et révocables.
- [ ] Limitation de débit par utilisateur et par adresse sur les routes sensibles ; verrouillage progressif contre le brute force.
- [ ] Tokens Deriv chiffrés au repos (AES-256-GCM, clés dans un coffre de secrets), jamais renvoyés au front-end, jamais journalisés.
- [ ] Aucun secret dans le code, les tests ou Git : variables d'environnement, fichiers `.env` locaux non versionnés.
- [ ] HTTPS partout, HSTS, CSP, en-têtes de sécurité, protection CSRF, CORS restreint aux domaines de l'application.
- [ ] Webhooks de paiement : signature vérifiée, idempotence, liste d'adresses autorisées si possible.
- [ ] Ordres émis uniquement par le moteur backend, après validation du module de risque ; verrou anti-doublon.
- [ ] Actions sensibles écrites dans un journal d'audit non modifiable.
- [ ] Dépendances à jour et analysées ; sauvegardes chiffrées et testées.
- [ ] Données personnelles minimisées ; droit de suppression.

## Design (section 15)

- Police Plus Jakarta Sans, hébergée sur le serveur. **Graisse maximale 500** ; la hiérarchie vient de la taille, de l'espacement et de la couleur.
- Tailles : H1 28 px/400, H2 22 px/400, H3 18 px/500, texte 14 px/400, libellés et boutons 13 px/500, petit texte 12 px/400, chiffres clés 24 px/500.
- **Zéro emoji**, sauf l'emoji de salutation à côté de « Bonjour, {prénom} » sur le tableau de bord.
- Icônes Lucide : trait 1,5 px, 20 px (16 px dans les tableaux).
- **Couleurs uniquement via les variables de thème** (jetons de design) ; aucune couleur en dur dans un composant.
- Thèmes clair, sombre et automatique (défaut) sur toutes les pages, sans flash au chargement ; contraste WCAG AA (4,5 : 1).
- Grille de 8 px, cartes à 24 px de marge interne, coins de 8 à 12 px, bordures 1 px, ombres légères ou absentes.
- Responsive : chaque écran est utilisable sur téléphone.

### Identité visuelle : rouge et anthracite (règle permanente, remplace le bleu de la section 15)

- La couleur principale est le **rouge de l'identité SafeTrade**, associé à l'**anthracite**, dans les thèmes clair et sombre. Jamais de nouvelle identité bleue, jamais de rouge sang, jamais de changement de teinte sans raison documentée.
- Valeurs retenues, mesurées sur le logo `docs/brand/logo-safetrade-source.png` (**hypothèse**, pas de charte officielle) : rouge `#D6041D`, anthracite `#202329`. Tableau complet des jetons et contrastes : `docs/decisions/q13-identite-visuelle.md`.
- Le rouge de marque est le même remplissage dans les deux thèmes ; seul le texte rouge du thème sombre utilise la variante claire `#FF3B4E`.
- Rouge de marque et pertes sont proches : une perte est **toujours** affichée avec son signe « - » et une icône, et utilise le rouge de perte (`#B91C1C` en clair), jamais l'accent.

## Docker : isolation absolue (règle permanente)

- **Ne jamais supprimer, réinitialiser, renommer ni modifier** un conteneur, une base, un volume, un réseau ou une image qui n'appartient pas à SafeTrade V2 (MUYUEXCHANGE, MUYUSTORE, ancien SafeTrade `safetrade-api` et `safetrade-pg`, ou tout autre projet). Aucun `docker system prune`, `docker volume prune` ni commande globale.
- Tout ce que crée SafeTrade V2 est préfixé `safetradev2` : projet Compose, base `safetradev2`, conteneurs `safetradev2-postgres`, `safetradev2-redis`, `safetradev2-backend` et `safetradev2-frontend`, réseau `safetradev2-network`, volumes `safetradev2-postgres-data` et `safetradev2-redis-data`.
- Avant de choisir ou de changer un port hôte : vérifier `netstat -ano | findstr LISTENING` et les ports réservés par **tous** les conteneurs, même arrêtés (`docker ps -a`). Entre conteneurs, toujours les ports standard des services.
- Détails et relevé des ports : `docs/decisions/q14-isolation-docker.md`.

## Traduction

- Aucun texte en dur : toute chaîne visible passe par les fichiers de traduction et existe en **français et en anglais**.
- Le backend renvoie des codes d'erreur ; le front-end les traduit. E-mails, notifications, reçus, pages légales et explications de l'IA sont aussi traduits.
- La construction échoue si une clé manque dans une langue.
- Mise en œuvre (front-end) : toutes les pages sous `src/app/[locale]/` (`/fr`, `/en`) ; textes dans `src/messages/{fr,en}.json` lus par `getMessages(locale)` ; variables `{nom}` via `interpolate` ; nombres, montants et dates uniquement via `formatters(locale)` (`src/i18n/format.ts`), jamais `Intl` directement dans un composant. `src/proxy.ts` redirige les adresses sans langue (cookie `st-locale`, sinon `Accept-Language`). `npm run check:messages` (lancé avant chaque build et en CI) refuse une clé manquante, vide ou des variables différentes.

## Interdits (section 19, règles 5 à 9)

1. Pas de refactorisation hors du périmètre de l'étape ; pas de nouvelle dépendance sans justification écrite (dans le message de commit ou une note de `docs/decisions/`).
2. Un doute sur une exigence se lève, il ne se devine pas (voir « Mode de travail » pour savoir quand interrompre le propriétaire).
3. Les tests contre Deriv utilisent uniquement un compte démo ; aucun test automatisé n'utilise un compte réel.
4. Aucun secret (token, clé de paiement, mot de passe) dans le code, les tests ou Git.
5. Le compte réel reste désactivé par un interrupteur de configuration jusqu'à la phase 8.

## Mode de travail

Directive du propriétaire du 30 octobre 2026, qui remplace la validation après chaque étape :

- Enchaîner les étapes de la section 20 dans l'ordre, dès que leurs dépendances sont satisfaites, sans demander de validation intermédiaire.
- Interrompre le propriétaire uniquement pour : une décision commerciale ou stratégique que le cahier ne tranche pas, une question juridique, une dépense réelle ou une souscription externe, une action irréversible, une opération de production ou impliquant de vrais fonds, une information indispensable impossible à supposer.
- Sinon : documenter le point bloquant dans `docs/decisions/`, adopter une hypothèse provisoire sûre, et avancer sur le travail indépendant.
- Compte rendu concis à chaque jalon : réalisé, fichiers, tests et résultats, commit et branche, blocages, prochaine étape.

## Git

- Une étape = une branche `step/ID-nom-court` (exemple : `step/1.5-inscription-connexion`), à partir de `main`.
- Messages de commit : `type(portée): résumé à l'impératif (étape ID)`, types `feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `ci`. Corps : ce qui change et pourquoi.
- Fusion dans `main` en fast-forward uniquement, et seulement quand la définition de « terminé » est remplie. Jamais de réécriture d'historique publié.
- Fin de phase : étiquette `phase-N` et courte note de bilan.

## Définition de « terminé »

- [ ] Le critère d'acceptation de l'étape est démontré (commande, capture ou test).
- [ ] Tests, types et lint passent en local et en intégration continue.
- [ ] Aucun texte non traduit, aucune couleur en dur, aucun secret dans le code.
- [ ] Les écrans touchés sont vérifiés en thème clair et sombre, sur ordinateur et téléphone.
- [ ] Un commit clair sur la branche dédiée ; fusion dans `main` une fois tout vérifié.
- [ ] Fin de phase : étiquette `phase-N` et note de bilan.

## Commandes

Environnement complet (PostgreSQL, Redis, backend, front-end), depuis la racine :

```bash
cp infra/.env.example infra/.env   # une seule fois, puis changer le mot de passe
docker compose -f infra/docker-compose.yml --env-file infra/.env up -d --build --wait
curl http://127.0.0.1:18000/health
docker compose -f infra/docker-compose.yml --env-file infra/.env down   # jamais -v sans raison
```

Ports hôte : API 18000, front-end 13000, PostgreSQL 15432, Redis 16379 (voir « Docker : isolation absolue »).

Backend (`backend/`, Python 3.11 ou plus) :

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"   # bin/ sous Linux
.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .        # lint et format
.venv/Scripts/mypy app tests                                             # types (strict)
.venv/Scripts/pytest                                                     # tests
.venv/Scripts/uvicorn app.main:app --reload                              # lancement local
```

Front-end (`frontend/`, Node 20, Next.js 16 : lire `node_modules/next/dist/docs/` avant d'utiliser une API) :

```bash
npm ci
npm run lint && npm run typecheck && npm test && npm run build
npm run dev
```

La CI (`.github/workflows/ci.yml`) exécute exactement ces contrôles, puis démarre la stack Compose et interroge `/health`.
