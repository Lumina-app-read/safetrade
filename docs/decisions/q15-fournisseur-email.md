# Q15. Fournisseur d'e-mails transactionnels

- **Statut :** à confirmer (choix et dépense du propriétaire)
- **Date :** 30 octobre 2026

## Besoin

L'inscription envoie un lien de vérification d'e-mail (étape 1.5). Suivront les rappels d'expiration d'abonnement, les alertes de sécurité, les reçus et les notifications (sections 9, 11 et 14), en français et en anglais.

## Situation provisoire

- Une interface `Mailer` isole l'envoi (`backend/app/auth/mailer.py`) : changer de fournisseur ne touche pas la logique d'inscription.
- **Développement** : `LogMailer` écrit le message, lien compris, dans le journal du conteneur `safetradev2-backend` (`docker logs safetradev2-backend`).
- **Hors développement** : l'API refuse de démarrer sans fournisseur réel. Aucun envoi n'est jamais simulé en préproduction ou en production.

## À décider par le propriétaire

- Le fournisseur (par exemple un service SMTP ou une API d'e-mails transactionnels), avec un abonnement payant éventuel.
- Le domaine d'envoi, avec les enregistrements SPF, DKIM et DMARC à configurer chez l'hébergeur DNS.

Bloque l'étape 7.1 (préproduction), pas le développement.
