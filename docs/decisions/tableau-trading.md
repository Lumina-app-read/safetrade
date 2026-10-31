# Tableau de trading (étapes 2.4, 2.6, 3.3, 3.8)

Compte démo uniquement. L'interface ne contient aucune règle de trading : elle envoie des demandes et affiche ce que renvoie l'API.

## Choix

- **Graphique :** `lightweight-charts` (Apache 2.0). Bougies en direct, réticule, zoom tactile et échelle de prix auraient demandé un moteur de graphique maison. La licence impose l'attribution : le logo TradingView reste affiché.
- **Prix en direct :** SSE (`/market/stream`). Une coupure n'est annoncée qu'après 5 s, car le serveur ferme volontairement le flux toutes les 5 minutes.
- **État du bot et positions :** lecture de l'API toutes les 2 s, en pause quand la page est cachée. Ce n'est pas un flux poussé ; le passage à SSE reste possible sans changer l'interface.
- **Évolution d'une position :** valeurs reçues depuis l'ouverture de la page, non conservées. L'historique complet d'une position n'est pas enregistré.
- **Signal de vie :** le moteur écrit `heartbeat_at` et `deriv_connected` toutes les 5 s. Au-delà de 20 s de silence, l'API répond `engine_online: false`.

## Risque

- `risk.SLIPPAGE_MARGIN` = 15 % : la marge de perte restante compte le stop plus le glissement. Mesuré en démo : jusqu'à 12 %, sur quelques contrats. **À revoir sur un grand échantillon.**
- Les protections (activation, niveau conservé, perte prévue) sont calculées par l'API.
- `multiplier`, `activation_r` et `locked_fraction` restent **provisoires, non optimisés** : l'écran de paramètres le dit.
- Deriv ne peut pas être déconnecté ni changé pendant qu'un bot est actif (`deriv.bot_active`).
- Le compte réel apparaît verrouillé, sans solde affiché, et reste refusé par l'API et le moteur.

## Essais réels (31 octobre 2026, compte démo)

| Scénario | Résultat |
| --- | --- |
| Connexion Deriv : jeton vide, jeton refusé | Erreurs sous le champ et traduites |
| Paramètre hors plage, enregistrement | Refus sous le champ ; fuseau du navigateur enregistré |
| Démarrer, pause, reprendre | État confirmé par le moteur |
| Position réelle, signal forcé | Résultat net, protections, lignes d'entrée et de stop sur le graphique |
| Clôture depuis l'interface | Vente chez Deriv, +0,10 fictif, historique et journal à jour |
| Plancher en cours de position | Refusé une fois, puis posé |
| Arrêt d'urgence avec confirmation | Session terminée |
| Marché fermé (or) | Signalé, démarrage bloqué |
| Worker de marché arrêté | `Prix figés`, moteur : `market.stale`, reprise seule |
| Moteur arrêté | Alerte après 20 s, reprise et réconciliation seules |
| API arrêtée | Alerte, dernières données conservées, reprise sans recharger |

## Vérifications restantes

- **Test de stabilité de 24 heures (2.6) : non exécuté.**
- **Endurance de 72 heures (3.9) : non exécutée.**
- Banc d'essai et calibrage des protections dynamiques (3.6) : non faits. Aucune performance n'est présentée comme une promesse.
- Glissement sur un grand échantillon, or marché ouvert.
- Tailles 375 et 430 px non contrôlées une à une pour cet écran. Les captures du navigateur intégré étant réduites, le rendu visuel reste à juger sur un vrai téléphone.
