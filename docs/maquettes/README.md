# Maquettes (étape 0.4)

Ouvrir [index.html](index.html) dans un navigateur. Une seule page interactive :

- 4 écrans : tableau de bord, page de trading, abonnement, administration ;
- thèmes clair, sombre et automatique (barre supérieure), sans flash au chargement ;
- français et anglais, nombres, dates et montants formatés selon la langue ;
- responsive : en dessous de 960 px, menu hamburger et cartes empilées.

Toutes les données sont fictives. Les boutons d'action montrent l'état d'attente de la confirmation du backend, puis rien d'autre : la maquette ne simule aucun succès.

## Contrôles effectués

- Les 4 écrans, en clair et en sombre, à 375 px de large : aucun débordement horizontal.
- Contraste WCAG calculé pour chaque couple texte et fond des jetons ci-dessous.

## Ajustements de couleurs proposés (question 9, à valider)

Les codes de la section 15 sont gardés pour les fonds, les remplissages, les pastilles et les graphiques. Plusieurs d'entre eux n'atteignent pas 4,5 : 1 **quand ils servent de couleur de texte**. La maquette utilise donc une variante de texte au plus près de l'original :

| Jeton | Code section 15 | Contraste mesuré | Variante de texte | Contraste |
| --- | --- | --- | --- | --- |
| Texte secondaire (clair), sur fond de page | #64748B | 4,44 | #5E6B80 | 5,04 |
| Gain (clair), sur carte | #16A34A | 3,30 | #15803D | 5,02 |
| Avertissement (clair), sur carte | #D97706 | 3,19 | #B45309 | 5,02 |
| Accent sur fond « accent très clair » (clair) | #1F6FDB | 4,23 | #1A5CB8 | 5,64 |
| Texte blanc sur accent (sombre) | #FFFFFF sur #5B9DF0 | 2,79 | #0B1220 sur #5B9DF0 | 6,71 |

Autres choix :

- **Bouton d'action principal en sombre** : #111827 est invisible sur le fond #0B1220. En thème sombre, il est inversé (fond #E6EAF2, texte #0B1220).
- **Sélecteur de langue** : un drapeau serait un emoji, ce que la règle « zéro emoji » interdit. La maquette utilise une icône globe suivie du code de la langue (FR, EN).
- **Logo** : simple pictogramme de bouclier sur l'accent, en attendant le logo définitif.

Tous les codes passent par des variables CSS (`:root` et `[data-theme="dark"]`) : les valider ou les changer ne touche aucun composant. Ils seront repris tels quels dans les jetons de design de l'étape 1.2.
