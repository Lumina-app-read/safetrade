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

