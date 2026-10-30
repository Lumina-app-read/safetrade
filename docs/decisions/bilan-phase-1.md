# Bilan de la phase 1 : socle

- **Date :** 31 octobre 2026
- **Étiquette Git :** `phase-1`

## Livré

| Étape | Résultat |
| --- | --- |
| 1.1 | Dépôt, Docker Compose isolé `safetradev2`, CI GitHub Actions |
| 1.2 | Thèmes rouge et anthracite, Plus Jakarta Sans, composants de base |
| 1.3 | Traduction FR et EN complète, contrôle bloquant des clés |
| 1.4 | Migrations Alembic, journal d'audit en ajout seul |
| 1.5 | Inscription, vérification d'e-mail, connexion, limitation des tentatives, écrans mobile d'abord, page d'accueil publique |
| 1.6 | Double authentification TOTP, codes de secours, sessions révocables, page Sécurité |
| 1.7 | Rôles, permissions, contrôle d'accès vérifié sur toutes les routes |
| 1.8 | Coquilles client et administrateur selon le rôle, tableau de bord sans donnée inventée |

## Critère d'acceptation de la phase

Parcours d'inscription à connexion fonctionnel et tests de sécurité de base passés : démontrés dans le navigateur sur la stack `safetradev2`, et par 50 tests backend et 28 tests front-end. Client refusé sur `/admin`, administrateur sans 2FA dirigé vers son activation, administrateur avec 2FA admis.

## Écart assumé

Les sections Trading, Historique et Abonnement sont des états « bientôt disponible » honnêtes, construits aux phases 2 à 4. L'espace administrateur ne contient que la vue d'ensemble ; ses modules arrivent en phase 5. La page de démonstration des composants de l'étape 1.2 a été retirée : elle n'avait pas à rester publique.

## En attente du propriétaire

- Compte développeur Deriv et compte démo (bloque l'étape 2.1 sur compte réel de démo ; voir `README.md` de ce dossier).
- Fournisseur d'e-mails ([q15](q15-fournisseur-email.md)), pays de lancement ([q02](q02-pays-vises.md)), budget IA ([q08](q08-ia.md)), hébergement ([q12](q12-hebergement.md)).
- Codes officiels de la charte, si elle existe ([q13](q13-identite-visuelle.md)), et images de la page publique.

## Dette connue

- En développement, l'adresse IP des visiteurs n'est pas connue : topologie de production à mettre en place à l'étape 7.1 ([q16](q16-adresse-ip-client.md)).
- Avertissement de dépréciation de Starlette sur `httpx` dans les tests, sans effet.
