# Audit : pourquoi le bot est peu actif, et architecture possible d'un scalping actif

- **Date :** 5 novembre 2026, à la demande du propriétaire
- **Statut :** audit et proposition seulement. **Aucune modification du moteur ni du module de risque, aucun ordre réel ou démo pendant cet audit.**
- **Sources :** code du moteur (`app/trading/strategy.py`, `bot.py`, `risk.py`, `app/market/quality.py`), journal des décisions du compte du propriétaire en base locale, vidéo fournie par le propriétaire (78 secondes, regardée image par image), lecture publique de `contracts_for` chez Deriv.

## 1. Le moteur actuel, tel qu'il est

| Élément | Règle exacte |
| --- | --- |
| Stratégie active | Version 1 : croisement de moyennes mobiles exponentielles 9 et 21 sur des bougies d'**une minute** |
| Fréquence de décision | **Une seule décision par bougie close**, donc 60 au plus par heure, même si le moteur tourne chaque seconde |
| Condition d'ouverture | Un **croisement vient de se produire** sur la dernière bougie (rapide qui passe au-dessus ou au-dessous de la lente). Une tendance déjà installée ne déclenche rien. |
| Filtre de volatilité | Bougie moyenne (ATR 14) d'au moins 2 % de la mise, multiplicateur compris (`MIN_CANDLE_VALUE`) |
| Contrôles du marché | Dernier prix de moins de 5 s, bougies continues et à jour, 60 s d'attente après un trou de données |
| Contrôles de risque | Stop obligatoire, mise fixe, une position ouverte à la fois par défaut (3 au plus), part du capital engagé, limites de perte de session et du jour, objectifs de session et du jour, marge pour le glissement |
| Refroidissement | Pause de 15 minutes après 3 pertes de suite ; arrêt de la session à l'objectif ou à la limite de perte |
| Ouverture possible seulement si | Le bot est en analyse **et aucune position n'est ouverte** |
| Sorties | Stop loss chez Deriv ; protection du gain à partir de +1 R (plancher, puis cliquet à 50 % du gain maximal) ; fermeture manuelle ; **aucun objectif de gain fixe** |
| Après une clôture | Le bot attend un **nouveau croisement** ; il ne réévalue pas le marché autrement |
| Seuil de confiance, confirmation | Aucun : le signal est binaire (croisement ou rien) |

## 2. Pourquoi il reste 30 minutes sans ouvrir

Mesuré sur le journal du compte `yecolardc+6@gmail.com` :

| Actif | Décisions sans croisement | Croisements | Positions ouvertes | Écart médian entre deux ouvertures |
| --- | --- | --- | --- | --- |
| Volatility 75 (1s) | 63 | 4 | 4 | **27 minutes** (19 à 35) |
| Step Index | 75 | 2 | 2 | 17 minutes |
| Or | 72 | 4 | 4 | 7 minutes |
| Volatility 10 | 24 | 3 | 3 | 10 minutes |
| Volatility 100 (1s) | 23 | 3 | 3 | 6,5 minutes |

Les refus pour cause de marché sont rares : 15 en tout, surtout des prix de plus de 5 secondes. Le filtre de volatilité n'a bloqué aucune entrée. **L'inactivité ne vient pas des filtres, elle vient de la conception :**

1. **Le signal est un événement rare.** Un croisement 9/21 sur des bougies d'une minute se produit environ une fois toutes les 15 à 30 bougies sur Volatility 75 (1s). Les mouvements visibles sur le graphique entre deux croisements ne comptent pas.
2. **Une décision par minute seulement.** Un mouvement de quelques secondes est invisible pour le bot.
3. **Une position à la fois, sans objectif de gain.** Une position reste ouverte jusqu'au stop, à la protection ou à ta main : 1 à 20 minutes dans ton historique. Pendant ce temps, rien d'autre n'est évalué.
4. **Après une clôture, il faut un nouveau croisement.** Le bot ne repart pas de l'état du marché.

## 3. La vidéo : ce qui est visible, et seulement cela

Je ne connais pas l'algorithme de ce robot. Voici ce que montrent les images :

| Élément visible | Observation |
| --- | --- |
| Plateforme | Tableau de bord web qui suit des « positions MT5 Bridge » : les ordres passent par **MetaTrader 5**, pas par l'API Options de Deriv |
| Marché | Boom 1000 Index (graphique MetaTrader cité par le propriétaire) |
| Positions | Toutes à l'achat (BUY), lot 0,2, origine « AVA » |
| Mouvements | +2,53 ; +5,20 ; +7,93 ; +10,73 points |
| Prix d'ouverture | 14 874,26 ; 14 871,61 ; 14 868,88 ; 14 866,08 : **chaque achat plus bas que le précédent, environ 2,7 points plus bas** |
| Prix de clôture | 14 876,79 puis **trois positions fermées au même prix, 14 876,81** : plusieurs achats fermés ensemble |
| Résultats affichés | 10 gagnantes sur 10 en 15 min, 18 sur 18 en 1 h (+42,20 $), 53 sur 53 en 24 h (+102,33 $) |
| Protection de session | Objectif +25 $, recul maximal toléré de 100 $, pic de session suivi (+47,49 $), entrées limitées une fois l'objectif atteint, « rythme requis 0,71 $/min » |

**Lecture prudente :** des achats répétés à des prix de plus en plus bas, puis fermés ensemble, ont la forme d'une **moyenne à la baisse** (grille). Le robot ajoute des positions tant que le prix descend, en attendant une remontée ; sur Boom 1000, cette remontée prend la forme d'un pic soudain. Ce profil produit beaucoup de petites victoires et **aucune perte visible, jusqu'au jour où la remontée ne vient pas assez vite** : la perte cumulée des positions empilées peut alors effacer des semaines de gains. Un historique de 53 gains sur 53 ne prouve pas un avantage : il ne montre ni la perte latente maximale pendant la descente, ni le capital nécessaire, ni ce qui arrive après une longue série sans pic. **Je ne peux pas affirmer que c'est leur méthode** ; c'est la forme des chiffres visibles.

À retenir de la vidéo, sans tout copier : la **protection de session** (objectif, pic suivi, recul toléré, verrouillage des entrées après l'objectif), qui ressemble à nos objectifs et limites de session et pourrait être affichée de la même façon ; le **suivi des positions par période** ; l'idée de **petites sorties rapides**. Le point à écarter : l'empilement de positions contre le marché, que notre règle « aucune hausse du risque après une perte » interdit.

## 4. MetaTrader 5 et l'API Deriv : ce qui diffère

| Point | Robot MetaTrader 5 (EA) | SafeTrade par l'API Deriv |
| --- | --- | --- |
| Produit | CFD sur indices synthétiques, en lots, effet de levier | Contrats Deriv : multiplicateurs, Rise/Fall, accumulateurs… (sur Boom 1000 : multiplicateurs ×100 à ×500 dans les deux sens, et accumulateurs) |
| Coût | Écart entre achat et vente (spread), parfois des frais de financement la nuit | Commission par position sur les multiplicateurs (0,039 % du notionnel sur Volatility 75 (1s)), paiement fixe sur Rise/Fall (53,1 % de réussite nécessaire) |
| Exécution | Ordre envoyé au serveur MT5 depuis le terminal ; le robot réagit à chaque tick (`OnTick`) | Deux allers-retours : devis, puis achat par identifiant ; vente par `sell` ; flux de ticks par WebSocket |
| Stop et objectif | Facultatifs, en prix | Stop obligatoire chez SafeTrade ; stop et objectif disponibles en montant sur les multiplicateurs, tenus par Deriv même si SafeTrade tombe |
| Positions multiples | Libres, y compris empilées | Possibles ; SafeTrade en permet 1 à 3, sans empilement contre le marché |
| Accès | Le terminal MT5 doit tourner (souvent sous Windows) avec le robot | L'API Deriv gère les comptes MT5 mais ne passe pas d'ordres MT5 ; SafeTrade reste sur l'API Options, côté serveur |

Une logique MetaTrader ne se transpose donc pas telle quelle : le coût, l'exécution et la gestion du stop diffèrent. Un robot MT5 serait un autre produit, avec un terminal à faire tourner, et n'est pas couvert par le cahier des charges actuel.

## 5. Réponses

**1. Pourquoi le bot est-il si peu actif ?** Parce qu'il attend un événement rare (un croisement de moyennes sur bougies d'une minute), qu'il ne décide qu'une fois par minute, qu'il garde chaque position jusqu'au stop ou à la protection, et qu'après une clôture il attend un nouveau croisement.

**2. Quelles conditions empêchent les entrées ?** Avant tout l'absence de croisement (plus de 90 % des décisions). Puis une position déjà ouverte. Les contrôles de marché refusent rarement, environ 15 fois sur tout l'historique. Le filtre de volatilité et les pauses de risque n'ont presque jamais joué.

**3. Peut-on concevoir un moteur plus réactif ?** Oui, techniquement : le moteur tourne déjà chaque seconde, et le flux de ticks arrive en direct. Le passage d'une décision par minute à une décision par tick est un changement d'architecture raisonnable. **Mais plus d'activité sans avantage, c'est perdre plus vite** (point 6). Le moteur réactif n'a de sens que si un signal court bat ses coûts.

**4. Quels signaux étudier ?** Ceux de l'étude en cours sur Volatility 75 (1s), tick par tick : momentum sur 5 à 30 ticks, micro-retournements après un mouvement excessif, accélération, cassure des 30 à 300 derniers ticks, séries de ticks, sortie de consolidation, sur des durées de 1 à 60 ticks et sur trois produits. Son verdict décidera s'il existe un signal à brancher.

**5. Comment enchaîner les positions après une clôture ?** Par une machine d'état : clôture, puis refroidissement court et réglable, puis réévaluation immédiate de l'**état** du marché, sans attendre un nouvel événement, puis ouverture seulement si un signal est présent, si le budget de coûts de l'heure le permet et si le module de risque l'accepte. Une seule position à la fois, l'une après l'autre.

**6. Risques d'une fréquence élevée :**
- **Coûts :** à ×100 sur Volatility 75 (1s), chaque position coûte 3,9 % de la mise. 60 positions par heure coûtent 2,3 fois la mise en commissions, avant tout gain.
- **Pertes accélérées :** sans avantage, le résultat converge plus vite vers la perte des frais.
- **Quotas de Deriv :** devis, achat et suivi consomment le budget d'appels ; les sorties doivent garder la priorité.
- **Exécution :** chaque seconde de délai sur un mouvement de quelques ticks change le résultat.
- **Séries de pertes :** plus de positions, donc des séries de pertes plus longues en valeur absolue.
- **Tentation de l'empilement :** elle est exclue.

**7. Modifications nécessaires, si un signal passe la validation :**

| Couche | Changement |
| --- | --- |
| Interface de stratégie | De `evaluate(bougies closes)` à `on_tick(état)` : un état (prix récents, volatilité, position) en entrée, une **intention** (ouvrir, fermer, attendre) en sortie, sans accès au courtier |
| Données | Tampon des derniers ticks dans le moteur, alimenté par le flux du worker de marché, en plus des bougies |
| Gestionnaire de sorties | Objectif et stop chez Deriv en montant (ordres limites des multiplicateurs), sortie au temps, protection actuelle conservée |
| Machine d'état | Clôture, refroidissement réglable, réévaluation, sans attendre un nouvel événement |
| Garde-fou de fréquence | Positions par heure et commissions par heure plafonnées, côté serveur, en plus du module de risque |
| Garde-fou d'avantage | Une stratégie ne peut être activée que si son rapport de validation est positif et figé dans Git |
| Produits | Multiplicateur avec objectif et stop chez Deriv ; Rise/Fall sur quelques ticks à étudier comme second produit (perte bornée à la mise, sans stop à gérer) |
| Interface | Panneau de protection de session (objectif, pic, recul, verrouillage), historique par période |
| Inchangé | Module de risque, stop obligatoire, anti-doublon, arrêt d'urgence, interdiction de toute hausse de risque après une perte |

## Proposition

1. Terminer l'étude tick par tick de Volatility 75 (1s), déjà lancée : elle dit si un signal court bat les coûts de Deriv.
2. **Si oui :** construire l'interface `on_tick`, la machine d'état et les garde-fous ci-dessus, brancher le seul signal validé, puis le tester en démo en comparant historique, simulation et démo.
3. **Si non :** ne pas accélérer le bot. Faire évoluer SafeTrade vers un outil d'exécution assistée : tu choisis le sens, et le système gère stop, objectif, protection du gain et limites. Ce sont les seules fermetures gagnantes de ton historique.
