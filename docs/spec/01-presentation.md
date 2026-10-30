# SafeTrade - Cahier des charges

Oct 29, 2026 · @Clovis

## 1. Présentation du projet

SafeTrade est un SaaS de trading semi-automatique qui se connecte au compte Deriv de l'utilisateur, analyse le marché en continu, ouvre des positions et les clôture dès qu'un bénéfice net est réalisé, dans le cadre de limites de risque fixées par l'utilisateur.

**Objectifs**

- Permettre à un trader de déléguer l'analyse et l'exécution à un moteur, tout en gardant la main à tout moment.
- Imposer une discipline de money management et de gestion du risque que l'utilisateur ne peut pas contourner dans le feu de l'action.
- Générer des revenus récurrents par abonnement (essai de 3 jours, puis semaine, mois ou année) et par affiliation.

**Ce que SafeTrade est**

- Un outil d'aide à l'exécution connecté par API à un broker tiers (Deriv).
- Une application web (puis mobile) avec une interface client et une interface administrateur.

**Ce que SafeTrade n'est pas**

- Il ne détient, ne reçoit et ne gère jamais les fonds des utilisateurs : l'argent reste chez Deriv.
- Il ne promet aucun gain, ni garanti ni estimé. Chaque écran et chaque communication rappelle que le trading comporte un risque de perte en capital.

**Marchés visés**

Indices synthétiques Deriv (priorité), or (uniquement quand le marché est ouvert), Bitcoin et autres actifs exposés par le compte de l'utilisateur après connexion de son token.

