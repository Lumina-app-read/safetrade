# Q1. Produit Deriv et authentification

- **Statut :** décidé (vérifications restantes à l'étape 2.1)
- **Date :** 30 octobre 2026

## Question

Quel produit Deriv utiliser : contrats via l'API avec mise en dollars, ou MT5 avec lots ?

## Décision

- API Deriv de la plateforme Options (REST et WebSocket). Mise en dollars : pas de lots, pas de MT5.
- Authentification : OAuth 2.0 en méthode principale (code d'autorisation avec PKCE, adresse de redirection HTTPS enregistrée à l'avance, jetons d'accès qui expirent), jeton personnel (PAT) en méthode alternative (en-tête `Deriv-App-ID` obligatoire sur les appels REST avec un PAT).
- L'API d'automatisation de Deriv (stratégies prédéfinies exécutées par Deriv) n'est pas utilisée : le moteur SafeTrade décide et exécute lui-même.

## Conséquences

- Parcours technique : jeton OAuth ou PAT, puis `POST /trading/v1/options/accounts/{accountId}/otp` (REST, api.derivws.com), dont la réponse donne l'adresse WebSocket prête à l'emploi. Trois points WebSocket : public (sans authentification), démo et réel (authentifiés par OTP).
- Le backend crée une application de chaque type (OAuth et PAT) dans le tableau de bord développeur Deriv, génère un OTP à chaque connexion WebSocket et ne transmet jamais le jeton au front-end.
- Le paramètre « taille de position » de la section 7 est une mise en USD.
- Spread : écart entre le prix d'achat du contrat et le prix auquel Deriv propose de le racheter. Gain net = prix de rachat proposé - prix d'achat (champs exacts confirmés à l'étape 2.1).
- Limites d'appels officielles à respecter :

| Appels comptés ensemble | Par minute | Par heure |
| --- | --- | --- |
| proposal, proposal_open_contract, buy, sell | 360 | 14 400 |
| balance, statement | 100 | 2 000 |
| portfolio, profit_table | 30 | 1 500 |
| Tous les autres appels | 220 | 14 400 |
| REST, par utilisateur connecté | 80 | non précisé |

- Règles internes qui en découlent : s'abonner aux flux plutôt qu'interroger en boucle ; une seule connexion par compte ; plafond interne de 120 appels par minute et par compte pour proposal, proposal_open_contract, buy et sell (valeur prudente, à ajuster après mesure) ; attente avant nouvel essai après un rejet.

## Précisions de l'étape 2.1

Détails, corrections et contrat retenu (multiplicateurs, hypothèse de travail) : [deriv.md](deriv.md). Le jeton OAuth dure 30 jours dans l'exemple actuel et n'a pas de jeton de renouvellement.

## Reste à faire

- Points listés dans [verifications-etape-2-1.md](verifications-etape-2-1.md).
- Côté propriétaire : compte développeur sur developers.deriv.com et compte Deriv avec son compte démo.

Source : [section 21](../spec/21-decisions.md) ; question 1 de la [section 18](../spec/18-questions-ouvertes.md).
