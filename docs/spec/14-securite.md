## 14. Sécurité

La sécurité est une exigence non négociable : une fonctionnalité qui ne la respecte pas n'est pas livrable.

**Principes**

- Le backend est la seule source de vérité. Toute entrée du front-end est considérée comme non fiable et revalidée côté serveur.
- Moindre privilège : tokens Deriv aux scopes minimaux, rôles administrateur limités.

**Authentification et sessions**

- Mots de passe hachés avec Argon2id ou bcrypt, politique de mot de passe robuste.
- Double authentification (TOTP) proposée aux clients, obligatoire pour les administrateurs et pour activer le compte réel.
- Jetons de session de courte durée avec renouvellement, cookies HttpOnly, Secure et SameSite, liste des sessions actives et déconnexion à distance.
- Protection contre le brute force : limitation de débit, verrouillage progressif, alerte de connexion inhabituelle.

**Données et secrets**

- Tokens Deriv chiffrés au repos (AES-256-GCM avec clés gérées dans un coffre de secrets), jamais renvoyés au client ni écrits dans les journaux.
- Secrets (clés de paiement, clés IA) hors du code source, rotation possible.
- HTTPS partout, HSTS, chiffrement des sauvegardes.

**Application**

- Validation stricte de toutes les entrées (schémas Pydantic), requêtes SQL paramétrées.
- Contrôle d'accès vérifié à chaque requête (un client ne voit que ses propres données).
- Protection CSRF, en-têtes de sécurité, politique CSP, CORS restreint aux domaines de l'application.
- Limitation de débit par utilisateur et par adresse sur toutes les routes sensibles.
- Webhooks de paiement : signature vérifiée, idempotence, liste d'adresses autorisées si le fournisseur le permet.
- Ordres uniquement émis par le moteur backend après validation du module de risque ; verrou empêchant les doubles ordres.

**Exploitation**

- Journal d'audit non modifiable pour les actions sensibles, surveillance et alertes.
- Dépendances mises à jour et analysées régulièrement.
- Sauvegardes testées, plan de réponse à incident, test d'intrusion avant l'ouverture au compte réel.
- Protection des données personnelles : minimisation, droit de suppression, politique de confidentialité.

