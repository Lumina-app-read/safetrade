# Q18. Sorties dynamiques et calcul de rentabilité

- **Statut :** principes décidés par le propriétaire ; paramètres à valider par backtest (étape 3.6)
- **Date :** 31 octobre 2026
- **Remplace :** la clôture systématique « dès le moindre bénéfice » (sections 1 et 6, étape 3.7) et le gain net minimal de la section 7, qui devient un paramètre parmi d'autres

## Décision du propriétaire

Aucun objectif de gain universel : ni 0,10 USD, ni 1 USD, ni 2 USD. Le moteur laisse évoluer une position quand les conditions sont favorables et protège les bénéfices déjà acquis. Une position à +10 USD ne doit pas pouvoir finir à -50 USD. Tout paramètre est configurable et validé en backtest avant usage.

## Vocabulaire de calcul

Ces termes ont un sens unique dans le code, les tests et l'interface.

| Terme | Définition |
| --- | --- |
| Mise | Montant engagé (`buy_price`), perte maximale du contrat |
| Commission | Frais prélevés par Deriv sur la position |
| Gain brut | Mise × multiplicateur × variation du cours, avant commission |
| Gain net | Gain brut moins tous les frais, s'il est positif |
| Perte nette | Même calcul, s'il est négatif ; commission comprise, jamais supérieure à la mise |
| Risque R | Perte nette maximale prévue par le stop loss de la position |

Le résultat de référence est celui de Deriv : `sell_price - buy_price`, ou `profit` tant que la position est ouverte. Le calcul local sert à la décision, jamais à l'affichage d'un résultat définitif.

### Seuils de rentabilité

- **Variation qui rembourse les frais** : commission / (mise × multiplicateur). Exemple mesuré : 0,03 / (1 × 100) = 0,03 % sur V75.
- **Taux de réussite d'équilibre** : perte nette moyenne / (gain net moyen + perte nette moyenne). Il se calcule sur les moyennes réelles du backtest, frais compris.

Une stratégie n'est présentée comme rentable que si un backtest et un test en avant suffisamment longs, hors de l'échantillon d'optimisation et frais compris, le montrent. Sinon, l'interface et les rapports ne le disent pas.

## Logique de sortie proposée

Trois niveaux, du plus robuste au plus dépendant du moteur.

1. **Stop loss initial chez Deriv**, posé à l'ouverture : toujours présent, il vaut 1 R. Ne dépend pas de SafeTrade.
2. **Protection dynamique** : quand le gain net dépasse un seuil d'activation, le niveau de sortie suit le gain sans jamais reculer (cliquet).
3. **Sortie d'opportunité** : le moteur clôture si les conditions se dégradent (régime de marché, retournement) ; la limite haute reste ouverte par défaut.

Les distances ne sont pas des montants fixes. Elles dépendent de :

| Facteur | Rôle |
| --- | --- |
| Capital | Mise et R calculés en pourcentage du solde, plafonnés par la section 7 |
| Volatilité | Distance du suivi en multiple de la volatilité récente de l'instrument (par exemple ATR) |
| Commissions | Activation impossible tant que le gain net ne couvre pas les frais avec une marge |
| Risque accepté | Seuils exprimés en multiples de R : activation à a × R, sécurisation d'une fraction f du gain maximal atteint |
| Instrument | Jeu de paramètres par actif, chacun validé séparément |

Paramètres configurables, tous à calibrer en backtest : `activation_r`, `trail_volatility_mult`, `locked_fraction`, `min_net_over_fees`, `time_stop` facultatif. Aucune valeur par défaut n'est retenue à ce stade.

Exemple de la règle de protection, à titre d'illustration : avec R = 5 USD, `activation_r` = 1 et `locked_fraction` = 0,5, une position qui atteint +10 USD ne peut plus sortir sous +5 USD, tant que le mécanisme est actif.

## Ce que Deriv protège, ce qui dépend de SafeTrade

| Mécanisme | Exécuté par | Actif si SafeTrade est coupé |
| --- | --- | --- |
| `stop_loss` et `take_profit` en place | Deriv | Oui [doc, à confirmer en démo] |
| `stop_out` (perte de la mise) | Deriv | Oui |
| Déplacement par `contract_update` | Demandé par SafeTrade, conservé par Deriv | Le dernier niveau envoyé reste actif [à vérifier] |
| Stop loss remonté en zone de gain | Inconnu | [à vérifier] : possible seulement si Deriv l'accepte |
| Suivi du cours en continu, sortie d'opportunité | SafeTrade | **Non** |

Deriv ne documente pas de trailing stop natif sur les multiplicateurs [à vérifier]. Deux cas pour le niveau 2 :

- **Si Deriv accepte un stop loss en zone de gain** : à chaque palier, le moteur l'envoie par `contract_update`. Le gain sécurisé survit à une panne.
- **Sinon** : le moteur surveille et vend par `sell`. Le gain n'est alors protégé que tant que SafeTrade fonctionne ; seul un `take_profit` chez Deriv en assure une partie. Ce compromis devra être affiché clairement.

## Limites connues

Aucun mécanisme ne garantit le prix de sortie : un marché rapide peut dépasser un niveau [à vérifier en démo]. Une position à +10 USD reste exposée pendant l'intervalle entre deux mises à jour.
