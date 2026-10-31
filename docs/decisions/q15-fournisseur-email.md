# Q15. Fournisseur d'e-mails transactionnels

- **Statut :** décidé
- **Date :** 31 octobre 2026

## Décision

Brevo, par son relais SMTP (décision du propriétaire). Paramètres dans `infra/.env` : `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_FROM_NAME`.

## Mise en œuvre

- `backend/app/auth/mailer.py` : `SmtpMailer`, SMTP chiffré obligatoire (STARTTLS ou port 465), messages texte et HTML, français et anglais.
- `QueuedMailer` : une requête n'attend jamais le fournisseur, et le temps de réponse ne révèle pas si une adresse a un compte. Trois nouvelles tentatives (5, 30, 120 s). Le journal indique le modèle et la cause, jamais l'adresse ni le lien.
- Sans configuration : `LogMailer` en développement ; hors développement, l'API refuse de démarrer.
- Plafond de 5 envois par heure et par adresse, liens et avertissements confondus.
- `POST /auth/verify-email/resend` : nouveau lien de confirmation, réponse identique dans tous les cas. Une nouvelle inscription sur un compte non confirmé envoie aussi un nouveau lien.

## Limites

- La file est en mémoire : un message en attente est perdu si l'API s'arrête. Le client peut redemander le lien.
- Avant la production : authentifier le domaine d'envoi chez Brevo (SPF, DKIM, DMARC). Sans cela, les messages risquent les courriers indésirables.
