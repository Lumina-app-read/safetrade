# SafeTrade - Cahier des charges

Oct 29, 2026 · @Clovis

## 1. Présentation du projet

SafeTrade est un SaaS de trading semi-automatique qui se connecte au compte Deriv de l'utilisateur, analyse le marché en continu, ouvre des positions et les clôture dès qu'un bénéfice net est réalisé, dans le cadre de limites de risque fixées par l'utilisateur.

**Objectifs**

- Permettre à un trader de déléguer l'analyse et l'exécution à un moteur, tout en gardant la main à tout moment.
- Imposer une discipline de money management et de gestion du risque que l'utilisateur ne peut pas contourner dans le feu de l'action.
- Générer des revenus récurrents par abonnement (essai de 3 jours, puis semaine, mois ou année) et par affiliation.

**Ce que SafeTrade est**

- Un outil d'aide à l'exécution connecté par API à un broker tiers (Deriv).
- Une application web (puis mobile) avec une interface client et une interface administrateur.

**Ce que SafeTrade n'est pas**

- Il ne détient, ne reçoit et ne gère jamais les fonds des utilisateurs : l'argent reste chez Deriv.
- Il ne promet aucun gain, ni garanti ni estimé. Chaque écran et chaque communication rappelle que le trading comporte un risque de perte en capital.

**Marchés visés**

Indices synthétiques Deriv (priorité), or (uniquement quand le marché est ouvert), Bitcoin et autres actifs exposés par le compte de l'utilisateur après connexion de son token.

## 2. Analyse du besoin

Le besoin est cohérent et réalisable, mais quatre points doivent être tranchés avant le développement car ils changent l'architecture ou le risque du produit.

**Points structurants**

- **Produit Deriv à cibler.** L'API Deriv (WebSocket) permet de trader des contrats (multiplicateurs, options, etc.) avec une mise en dollars, alors que la notion de lots relève plutôt de MT5. Le choix détermine le moteur d'ordres et le paramétrage « lots ». À confirmer avec la documentation officielle à jour.
- **Méthode d'authentification.** Le besoin cite le token personnel (PAT) et OAuth 2.0 selon la documentation Deriv. Le développeur doit valider les flux, les scopes (lecture, trading) et l'enregistrement de l'application sur la documentation en vigueur au moment du développement.
- **Clôture dès le moindre bénéfice.** Couper à 0,2 ou 0,3 dollar de gain produit beaucoup de petits gains. Sans stop loss ni limite de perte, quelques pertes isolées peuvent effacer des dizaines de gains, voire vider le compte. Le cahier des charges impose donc un stop loss obligatoire et des limites de perte (section 7).
- **Efficacité réelle de l'analyse.** Les indices synthétiques sont générés de façon pseudo-aléatoire : un avantage statistique durable est incertain. Le moteur et l'IA doivent être validés en démo avant toute ouverture au réel, et le discours commercial doit rester prudent.

**Risques**

| Domaine | Risque | Mesure |
| --- | --- | --- |
| Trading | Pertes d'utilisateurs, réclamations | Démo par défaut, avertissements, limites de risque non contournables, kill switch |
| Juridique | Réglementation des services financiers et de l'automatisation selon les pays visés ; conditions d'usage de l'API Deriv | Avis juridique avant lancement, conditions d'utilisation, clause de non-garantie |
| Technique | Coupure de connexion pendant une position ouverte | Reconnexion automatique, réconciliation des positions au redémarrage, alertes |
| Sécurité | Vol de tokens API | Chiffrement, scopes minimaux, révocation, journalisation (section 14) |
| Business | Dépendance à une seule API de broker | Couche d'abstraction broker dès le départ |

## 3. Acteurs et rôles

| Acteur | Description | Droits principaux |
| --- | --- | --- |
| Visiteur | Personne non inscrite | Voir la page de présentation, s'inscrire, se connecter |
| Client | Utilisateur inscrit, en essai ou abonné | Connecter son token Deriv, choisir démo ou réel, paramétrer et lancer le bot, intervenir sur ses positions, gérer son abonnement |
| Affilié | Client dont la demande d'affiliation est approuvée | Obtenir un code ou lien, suivre ses filleuls et ses gains |
| Administrateur | Équipe SafeTrade | Gérer utilisateurs, abonnements, prix, affiliations, réglages, journaux, support |

Les rôles administrateur sont eux-mêmes différenciés (super administrateur, support, finance) pour limiter les accès au strict nécessaire.

## 4. Architecture technique

Le backend est l'unique source de vérité : le front-end affiche et envoie des demandes, jamais des décisions. Toute règle (limites, droits d'accès, état du bot, abonnement) est appliquée et vérifiée côté serveur.

**Stack recommandée**

| Couche | Choix | Raison |
| --- | --- | --- |
| Backend API | Python, FastAPI | Choix de l'utilisateur ; asynchrone, WebSocket natif, écosystème data et IA |
| Front-end web | Next.js (React) avec TypeScript | Typage strict, rendu serveur pour la page publique, large vivier de développeurs |
| Style et composants | Tailwind CSS, bibliothèque de composants sobre, icônes Lucide | Interface fine et aérée, cohérente avec la charte |
| Base de données | PostgreSQL | Transactions fiables pour abonnements, paiements, journal des ordres |
| Cache et file de messages | Redis | États temps réel, verrous, limitation de débit, files de tâches |
| Tâches de fond | Worker dédié (ARQ ou Celery) | Moteur de trading, webhooks, expirations d'abonnement |
| Temps réel vers le client | WebSocket (ou Server-Sent Events) | Prix, positions et état du bot en direct |
| Mobile | Application web responsive (PWA) en première version, puis React Native si besoin | Réduit le coût initial |
| Déploiement | Docker, reverse proxy HTTPS, sauvegardes automatiques | Reproductible et sécurisé |

**Composants backend**

1. Service d'authentification et de comptes.
2. Connecteur Deriv : connexion WebSocket par utilisateur, abonnement aux prix, passage et clôture d'ordres, réconciliation.
3. Trading engine : une instance isolée par session de bot active.
4. Module de risque : couche indépendante qui valide ou refuse chaque ordre avant envoi.
5. Module IA d'assistance.
6. Facturation : abonnements, paiements, webhooks.
7. Affiliation.
8. API d'administration et journal d'audit.
9. Passerelle temps réel vers le front-end.

**Principes**

- Le moteur tourne côté serveur, indépendamment du navigateur : fermer l'onglet n'arrête pas le bot, et ne le lance pas non plus sans commande explicite.
- Une couche d'abstraction broker isole Deriv pour permettre d'autres brokers plus tard.
- Chaque action sensible est journalisée avec horodatage, utilisateur et résultat.

## 5. Intégration Deriv

SafeTrade se connecte au compte de l'utilisateur sans jamais toucher à ses fonds. Les modalités exactes ont été vérifiées dans la documentation officielle Deriv et sont résumées en section 21, qui prévaut sur le texte ci-dessous en cas de différence.

**Parcours de connexion**

1. Le client crée un token API (ou autorise l'application via OAuth 2.0) depuis son espace Deriv, avec les scopes minimaux : lecture et trading, sans retrait ni administration.
2. Il colle le token ou valide l'autorisation dans SafeTrade.
3. Le backend vérifie le token auprès de Deriv, récupère la liste des comptes et affiche leur type (démo ou réel) et leur devise.
4. Le client choisit explicitement le compte de travail. Le mode démo est présélectionné.
5. Le backend détecte les actifs disponibles pour ce compte et les propose sur la page de trading.

**Données de marché**

- Flux de prix en temps réel (ticks) et bougies historiques par actif, reçus côté backend, puis relayés au front-end.
- Gestion du marché fermé (or, week-end) : l'actif est signalé indisponible et le bot refuse de démarrer dessus.
- Reconnexion automatique avec reprise des abonnements et contrôle de cohérence des données.

**Ordres et positions**

- Ouverture, suivi et clôture des positions par le backend uniquement.
- Au démarrage ou après une coupure, réconciliation entre les positions connues de SafeTrade et celles réellement ouvertes chez Deriv.
- Respect des limites de débit de l'API Deriv.

**Gestion du token**

Chiffré au repos, jamais renvoyé au front-end après saisie, jamais écrit dans les journaux, révocable en un clic côté SafeTrade (le client peut aussi le révoquer chez Deriv).

## 6. Trading engine

Le moteur répète un cycle : analyser, décider, exécuter, surveiller, clôturer. Chaque ordre passe par le module de risque avant envoi.

**Cycle d'une session**

1. Démarrage : le client choisit l'actif et lance le bot ; le backend vérifie abonnement, connexion Deriv, marché ouvert et paramètres valides.
2. Analyse : indicateurs techniques et détection du régime de marché (tendance, range, volatilité) sur les ticks et bougies.
3. Signal : le moteur produit un signal (achat, vente ou attente) avec un score de confiance, éventuellement filtré par l'IA.
4. Validation par le module de risque : taille de position, nombre de positions ouvertes, limites de session et journalières, spread.
5. Ouverture de la position avec un stop loss obligatoire.
6. Surveillance continue de la position.
7. Clôture automatique dès que le bénéfice net est positif, c'est-à-dire profit moins spread et frais, quel qu'en soit le montant (0,20 dollar comme 2 dollars), avec un seuil minimum net configurable pour éviter les clôtures à gain nul.
8. Retour à l'analyse, jusqu'à arrêt par le client, atteinte d'un objectif ou d'une limite, ou incident.

**États du bot**

| État | Signification |
| --- | --- |
| Arrêté | Aucune activité |
| Démarrage | Vérifications préalables |
| Analyse | En attente de signal |
| Position ouverte | Suivi d'une ou plusieurs positions |
| En pause | Pause décidée par le client ou cooldown après pertes consécutives |
| Objectif atteint | Objectif de session ou journalier atteint, plus de nouvelles positions |
| Limite atteinte | Limite de perte atteinte, plus de nouvelles positions |
| Erreur | Incident de connexion ou de données, alerte envoyée, positions protégées |

**Intervention du client**

À tout moment, le client peut clôturer manuellement une position, mettre le bot en pause, l'arrêter, ou le laisser travailler. Un bouton d'arrêt d'urgence clôture les positions ouvertes et bloque de nouvelles entrées.

**Exigences**

- Chaque décision (signal, refus, ouverture, clôture) est enregistrée avec ses données d'entrée pour audit et amélioration.
- Un bot ne peut jamais tourner deux fois en parallèle pour le même compte.
- Après redémarrage serveur, le moteur reprend dans un état sûr (pas de nouvelle position avant réconciliation).

## 7. Money management et gestion des risques

Le client paramètre, le backend applique. Aucun paramètre ne peut être contourné depuis le front-end ni par l'IA.

**Paramètres client**

| Paramètre | Description |
| --- | --- |
| Taille de position | Mise en dollars par trade (l'API Deriv fonctionne par mises, pas par lots) |
| Capital engagé | Part maximale du solde utilisable par le bot |
| Positions simultanées | Nombre maximal de positions ouvertes |
| Stop loss par trade | Obligatoire, en montant ou en pourcentage |
| Gain net minimal pour clôturer | Seuil net après spread, strictement positif |
| Objectif de session | Profit visé ; le bot s'arrête une fois atteint |
| Limite de perte de session | Perte maximale ; le bot s'arrête une fois atteinte |
| Objectif journalier | Profit visé sur la journée |
| Limite de perte journalière | Perte maximale sur la journée |
| Pertes consécutives | Nombre déclenchant une pause automatique |
| Actifs autorisés | Liste des marchés sur lesquels le bot peut travailler |

**Garde-fous imposés par SafeTrade**

- Valeurs plafonds définies par l'administrateur (par exemple mise maximale en compte réel), que le client ne peut pas dépasser.
- Pas de martingale ni d'augmentation de mise après une perte dans la première version.
- Compte réel : confirmation explicite, avertissement de risque accepté et tracé, paramètres plus restrictifs par défaut qu'en démo.
- Contrôle du solde disponible avant chaque ordre ; refus si la marge est insuffisante.
- Arrêt automatique et alerte en cas de limite atteinte, de données de marché anormales ou de perte de connexion prolongée.

**Rôle de l'IA**

L'IA reçoit ces paramètres comme contraintes. Elle peut proposer de s'abstenir ou de réduire l'exposition, jamais de dépasser une limite.

**Valeurs par défaut et plafonds proposés (à valider avant développement)**

| Paramètre | Défaut démo | Défaut réel | Plage client | Plafond admin |
| --- | --- | --- | --- | --- |
| Mise par trade (USD) | 1 | 1 | 0,35 à 50 | 10 en réel au lancement |
| Capital engagé (% du solde) | 20 | 10 | 1 à 50 | 25 |
| Positions simultanées | 1 | 1 | 1 à 5 | 3 |
| Stop loss par trade (% de la mise) | 50 | 50 | 10 à 100 | Obligatoire, jamais désactivable |
| Gain net minimal pour clôturer (USD) | 0,10 | 0,10 | 0,05 à 5 | Strictement supérieur à 0 |
| Objectif de session (% du solde) | 2 | 1 | 0,5 à 10 | 10 |
| Limite de perte de session (% du solde) | 2 | 1 | 0,5 à 10 | 10 |
| Objectif journalier (% du solde) | 5 | 2 | 0,5 à 20 | 20 |
| Limite de perte journalière (% du solde) | 5 | 2 | 0,5 à 10 | 10 |
| Pertes consécutives avant pause | 3 | 3 | 2 à 10 | 10 |
| Durée de pause après pertes (min) | 15 | 30 | 5 à 240 | 5 minimum |

La journée se calcule de 00:00 à 24:00 dans le fuseau horaire du client. Le gain net se calcule comme profit brut moins spread et frais.

## 8. Module IA d'assistance

L'IA assiste le moteur, elle ne le remplace pas : le moteur et le module de risque gardent le dernier mot sur tout ordre.

**Fonctions**

- Filtrage des signaux : note la qualité d'un signal du moteur et recommande d'entrer ou d'attendre.
- Détection du régime de marché (tendance, range, forte volatilité) pour adapter ou suspendre la stratégie.
- Explication en langage clair de chaque décision, affichée au client (« position ouverte parce que… »).
- Suggestions de réglages cohérents avec l'objectif du client, à valider par lui, jamais appliquées seules.
- Résumé de fin de session : résultats, décisions, enseignements.

**Entrées et sorties**

| Entrées | Sorties |
| --- | --- |
| Prix, bougies, indicateurs, volatilité, spread | Score de signal et recommandation |
| Paramètres de risque et objectifs du client | Régime de marché détecté |
| Historique des décisions et résultats de la session | Explication textuelle et suggestions |

**Règles**

- L'IA n'envoie jamais d'ordre directement : elle renvoie un avis au moteur.
- En cas d'indisponibilité de l'IA, le moteur continue avec ses règles déterministes, ou s'abstient selon le réglage choisi.
- Mise en service progressive : mode observation (l'IA note sans influencer), puis mode filtrage en démo, puis réel.
- Validation obligatoire par backtests et tests en avant (walk-forward) sur démo avant toute activation en réel ; les résultats sont documentés.
- Les modèles sont versionnés et chaque décision enregistre la version utilisée.
- Approche proposée : modèles statistiques ou d'apprentissage classique pour le scoring, et un modèle de langage uniquement pour les explications et l'assistant conversationnel.

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

## 10. Interface administrateur

Interface séparée de l'interface client, accessible uniquement aux comptes administrateur, avec double authentification obligatoire.

| Module | Fonctions |
| --- | --- |
| Tableau de bord | Utilisateurs actifs, nouveaux inscrits, essais en cours, abonnés, revenus, bots actifs, erreurs |
| Utilisateurs | Recherche, fiche détaillée, suspension, réactivation, prolongation d'essai ou d'abonnement, historique |
| Abonnements | Création et modification des formules (semaine, mois, année), prix, devises, durée d'essai, promotions |
| Paiements | Liste des transactions Chariow et NOWPayments, statuts, rapprochement, remboursements enregistrés |
| Affiliation | Demandes à approuver ou refuser, barèmes de commission, filleuls, gains, paiements aux affiliés |
| Trading et risque | Plafonds globaux (mise maximale, positions maximales), liste des actifs activés, arrêt d'urgence global, supervision des bots |
| Réglages | Textes légaux, messages d'avertissement, e-mails types, clés des services externes (stockées de façon sécurisée) |
| Équipe et rôles | Création de comptes administrateur et attribution de droits |
| Journal d'audit | Toute action administrateur et toute action sensible, non modifiable |
| Support | Consultation de l'état d'un compte sans jamais voir le token Deriv en clair |

Toute modification de prix ou de plafond est versionnée et ne s'applique pas rétroactivement aux abonnements déjà payés.

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

## 13. Module d'affiliation

Le module est proposé ici sous forme de première version simple ; les avantages seront enrichis avec le temps, et son développement vient après le cœur du produit.

**Version initiale proposée**

1. Un client demande à devenir affilié depuis son espace.
2. L'administrateur examine la demande et l'approuve ou la refuse.
3. L'affilié obtient un code et un lien de parrainage uniques.
4. Une personne qui s'inscrit via le lien ou le code est rattachée à l'affilié (fenêtre d'attribution configurable, par exemple 30 jours).
5. Quand le filleul paie un abonnement, une commission est créditée à l'affilié selon le barème défini par l'administrateur (pourcentage, première commande ou récurrent).
6. L'affilié consulte ses filleuls, ses conversions et son solde ; les versements sont validés et enregistrés par l'administrateur.

**Contrôles anti-fraude**

- Auto-parrainage interdit (même appareil, même moyen de paiement, même identité).
- Commission versée seulement après paiement confirmé, avec délai de rétractation configurable.
- Journal complet des attributions et des commissions.

**Évolutions prévues (hors première version)**

- Niveaux d'affiliés avec avantages croissants.
- Bonus de performance, matériel promotionnel, tableau de classement.
- Versements automatisés et avantages pour les filleuls.

## 14. Sécurité

La sécurité est une exigence non négociable : une fonctionnalité qui ne la respecte pas n'est pas livrable.

**Principes**

- Le backend est la seule source de vérité. Toute entrée du front-end est considérée comme non fiable et revalidée côté serveur.
- Moindre privilège : tokens Deriv aux scopes minimaux, rôles administrateur limités.

**Authentification et sessions**

- Mots de passe hachés avec Argon2id ou bcrypt, politique de mot de passe robuste.
- Double authentification (TOTP) proposée aux clients, obligatoire pour les administrateurs et pour activer le compte réel.
- Jetons de session de courte durée avec renouvellement, cookies HttpOnly, Secure et SameSite, liste des sessions actives et déconnexion à distance.
- Protection contre le brute force : limitation de débit, verrouillage progressif, alerte de connexion inhabituelle.

**Données et secrets**

- Tokens Deriv chiffrés au repos (AES-256-GCM avec clés gérées dans un coffre de secrets), jamais renvoyés au client ni écrits dans les journaux.
- Secrets (clés de paiement, clés IA) hors du code source, rotation possible.
- HTTPS partout, HSTS, chiffrement des sauvegardes.

**Application**

- Validation stricte de toutes les entrées (schémas Pydantic), requêtes SQL paramétrées.
- Contrôle d'accès vérifié à chaque requête (un client ne voit que ses propres données).
- Protection CSRF, en-têtes de sécurité, politique CSP, CORS restreint aux domaines de l'application.
- Limitation de débit par utilisateur et par adresse sur toutes les routes sensibles.
- Webhooks de paiement : signature vérifiée, idempotence, liste d'adresses autorisées si le fournisseur le permet.
- Ordres uniquement émis par le moteur backend après validation du module de risque ; verrou empêchant les doubles ordres.

**Exploitation**

- Journal d'audit non modifiable pour les actions sensibles, surveillance et alertes.
- Dépendances mises à jour et analysées régulièrement.
- Sauvegardes testées, plan de réponse à incident, test d'intrusion avant l'ouverture au compte réel.
- Protection des données personnelles : minimisation, droit de suppression, politique de confidentialité.

## 15. Design et UX

Interface professionnelle, aérée, fine et affirmée.

**Typographie : Plus Jakarta Sans, hébergée sur le serveur**

| Élément | Taille | Graisse |
| --- | --- | --- |
| Titre de page (H1) | 28 px | 400 (Regular) |
| Titre de section (H2) | 22 px | 400 (Regular) |
| Sous-titre (H3) | 18 px | 500 (Medium) |
| Texte courant | 14 px | 400 (Regular) |
| Libellés, boutons, en-têtes de tableau | 13 px | 500 (Medium) |
| Petit texte, aides, horodatages | 12 px | 400 (Regular) |
| Chiffres clés (solde, profit) | 24 px | 500 (Medium) |

Aucune graisse supérieure à 500 dans l'interface. Pas de gros titres en gras ; la hiérarchie vient de la taille, de l'espacement et de la couleur.

**Emojis et icônes**

- Zéro emoji dans l'interface, avec une seule exception : l'emoji de salutation à côté de « Bonjour, {prénom} » sur le tableau de bord.
- Icônes modernes de type Lucide : trait de 1,5 px, taille de 20 px (16 px dans les tableaux).

**Mise en page**

- Grille d'espacement de 8 px ; marges internes de cartes de 24 px.
- Coins arrondis de 8 à 12 px ; bordures de 1 px de gris clair ; ombres très légères ou absentes.
- Une couleur d'accent unique ; vert et rouge réservés aux gains et pertes, toujours accompagnés d'un signe (+ ou -) ou d'une icône, jamais la couleur seule.
- Contraste de texte conforme WCAG AA (au moins 4,5 : 1).
- Thèmes clair et sombre sur toutes les pages (voir ci-dessous).
- Interface entièrement traduite en français et en anglais (voir ci-dessous).

**Couleurs : bleu clair professionnel**

La couleur d'accent est un bleu clair et sobre, inspiré de la capture de référence. Les codes ci-dessous sont des approximations à valider sur maquette ; chaque couple texte et fond doit atteindre un contraste d'au moins 4,5 : 1.

| Rôle | Thème clair | Thème sombre |
| --- | --- | --- |
| Accent principal (boutons pleins, liens, bandeau) | #1F6FDB | #5B9DF0 |
| Accent au survol | #1A5CB8 | #7AB1F4 |
| Accent très clair (fonds de badges, sélections) | #E8F1FD | #16263F |
| Fond de page | #F6F7F9 | #0B1220 |
| Fond des cartes et du menu | #FFFFFF | #111A2B |
| Bordures | #E5E7EB | #1F2A3D |
| Texte principal | #0F172A | #E6EAF2 |
| Texte secondaire | #64748B | #94A3B8 |
| Gain | #16A34A | #34D399 |
| Perte | #DC2626 | #F87171 |
| Avertissement | #D97706 | #FBBF24 |

Bouton d'action principal : fond sombre (#111827 en clair), texte blanc, comme sur la référence ; bouton d'accent bleu pour les actions de la page de trading.

**Référence visuelle : capture TestMonApp**

La capture sert de modèle pour l'apparence et la structure uniquement ; ni le logo, ni les textes, ni la marque ne sont repris. Éléments à reproduire :

- Barre supérieure sur fond blanc avec logo à gauche, menu central avec icônes, sélecteur de langue (drapeau et code) et profil à droite.
- En-tête de page : salutation « Bonjour, {prénom} » avec emoji, phrase d'accueil en petit texte gris, bouton d'action principal aligné à droite.
- Grand bandeau bleu d'accueil avec motifs circulaires discrets, accompagné d'une grille de cartes de statistiques (2 colonnes sur 2 lignes) et de cartes de raccourcis (parrainage, support).
- Titres de section en majuscules, petits et espacés ; tableaux avec en-têtes en majuscules, pastille de statut colorée et icônes d'action.
- Bouton d'assistance flottant en bas à droite.
- Version mobile : barre réduite avec menu hamburger, bandeau et cartes empilées en pleine largeur.

La règle de graisse maximale 500 reste prioritaire : la référence utilise des gras plus marqués, qui ne sont pas reproduits.

**Thèmes clair et sombre**

- Trois options dans le profil et dans la barre supérieure : clair, sombre, automatique (suit le système). Défaut : automatique.
- Disponibles sur toutes les pages sans exception : site public, espace client, page de trading, interface administrateur, pages de paiement propres à SafeTrade.
- Toutes les couleurs passent par des variables de thème (jetons de design) ; aucune couleur écrite en dur dans les composants.
- Le choix est enregistré dans le profil (côté serveur) et en local ; aucun flash de mauvais thème au chargement.
- Graphiques de prix, tableaux et icônes adaptés aux deux thèmes.
- Critère d'acceptation : chaque page contrôlée en clair et en sombre, aucun texte illisible, contraste AA respecté.

**Traduction complète : français et anglais**

- Langues autorisées dans la première version : français et anglais, et seulement celles-ci.
- Traduction totale, jamais partielle : pages publiques, espace client, page de trading, interface administrateur, messages d'erreur et de validation du backend, e-mails, notifications, factures et reçus, pages légales, avertissements de risque, explications générées par l'IA.
- Sélecteur de langue dans la barre supérieure ; langue par défaut déduite du navigateur, choix enregistré dans le profil.
- Aucun texte écrit en dur dans le code : tout passe par des fichiers de traduction ; le backend renvoie des codes d'erreur que le front-end traduit.
- Dates, nombres, devises et fuseaux horaires formatés selon la langue choisie.
- Pages publiques avec préfixe d'adresse par langue (/fr et /en) pour le référencement.
- Contrôle automatique à chaque livraison : la construction échoue si une clé existe dans une langue et pas dans l'autre.
- Architecture prête à accueillir d'autres langues plus tard sans modification du code.

## 16. Exigences non fonctionnelles, tests et déploiement

**Objectifs mesurables (valeurs proposées)**

| Critère | Cible |
| --- | --- |
| Affichage d'un tick côté client après réception chez Deriv | moins de 500 ms (95e percentile) |
| Décision du moteur puis envoi de l'ordre, hors délai Deriv | moins de 300 ms (95e percentile) |
| Temps de réponse des API standard | moins de 300 ms (95e percentile) |
| Disponibilité mensuelle | 99,5 % minimum |
| Capacité de lancement | 2 000 comptes, 300 bots actifs simultanément |
| Perte de données maximale (RPO) | 1 heure |
| Reprise après sinistre (RTO) | 4 heures |
| Sauvegardes | Quotidiennes complètes, journal de transactions continu, test de restauration mensuel |

**Tests**

- Tests unitaires : couverture d'au moins 80 % sur le code global et 100 % sur les règles du module de risque.
- Tests d'intégration sur un compte démo Deriv : connexion, ordres, clôture, reconnexion, réconciliation.
- Tests de paiement en mode test de Chariow et NOWPayments : succès, échec, expiration, webhook en double.
- Test de charge à 1,5 fois la capacité de lancement.
- Test d'endurance du moteur en démo pendant 14 jours consécutifs sans incident bloquant avant tout accès au réel.
- Test d'intrusion par un tiers avant l'ouverture du compte réel.

**Déploiement**

- Trois environnements : développement, préproduction, production.
- Intégration et déploiement continus avec tests automatiques bloquants.
- Supervision : journaux centralisés, métriques, alertes en cas d'erreur de moteur, de webhook en échec ou de latence dépassée.
- Mentions légales, conditions d'utilisation, politique de confidentialité et avertissement de risque publiés avant le lancement.

## 17. Planification et critères d'acceptation

Ces durées étaient estimées pour une équipe humaine. Le travail étant réalisé par Claude Code, le plan de travail de la section 19 (étapes courtes, validées une à une) fait foi pour l'exécution ; les livrables et critères d'acceptation de ce tableau restent valables.

| Phase | Durée | Livrables | Critère d'acceptation |
| --- | --- | --- | --- |
| 0. Cadrage | 1 semaine | Réponses aux questions ouvertes, choix du produit Deriv, maquettes principales | Section 18 entièrement tranchée et signée |
| 1. Socle | 3 semaines | Inscription, connexion, double authentification, rôles, base de données, intégration continue, système de thèmes clair et sombre, traduction française et anglaise | Parcours inscription à connexion fonctionnel ; tests de sécurité de base passés |
| 2. Connexion Deriv | 3 semaines | Saisie ou OAuth du token, choix du compte, flux de prix, reconnexion | Prix affichés en direct sur 5 actifs pendant 24 h sans coupure non récupérée |
| 3. Moteur et risque en démo | 5 semaines | Moteur, module de risque, paramètres, page de trading, arrêt d'urgence | Toutes les limites de la section 7 testées et respectées à 100 % ; réconciliation correcte après coupure |
| 4. Abonnements et paiements | 3 semaines | Essai de 3 jours, formules, Chariow, NOWPayments, webhooks | Paiement test crédité une seule fois, même avec webhook en double ; expiration appliquée à la minute près |
| 5. Interface administrateur | 3 semaines | Modules de la section 10, journal d'audit | Un administrateur gère un utilisateur, un prix et un paiement sans intervention technique |
| 6. Module IA | 4 semaines | Scoring, régime de marché, explications, mode observation | Modèle versionné ; rapport de backtest et de test en avant documenté |
| 7. Bêta fermée en démo | 4 semaines | 30 à 50 testeurs, corrections | 14 jours d'endurance sans incident bloquant ; retours traités |
| 8. Ouverture du réel | 3 semaines | Plafonds réel, avertissements, test d'intrusion | Test d'intrusion sans faille critique ou élevée ouverte ; avis juridique obtenu |
| 9. Affiliation | 3 semaines | Module de la section 13 | Parcours demande, approbation, parrainage, commission validé de bout en bout |

Durée totale estimée : environ 32 semaines, avec des chevauchements possibles (les phases 5 et 6 peuvent avancer en parallèle de la phase 4).

## 18. Questions ouvertes à valider avant développement

Statut au 30 octobre 2026 : toutes les questions ci-dessous ont reçu une réponse de travail en section 21. Seules les mentions « à confirmer » restent ouvertes.

1. Quel produit Deriv utiliser : contrats via l'API WebSocket (multiplicateurs ou autres) avec mise en dollars, ou MT5 avec lots ? Cela décide du paramètre « lots » de la page de trading.
2. Quels pays sont visés au lancement ? Cela détermine l'avis juridique, les mentions légales et les moyens de paiement prioritaires.
3. Le stop loss obligatoire par trade est-il accepté, sachant qu'une clôture dès le moindre gain sans limite de perte expose à de fortes pertes isolées ?
4. Les valeurs par défaut et plafonds de la section 7 sont-ils validés ?
5. Prix des formules (semaine, mois, année) et devise de facturation ?
6. Sort des positions ouvertes à l'expiration de l'abonnement : les laisser se clôturer sous stop loss (recommandé) ou les clôturer immédiatement ?
7. Commission d'affiliation : pourcentage, première commande ou récurrent, délai avant versement ?
8. Qui développe et héberge le module IA : modèle interne, service externe, ou les deux ? Quel budget mensuel d'infrastructure ?
9. Les codes couleur de la section 15 sont-ils validés sur maquette, pour les thèmes clair et sombre (décidés) ?
10. Français et anglais complets sont décidés ; une troisième langue (par exemple le swahili) est-elle prévue après le lancement ?
11. Une application mobile native est-elle nécessaire dès la première version, ou la version web responsive suffit-elle ?
12. Hébergement visé (fournisseur cloud, région) ?

## 19. Plan de travail pour Claude Code

Le développement est réalisé par Claude Code, étape par étape. Il est interdit de demander l'application entière en une seule fois : chaque étape est petite, testée et validée par toi avant la suivante.

**Règles de travail**

1. Une étape = une session Claude Code = une branche Git = un livrable vérifiable. Taille cible : moins de 400 lignes modifiées hors tests et fichiers générés ; au-delà, l'étape est découpée.
2. Chaque session commence par lire le fichier CLAUDE.md et uniquement la section du cahier des charges concernée (voir le découpage ci-dessous).
3. Claude Code propose d'abord un plan (fichiers touchés, approche) et attend ta validation avant d'écrire du code.
4. Les tests s'écrivent avec le code. Une étape n'est terminée que si tests, vérification de types et lint passent.
5. Claude Code ne touche qu'à ce que l'étape demande : pas de refactorisation hors périmètre, pas de nouvelle dépendance sans justification écrite.
6. En cas de doute sur une exigence, Claude Code pose la question au lieu de deviner.
7. Les tests contre Deriv utilisent uniquement un compte démo. Aucun test automatisé n'utilise un compte réel.
8. Aucun secret (token, clé de paiement, mot de passe) n'est écrit dans le code, les tests ou Git : fichiers .env locaux non versionnés.
9. Le compte réel reste désactivé par un interrupteur de configuration jusqu'à la phase 8.

**Organisation du dépôt**

| Dossier | Contenu |
| --- | --- |
| backend/ | API FastAPI, moteur de trading, module de risque, IA, facturation, tests |
| frontend/ | Application Next.js, composants, thèmes, fichiers de traduction (fr, en) |
| infra/ | Docker Compose, configuration de déploiement, scripts de sauvegarde |
| docs/spec/ | Ce cahier des charges découpé en un fichier Markdown par section (01 à 21) |
| docs/decisions/ | Une courte note par décision d'architecture (produit Deriv, choix IA, etc.) |
| CLAUDE.md | Règles permanentes lues au début de chaque session |

**Contenu obligatoire de CLAUDE.md**

- Stack : FastAPI et Python, PostgreSQL, Redis, Next.js avec TypeScript, Tailwind.
- Règle d'or : le backend est la seule source de vérité ; le front-end n'envoie que des demandes et affiche les réponses.
- Règles de sécurité de la section 14, résumées en liste de contrôle.
- Règles de design de la section 15 : Plus Jakarta Sans, graisse maximale 500, zéro emoji sauf la salutation du tableau de bord, icônes Lucide, couleurs uniquement via les variables de thème.
- Règle de traduction : aucun texte en dur ; toute chaîne existe en français et en anglais.
- Commandes exactes pour lancer l'application, les tests, le lint et la vérification de types.
- Convention de nommage des branches (step/ID-nom-court) et des messages de commit.
- Liste des interdits : section 19, règles 5 à 9.

**Définition de « terminé » pour chaque étape**

- [ ] Le critère d'acceptation de l'étape est démontré (commande, capture ou test).
- [ ] Tests, types et lint passent en local et en intégration continue.
- [ ] Aucun texte non traduit, aucune couleur en dur, aucun secret dans le code.
- [ ] Les écrans touchés sont vérifiés en thème clair et en thème sombre, sur ordinateur et téléphone.
- [ ] Un commit clair sur une branche dédiée ; fusion dans main après ta validation.
- [ ] À la fin d'une phase : étiquette Git phase-N et courte note de bilan.

**Modèle de message à donner à Claude Code pour chaque étape**

```markdown
Étape {ID} : {titre}.
Lis CLAUDE.md et docs/spec/{fichier de la section concernée}.
Objectif : {objectif en une phrase}.
Hors périmètre : tout ce qui n'est pas listé dans les livrables.
Procède d'abord en mode plan : liste les fichiers que tu vas créer ou modifier et attends ma validation.
Puis implémente avec les tests. Termine par : tests, types et lint verts, résumé de ce qui a été fait, et démonstration du critère d'acceptation : {critère}.
```

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

## 21. Décisions prises et vérifications dans la documentation officielle Deriv

**Décisions (réponses aux questions de la section 18)**

| Question | Décision | Statut |
| --- | --- | --- |
| 1. Produit Deriv | API Deriv de la plateforme Options (REST et WebSocket) ; mise en dollars, pas de lots ni de MT5 ; authentification OAuth 2.0 en méthode principale, jeton personnel (PAT) en méthode alternative | Décidé ; vérifications restantes à l'étape 2.1 |
| 2. Pays visés | Aucun pays écrit en dur ; liste de pays bloqués configurable dans l'administration ; avis juridique avant l'étape 8.4 | Pays de lancement à confirmer par toi |
| 3. Stop loss obligatoire | Oui. Pour les contrats à perte limitée à la mise, le plafond de mise tient lieu de stop loss ; pour les contrats qui acceptent un ordre limite, le stop loss est posé à l'ouverture. Le moteur ne traite que des contrats qui permettent la vente avant l'échéance | Décidé |
| 4. Valeurs par défaut et plafonds | Tableau de la section 7 | Décidé |
| 5. Prix des formules | Prix fictifs de démarrage : semaine 5 USD, mois 15 USD, année 120 USD ; essai de 3 jours ; tout est modifiable dans l'interface administrateur avant la mise en production | Décidé (valeurs fictives) |
| 6. Positions à l'expiration | Les laisser se clôturer sous leur protection, puis arrêter le bot | Décidé |
| 7. Commissions d'affiliation | Valeurs fictives de départ : 20 % du premier paiement du filleul, fenêtre d'attribution de 30 jours, versement possible après 14 jours ; modifiables dans l'administration | Décidé (valeurs fictives) |
| 8. IA | Scoring par modèles statistiques ou d'apprentissage classique entraînés sur notre serveur ; explications par un modèle de langage via API ; plafond de dépense mensuel réglable dans l'administration | Budget mensuel à fixer par toi |
| 9. Couleurs | Codes de la section 15 validés sur les maquettes de l'étape 0.4 | À l'étape 0.4 |
| 10. Troisième langue | Non avant le lancement ; architecture prête à en accueillir | Décidé |
| 11. Mobile | Application web responsive (PWA) ; application native plus tard si nécessaire | Décidé |
| 12. Hébergement | Serveur cloud sous Docker, région européenne en hypothèse ; latence vers Deriv mesurée à l'étape 2.5 ; fournisseur choisi selon ton budget | Hypothèse à confirmer |

**Ce qui est confirmé par la documentation officielle Deriv**

- L'API couvre la plateforme Options : REST (adresse api.derivws.com) pour les comptes et la génération d'un mot de passe à usage unique (OTP), WebSocket pour le trading et les données.
- Trois points WebSocket : public (sans authentification), démo et réel (authentifiés par OTP).
- Parcours technique : 1. jeton OAuth ou PAT ; 2. appel REST POST /trading/v1/options/accounts/{accountId}/otp ; 3. la réponse contient l'adresse WebSocket prête à l'emploi ; 4. connexion et opérations de trading.
- OAuth 2.0 : flux par code d'autorisation avec PKCE, page d'autorisation auth.deriv.com/oauth2/auth, adresse de redirection en HTTPS enregistrée à l'avance, jetons d'accès qui expirent (l'exemple officiel indique 3 600 secondes). Deriv le recommande pour les applications web.
- PAT : l'utilisateur génère le jeton dans Deriv et le colle dans l'application ; l'en-tête Deriv-App-ID est obligatoire sur les appels REST avec un PAT.
- Un compte démo est créé automatiquement à l'inscription de l'utilisateur chez Deriv.
- Opérations de trading WebSocket : proposal, buy, sell (vente d'un contrat ouvert avant échéance), proposal\_open\_contract, contract\_update, cancel, achat groupé. Données : active\_symbols, contracts\_for, ticks, ticks\_history, trading\_times.
- Deriv propose aussi une API d'automatisation (stratégies prédéfinies exécutées par Deriv). Elle n'est pas utilisée : le moteur de SafeTrade décide et exécute lui-même.

**Limites d'appels officielles (à respecter par le moteur)**

| Appels comptés ensemble | Par minute | Par heure |
| --- | --- | --- |
| proposal, proposal\_open\_contract, buy, sell | 360 | 14 400 |
| balance, statement | 100 | 2 000 |
| portfolio, profit\_table | 30 | 1 500 |
| Tous les autres appels | 220 | 14 400 |
| REST, par utilisateur connecté | 80 par minute | non précisé |

Règles qui en découlent : s'abonner aux flux au lieu d'interroger en boucle, une seule connexion par compte, et un plafond interne de 120 appels par minute pour proposal, proposal\_open\_contract, buy et sell par compte (valeur prudente, à ajuster après mesure). Après un rejet, le moteur attend avant de réessayer, conformément au guide des bonnes pratiques de Deriv.

**Conséquences sur le cahier des charges**

- Le « spread » devient l'écart entre le prix d'achat du contrat et le prix auquel Deriv propose de le racheter. Le gain net se calcule : prix de rachat proposé moins prix d'achat. Les champs exacts sont confirmés à l'étape 2.1.
- Le backend crée une application de chaque type (OAuth et PAT) dans le tableau de bord développeur de Deriv, génère un OTP à chaque connexion WebSocket et ne transmet jamais le jeton au front-end.

**À vérifier à l'étape 2.1 (non confirmé à ce jour)**

- Disponibilité de l'or et du Bitcoin dans la liste des actifs d'un compte (appel active\_symbols). Deriv indique que chaque actif n'accepte que certains types de contrats.
- Types de contrats autorisant la vente anticipée et les ordres limites pour chaque actif retenu (appel contracts\_for), sur un compte démo.
- Étendues (scopes) exactes des jetons PAT et OAuth : une page officielle citée cherche par exemple trade et account\_manage, à confirmer.
- Durée de vie des jetons OAuth et du jeton de renouvellement.

**Ce qu'il te reste à faire de ton côté**

- Créer un compte développeur sur developers.deriv.com et un compte Deriv avec son compte démo.
- Créer des comptes marchands de test chez Chariow et NOWPayments (la lecture de leurs documentations officielles aura lieu aux étapes 4.2 et 4.3).
- Choisir les pays de lancement, le budget mensuel de l'IA et le fournisseur d'hébergement.
- Remplacer les prix et commissions fictifs dans l'administration avant la mise en production, et faire relire les textes légaux par un juriste.

**Sources officielles consultées le 30 octobre 2026**

[Deriv API : documentation](https://developers.deriv.com/docs/) · [Aperçu de l'API](https://developers.deriv.com/docs/intro/api-overview/) · [Authentification](https://developers.deriv.com/docs/intro/authentication/) · [OAuth 2.0](https://developers.deriv.com/docs/intro/oauth) · [Limites d'appels](https://developers.deriv.com/docs/limits/) · [Vente d'un contrat](https://developers.deriv.com/docs/trading/sell/) · [Contrats par actif](https://developers.deriv.com/docs/data/contracts-for/) · [Mises à jour du produit](https://developers.deriv.com/product-updates/)
