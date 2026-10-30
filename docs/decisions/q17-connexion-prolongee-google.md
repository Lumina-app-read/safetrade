# Q17. Connexion prolongée, mot de passe oublié, Google

- **Statut :** décidé par le propriétaire ; Google à brancher plus tard
- **Date :** 31 octobre 2026

## Décisions

- **Se souvenir de moi** (facultatif) : session de 30 jours, fermée après 7 jours d'inactivité. Sans cette case, les durées de la section 14 s'appliquent : 12 heures au maximum, 30 minutes d'inactivité. C'est un écart volontaire à « sessions courtes », choisi par l'utilisateur et limité à ce choix.
- **Mot de passe oublié** : lien de 60 minutes à usage unique, un seul lien valide à la fois, 3 envois par heure au maximum. La réponse ne révèle jamais si l'adresse existe. Le changement ferme toutes les sessions et prévient le titulaire par e-mail. La double authentification reste exigée à la connexion suivante.
- **Reconnaissance du risque à l'inscription** : case obligatoire, vérifiée par le backend et datée (`users.risk_accepted_at`).

## Conséquence à appliquer plus tard

Avant l'ouverture du compte réel (phase 8), une session prolongée ne doit pas suffire pour les actions sensibles : activation du compte réel, démarrage du bot en réel, modification des limites. Exiger alors une nouvelle confirmation (mot de passe ou double authentification).

## Connexion avec Google

Le bouton est présent sur la connexion et l'inscription, désactivé et marqué « Bientôt » : aucune connexion n'est simulée.

À prévoir quand le site évoluera, côté propriétaire : un projet Google Cloud, un client OAuth et un domaine de production vérifié. Côté développement : flux OAuth 2.0 avec PKCE, rattachement à un compte existant uniquement si l'e-mail Google est vérifié, double authentification SafeTrade conservée.
