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

### Version 7.7 — 2026-05-25

#### 🎯 Objectif
Mettre en place une page Help statique complète expliquant ISMaiLa et les permissions par profil

#### 📋 Modifications
- **Nouvelle vue** : views/help_view.py — 4 tabs informatifs
- **Navigation** : Intégration dans app.py (menu + page publique)
- **Contenu** :
  - Objectif & Vision : Explique ISMaiLa, son importance, workflow
  - Rôles & Permissions : Détail des 5 profils (Public, Contributeur, Validateur, Admin)
  - Guide par profil : Instructions personnalisées selon rôle connecté
  - FAQ : 8 Q&R sur délais, modifications, récompenses, catégorisation

#### 🔧 Détails Techniques
- Framework : Streamlit (st.tabs, st.expander)
- Détection profil : st.session_state.user
- Fichiers modifiés :
  - app.py (navigation + page publique)
  - views/help_view.py (nouveau, 416 lignes)

#### ✅ Résultat
- ✅ Page Help visible pour tous (connectés + publics)
- ✅ Contenu adaptatif par rôle
- ✅ FAQ couvre les cas courants
- ✅ Documentation de l'UX complète

---

### Version 7.6 — 2026-05-25

#### 🎯 Objectif
Ajouter filtres catégorie + statut dans toutes les vues et template digest personnalisable

#### 📋 Modifications
- **Filtres** : Sélecteurs catégorie + statut dans contributor, validator, admin, ai_categorization
- **Template digest** : Création config/digest_templates.py (templates default)
- **Admin notifications** : Sous-onglets "Envoi rapide" / "Personnaliser template"
- **Controller** : send_digest_to_all() accepte templates personnalisés
- **Utilitaires** : Script clean_db.py pour nettoyage manuel

#### 🔧 Détails Techniques
- Fichiers modifiés (7 fichiers, 231 insertions) :
  - controllers/admin_controller.py : send_digest_to_all signature étendue
  - views/admin_view.py : Notifications UI (100 lignes ajoutées)
  - views/ai_categorization_view.py : Selectbox statut + filtre query
  - views/contributor_view.py : Statut filter appliqué
  - views/validator_view.py : Rework filtres DB + helpers
  - config/digest_templates.py (nouveau, 76 lignes)
  - clean_db.py (nouveau, 16 lignes)
- Mapping statut : "En attente"→"en_attente", "Validée"→"valide", "Archivée"→"archive"

#### ⚠️ Notes
- Helper has_real_response/has_no_real_response utilisé partout
- Admin peut envoyer digest custom (mais mailer.send_pending_digest()call doit être étendu)
- Tests : 68 passed, 0 failures

#### ✅ Résultat
- ✅ Filtres statut/catégorie opérationnels
- ✅ UI Admin notifications améliorée
- ✅ Template digest prêt pour personnalisation

---

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

**Dernière mise à jour** : 2026-05-25
**Mainteneur** : Équipe ISMaiLa
