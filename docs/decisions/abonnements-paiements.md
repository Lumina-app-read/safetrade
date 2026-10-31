# Abonnements et paiement Chariow (phase 4)

## Fonctionnement

- Essai de 3 jours à la confirmation de l'e-mail, un seul par compte (index unique). Compte déjà vérifié : essai accordé par la migration 0008.
- Formules dans la table `plans` (prix fictifs de q05) : modifiables sans changer le code.
- Accès calculé par le backend (`app/billing/service.py`) : essai, actif, expiré, suspendu ou aucun. Démarrage du bot refusé sans accès (`billing.access_required`).
- À l'expiration, le moteur n'ouvre plus de position et laisse les positions se clôturer sous leur stop loss, puis s'arrête (q06).
- Paiement : commande en base, vente Chariow, redirection. **L'accès n'est activé que par une notification signée ou le rapprochement, tous deux confirmés par `GET /sales/{id}`**, jamais par le retour du navigateur.
- Double crédit impossible : commande verrouillée, `subscriptions.order_id` unique, `x-pulse-delivery-id` unique.
- `payment_events` en ajout seul. Interface `PaymentGateway` prête pour NOWPayments.
- Toutes les 5 minutes, le moteur rapproche les commandes en attente et envoie les rappels 24 h avant l'échéance.

## Chariow : points tirés de la documentation

- **Aucun mode de test : toute vente est réelle.** Aucune vente n'a été créée pendant le développement.
- Clé `sk_...` avec les droits `checkout.write` et `sales.read`.
- Chaque formule exige un **produit publié de type licence**. Les autres types renvoient `already_purchased` à un client ayant déjà un accès, ce qui bloquerait les renouvellements.
- Le produit doit être en USD, au prix de la table `plans` : un montant ou une devise différents laissent la commande en `partial`, sans accès.
- Téléphone et nom de famille obligatoires : le formulaire de paiement les demande.
- Pulse à créer pour `successful.sale`, `failed.sale` et `abandoned.sale`, sur `https://<domaine>/api/billing/webhooks/chariow`. HTTPS obligatoire.
- Secret de signature `whsec_...`, propre à chaque Pulse. Cinq échecs désactivent le Pulse.

## État de la connexion (31 octobre 2026)

Clé détectée et authentifiée sur la vraie API, en lecture seule. `store.read`, `products.read`, `sales.read`, `webhooks.read` et `licenses.read` répondent 200 ; `checkout.write` est confirmé par un `POST /checkout` à corps vide, refusé en 422, qui ne crée aucune vente.

Boutique active, 0 produit, 0 Pulse. Le parcours de paiement reste donc testé contre un Chariow simulé uniquement : **aucune vente n'a été créée.**

## Produits

- Type `license` obligatoire : la documentation réserve le rachat répété à ce type, et refuse Service et Coaching au paiement par API.
- Création manuelle : l'API n'a aucun droit d'écriture sur les produits.
- Réglage `requires_activation` désactivé, le mode prévu pour un SaaS. SafeTrade ne lit pas les licences : il calcule seul la durée d'accès.

## Restes

- NOWPayments.
- Signaux anti-abus de l'essai (appareil, adresse, compte Deriv).
- Remboursements : statut prévu, aucun traitement encore.
- Prix et durée de l'essai modifiables dans l'administration (5.3), journal des transactions pour l'administrateur (5.4).
