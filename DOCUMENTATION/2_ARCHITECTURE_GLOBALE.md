# 🏗️ Architecture Globale - ISMaiLa

## Vue d'ensemble du Système

ISMaiLa est une plateforme de gestion des connaissances basée sur Streamlit avec une architecture en couches :

```
┌─────────────────────────────────────────────────┐
│           INTERFACE UTILISATEUR (Streamlit)      │
│  ├─ student_view.py    (Chat Public)           │
│  ├─ admin_view.py      (Dashboard Admin)       │
│  ├─ validator_view.py  (Validation)            │
│  └─ contributor_view.py (Contributions)        │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│          COUCHE CONTRÔLEURS (Controllers)        │
│  ├─ auth_controller.py    → Authentification   │
│  ├─ kb_controller.py      → Base de connaissances
│  ├─ search_controller.py  → Recherche sémantique
│  ├─ mkt_controller.py     → Marketing/Leads    │
│  └─ admin_controller.py   → Administration     │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│           COUCHE SERVICES (Services)             │
│  ├─ db_connector.py    → MongoDB               │
│  ├─ nlp_engine.py      → Embeddings            │
│  ├─ llm_engine.py      → Ollama/LLM            │
│  ├─ ollama_service.py  → Intégration Ollama   │
│  ├─ mailer.py          → Emails SMTP           │
│  └─ sf_connector.py    → Salesforce Webhook   │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│         COUCHE DONNÉES & RESSOURCES              │
│  ├─ MongoDB (connaissances, users, leads)      │
│  ├─ survival_kit.json  (mode offline)          │
│  └─ Fichiers de configuration                  │
└─────────────────────────────────────────────────┘
```

---

## 🔄 Flux de Données

### 1. Flux : Question → Réponse (Chat Public)

```
Utilisateur pose question
         │
         ▼
    Student View
    (Interface)
         │
         ▼
    Search Controller
    • Tokenize question
    • Générer embedding NLP
    • Recherche sémantique MongoDB
         │
         ├─ Score NLP > 0.75 ?
         │  YES ─→ Retourner réponse + source
         │  NO ──→ Alerte Expert (mailer)
         │
         ▼
    Afficher réponse utilisateur
    + Log dans MongoDB
```

### 2. Flux : Capture Lead (RG-05)

```
Utilisateur pose 3 questions non résolues
         │
         ▼
    Marketing Controller
    (Compteur questions)
         │
    (3 questions = trigger)
         │
         ▼
    Afficher formulaire capture lead
         │
         ▼
    Lead enregistré MongoDB
         │
         ▼
    Webhook Salesforce
    (Store then Forward)
```

### 3. Flux : Contribution → Validation

```
Contributeur soumet réponse
         │
         ▼
    Contribution Controller
         │
         ▼
    Enregistrer dans MongoDB
    Status = "pending"
         │
         ▼
    Notifier validateurs
         │
         ▼
    Validateur examine
         │
    ├─ Accepter → Status = "approved"
    │           → Intégrer KB
    │           → Alerte email
    │
    └─ Rejeter  → Status = "rejected"
                → Notifier contributeur
```

---

## 👥 Modèle de Rôles & Accès

```
┌─────────────────┐
│   ADMINISTRATION │  → Accès total
├─────────────────┤
│   VALIDATEUR    │  → Valider contributions
├─────────────────┤
│   CONTRIBUTEUR  │  → Proposer des réponses
├─────────────────┤
│   ÉTUDIANT      │  → Chat
├─────────────────┤
│   PUBLIC (anon) │  → Chat + capture lead
└─────────────────┘
```

**Matrice d'accès détaillée dans LOGIQUE_METIER.md**

---

## 📊 Modèles de Données Principaux

### Model: User
```
{
  _id: ObjectId
  username: str (unique)
  email: str (unique)
  password_hash: str (bcrypt)
  role: Literal["admin", "validator", "contributor", "student", "anonymous"]
  created_at: datetime
  updated_at: datetime
  last_login: datetime
  is_active: bool
}
```

### Model: Lead
```
{
  _id: ObjectId
  name: str
  email: str
  company: str
  topic: str
  questions: List[str]
  timestamp: datetime
  source: str ("chat")
  sf_id: str (optional)  # Salesforce ID
  status: Literal["new", "processed", "closed"]
}
```

### Model: Contribution
```
{
  _id: ObjectId
  contributor_id: ObjectId (User)
  question: str
  answer: str
  category: str
  status: Literal["pending", "approved", "rejected"]
  validator_id: ObjectId (optional)
  validation_comment: str (optional)
  created_at: datetime
  updated_at: datetime
  score: float
}
```

---

## 🔐 Sécurité

- **Authentification** : bcrypt + sessions Streamlit
- **Base de données** : MongoDB avec authentification
- **Emails** : SMTP sécurisé
- **Secrets** : Variables d'environnement (.env, Streamlit secrets)
- **Souveraineté NLP** : Aucun appel externe pour embeddings

---

## 🌐 Intégrations Externes

### Salesforce
- **Type** : Webhook (Store then Forward)
- **Déclenchement** : Nouvel lead capture (RG-06)
- **Donnée** : Lead details
- **Reconnexion** : Queue locale en cas d'échec

### SMTP Email
- **Type** : Alertes
- **Utilisé pour** :
  - Alertes experts (score NLP < 0.75)
  - Notifications validation
  - Confirmations lead

### Ollama
- **Type** : LLM local
- **Utilisé pour** : Génération réponses, catégorisation
- **Mode fallback** : survival_kit.json si offline

---

**Dernière mise à jour** : 2026-05-23
**Version** : MVP 7 - Pilote V3
