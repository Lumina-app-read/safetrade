# Interface d'administration complète (section 10)

- **Statut :** livré le 4 novembre 2026, à la demande du propriétaire : tous les modules actifs, plus aucun « Bientôt »
- **Accès :** seconde connexion, voir `acces-admin.md`
- **Code :** `backend/app/admin/` (`router.py`, `accounts.py`, `operations.py`, `common.py`), `backend/app/trading/controls.py` ; écrans `frontend/src/components/account/admin-*.tsx`
- **Tests :** `backend/tests/test_admin_modules.py`, `test_admin_access.py`, et trois tests du moteur dans `test_trading_engine.py`

| Module | Contenu | Permission |
| --- | --- | --- |
| Vue d'ensemble | Clients, nouveaux et actifs sur 7 jours, essais, abonnés, revenus sur 30 jours, bots actifs, positions ouvertes, bots en erreur, alerte d'arrêt d'urgence | `users.read` ; revenus avec `payments.read` |
| Utilisateurs | Recherche et filtres, fiche complète : profil, accès et historique, compte Deriv relié (jamais le token), bots, résultat net, commandes, parrain et affiliation. Actions : suspendre, réactiver, déconnecter tous les appareils, accorder ou retirer un accès | lecture `users.read` ; actions `users.write` ; accès `subscriptions.write` |
| Abonnements | Prix, durée et disponibilité de chaque formule, durée de l'essai, historique des changements | `settings.write` |
| Paiements | Transactions filtrées par statut et recherche, vérification chez le fournisseur à la demande | `payments.read` |
| Affiliation | Inchangé | `affiliates.read` |
| Trading et risque | Arrêt d'urgence global (avec ou sans fermeture des positions), plafonds globaux de mise et de positions, actifs désactivés, supervision et arrêt de chaque bot | `risk.write` |
| Réglages | Lien partenaire Deriv, inchangé | `settings.write` |
| Équipe et rôles | Membres, droits, attribution et retrait d'un rôle | `team.write` |
| Journal d'audit | Auteur, domaine, pages successives, lecture seule | `audit.read` |

Support : lecture des comptes seulement. Finance : paiements, comptes et versements. Super administrateur : tout.

## Règles

- **Motif obligatoire** pour toute action sensible, inscrit au journal d'audit avec l'état avant et après.
- **Contrôles globaux :** ils s'ajoutent au module de risque de chaque client, ils ne peuvent que restreindre. Le moteur les relit à chaque tour (`controls.entry_refusal`) ; le démarrage d'un bot est refusé pendant l'arrêt d'urgence ou sur un actif désactivé. Pendant l'arrêt, les bots s'arrêtent et les positions gardent leur stop loss, sauf si la fermeture est demandée.
- **Formules :** un nouveau prix ne vaut que pour les prochaines commandes (prix figé à la commande). L'essai reste gratuit et toujours proposé. Le prix du produit Chariow doit être changé aussi : sinon la vérification de prix refuse le paiement.
- **Suspension :** sessions fermées, connexion refusée, bot arrêté au tour suivant ; un super administrateur et son propre compte sont protégés.
- **Équipe :** un compte existant à l'e-mail vérifié reçoit un rôle ; jamais son propre rôle ; il reste toujours au moins un super administrateur. Un rôle retiré ferme aussitôt l'administration ouverte.
- **Accès accordé à la main :** le super administrateur peut s'en accorder un à lui-même (décision du propriétaire du 4 novembre 2026), le journal le montre.
- **Paiements :** la vérification relit l'état chez le fournisseur ; aucun statut n'est saisi à la main.

## Hors périmètre, à venir

- Promotions et remboursements : ils dépendent du fournisseur de paiement.
- Textes légaux, messages et e-mails types, clés des services externes modifiables dans l'administration.
