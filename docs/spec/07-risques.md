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

