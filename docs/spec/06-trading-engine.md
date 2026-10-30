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

