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
