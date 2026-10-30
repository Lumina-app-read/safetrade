## 11. Modèle SaaS : essai et abonnements

**Règles**

- Dès l'inscription (e-mail vérifié), le client reçoit 3 jours d'essai gratuit avec accès complet.
- Un seul essai par personne : contrôle par e-mail vérifié et signaux anti-abus (appareil, adresse, compte Deriv déjà utilisé).
- Après l'essai, un abonnement est nécessaire. Trois durées : 1 semaine, 1 mois, 1 an. Prix et durée d'essai modifiables depuis l'interface administrateur.
- Le renouvellement est manuel au départ (paiement mobile money et crypto se prêtent mal au prélèvement automatique) ; l'extension à un renouvellement automatique reste possible.

**Statuts d'un compte**

| Statut | Condition | Accès au bot |
| --- | --- | --- |
| Essai | Moins de 3 jours depuis l'inscription | Oui |
| Actif | Abonnement payé et non expiré | Oui |
| Expiré | Essai ou abonnement terminé | Non : lancement bloqué, consultation de l'historique conservée |
| Suspendu | Décision administrateur | Non |

**À l'expiration**

- Le backend empêche toute nouvelle position et envoie des rappels avant l'échéance (par exemple 24 heures avant).
- Le sort des positions déjà ouvertes (laisser le moteur les clôturer au bénéfice ou au stop loss, ou les clôturer immédiatement) doit être décidé ; la recommandation est de les laisser se terminer sous la protection du stop loss, puis d'arrêter le bot.
- L'expiration est calculée côté serveur, jamais côté client.

**Facturation**

Chaque paiement valide crée ou prolonge l'abonnement de façon atomique et génère une facture ou un reçu.

