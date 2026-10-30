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

## Couleurs

Identité **rouge et anthracite** : rouge `#D6041D`, anthracite `#202329`, mesurés sur le logo (hypothèse, pas de charte officielle). Jetons complets, contrastes mesurés et règles d'usage : [q13-identite-visuelle.md](../decisions/q13-identite-visuelle.md). La première version bleue de ces maquettes (section 15) est abandonnée.

Autres choix :

- **Bandeau d'accueil** anthracite avec motifs rouges, comme le logo, plutôt qu'un grand aplat rouge.
- **États neutres** (bot en analyse, position ouverte) en pastille neutre, jamais en rouge, pour ne pas se confondre avec une perte.
- **Bouton d'action principal** anthracite en thème clair, inversé (clair sur sombre) en thème sombre.
- **Sélecteur de langue** : un drapeau serait un emoji, ce que la règle « zéro emoji » interdit. La maquette utilise une icône globe suivie du code de la langue (FR, EN).
- **Logo** : pictogramme provisoire ; le logo source est dans [docs/brand](../brand/).

Tous les codes passent par des variables CSS (`:root` et `[data-theme="dark"]`).
