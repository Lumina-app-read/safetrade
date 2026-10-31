# Affiliation (section 13, phase 9)

Module avancé avant la phase 9 à la demande du propriétaire (31 octobre 2026). Barème de [q07](q07-affiliation.md), valeurs fictives à remplacer avant la production.

## Parcours

1. Le client demande à devenir affilié (`POST /affiliate/apply`) : texte, coordonnées de versement, engagement de ne promettre aucun gain et de ne pas se parrainer.
2. L'administrateur approuve ou refuse. L'approbation crée un code de 8 caractères, sans 0, O, 1 ni I, conservé à vie, et passe le compte au rôle `affiliate`.
3. Le lien est `{public_app_url}/register?ref=CODE`, sans langue : le site choisit celle du filleul. Le code peut aussi être saisi à la main.
4. Le filleul est rattaché **une seule fois, à la création de son compte** (`referrals.referred_user_id` unique). Un compte existant n'est jamais rattaché. Un code inconnu est refusé avant de chercher l'adresse : la réponse ne révèle pas si elle existe.
5. La commission naît dans la transaction de `billing.service.settle`, jamais ailleurs. Elle n'existe donc qu'après un paiement validé auprès du fournisseur. Elle reste `held` pendant le délai de rétractation.
6. L'administrateur enregistre le versement : le serveur prend tout le disponible, le montant ne vient jamais de la requête.

## Règles de calcul

- Base : `payment_orders.amount`, le prix de référence en USD, jamais le montant converti chez Chariow.
- Taux figé sur chaque commission : changer le barème ne touche pas le passé.
- « Premier paiement » : un seul par filleul. « Récurrent » : chaque paiement, si le premier a ouvert une commission.
- Fenêtre d'attribution : délai entre l'inscription et le **premier** paiement. Interprétation retenue, le cahier ne tranche pas entre ce délai et la durée de vie du lien.
- « Disponible » n'est pas stocké : c'est `held`, sans réserve, une fois `available_at` passé. Aucune tâche planifiée n'est nécessaire.
- Filleul verrouillé pendant le crédit : deux paiements simultanés ne créent pas deux commissions.

## Auto-parrainage

| Signal | Effet |
| --- | --- |
| Même identité : adresse identique après retrait du `+tag` et des points Gmail | Parrainage bloqué |
| Même appareil : cookie `st_device` vu sur une session de l'affilié, à l'inscription ou au paiement | Bloqué, ou commission annulée |
| Même moyen de paiement : empreinte du téléphone du payeur égale à celle d'une commande de l'affilié ou de son numéro de versement | Commission annulée, parrainage bloqué |
| Même adresse réseau publique | Réserve : l'administrateur valide ou annule. Un réseau partagé ne prouve rien |

- Un parrainage bloqué n'apparaît pas à l'affilié, et aucun motif ne lui est montré : ne pas décrire les contrôles.
- `st_device` est un cookie aléatoire HttpOnly de 400 jours, posé à l'inscription et après l'ouverture d'une session ; seule son empreinte est stockée. Il devra figurer dans la politique de confidentialité.
- Les téléphones ne sont pas conservés : empreinte HMAC-SHA256 (`payer_hash`, `payout_hash`).
- Limite : Chariow ne donne pas d'identifiant de carte ou de portefeuille. Le contrôle du moyen de paiement repose sur le numéro saisi à la commande. Un numéro de versement écrit autrement (`097...` contre `24397...`) n'est pas reconnu, et une adresse crypto n'est pas comparée.

## Droits et traces

- `affiliates.read` : super administrateur et finance. `affiliates.write` : super administrateur. `payouts.write` : super administrateur et finance. Barème : `settings.write`. Le support n'y a pas accès.
- Journal d'audit : `affiliate.apply`, `approve`, `refuse`, `suspend`, `attribution`, `commission`, `commission_release`, `commission_cancel`, `payout`, `program`.
- `affiliate_payouts` en ajout seul (déclencheurs PostgreSQL).
- Le filleul apparaît masqué à l'affilié : une initiale, jamais son adresse.

## Limites connues

- **SafeTrade n'envoie aucun fonds** : l'administrateur paie hors du site, puis enregistre le versement.
- Aucun remboursement automatique n'existe encore. Pendant le délai de rétractation, un remboursement exige d'annuler la commission à la main. Le futur module de remboursement devra l'annuler lui-même. Après un versement, il n'existe pas de reprise.
- Pas de modification des coordonnées de versement après la demande.
- Aucune vente réelle n'a eu lieu : le parcours est prouvé par les tests et sur la base locale avec des paiements simulés, pas sur Chariow.
- Commission calculée sur le prix affiché : sur 5 USD à 20 %, 1 USD, alors que le net après 15 % de frais Chariow est d'environ 4,25 USD. À considérer en fixant le barème définitif.
