# Q13. Identité visuelle : rouge et anthracite

- **Statut :** décidé pour le principe (rouge et anthracite) ; codes exacts en **hypothèse**
- **Date :** 30 octobre 2026
- **Remplace :** l'accent bleu de la section 15 et la proposition bleue de [q09](q09-couleurs.md)

## Décision du propriétaire

La couleur principale de SafeTrade est le rouge de son identité actuelle, associé à l'anthracite, dans les thèmes clair et sombre. Pas de nouvelle identité bleue, pas de rouge sang, pas de changement arbitraire de la teinte.

## Source et méthode

Seule ressource disponible : [logo-safetrade-source.png](../brand/logo-safetrade-source.png), une image matricielle avec halo lumineux, sans code couleur officiel. Les valeurs ont été mesurées sur les aplats, hors halo :

| Zone du logo | Valeur mesurée |
| --- | --- |
| Lettres « Trade », faces ombrées du « S » | #D6041D (médiane) |
| Faces éclairées du « S » | #F50A24 |
| Découpes du « S » | #202329 |
| Lettres « Safe » | #15191C |

**Hypothèse retenue, non officielle :** rouge de marque `#D6041D`, anthracite `#202329`. À remplacer par les codes de la charte graphique si elle existe (fichier vectoriel ou guide de marque).

## Jetons de couleur

Le rouge de marque est le même remplissage dans les deux thèmes. Une variante plus claire de la même teinte sert uniquement au **texte** rouge en thème sombre, où `#D6041D` n'atteint pas le contraste AA (3,45 sur la carte sombre).

| Rôle | Clair | Sombre |
| --- | --- | --- |
| Accent (boutons pleins, sélection) | #D6041D, texte blanc (5,39) | #D6041D, texte blanc (5,39) |
| Accent au survol | #B80318 | #B80318 |
| Accent comme texte (liens, onglet actif) | #B80318 (6,85) | #FF3B4E (4,82) |
| Accent très clair (fonds de badges) | #FDE8EA | #3A1418 |
| Anthracite (bouton principal, bandeau) | #202329, texte blanc (15,74) | #202329 sur fond #111316 |
| Fond de page | #F5F6F7 | #111316 |
| Fond des cartes et du menu | #FFFFFF | #1A1D21 |
| Bordures | #E4E6E9 | #2A2F36 |
| Texte principal | #15191C | #ECEEF1 |
| Texte secondaire | #5C636E (6,06) | #9AA1AC (6,50) |
| Gain | #15803D | #34D399 |
| Perte | #B91C1C | #F87171 |
| Avertissement | #B45309 | #FBBF24 |

Contrastes mesurés selon WCAG 2.x, sur la carte : tous les couples texte et fond dépassent 4,5 : 1.

## Conséquences

- **Rouge de marque et pertes.** Les deux sont rouges. La règle de la section 15 s'applique donc strictement : une perte est toujours affichée avec son signe « - » et une icône, jamais par la couleur seule. La perte utilise un rouge plus sombre (`#B91C1C`) que la marque. Dans les tableaux de résultats, l'accent n'est pas utilisé comme décoration.
- Le bandeau d'accueil est anthracite avec des motifs rouges, comme le logo, plutôt qu'un grand aplat rouge, qu'on lirait comme une alerte sur une plateforme de trading.
- Tous les codes passent par les variables de thème : remplacer l'hypothèse par les codes officiels ne touche aucun composant.
