## 12. Paiements

| Moyen | Fournisseur | Usage |
| --- | --- | --- |
| Mobile money | Chariow (API) | Clients disposant de mobile money |
| Cryptomonnaies | NOWPayments (API) | Clients payant en crypto |

Le développeur suit la documentation officielle de chaque fournisseur pour les points d'API, les statuts et la signature des notifications.

**Flux commun**

1. Le client choisit une formule et un moyen de paiement.
2. Le backend crée une commande en statut « en attente » et demande un paiement au fournisseur.
3. Le client est redirigé vers la page de paiement du fournisseur.
4. Le fournisseur notifie le backend par webhook.
5. Le backend vérifie l'authenticité de la notification (signature), puis confirme le montant, la devise et la commande.
6. Si tout est conforme, l'abonnement est activé ou prolongé.

**Exigences**

- L'activation ne dépend jamais du retour du navigateur du client, uniquement du webhook vérifié (avec vérification directe auprès de l'API du fournisseur en cas de doute).
- Idempotence : un même webhook reçu plusieurs fois ne prolonge l'abonnement qu'une fois.
- Statuts gérés : en attente, payé, partiel, échoué, expiré, remboursé.
- Paiements crypto : gestion du sous-paiement, du sur-paiement et de l'expiration de la facture.
- Tâche de rapprochement périodique pour récupérer les paiements dont le webhook a été perdu.
- Table des transactions complète et non modifiable, consultable par l'administrateur.
- Clés des fournisseurs en variables d'environnement ou coffre de secrets, jamais dans le code ni côté front-end.
- Architecture avec une interface commune de paiement pour ajouter d'autres fournisseurs plus tard.

