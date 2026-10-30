## 16. Exigences non fonctionnelles, tests et déploiement

**Objectifs mesurables (valeurs proposées)**

| Critère | Cible |
| --- | --- |
| Affichage d'un tick côté client après réception chez Deriv | moins de 500 ms (95e percentile) |
| Décision du moteur puis envoi de l'ordre, hors délai Deriv | moins de 300 ms (95e percentile) |
| Temps de réponse des API standard | moins de 300 ms (95e percentile) |
| Disponibilité mensuelle | 99,5 % minimum |
| Capacité de lancement | 2 000 comptes, 300 bots actifs simultanément |
| Perte de données maximale (RPO) | 1 heure |
| Reprise après sinistre (RTO) | 4 heures |
| Sauvegardes | Quotidiennes complètes, journal de transactions continu, test de restauration mensuel |

**Tests**

- Tests unitaires : couverture d'au moins 80 % sur le code global et 100 % sur les règles du module de risque.
- Tests d'intégration sur un compte démo Deriv : connexion, ordres, clôture, reconnexion, réconciliation.
- Tests de paiement en mode test de Chariow et NOWPayments : succès, échec, expiration, webhook en double.
- Test de charge à 1,5 fois la capacité de lancement.
- Test d'endurance du moteur en démo pendant 14 jours consécutifs sans incident bloquant avant tout accès au réel.
- Test d'intrusion par un tiers avant l'ouverture du compte réel.

**Déploiement**

- Trois environnements : développement, préproduction, production.
- Intégration et déploiement continus avec tests automatiques bloquants.
- Supervision : journaux centralisés, métriques, alertes en cas d'erreur de moteur, de webhook en échec ou de latence dépassée.
- Mentions légales, conditions d'utilisation, politique de confidentialité et avertissement de risque publiés avant le lancement.

