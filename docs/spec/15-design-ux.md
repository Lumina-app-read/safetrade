## 15. Design et UX

Interface professionnelle, aérée, fine et affirmée.

**Typographie : Plus Jakarta Sans, hébergée sur le serveur**

| Élément | Taille | Graisse |
| --- | --- | --- |
| Titre de page (H1) | 28 px | 400 (Regular) |
| Titre de section (H2) | 22 px | 400 (Regular) |
| Sous-titre (H3) | 18 px | 500 (Medium) |
| Texte courant | 14 px | 400 (Regular) |
| Libellés, boutons, en-têtes de tableau | 13 px | 500 (Medium) |
| Petit texte, aides, horodatages | 12 px | 400 (Regular) |
| Chiffres clés (solde, profit) | 24 px | 500 (Medium) |

Aucune graisse supérieure à 500 dans l'interface. Pas de gros titres en gras ; la hiérarchie vient de la taille, de l'espacement et de la couleur.

**Emojis et icônes**

- Zéro emoji dans l'interface, avec une seule exception : l'emoji de salutation à côté de « Bonjour, {prénom} » sur le tableau de bord.
- Icônes modernes de type Lucide : trait de 1,5 px, taille de 20 px (16 px dans les tableaux).

**Mise en page**

- Grille d'espacement de 8 px ; marges internes de cartes de 24 px.
- Coins arrondis de 8 à 12 px ; bordures de 1 px de gris clair ; ombres très légères ou absentes.
- Une couleur d'accent unique ; vert et rouge réservés aux gains et pertes, toujours accompagnés d'un signe (+ ou -) ou d'une icône, jamais la couleur seule.
- Contraste de texte conforme WCAG AA (au moins 4,5 : 1).
- Thèmes clair et sombre sur toutes les pages (voir ci-dessous).
- Interface entièrement traduite en français et en anglais (voir ci-dessous).

**Couleurs : bleu clair professionnel**

La couleur d'accent est un bleu clair et sobre, inspiré de la capture de référence. Les codes ci-dessous sont des approximations à valider sur maquette ; chaque couple texte et fond doit atteindre un contraste d'au moins 4,5 : 1.

| Rôle | Thème clair | Thème sombre |
| --- | --- | --- |
| Accent principal (boutons pleins, liens, bandeau) | #1F6FDB | #5B9DF0 |
| Accent au survol | #1A5CB8 | #7AB1F4 |
| Accent très clair (fonds de badges, sélections) | #E8F1FD | #16263F |
| Fond de page | #F6F7F9 | #0B1220 |
| Fond des cartes et du menu | #FFFFFF | #111A2B |
| Bordures | #E5E7EB | #1F2A3D |
| Texte principal | #0F172A | #E6EAF2 |
| Texte secondaire | #64748B | #94A3B8 |
| Gain | #16A34A | #34D399 |
| Perte | #DC2626 | #F87171 |
| Avertissement | #D97706 | #FBBF24 |

Bouton d'action principal : fond sombre (#111827 en clair), texte blanc, comme sur la référence ; bouton d'accent bleu pour les actions de la page de trading.

**Référence visuelle : capture TestMonApp**

La capture sert de modèle pour l'apparence et la structure uniquement ; ni le logo, ni les textes, ni la marque ne sont repris. Éléments à reproduire :

- Barre supérieure sur fond blanc avec logo à gauche, menu central avec icônes, sélecteur de langue (drapeau et code) et profil à droite.
- En-tête de page : salutation « Bonjour, {prénom} » avec emoji, phrase d'accueil en petit texte gris, bouton d'action principal aligné à droite.
- Grand bandeau bleu d'accueil avec motifs circulaires discrets, accompagné d'une grille de cartes de statistiques (2 colonnes sur 2 lignes) et de cartes de raccourcis (parrainage, support).
- Titres de section en majuscules, petits et espacés ; tableaux avec en-têtes en majuscules, pastille de statut colorée et icônes d'action.
- Bouton d'assistance flottant en bas à droite.
- Version mobile : barre réduite avec menu hamburger, bandeau et cartes empilées en pleine largeur.

La règle de graisse maximale 500 reste prioritaire : la référence utilise des gras plus marqués, qui ne sont pas reproduits.

**Thèmes clair et sombre**

- Trois options dans le profil et dans la barre supérieure : clair, sombre, automatique (suit le système). Défaut : automatique.
- Disponibles sur toutes les pages sans exception : site public, espace client, page de trading, interface administrateur, pages de paiement propres à SafeTrade.
- Toutes les couleurs passent par des variables de thème (jetons de design) ; aucune couleur écrite en dur dans les composants.
- Le choix est enregistré dans le profil (côté serveur) et en local ; aucun flash de mauvais thème au chargement.
- Graphiques de prix, tableaux et icônes adaptés aux deux thèmes.
- Critère d'acceptation : chaque page contrôlée en clair et en sombre, aucun texte illisible, contraste AA respecté.

**Traduction complète : français et anglais**

- Langues autorisées dans la première version : français et anglais, et seulement celles-ci.
- Traduction totale, jamais partielle : pages publiques, espace client, page de trading, interface administrateur, messages d'erreur et de validation du backend, e-mails, notifications, factures et reçus, pages légales, avertissements de risque, explications générées par l'IA.
- Sélecteur de langue dans la barre supérieure ; langue par défaut déduite du navigateur, choix enregistré dans le profil.
- Aucun texte écrit en dur dans le code : tout passe par des fichiers de traduction ; le backend renvoie des codes d'erreur que le front-end traduit.
- Dates, nombres, devises et fuseaux horaires formatés selon la langue choisie.
- Pages publiques avec préfixe d'adresse par langue (/fr et /en) pour le référencement.
- Contrôle automatique à chaque livraison : la construction échoue si une clé existe dans une langue et pas dans l'autre.
- Architecture prête à accueillir d'autres langues plus tard sans modification du code.

