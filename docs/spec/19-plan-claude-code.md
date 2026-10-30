## 19. Plan de travail pour Claude Code

Le développement est réalisé par Claude Code, étape par étape. Il est interdit de demander l'application entière en une seule fois : chaque étape est petite, testée et validée par toi avant la suivante.

**Règles de travail**

1. Une étape = une session Claude Code = une branche Git = un livrable vérifiable. Taille cible : moins de 400 lignes modifiées hors tests et fichiers générés ; au-delà, l'étape est découpée.
2. Chaque session commence par lire le fichier CLAUDE.md et uniquement la section du cahier des charges concernée (voir le découpage ci-dessous).
3. Claude Code propose d'abord un plan (fichiers touchés, approche) et attend ta validation avant d'écrire du code.
4. Les tests s'écrivent avec le code. Une étape n'est terminée que si tests, vérification de types et lint passent.
5. Claude Code ne touche qu'à ce que l'étape demande : pas de refactorisation hors périmètre, pas de nouvelle dépendance sans justification écrite.
6. En cas de doute sur une exigence, Claude Code pose la question au lieu de deviner.
7. Les tests contre Deriv utilisent uniquement un compte démo. Aucun test automatisé n'utilise un compte réel.
8. Aucun secret (token, clé de paiement, mot de passe) n'est écrit dans le code, les tests ou Git : fichiers .env locaux non versionnés.
9. Le compte réel reste désactivé par un interrupteur de configuration jusqu'à la phase 8.

**Organisation du dépôt**

| Dossier | Contenu |
| --- | --- |
| backend/ | API FastAPI, moteur de trading, module de risque, IA, facturation, tests |
| frontend/ | Application Next.js, composants, thèmes, fichiers de traduction (fr, en) |
| infra/ | Docker Compose, configuration de déploiement, scripts de sauvegarde |
| docs/spec/ | Ce cahier des charges découpé en un fichier Markdown par section (01 à 21) |
| docs/decisions/ | Une courte note par décision d'architecture (produit Deriv, choix IA, etc.) |
| CLAUDE.md | Règles permanentes lues au début de chaque session |

**Contenu obligatoire de CLAUDE.md**

- Stack : FastAPI et Python, PostgreSQL, Redis, Next.js avec TypeScript, Tailwind.
- Règle d'or : le backend est la seule source de vérité ; le front-end n'envoie que des demandes et affiche les réponses.
- Règles de sécurité de la section 14, résumées en liste de contrôle.
- Règles de design de la section 15 : Plus Jakarta Sans, graisse maximale 500, zéro emoji sauf la salutation du tableau de bord, icônes Lucide, couleurs uniquement via les variables de thème.
- Règle de traduction : aucun texte en dur ; toute chaîne existe en français et en anglais.
- Commandes exactes pour lancer l'application, les tests, le lint et la vérification de types.
- Convention de nommage des branches (step/ID-nom-court) et des messages de commit.
- Liste des interdits : section 19, règles 5 à 9.

**Définition de « terminé » pour chaque étape**

- [ ] Le critère d'acceptation de l'étape est démontré (commande, capture ou test).
- [ ] Tests, types et lint passent en local et en intégration continue.
- [ ] Aucun texte non traduit, aucune couleur en dur, aucun secret dans le code.
- [ ] Les écrans touchés sont vérifiés en thème clair et en thème sombre, sur ordinateur et téléphone.
- [ ] Un commit clair sur une branche dédiée ; fusion dans main après ta validation.
- [ ] À la fin d'une phase : étiquette Git phase-N et courte note de bilan.

**Modèle de message à donner à Claude Code pour chaque étape**

```markdown
Étape {ID} : {titre}.
Lis CLAUDE.md et docs/spec/{fichier de la section concernée}.
Objectif : {objectif en une phrase}.
Hors périmètre : tout ce qui n'est pas listé dans les livrables.
Procède d'abord en mode plan : liste les fichiers que tu vas créer ou modifier et attends ma validation.
Puis implémente avec les tests. Termine par : tests, types et lint verts, résumé de ce qui a été fait, et démonstration du critère d'acceptation : {critère}.
```

