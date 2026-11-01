# Images de la page publique

La page d'accueil prévoit **trois emplacements**. Tant qu'un fichier manque, la page affiche une composition d'interface dessinée en CSS : rien n'est cassé ni vide.

## Remplacer une image

1. Déposer le fichier dans ce dossier (`frontend/public/images/`) sous le **nom exact** de l'emplacement.
2. Extensions acceptées : `.webp` (recommandé), `.png`, `.jpg`, `.jpeg`, `.svg`. Si plusieurs fichiers portent le même nom, l'ordre de priorité est celui de cette liste.
3. Reconstruire le front-end, car les images sont détectées au build :
   `docker compose -f infra/docker-compose.yml --env-file infra/.env up -d --build frontend`

Aucune modification de code n'est nécessaire.

## Emplacements

| Fichier | Section | Proportions | Taille conseillée | Contenu conseillé |
| --- | --- | --- | --- | --- |
| `hero.webp` | Hero, à droite du titre (au-dessus sur téléphone) | 16:10 | 1600 × 1000 px | Capture de l'interface de trading ou visuel produit, fond sombre de préférence |
| `platform.webp` | Fonctionnalités, visuel d'ensemble | 16:10 | 1600 × 1000 px | Tableau de bord sur ordinateur et téléphone |
| `security.webp` | Risque et sécurité, sur fond anthracite | 4:3 | 1200 × 900 px | Illustration de protection ou capture des réglages de risque |

## Recommandations

- Moins de 300 Ko par image (WebP, qualité 80).
- Les images sont affichées avec des coins arrondis de 16 px et recadrées pour respecter les proportions.
- Toute capture contenant des chiffres doit montrer la mention « Données de démonstration » ou des données réelles et vérifiables. Jamais de performance simulée présentée comme réelle.
- Le texte alternatif de chaque image est traduit dans `src/messages/{fr,en}.json` (clés `landing.images`).

## Icône de l'application

Source du propriétaire : `public/icons/icon.png`, 1920 × 1920 px, coins transparents. Elle servira à l'écran de démarrage de la future application.

Le logo du site reste le composant `Logo`, qui s'adapte à toutes les tailles. L'icône ne sert qu'au navigateur et aux téléphones : `src/app/favicon.ico` (16, 32 et 48 px), `src/app/icon.png` (192 px) et `src/app/apple-icon.png` (180 px, sans transparence, car iOS la peindrait en noir). Ces trois fichiers sont déclinés de la source : les refaire si elle change.
