# Accès à l'administration et abonnements accordés à la main

- **Statut :** livré le 4 novembre 2026, à la demande du propriétaire
- **Code :** `backend/app/auth/admin_access.py`, `backend/app/authz.py`, `backend/app/billing/service.py` (`grant`, `revoke`), `backend/app/admin/router.py` ; écran `frontend/src/components/shell/admin-entry.tsx` et `components/account/admin-users.tsx`
- **Tests :** `backend/tests/test_admin_access.py`

## Parcours

1. Tout le monde se connecte par la page habituelle et arrive sur **l'espace client**, administrateurs compris. Avant, un administrateur arrivait directement dans l'administration.
2. Un bouton « Administration » n'apparaît qu'aux administrateurs : dans la barre sur ordinateur et tablette, en tête du tableau de bord sur téléphone, et dans le menu du compte. Il n'ouvre rien par lui-même : le serveur décide.
3. Il mène à la **connexion de l'administration**. Le serveur vérifie, dans l'ordre :
   - une session client valide ;
   - un rôle administrateur (super administrateur, support ou finance) ;
   - la double authentification activée ;
   - le mot de passe, saisi à nouveau ;
   - un code de l'application d'authentification jamais utilisé. Les codes de secours sont refusés ici : un code noté sur papier se vole plus facilement qu'un téléphone.
4. La réponse ne dit jamais lequel des deux facteurs était faux.

## Freins supplémentaires

| Frein | Règle |
| --- | --- |
| Échecs | Au troisième échec, la session entière est fermée et l'administration reste bloquée 15 minutes, même après une nouvelle connexion |
| Durée | 15 minutes sans activité, une heure au plus ; l'heure de fin est affichée dans la barre |
| Liaison | Accès lié à la session, à l'adresse IP et au navigateur ; un changement le ferme pour de bon |
| Sortie | « Quitter l'administration » la ferme sans déconnecter l'espace client |
| Alerte | E-mail au titulaire à chaque entrée et à chaque blocage |
| Journal | Chaque entrée, échec, blocage et sortie est inscrit au journal d'audit non modifiable |

Réglages : `admin_idle_minutes`, `admin_absolute_minutes`, `admin_max_failures` dans `app/config.py`.

## Abonnements accordés à la main

Module « Utilisateurs » de l'administration. Il sert notamment à ouvrir l'accès d'un compte en attendant un paiement.

- **Permission `subscriptions.write`**, réservée au super administrateur. Support et finance voient l'historique, sans pouvoir rien changer.
- **Motif obligatoire** (5 à 300 caractères), inscrit au journal d'audit avec la formule et la durée.
- **Formules payantes actives seulement** ; jamais l'essai. Durée de la formule par défaut, 1 à 366 jours.
- **L'accès s'ajoute à la suite** de l'accès en cours, comme un paiement.
- **Aucune commande et aucune commission d'affiliation :** rien n'a été encaissé.
- **Personne ne s'accorde un accès à soi-même.**
- **Retrait :** seulement pour un accès accordé à la main, avec motif. La ligne reste dans l'historique, marquée « Retiré », et ne compte plus. Un accès payé ne se retire pas ici : il se rembourse, dans un futur module. Quand plusieurs périodes s'enchaînent, la plus récente se retire en premier.

## Vérifications

- 17 tests dédiés, et toute la suite du backend passe, à l'exception des 3 tests de la recherche de stratégies en pause, qui ne font pas partie de ce commit.
- Parcours essayé dans le navigateur sur la stack locale avec le compte de test `aff-admin@example.com` : arrivée sur l'espace client, refus d'un mauvais mot de passe, entrée, accès accordé puis retiré à un compte de test.
- Aucun débordement mesuré de 320 à 768 px sur le tableau de bord, la connexion de l'administration et le module « Utilisateurs », dans un cadre de largeur fixe. Le thème clair et l'anglais ont été regardés.
