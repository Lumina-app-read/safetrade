## 2. Analyse du besoin

Le besoin est cohérent et réalisable, mais quatre points doivent être tranchés avant le développement car ils changent l'architecture ou le risque du produit.

**Points structurants**

- **Produit Deriv à cibler.** L'API Deriv (WebSocket) permet de trader des contrats (multiplicateurs, options, etc.) avec une mise en dollars, alors que la notion de lots relève plutôt de MT5. Le choix détermine le moteur d'ordres et le paramétrage « lots ». À confirmer avec la documentation officielle à jour.
- **Méthode d'authentification.** Le besoin cite le token personnel (PAT) et OAuth 2.0 selon la documentation Deriv. Le développeur doit valider les flux, les scopes (lecture, trading) et l'enregistrement de l'application sur la documentation en vigueur au moment du développement.
- **Clôture dès le moindre bénéfice.** Couper à 0,2 ou 0,3 dollar de gain produit beaucoup de petits gains. Sans stop loss ni limite de perte, quelques pertes isolées peuvent effacer des dizaines de gains, voire vider le compte. Le cahier des charges impose donc un stop loss obligatoire et des limites de perte (section 7).
- **Efficacité réelle de l'analyse.** Les indices synthétiques sont générés de façon pseudo-aléatoire : un avantage statistique durable est incertain. Le moteur et l'IA doivent être validés en démo avant toute ouverture au réel, et le discours commercial doit rester prudent.

**Risques**

| Domaine | Risque | Mesure |
| --- | --- | --- |
| Trading | Pertes d'utilisateurs, réclamations | Démo par défaut, avertissements, limites de risque non contournables, kill switch |
| Juridique | Réglementation des services financiers et de l'automatisation selon les pays visés ; conditions d'usage de l'API Deriv | Avis juridique avant lancement, conditions d'utilisation, clause de non-garantie |
| Technique | Coupure de connexion pendant une position ouverte | Reconnexion automatique, réconciliation des positions au redémarrage, alertes |
| Sécurité | Vol de tokens API | Chiffrement, scopes minimaux, révocation, journalisation (section 14) |
| Business | Dépendance à une seule API de broker | Couche d'abstraction broker dès le départ |

