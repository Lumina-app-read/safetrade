## 9. Interface client

**Pages**

| Page | Contenu |
| --- | --- |
| Inscription et connexion | Création de compte, vérification e-mail, authentification renforcée |
| Tableau de bord | Salutation, solde du compte Deriv, résultats du jour, état du bot, jours d'essai ou abonnement restants |
| Connexion Deriv | Saisie ou autorisation du token, choix du compte démo ou réel |
| Page de trading | Choix de l'actif, graphique en direct, panneau de paramètres, bouton de démarrage, positions ouvertes, journal des décisions |
| Historique | Trades passés, résultats par jour et par actif, export |
| Abonnement | Formule en cours, renouvellement, choix du moyen de paiement, factures |
| Affiliation | Demande, code ou lien, filleuls, gains (selon version) |
| Profil et sécurité | Informations, mot de passe, double authentification, sessions actives, token connecté |

**Page de trading**

- Un indicateur permanent et très visible du mode actif (démo ou réel).
- Le bouton de démarrage n'est actif que si abonnement valide, connexion Deriv saine, marché ouvert et paramètres complets.
- Chaque action (démarrer, pauser, arrêter, clôturer) affiche un état d'attente jusqu'à la confirmation du backend, puis le résultat réel. Le front-end ne simule jamais un succès.
- Les paramètres de la section 7 sont modifiables avec validation côté serveur et message clair en cas de refus.
- Mise à jour en direct des prix, positions et profits par WebSocket, avec indicateur de connexion.

**Exigences d'usage**

- Responsive : utilisable sur téléphone, car beaucoup de traders opèrent depuis un mobile.
- Avertissement de risque visible sur la page de trading et à l'activation du compte réel.
- Notifications (dans l'application, puis e-mail ou push) pour objectif atteint, limite atteinte, erreur, abonnement bientôt expiré.

