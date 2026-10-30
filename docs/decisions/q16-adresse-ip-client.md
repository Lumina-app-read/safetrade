# Q16. Adresse IP réelle du visiteur

- **Statut :** décidé (topologie de production à mettre en place à l'étape 7.1)
- **Date :** 30 octobre 2026

## Constat (étape 1.6b)

En développement, le navigateur appelle `/api` sur le front-end Next.js, qui réécrit la requête vers le backend. Cette réécriture **n'ajoute pas** l'en-tête `X-Forwarded-For` : le backend voit l'adresse du conteneur front-end pour tous les visiteurs. Un en-tête `X-Forwarded-For` envoyé par le navigateur, lui, était transmis tel quel, donc usurpable.

## Décision

1. **Le front-end supprime les en-têtes d'adresse** (`X-Forwarded-For`, `X-Real-IP`, `Forwarded`) venant du navigateur sur `/api` (`frontend/src/proxy.ts`). L'usurpation est impossible.
2. **Le backend ne compte les échecs par adresse que pour une adresse publique** (`is_global`). Une adresse interne, partagée par tous, n'est jamais bloquée : personne ne peut bloquer la connexion de tous les utilisateurs. La limite par e-mail (5 échecs en 15 minutes) s'applique toujours.
3. **Production** : le reverse proxy HTTPS (section 4) envoie `/api/*` **directement au backend**, sans passer par Next.js, et remplace `X-Forwarded-For` par l'adresse réelle du client. Uvicorn n'accepte cet en-tête que du reverse proxy (`FORWARDED_ALLOW_IPS` égal à l'adresse du proxy, jamais `*`).

## Conséquences

- En développement, la liste des sessions affiche l'adresse interne du conteneur, et la limite par adresse IP est inactive. C'est attendu.
- À l'étape 7.1 : configurer le reverse proxy comme ci-dessus et tester que l'adresse réelle apparaît dans les sessions et dans le journal d'audit.
