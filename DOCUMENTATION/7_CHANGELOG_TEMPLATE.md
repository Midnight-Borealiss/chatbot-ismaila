# 📝 Changelog - ISMaiLa

## Template pour Documenter les Modifications

Utilisez ce template à chaque modification importante du projet.

---

## Format Standard

```
### Version X.Y.Z — Date YYYY-MM-DD

#### 🎯 Objectif
Brève description du changement

#### 📋 Modifications
- **Module affecté** : Description changement
- **Module affecté** : Description changement

#### 🔧 Détails Techniques
- Fonction modifiée : old_signature() → new_signature()
- Dépendance ajoutée : package-name==version
- Migration BD : (si applicable)

#### ⚠️ Notes
- Points importants
- Changements breaking (si applicable)
- Actions manuelles requises (si applicable)

#### ✅ Tests
- Test X validé
- Cas d'usage Y fonctionnel
- RG-XX respectée
```

---

## Historique des Versions

### Version 7.6 — 2026-05-25

#### 🎯 Objectif
Refactoring majeur de l'architecture de la vue administration pour améliorer l'expérience utilisateur (UX) et optimiser les performances de requêtage MongoDB.

#### 📋 Modifications
- **views/admin_view.py** : Réduction drastique de la taille du fichier (externalisation des composants de rendu).
- **Interface Admin** : Fusion et passage de 5 à 4 onglets principaux avec sous-navigation horizontale par bouton radio.
- **Dossier DOCUMENTATION** : Mise à jour de la documentation d'architecture d'interface utilisateur et de la logique métier.

#### 🔧 Détails Techniques
- `render_admin_view()` : Restructuration complète de la table des onglets Streamlit (indices 0 à 3).
- Implémentation des fonctions privées de rendu modulaire : `_render_pending_questions()`, `_render_users_list_and_creation()`, et `_render_digests_and_logs_subtab()`.

#### ⚠️ Notes
- Aucun changement disruptif (Non-breaking change) sur la base de données.
- Amélioration de la sécurité : l'onglet de configuration du Digest et le journal de sécurité admin sont désormais consolidés sur la même vue d'accès restreint.

#### ✅ Tests
- ✅ Interface Streamlit fluide sans erreur `IndexError` sur les onglets.
- ✅ Isolement des états de formulaires préservé grâce à l'utilisation de clés uniques (`key=`).

### Version 7.5 — 2026-05-24

#### 🎯 Objectif
Nettoyer placeholders "En attente" polluant la base de données

#### 📋 Modifications
- **Database** : Suppression 166 documents avec placeholders
  - 70 × "En attente"
  - 96 × "En attente de réponse admin..."
- **SearchController** : Nouvelles questions créées avec response=""
- **Scripts** : Ajout cleanup_placeholders.py réutilisable

#### 🔧 Détails Techniques
- Méthode : `update_many()` MongoDB remplaçant placeholders par ""
- Fichiers modifiés :
  - controllers/search_controller.py (2 méthodes)
  - scripts/cleanup_placeholders.py (nouveau)

#### ⚠️ Notes
- Les questions créées avant v7.5 avaient des placeholders polluant les données
- Script cleanup_placeholders.py peut être ré-exécuté pour futures données
- Pas de breaking change

#### ✅ Résultat
- ✅ 166 documents nettoyés
- ✅ Filtrage "Avec proposition" désormais exact
- ✅ Admin voit uniquement vraies propositions

---

### Version 7.4 — 2026-05-24

#### 🎯 Objectif
Corriger détection fausses réponses dans filtres

#### 📋 Modifications
- **Bug fix** : Questions avec placeholder comptées comme répondues
- **Helper** : Création config/response_helpers.py centralisé
- **Vues** : validator_view.py, contributor_view.py, admin_view.py
- **Contrôleurs** : admin_controller.py (2 méthodes)

#### 🔧 Détails Techniques
- Nouveau helper : `has_real_response(response: str) -> bool`
- Placeholders définis : "En attente", "En attente de réponse admin...", ""
- Remplace logique dupliquée dans 5 fichiers
- Méthodes affectées :
  - AdminController.send_digest_to_all()
  - AdminController.get_filtered_pending()

#### ⚠️ Notes
- BREAKING: Filtres maintenant plus stricts
- Questions "En attente..." ne sont plus comptées comme propositions
- Code plus maintenable via helper centralisé

#### ✅ Résultat
- ✅ Filtrage "Sans réponse" identifie correctement les questions vides
- ✅ Filtrage "Avec proposition" ne voit que vraies réponses
- ✅ Admin_controller précis

---

### Version 7.3 — 2026-05-23

#### 🎯 Objectif
Initialisation structure de documentation complète

#### 📋 Modifications
- **Documentation** : Création 7 fichiers doc
- **Dossier** : Créé dossier `/DOCUMENTATION` dans chatbot-ismaila
- **Templates** : Changelogs, architectures, guides

#### 🔧 Détails Techniques
- Langues supportées : Français/Anglais
- Format : Markdown (.md)
- Localisation : `/chatbot-ismaila/DOCUMENTATION/`

#### ✅ Statut
- ✅ Documentation initiale complète
- ✅ Prêt pour production
- ✅ Évolutif

---

### Version 7.10 — 2026-05-26

#### 🎯 Objectif
Créer un dashboard personnel pour chaque utilisateur affichant ses permissions, son historique d'actions et ses notifications. Interface unifiée accessible à tous les rôles.

#### 📋 Modifications
- **views/shared_dashboard_components.py** (NEW, 620 lignes) : Composant réutilisable `render_user_profile_metrics()` avec 3 onglets
- **views/user_dashboard_view.py** (NEW, 35 lignes) : Vue Streamlit pour afficher le dashboard
- **app.py** : Ajout menu "📊 Mon Dashboard" en premier item + router
- **DOCUMENTATION/8_MONGODB_DASHBOARD_SCHEMA.md** (NEW) : Schéma complet des collections
- **DOCUMENTATION/9_GUIDE_DASHBOARD_UTILISATEUR.md** (NEW) : Guide utilisateur complet
- **DOCUMENTATION/6_FONCTIONS_PRINCIPALES.md** : Mise à jour avec v7.10

#### 🔧 Détails Techniques
- Collections MongoDB nouvelles : `user_audit_logs`, `user_notifications`
- Indexes : (user_email, timestamp DESC), (recipient_email, created_at DESC)
- Helpers : `render_user_profile_metrics()`, `create_notification()`, `log_action()`
- Timestamps relatifs intelligents : "À l'instant", "Il y a 5m", "Il y a 2h", etc.
- Emojis par type d'action : 🔓 LOGIN, ❓ QUESTION, ✍️ CONTRIBUTION, ✅ VALIDATED, etc.
- Intégration services/audit_service.py (déjà créé v7.9)

#### 🎨 Interface
3 onglets du dashboard :
1. **🛡️ Mes Permissions** : Badges des droits + domaines d'expertise
2. **📜 Historique de mes actions** : Tableau filtrable + stats
3. **🔔 Mes Notifications** : Flux notifications (lues/non-lues)

Composants Streamlit : st.columns, st.dataframe, st.expander, st.status, st.metric

#### ⚠️ Notes
- Chaque utilisateur ne voit que son propre dashboard
- Accessible à TOUS les rôles : SUPER_ADMIN, ADMINISTRATION, VALIDATEUR, CONTRIBUTEUR, ETUDIANT
- Permissions affichées selon `config/roles.py` et `config/permissions.py`
- Domaines d'expertise depuis `domain_permissions` ou `expert_topics` (legacy)

#### ✅ Tests
- ✅ Syntaxe Python validée (py_compile)
- ✅ Imports vérifiés
- ✅ Git push réussi (commit 8dc50cf)
- ✅ Collections MongoDB schema documenté
- ✅ Composant réutilisable validé

---

## Guide de Versioning

### Format de Version
`MAJOR.MINOR.PATCH`

- **MAJOR** (7.x.x) : Changements architecture/fondamentaux
- **MINOR** (x.3.x) : Features nouvelles
- **PATCH** (x.x.1) : Bug fixes

### Quand Documenter
✅ **Documenter** :
- Nouvelle feature
- Changement architecture
- Modification règle métier
- Changement dependencies
- Migration DB

---

**Dernière mise à jour** : 2026-05-24
**Mainteneur** : Équipe ISMaiLa
