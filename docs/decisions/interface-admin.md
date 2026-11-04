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
| Réglages | Lien partenaire Deriv, bandeau d'annonce, avertissement de risque, textes légaux versionnés, e-mails types, clés des services externes | `settings.write` |
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

## Réglages

- **Messages :** bandeau d'annonce (information ou alerte, français et anglais) en haut de l'accueil et de l'espace client ; avertissement de risque qui remplace celui des traductions dans le pied de page et la page de trading. Vides, les textes par défaut reviennent.
- **Textes légaux :** mentions légales, conditions d'utilisation, confidentialité et avertissement sur les risques, en français et en anglais, publiés sous `/{langue}/legal/{legal-notice|terms|privacy|risk}`. Chaque publication est une nouvelle version ; un déclencheur PostgreSQL refuse toute modification ou suppression d'une version publiée. Sans version dans la langue demandée, l'autre langue s'affiche. Les textes doivent être relus par un juriste avant la mise en production.
- **E-mails types :** objet, titre, paragraphes, bouton et note de fin modifiables par langue, avec aperçu et retour au texte d'origine. Une variable n'est acceptée que dans la note et seulement si le texte d'origine l'emploie. Textes relus au plus une fois par minute par l'API et par le moteur (`app/email_templates.py`) ; base illisible : le texte d'origine part.
- **Clés des services :** clé d'API et secret des notifications Chariow, identifiants des trois produits. Chiffrées en AES-256-GCM avec la clé du serveur, liées à leur nom, jamais renvoyées ni journalisées ; une clé enregistrée ici passe avant la variable d'environnement, la retirer fait revenir la variable. Prises en compte sans redémarrage par l'API (fournisseurs reconstruits quand l'empreinte change) et par le moteur (relues à chaque tour de rapprochement). L'application Deriv, le mot de passe d'envoi des e-mails et la clé de chiffrement restent dans l'environnement : ils sont lus au démarrage ; leur état seul est affiché.

## Hors périmètre, à venir

- Promotions et remboursements : ils dépendent du fournisseur de paiement.
