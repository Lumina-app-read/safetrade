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

