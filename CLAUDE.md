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
  - Mise en œuvre : `backend/app/authz.py`. Routes privées : dépendance `CurrentSession`. Administration : routeur `/admin` protégé au niveau du routeur (`require_admin` : rôle administrateur **et** double authentification), puis `require_permission(...)` par route. Rôles et permissions : `ROLE_PERMISSIONS`.
  - `tests/test_authz.py` parcourt toutes les routes (schéma OpenAPI) : une route non listée dans `PUBLIC_ROUTES` doit refuser l'accès sans session, toute route `/admin` doit refuser un client.
  - Créer un administrateur : `docker exec -it safetradev2-backend python -m app.cli create-admin --email ... --role super_admin` (mot de passe demandé de façon masquée).
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
- **Champs de saisie** (composant `Field`) : icône Lucide en tête, texte indicatif (placeholder) traduit, focus rouge de marque avec halo léger.
- **Formulaires** : `noValidate` et `useFormErrors` (`src/lib/use-form-errors.ts`), règles dans `src/lib/validation.ts`. Erreur en rouge sous le champ, jamais de bulle du navigateur ; le serveur revalide tout.
- **Thème dans les barres** : un seul bouton (`ThemeToggle`) dont l'icône montre le mode affiché (soleil en clair, lune en sombre) ; sans choix enregistré, le thème suit le système. Le choix « automatique » explicite sera proposé dans le profil (section 15). Décision du propriétaire du 30 octobre 2026.
- **Langue** : menu déroulant (`LanguageSelect`) avec drapeaux en SVG (`public/flags`, jamais d'emoji) et nom de chaque langue ; le bouton affiche le drapeau et le code (FR, EN).

### Identité visuelle : rouge et anthracite (règle permanente, remplace le bleu de la section 15)

- La couleur principale est le **rouge de l'identité SafeTrade**, associé à l'**anthracite**, dans les thèmes clair et sombre. Jamais de nouvelle identité bleue, jamais de rouge sang, jamais de changement de teinte sans raison documentée.
- Valeurs retenues, mesurées sur le logo `docs/brand/logo-safetrade-source.png` (**hypothèse**, pas de charte officielle) : rouge `#D6041D`, anthracite `#202329`. Tableau complet des jetons et contrastes : `docs/decisions/q13-identite-visuelle.md`.
- Le rouge de marque est le même remplissage dans les deux thèmes ; seul le texte rouge du thème sombre utilise la variante claire `#FF3B4E`.
- Rouge de marque et pertes sont proches : une perte est **toujours** affichée avec son signe « - » et une icône, et utilise le rouge de perte (`#B91C1C` en clair), jamais l'accent.

## Qualité front-end et expérience utilisateur (règle permanente, 30 octobre 2026)

Objectif : un vrai produit SaaS de trading professionnel et international, pas un tableau de bord administratif, un formulaire classique ou un document qu'on fait défiler. La maquette de l'étape 0.4 n'est qu'une base fonctionnelle : la dépasser.

- **Impression** : sérieux, maîtrise technologique, sécurité, précision financière, confiance. Identité rouge et anthracite, typographie et icônes de la section « Design » inchangées.
- **Mobile d'abord** (cible principale : smartphone). Concevoir à 360 px puis enrichir vers tablette et ordinateur, jamais réduire une page d'ordinateur. Tableaux financiers transformés en cartes ou listes sur mobile, graphiques lisibles, menus et actions accessibles au pouce, cibles tactiles de 44 px minimum, champs de 16 px minimum (pas de zoom iOS), clavier virtuel pris en compte (`inputMode`, `autoComplete`, `enterKeyHint`, `dvh`), aucun élément fixe qui masque le contenu, aucun débordement horizontal.
- **Connexion et inscription** : deux colonnes (visuel et formulaire) sur ordinateur ; sur téléphone, page pleine largeur à structure verticale, en-tête compact avec logo, formulaire intégré à la page, **jamais une petite carte centrée**. États de chargement, d'erreur, de validation et de réussite soignés.
- **Page publique** : header avec connexion et inscription, hero fort, fonctionnement, marchés, fonctionnalités, risque et sécurité, abonnements, FAQ, footer. Peu de texte, hiérarchie forte, sections aérées.
- **Expérience de trading** : graphiques financiers, indicateurs de performance, cartes de positions, données de marché structurées, états de connexion et du bot, historiques lisibles, indicateurs de risque.
- **Données fictives** toujours marquées « Données de démonstration » ; jamais de performance simulée présentée comme réelle.
- **Animations** discrètes et légères : apparition au défilement, transitions d'états et de pages, survols, profondeur et lumière maîtrisées, graphiques animés. CSS et API natives (IntersectionObserver, View Transitions) avant toute bibliothèque ; `prefers-reduced-motion` toujours respecté ; aucune animation qui ralentit l'interface.
- **Images** : deux à quatre au maximum sur la page publique, déposées par le propriétaire dans `frontend/public/images/` (chemins et dimensions documentés dans `frontend/public/images/README.md`). Le composant d'image accepte PNG, JPG, JPEG, WebP et SVG et affiche un repli élégant tant que le fichier manque. Préférer les illustrations CSS et les compositions d'interface aux images.
- **Système de composants** réutilisable : pas de composant dupliqué ni de style dispersé ; tout passe par les jetons de thème.
- **Vérification avant « terminé »** dans le navigateur : téléphone 360, 375, 390 et 430 px, tablette, ordinateur 1366 et 1920 px ; interactions, animations, formulaires, clair et sombre, FR et EN, accessibilité (clavier, contrastes, libellés) et performances.
- Les choix esthétiques relèvent du jugement du développeur : pas de validation demandée au propriétaire.

## Docker : isolation absolue (règle permanente)

- **Ne jamais supprimer, réinitialiser, renommer ni modifier** un conteneur, une base, un volume, un réseau ou une image qui n'appartient pas à SafeTrade V2 (MUYUEXCHANGE, MUYUSTORE, ancien SafeTrade `safetrade-api` et `safetrade-pg`, ou tout autre projet). Aucun `docker system prune`, `docker volume prune` ni commande globale.
- Tout ce que crée SafeTrade V2 est préfixé `safetradev2` : projet Compose, base `safetradev2`, conteneurs `safetradev2-postgres`, `safetradev2-redis`, `safetradev2-backend`, `safetradev2-worker`, `safetradev2-engine` et `safetradev2-frontend`, réseau `safetradev2-network`, volumes `safetradev2-postgres-data` et `safetradev2-redis-data`.
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
6. **Règle absolue : aucun ordre réel, aucun accès à des fonds réels et aucune mise en production sans validation explicite du propriétaire.**
7. Achats uniquement par identifiant de proposition, jamais par paramètres. Après un délai dépassé ou une réponse perdue, lire `statement` avant toute nouvelle tentative : un achat n'est jamais renvoyé automatiquement.
8. Aucune stratégie présentée comme rentable sans backtest et test en avant solides, frais compris. Vocabulaire de calcul et sorties dynamiques : `docs/decisions/q18-sorties-dynamiques.md`.

## Mode de travail

Directive du propriétaire du 31 octobre 2026, qui remplace les précédentes :

- Développer par **blocs fonctionnels complets et intégrés**, de bout en bout, sans valider chaque petite étape. Regrouper le travail lié, ne pas répéter les analyses déjà faites.
- Interrompre le propriétaire uniquement pour : une décision commerciale, réglementaire ou stratégique, une dépense externe, une action irréversible, une opération impliquant des fonds réels ou la production.
- CI : classer un échec selon sa gravité. Corriger aussitôt sécurité, données, architecture et exécution ; documenter le mineur et continuer. Jamais de test désactivé. Une fonctionnalité dont un test essentiel échoue n'est pas validée.
- Ne jamais présenter comme réelle une intégration qui n'a pas été essayée.
- Rapport à la fin de chaque bloc, et seulement alors : ce qui a été développé, ce qui fonctionne et a été testé, les blocages, le commit et son état sur GitHub, la prochaine fonctionnalité concrète.

## Connexion au broker

- Interface : `backend/app/broker/base.py` ; le moteur ne dépend que de ce contrat. Client Deriv : `app/broker/deriv.py`.
- Quotas : `app/broker/quotas.py`, REST et WebSocket séparés, par groupe d'appels, partagés entre les bots via Redis (80 % des limites officielles). Les sorties gardent du budget quand les entrées sont plafonnées.
- `DerivConnection` ne renvoie jamais une requête. Une réponse d'achat perdue lève `OrderOutcomeUnknownError` : lire `statement` avant toute autre tentative.
- Tests sur `tests/fake_deriv.py`, sans réseau.
- Données de marché : worker `app/market/worker.py`, une connexion publique pour tout le serveur, puis Redis et flux SSE (`/market/stream`). Un seul worker actif (bail Redis vérifié à chaque écriture). Le statut d'un actif est calculé par le backend ; aucune ouverture sans `entry_refusal` nul (`app/market/quality.py`). Détails : `docs/decisions/q19-donnees-marche.md`.

## Moteur de trading

- Seul `safetradev2-engine` (`app/trading/worker.py`) émet des ordres ; l'API enregistre des demandes. Détails : `docs/decisions/moteur-trading.md`.
- Tout ordre passe par `risk.order_refusal` et `entry_refusal`. Stop loss obligatoire, jamais retiré. Une position est écrite en base avant l'envoi.
- Le mot d'ordre `stop_loss: null` est interdit : `DerivTrading.update_stop` le refuse.

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

Base de données (variables à exporter, valeurs dans `infra/.env`) :

```bash
export SAFETRADE_DATABASE_URL=postgresql+psycopg://safetradev2:<mot de passe>@127.0.0.1:15432/safetradev2
export SAFETRADE_TEST_DATABASE_URL=postgresql+psycopg://safetradev2:<mot de passe>@127.0.0.1:15432/safetradev2_test
.venv/Scripts/alembic upgrade head        # appliquer ; downgrade -1 pour annuler
.venv/Scripts/alembic revision --autogenerate -m "résumé" --rev-id 0002   # nouvelle migration, à relire
```

- Le test des quotas Redis exige `SAFETRADE_TEST_REDIS_URL` (par exemple `redis://127.0.0.1:16379/9`).
- Les tests de base de données recréent `safetradev2_test` à chaque exécution (nom obligatoirement en `_test`) ; ils sont ignorés si `SAFETRADE_TEST_DATABASE_URL` est absent, jamais en CI.
- Chaque migration a une descente testée ; `test_models_match_migrations` échoue si un modèle diverge des migrations.
- Le conteneur backend applique `alembic upgrade head` à chaque démarrage.

Front-end (`frontend/`, Node 20, Next.js 16 : lire `node_modules/next/dist/docs/` avant d'utiliser une API) :

```bash
npm ci
npm run lint && npm run typecheck && npm test && npm run build
npm run dev
```

Le front-end appelle l'API uniquement via `src/lib/api.ts`, sous `/api/...` sur sa propre origine (réécriture Next.js vers `API_INTERNAL_URL`, figée au build) : cookie de session HttpOnly limité au domaine du site, pas de CORS. Les codes d'erreur sont traduits par `errorMessage()` ; un test vérifie que chaque code du backend a sa traduction.

La CI (`.github/workflows/ci.yml`) exécute exactement ces contrôles, puis démarre la stack Compose et interroge `/health`.
