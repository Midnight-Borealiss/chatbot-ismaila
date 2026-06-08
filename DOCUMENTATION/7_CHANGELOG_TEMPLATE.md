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

### Version 7.15 — 2026-06-08

#### 🎯 Objectif
1. Figer les profils admin pendant le pilote (désactiver l'auto-qualification).
2. Rétablir une vraie compréhension sémantique via MongoDB Atlas Vector Search.
3. Catégorisation fine via une taxonomie hiérarchique (4 parents × ~16 sous-catégories).

#### 📋 Modifications
- **views/qualification_view.py** : auto-qualification désactivée (`QUALIFICATION_FORM_ENABLED = False`).
- **views/user_dashboard_view.py** : profil en lecture seule + restauration de `render_user_dashboard_view()` + écriture du mot de passe dans `password_hash`.
- **config/categories.py** : référentiel hiérarchique `CATEGORY_HIERARCHY` (remplace le plat).
- **services/nlp_engine.py** : embeddings (sentence-transformers) + `classify_category_full()`, matching mots-clés robuste.
- **controllers/search_controller.py** : `$vectorSearch` Atlas + post-filtre + repli token ; stockage `parent_category`.
- **controllers/kb_controller.py** : auto-embedding à la certification.
- **services/llm_service.py** : `VALID_CATEGORIES` dérivé de la hiérarchie.
- **config/settings.py** : `EMBEDDING_MODEL_NAME`, `EMBEDDING_DIM`, `VECTOR_INDEX_NAME`.
- **scripts/** : `init_embeddings.py` (refonte), `create_vector_index.py` (NEW), `recategorize_hierarchy.py` (NEW).
- **services/audit_service.py** + **tests/test_search_controller.py** : réparation suite de tests.

#### 🔧 Détails Techniques
- Modèle d'embedding : `paraphrase-multilingual-MiniLM-L12-v2` (384 dim, cosine), index Atlas `autoembed_index`.
- `seek_answer()` : `classify_category_full()` → (sous-catégorie, parent) ; matching via `_find_best_answer` (`_vector_search` → `_token_match`).
- Migration BD : 288 contributions ré-embeddées (`question_embedding`) et re-taguées (`category` + `parent_category`).

#### ⚠️ Notes
- BREAKING : l'ancien référentiel plat (MBA, Bourses, Scolarité, Vie_Campus, Général) est remplacé.
- Action manuelle : relancer `scripts/init_embeddings.py` / `scripts/recategorize_hierarchy.py` après un import massif de contributions (sinon repli token en attendant).
- Le module `ollama_service.py` n'existe pas ; la catégorisation LLM passe par `llm_service.py` (HF).

#### ✅ Tests
- ✅ Suite complète : **87 tests passent** (0 erreur).
- ✅ Recherche sémantique validée sur paraphrases (ex. « blazer » ↔ « veste », score 0.86).
- ✅ RG-01 / RG-03 / RG-05 préservées.

---

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

### Version 7.11 — 2026-05-27

#### 🎯 Objectif
1. Intégrer logging d'audit (LOGIN/LOGOUT) dans auth_controller pour traçabilité complète
2. Valider toutes les features en staging avant déploiement production

#### 📋 Modifications
- **controllers/auth_controller.py** : Ajout logging LOGIN/LOGOUT via audit_instance
- **services/audit_service.py** (NEW) : Service d'audit logging (créé en v7.9, maintenant commité)
- **services/notification_service.py** (NEW) : Service notifications (créé en v7.9, maintenant commité)
- **scripts/validate_staging.py** (NEW) : Suite de tests de validation complète
- **tests/test_audit_integration.py** (NEW) : Tests intégration LOGIN/LOGOUT

#### 🔧 Détails Techniques
- `login()` : Log action LOGIN après authentification réussie
- `logout()` : Log action LOGOUT avant déconnexion
- Gestion d'erreurs : Non-bloquant (déconnexion réussit même si log échoue)
- Audit trail complet : login → [actions] → logout
- Services audit_service et notification_service finalement commités après création v7.9

#### ✅ Tests de Staging (TOUS PASS)
1. **MongoDB Connection** - PASS ✅
2. **Audit Logging** - PASS ✅ (4 actions: LOGIN, QUESTION, CONTRIBUTION, LOGOUT)
3. **Role Hierarchy** - PASS ✅ (7/7 tests de rôles)
4. **Permissions by Role** - PASS ✅
5. **Notifications System** - PASS ✅
6. **Dashboard Components** - PASS ✅ (helpers, timestamps, emojis)

Résultat : **6/6 TESTS PASSED** - Prêt pour production ✅

#### 🐛 Correction
- Résout ModuleNotFoundError sur Streamlit Cloud (audit_service.py, notification_service.py manquaient)

#### ⚠️ Notes
- Chaque action utilisateur créée une trace audit
- Permet réconstruction complète de la session utilisateur
- Historique visible dans Mon Dashboard → Historique
- Tests exécutables via `python scripts/validate_staging.py`

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

**Dernière mise à jour** : 2026-06-08 (v7.15)
**Mainteneur** : Équipe ISMaiLa
