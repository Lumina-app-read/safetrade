# Essais sur compte démo du 31 octobre 2026

Une dizaine de contrats de 1 USD fictif, sur `1HZ100V` (multiplicateurs ×200 et ×400), compte démo uniquement. **Échantillon très petit : ces chiffres décrivent le comportement de l'API, pas une performance.**

## Résultats

| Question | Résultat |
| --- | --- |
| Vente juste après l'achat | Variable. Une vente a été refusée (`InvalidtoSell`, « Waiting for entry tick »), une autre acceptée pendant ce même état. Vendable à coup sûr après 1,75 s dans l'essai suivi. |
| Résultat juste après l'achat | `bid_price` = 0,90 pour 1 USD : **`bid_price` et `profit` incluent déjà la commission** |
| Déplacer le stop loss | Accepté par `contract_update`, une fois par seconde au maximum (`ContractUpdateTooFrequent`) |
| **Stop loss en zone de gain** | **Refusé.** `0`, `-0,05` et `0,05` rejetés (`LimitOrderAmountTooLow`), minimum 0,11 pour une commission de 0,10 |
| Take profit | Ajout et retrait acceptés. Minimum juste au-dessus du gain courant (0,13 demandé pour un gain proche de 0,14) : il ne peut pas verrouiller un gain acquis |
| Retrait du stop loss | **Accepté par Deriv** (`stop_loss: null`). Seul le `stop_out` reste. Le moteur ne doit jamais l'envoyer |
| Niveaux minimaux à l'achat | ×400 : 0,21, pour une commission de 0,20. Ils dépendent du contrat |
| Clôture chez Deriv pendant une vente | `BetExpired` : la position venait de se clôturer, ce refus n'est pas une panne |
| Trailing stop natif | Aucun dans les champs observés ni les schémas |

## SafeTrade coupé

Position ouverte avec `stop_loss` et `take_profit` de 0,25 USD, connexion fermée, lecture au retour.

| Contrat | Clôturé pendant la coupure | Résultat | Écart à l'ordre |
| --- | --- | --- | --- |
| 1 | Oui | -0,28 | **0,03 de glissement** |
| 2 | Oui | +0,26 | +0,01 |
| 3 | Oui | -0,25 | 0 |

Les ordres posés chez Deriv s'exécutent sans SafeTrade, mais le prix n'est pas garanti : le stop loss a glissé de 12 % sur le contrat 1. Le glissement réel, surtout en marché rapide et sur l'or, reste à mesurer sur un grand échantillon.

## Commission

Mesurée pour 1 USD : 0,03 à ×100 sur `1HZ75V`, 0,09 à ×100 sur `cryBTCUSD`, 0,10 à ×200 et 0,20 à ×400 sur `1HZ100V`. Elle suit le multiplicateur : la variation de cours qui rembourse les frais semble fixe par instrument (0,03 %, 0,09 % et 0,05 %), à confirmer sur d'autres mises.

## Réconciliation

`statement` (`action_type: buy`, `date_from`, `description: 1`) renvoie `contract_id`, `transaction_id`, `transaction_time`, `amount`, `shortcode` et `app_id`. L'appariement après une réponse perdue est donc possible. L'identifiant de proposition n'y figure pas : apparier sur l'application, le montant, le shortcode et l'heure.

## Limites d'appels

`RateLimit` sur `proposal_open_contract` a été reçu une fois, après deux lectures rapprochées et une vente, bien sous le quota documenté. **Cause non établie :** 30 lectures espacées de 0,5 à 2 s n'ont ensuite rien déclenché. Le premier essai s'était aussi interrompu sans que sa cause exacte soit prouvée. Décision : suivre les positions par abonnement, jamais par lectures répétées, et attendre après un `RateLimit`.
