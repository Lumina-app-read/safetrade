# Moteur de trading (phase 3, bloc moteur)

Démo uniquement. Le compte réel reste refusé à quatre niveaux : API de démarrage, module de risque, `otp_url`, interrupteur de configuration.

## Architecture

| Élément | Rôle |
| --- | --- |
| `safetradev2-engine` (`app/trading/worker.py`) | Seul processus qui émet des ordres. Une boucle par session, sous bail Redis par compte |
| `app/trading/router.py` | L'API enregistre des demandes ; elle ne parle jamais à Deriv pour trader |
| `app/trading/risk.py` | Limites de la section 7, fonctions pures |
| `app/trading/execution.py` | Ouverture, clôture, réconciliation |
| `app/trading/exits.py` | Plancher et cliquet (q18), fonctions pures |
| `app/trading/strategy.py` | Stratégie v1, déterministe, **non présentée comme rentable** |
| `app/trading/bot.py` | Machine d'états |

## Garanties sur les ordres

- Position écrite en base avant tout envoi. Index unique : un seul ordre en attente par compte, même après un redémarrage.
- Date d'envoi enregistrée avant l'achat : `sent_at` vide signifie « jamais parti ».
- Issue inconnue : position `unknown`, aucune autre tentative, lecture de `statement`. Contrat trouvé : adopté. Absent après 20 s : annulé.
- Bail relu juste avant l'achat : un moteur remplacé n'achète plus.
- Avant toute décision après un démarrage ou une coupure : réconciliation. Un contrat inconnu appartient au client : il est tracé et jamais touché.
- Journal `trading_decisions` en ajout seul, avec déclencheurs PostgreSQL.

## États ajoutés à la section 6

`stopping` : plus d'entrée, gestion des positions jusqu'à leur clôture, puis `stopped`. L'arrêt normal laisse les positions se clôturer sous protection (q06), l'arrêt d'urgence les vend.

## Essais réels sur compte démo (31 octobre 2026)

Contrats de 1 USD fictif, `1HZ100V`, ×400, signal forcé. **Échantillon de quelques contrats : aucune conclusion de performance.**

| Scénario | Résultat |
| --- | --- |
| Ouverture avec stop loss, contrôles marché et risque réels | OK |
| Stop loss exécuté chez Deriv et enregistré | OK, -0,50 à -0,55 pour un stop de 0,50 |
| Réponse d'achat perdue | Retrouvée dans `statement`, 2 achats sur 2 attendus, aucun doublon |
| Plancher en cours de position | **Refusé à 0,21 malgré « 0,21 ou plus »**, accepté à 0,22 |
| Moteur coupé pendant une position sous plancher | Clôturée par Deriv à -0,24 au lieu de -0,50, enregistrée à la reprise |
| Redémarrage avec position ouverte | Position reprise, puis clôture manuelle exécutée |
| Trois pertes de suite | Pause automatique |
| Arrêt d'urgence | Vente, session terminée, 0 contrat restant |

## Constats

- Minimum du stop arrondi à l'affichage : le moteur monte d'un cent après chaque refus, sans jamais dépasser le stop en place.
- Glissement mesuré au stop : jusqu'à 0,05 USD sur 0,50. La marge de perte restante en tient compte (`SLIPPAGE_MARGIN`, 15 %), voir [tableau-trading.md](tableau-trading.md).
- Multiplicateur par défaut, `activation_r` et `locked_fraction` : provisoires, à calibrer par backtest (q18).

## Pas encore fait

- Banc d'essai sur bougies historiques, puis calibrage.
- Plafonds modifiables par l'administrateur (5.5).
- Notifications (3.9) : aujourd'hui, journaux et base uniquement.
- Reconfirmation et double authentification pour le compte réel (phase 8).
- Endurance de 72 heures (3.9) et test de stabilité de 24 heures (2.6) : **non exécutés**.

## Démarrage sans identifiant Deriv

En développement, le moteur démarre sans `SAFETRADE_DERIV_APP_ID` et reste inactif, avec l'avertissement `trading.no_app_id` : une installation neuve depuis `infra/.env.example` doit démarrer, et la CI en dépend. Hors développement, il refuse de démarrer.
