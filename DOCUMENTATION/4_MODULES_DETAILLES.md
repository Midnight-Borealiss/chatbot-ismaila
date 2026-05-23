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
**Responsabilité** : Catégories de connaissances
- Liste domaines
- Mappings experts par domaine
- Métadonnées catégories

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
- `seek_answer()` → Recherche sémantique
- `get_session_history()` → Historique utilisateur
- `clear_session_history()` → Réinitialiser historique

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
Embeddings et classification (Sentence-Transformers)

### `llm_engine.py`
Intégration Ollama pour génération texte

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

---

**Dernière mise à jour** : 2026-05-23
