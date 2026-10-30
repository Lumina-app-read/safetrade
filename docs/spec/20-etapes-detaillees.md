## 20. Étapes détaillées, phase par phase

Chaque ligne est une session Claude Code. L'ordre est obligatoire : une étape ne commence que lorsque la précédente est validée. Les numéros de phase suivent la section 17.

**Phase 0 : cadrage (sans code applicatif)**

| ID | Étape | Livrables | Preuve de fin |
| --- | --- | --- | --- |
| 0.1 | Découper le cahier des charges | Export Markdown de ce document, un fichier par section dans docs/spec/ | 21 fichiers présents, contenu concaténé identique au document |
| 0.2 | Trancher les questions de la section 18 | Réponses écrites dans docs/decisions/ ; les questions 1, 3, 5, 6 bloquent les phases 2, 3 et 4 | Chaque question a une réponse datée |
| 0.3 | Rédiger CLAUDE.md | Fichier complet selon la section 19 | Relu et validé par toi |
| 0.4 | Maquettes des écrans clés | Tableau de bord, page de trading, abonnement, administration, en clair et en sombre | Validées par toi avant la phase 1 |

**Phase 1 : socle**

| ID | Étape | Livrables | Preuve de fin |
| --- | --- | --- | --- |
| 1.1 | Initialiser le dépôt | Dossiers backend, frontend, infra ; Docker Compose avec PostgreSQL et Redis ; route /health ; lint, types et tests vides en intégration continue | docker compose up démarre tout ; /health répond 200 ; la CI est verte |
| 1.2 | Thèmes et composants de base | Variables de thème clair et sombre (section 15), Plus Jakarta Sans, boutons, cartes, champs, tableaux, badges, barre supérieure | Page de démonstration des composants correcte dans les deux thèmes |
| 1.3 | Traduction français et anglais | Mécanisme de traduction, sélecteur de langue, contrôle automatique des clés manquantes | La CI échoue si une clé manque dans une langue ; bascule de langue visible |
| 1.4 | Base de données | Migrations (Alembic) pour utilisateurs, sessions, journal d'audit | Migration appliquée et annulée sans erreur |
| 1.5 | Inscription et connexion | E-mail vérifié, hachage Argon2id, sessions courtes, limitation de débit | Tests : inscription, vérification, connexion, blocage après tentatives répétées |
| 1.6 | Double authentification | TOTP, liste des sessions, déconnexion à distance | Tests : activation, connexion avec code, révocation d'une session |
| 1.7 | Rôles et journal d'audit | Rôles client, affilié, administrateur ; contrôle d'accès sur chaque route ; audit des actions sensibles | Test : un client reçoit un refus sur toute route administrateur |
| 1.8 | Coquilles d'interface | Tableau de bord client avec salutation, interface administrateur vide protégée | Les deux espaces s'affichent selon le rôle, en clair et en sombre, sur téléphone |

**Phase 2 : connexion Deriv (décision de la question 1 requise)**

| ID | Étape | Livrables | Preuve de fin |
| --- | --- | --- | --- |
| 2.1 | Lire la documentation officielle Deriv | Note docs/decisions/deriv.md : méthode d'authentification, scopes, points d'API, limites de débit | Note relue par toi ; aucun code |
| 2.2 | Interface broker et client Deriv | Interface abstraite de broker ; client WebSocket (connexion, autorisation, reconnexion, limite de débit) | Tests sur un faux serveur : coupure puis reprise automatique |
| 2.3 | Stockage et validation du token | Chiffrement AES-256-GCM, route de connexion, vérification auprès de Deriv, liste des comptes, choix du compte (démo par défaut) | Le token n'apparaît ni dans les réponses ni dans les journaux (test automatisé) |
| 2.4 | Écran de connexion Deriv | Page de saisie ou d'autorisation, choix démo ou réel, état de la connexion | Parcours complet sur un compte démo |
| 2.5 | Données de marché | Abonnement aux ticks, bougies historiques, diffusion par Redis puis WebSocket, détection marché ouvert ou fermé | Prix de 5 actifs reçus en direct côté backend |
| 2.6 | Graphique en direct | Page de trading en lecture seule avec graphique et choix de l'actif | 24 heures sans coupure non récupérée ; actif fermé signalé indisponible |

**Phase 3 : moteur et risque en démo uniquement (décisions des questions 1, 3 et 4 requises)**

| ID | Étape | Livrables | Preuve de fin |
| --- | --- | --- | --- |
| 3.1 | Modèle de données du trading | Tables de sessions de bot, positions, ordres, décisions, paramètres de risque | Migrations appliquées ; contraintes d'unicité d'un bot par compte |
| 3.2 | Module de risque | Fonctions pures validant chaque ordre selon la section 7, sans accès réseau | 100 % de couverture ; un test par limite et par plafond |
| 3.3 | Paramètres de risque | API de paramétrage avec validation, plafonds administrateur, écran de paramètres | Une valeur hors plage est refusée par le backend même si le front-end l'envoie |
| 3.4 | Exécution des ordres | Ouverture et clôture via l'interface broker, verrou anti-doublon, réconciliation avec Deriv | Après coupure simulée, aucune position fantôme ni doublon |
| 3.5 | Machine d'états du bot | États de la section 6, démarrage, pause, arrêt, arrêt d'urgence, reprise sûre après redémarrage | Test de chaque transition, y compris redémarrage serveur pendant une position |
| 3.6 | Stratégie version 1 | Indicateurs, détection du régime, génération de signaux déterministes, banc d'essai sur bougies historiques | Rapport de backtest généré pour 3 actifs |
| 3.7 | Règle de clôture | Clôture dès gain net strictement positif après spread, stop loss obligatoire, clôture manuelle par le client | Tests : gain net atteint, stop loss atteint, clôture manuelle |
| 3.8 | Page de trading complète | Paramètres, démarrage, positions, journal des décisions, mises à jour en direct, indicateur démo ou réel | Session de bout en bout sur compte démo |
| 3.9 | Notifications et endurance | Notifications dans l'application ; exécution continue en démo | 72 heures sans incident bloquant |

**Phase 4 : abonnements et paiements (décisions des questions 5 et 6 requises)**

| ID | Étape | Livrables | Preuve de fin |
| --- | --- | --- | --- |
| 4.1 | Formules et essai | Tables de formules, prix et abonnements ; essai de 3 jours ; statut calculé côté serveur ; blocage du démarrage du bot si accès expiré | Tests : essai expiré à la minute près, abonnement actif, suspendu |
| 4.2 | Chariow | Lecture de la documentation officielle, création de commande, redirection, webhook avec signature vérifiée, idempotence | Paiement test crédité une seule fois, même avec webhook reçu deux fois |
| 4.3 | NOWPayments | Même exigence ; gestion du sous-paiement, du sur-paiement et de l'expiration | Tests des cas : payé, partiel, expiré, en double |
| 4.4 | Écran d'abonnement | Choix de formule et de moyen de paiement, historique, reçus, rappels avant expiration | Parcours complet en mode test des deux fournisseurs |
| 4.5 | Rapprochement | Tâche périodique récupérant les paiements dont le webhook a été perdu | Webhook supprimé volontairement : le paiement est tout de même crédité une seule fois |

**Phase 5 : interface administrateur**

| ID | Étape | Livrables | Preuve de fin |
| --- | --- | --- | --- |
| 5.1 | Tableau de bord administrateur | Indicateurs de la section 10 | Chiffres identiques à ceux de la base de données |
| 5.2 | Gestion des utilisateurs | Recherche, fiche, suspension, prolongation | Chaque action écrite dans le journal d'audit |
| 5.3 | Formules et prix | Création et modification versionnées | Un changement de prix n'affecte pas un abonnement déjà payé |
| 5.4 | Paiements | Liste, statuts, rapprochement manuel | Une transaction retrouvée par référence |
| 5.5 | Plafonds de risque et arrêt global | Plafonds du tableau de la section 7, interrupteur d'arrêt d'urgence global | Interrupteur activé : tous les bots s'arrêtent en moins de 10 secondes (test) |
| 5.6 | Réglages et textes | Textes légaux, avertissements, e-mails types, en français et en anglais | Modification visible sans redéploiement |
| 5.7 | Équipe et rôles | Comptes et droits administrateur, consultation du journal d'audit | Un rôle support ne voit jamais un token Deriv |

**Phase 6 : module IA**

| ID | Étape | Livrables | Preuve de fin |
| --- | --- | --- | --- |
| 6.1 | Données et indicateurs | Collecte historique, calcul des variables d'entrée | Jeu de données versionné et reproductible |
| 6.2 | Mode observation | L'IA note chaque signal sans influencer les décisions | Notes enregistrées à côté de chaque décision pendant 7 jours |
| 6.3 | Validation | Backtest et test en avant documentés | Rapport comparant le moteur seul et le moteur avec IA |
| 6.4 | Mode filtrage en démo | L'IA peut refuser un signal, jamais dépasser une limite de risque | Test : un avis de l'IA ne contourne aucune règle du module de risque |
| 6.5 | Explications | Explication de chaque décision en français et en anglais | Aucune explication dans la mauvaise langue |
| 6.6 | Résumé de session | Résumé de fin de session affiché au client | Résumé cohérent avec les chiffres réels de la session |

**Phase 7 : bêta fermée en démo**

| ID | Étape | Livrables | Preuve de fin |
| --- | --- | --- | --- |
| 7.1 | Préproduction | Déploiement automatisé, HTTPS, sauvegardes | Restauration d'une sauvegarde réussie |
| 7.2 | Supervision | Journaux centralisés, métriques, alertes de la section 16 | Alerte reçue lors d'une panne simulée |
| 7.3 | Bêta | 30 à 50 testeurs, collecte et correction des retours | Retours triés, correctifs livrés |
| 7.4 | Endurance | Fonctionnement continu en démo | 14 jours sans incident bloquant |

**Phase 8 : ouverture du compte réel (avis juridique requis)**

| ID | Étape | Livrables | Preuve de fin |
| --- | --- | --- | --- |
| 8.1 | Garde-fous du réel | Double authentification obligatoire, avertissement accepté et tracé, plafonds réels de la section 7 | Test : impossible d'activer le réel sans ces conditions |
| 8.2 | Revue de sécurité | Liste de contrôle de la section 14 passée en revue, test d'intrusion par un tiers | Aucune faille critique ou élevée ouverte |
| 8.3 | Pages légales | Conditions d'utilisation, confidentialité, avertissement de risque, en deux langues | Publiées et validées juridiquement |
| 8.4 | Ouverture progressive | Interrupteur du réel activé pour un petit groupe, puis élargi | Aucun incident pendant 14 jours avant élargissement |

**Phase 9 : affiliation**

| ID | Étape | Livrables | Preuve de fin |
| --- | --- | --- | --- |
| 9.1 | Demande d'affiliation | Formulaire, approbation ou refus par l'administrateur, code et lien uniques | Parcours demande, approbation, obtention du lien |
| 9.2 | Attribution | Suivi du parrainage à l'inscription, fenêtre d'attribution, auto-parrainage bloqué | Un filleul est rattaché une seule fois à un seul affilié |
| 9.3 | Commissions | Calcul après paiement confirmé, barème administrateur, délai de rétractation | Commission créée uniquement après un paiement validé |
| 9.4 | Interfaces affilié et administrateur | Suivi des filleuls et des gains, validation des versements | Parcours complet de bout en bout |

**Décisions qui bloquent des étapes**

| Décision (section 18) | Bloque |
| --- | --- |
| Question 1 : produit Deriv | 2.1 et tout ce qui suit |
| Question 3 : stop loss obligatoire | 3.2 et 3.7 |
| Question 4 : valeurs par défaut et plafonds | 3.2, 3.3, 5.5, 8.1 |
| Questions 5 et 6 : prix et sort des positions à l'expiration | 4.1 |
| Question 2 : pays visés et avis juridique | 8.3 et 8.4 |
| Question 7 : commissions d'affiliation | 9.3 |
| Question 8 : choix et budget de l'IA | 6.1 |

