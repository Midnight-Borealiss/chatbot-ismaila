# 📚 Description Détaillée des Modules

## 🏢 Structure des Dossiers

```
chatbot-ismaila/
├── DOCUMENTATION/       → Cette documentation
├── config/             → Configuration centralisée
├── controllers/        → Logique métier principale  
├── models/            → Structures Pydantic
├── services/          → Services techniques
├── views/             → Interfaces Streamlit
├── scripts/           → Utilitaires administration
├── tests/             → Tests unitaires
└── app.py             → Point d'entrée
```

---

## 📁 CONFIG/ - Configuration

### `settings.py`
**Responsabilité** : Centraliser les variables d'environnement et configuration
- Charger depuis `.env` ou Streamlit secrets
- Validations et defaults
- Logging centralisé
- Constantes globales

### `roles.py`
**Responsabilité** : Énumérations et constantes de rôles
- Définitions rôles utilisateur
- Niveaux d'accès
- Mappings permissions

### `permissions.py`
**Responsabilité** : Matrice d'accès fine
- Par module/action
- Par rôle
- Vérifications d'accès

### `categories.py`
**Responsabilité** : Référentiel **hiérarchique** des catégories (depuis v7.15)
- 4 catégories parentes × ~16 sous-catégories (tags fins) — `CATEGORY_HIERARCHY`
- Chaque sous-catégorie : `description` (ancre sémantique zero-shot) + `synonyms` (fast path)
- Helpers : `get_top_categories()`, `get_subcategories()`, `get_parent_category()`,
  `get_all_canonical()` (= sous-catégories), `normalize_category()`, `DEFAULT_CATEGORY`
- Remplace l'ancien référentiel plat (MBA, Bourses, Scolarité, Vie_Campus, Général)

---

## 🎮 CONTROLLERS/ - Logique Métier

### `auth_controller.py`
**Responsabilité** : Gestion authentification/autorisation

**Fonctions principales** :
- `hash_password()` → Hash bcrypt
- `verify_password()` → Vérification
- `check_login()` → Validation credentials
- `login()` → Création session

### `search_controller.py`
**Responsabilité** : Moteur recherche sémantique + RG-01

**Fonctions principales** :
- `seek_answer()` → Recherche sémantique (catégorise via `classify_category_full`)
- `_find_best_answer()` → Vector search Atlas, puis repli token
- `_vector_search()` → `$vectorSearch` sur `question_embedding` + post-filtre matriciel (`_matches_filter`)
- `_token_match()` → Repli léger (chevauchement de tokens)
- `get_session_history()` / `clear_session_history()` → Historique utilisateur

> Les tickets créés stockent `category` (sous-catégorie) **et** `parent_category`.

### `mkt_controller.py`
**Responsabilité** : Gestion leads + RG-05/06

**Fonctions principales** :
- `capture_lead()` → Enregistrer lead
- `get_lead_stats()` → Statistiques
- `resync_failed()` → Reconnexion Salesforce

---

## 🗂️ MODELS/ - Structures Pydantic

### `user.py`
Modèle utilisateur avec rôles et permissions

### `lead.py`
Modèle lead avec détails contact et historique

### `contribution.py`
Modèle contribution avec validation workflow

---

## 🔧 SERVICES/ - Couche Technique

### `db_connector.py`
Abstraction MongoDB avec fallback JSON

### `nlp_engine.py`
Moteur sémantique (Sentence-Transformers, chargement paresseux + cache)
- `embed(text)` → vecteur 384 dim (ou None si modèle indisponible)
- `classify_category(q)` / `classify_category_full(q)` → (sous-catégorie, parent)
- Hybride : fast path mots-clés (frontières de mots `\b` + accents + pluriels) puis
  sémantique zero-shot (ancres = descriptions des sous-catégories)
- Dégradation gracieuse : repli mots-clés si sentence-transformers/torch absents

### `llm_service.py`
Catégorisation LLM via HF Inference (Mistral-7B-Instruct). `VALID_CATEGORIES`
dérivé de la hiérarchie. Optionnel (nécessite `st.secrets["llm"]["api_token"]`).

### `mailer.py`
Alertes email SMTP

### `sf_connector.py`
Intégration Salesforce (RG-06 Store then Forward)

---

## 👁️ VIEWS/ - Interfaces Streamlit

### `student_view.py`
Chat public, historique, capture lead

### `admin_view.py`
Dashboard, gestion utilisateurs, rapports

### `validator_view.py`
Queue contributions, validation interface

### `contributor_view.py`
Soumission réponses, tracker contributions

### `user_dashboard_view.py`
Dashboard personnel. **Profil en lecture seule (figé pour le pilote)** : profils
et permissions pré-assignés par l'administration. Seul le changement de mot de
passe reste actif (`render_user_dashboard_view()` est le point d'entrée appelé par `app.py`).

### `qualification_view.py`
Formulaire d'auto-qualification **désactivé pendant le pilote**
(`QUALIFICATION_FORM_ENABLED = False`). Conservé pour réactivation post-pilote.

---

## 📜 SCRIPTS/ - Utilitaires administration

### `init_embeddings.py`
Génère `question_embedding` pour les contributions (modèle unifié, idempotent).
`--all` régénère tout, sinon seulement les manquants.

### `create_vector_index.py`
Crée/liste l'index Atlas Vector Search (`autoembed_index`, 384 dim, cosine).

### `recategorize_hierarchy.py`
Re-catégorise les contributions selon la hiérarchie (sous-catégorie + parent).
Dry-run par défaut, `--apply` pour écrire.

> `controllers/kb_controller.py` : `update_contribution()` génère automatiquement
> l'embedding de la question à la certification (`_ensure_question_embedding`).

---

**Dernière mise à jour** : 2026-06-08 (v7.15)
