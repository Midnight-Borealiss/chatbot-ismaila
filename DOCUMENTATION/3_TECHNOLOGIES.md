# ⚙️ Technologies et Stack Technique

## 📋 Overview

ISMaiLa est construite avec un stack **Python moderne** centré sur la productivité et la souveraineté des données.

---

## 🐍 Stack Backend

### Framework Principal
| Technologie | Version | Usage | Raison |
|-------------|---------|-------|--------|
| **Streamlit** | Latest | Interface web UI | Rapid prototyping, UI moderne |
| **Python** | 3.9+ | Runtime | Écosystème ML/NLP riche |

### Base de Données
| Technologie | Version | Usage |
|-------------|---------|-------|
| **MongoDB** | 4.4+ | Données persistantes |
| **JSON local** | N/A | Fallback offline |

### IA & ML
| Technologie | Version | Usage | Raison |
|-------------|---------|-------|--------|
| **Sentence-Transformers** | 3.0+ | Embeddings NLP (encodage requête/contributions) | Souveraineté (local) |
| **paraphrase-multilingual-MiniLM-L12-v2** | - | Modèle embedding (384 dim) | Multilingue FR, ~470MB |
| **MongoDB Atlas Vector Search** | - | Recherche sémantique (`$vectorSearch`) | Index vectoriel scalable |
| **HF Inference — Mistral-7B-Instruct** | v0.3 | Catégorisation LLM (optionnelle) | via `services/llm_service.py` |
| **PyTorch** | Latest | Backend ML | Inference embeddings |

> **Note** : la recherche n'utilise plus de calcul de similarité en mémoire. La
> requête est encodée par Sentence-Transformers puis comparée via l'index Atlas
> Vector Search (`autoembed_index`, 384 dim, cosine). Repli automatique sur un
> matching textuel léger si le modèle ou l'index est indisponible.

### Sécurité
| Technologie | Version | Usage |
|-------------|---------|-------|
| **bcrypt** | 4.0+ | Hash passwords |
| **python-dotenv** | Latest | Gestion .env |

### Intégrations
| Technologie | Version | Usage |
|-------------|---------|-------|
| **requests** | Latest | HTTP requests |
| **pymongo** | 4.0+ | Driver MongoDB |

---

## 📦 Configuration Requise

### Serveur/Machine Locale
- **RAM** : 8GB minimum (Ollama + MongoDB)
- **CPU** : Multi-core recommandé
- **Disk** : 50GB+ (modèles ML + DB)
- **OS** : Linux, macOS, Windows (WSL)

### Python
- **Version** : 3.9, 3.10, 3.11
- **Virtual Env** : Recommandé (venv, conda)

---

## 🔐 Variables d'Environnement

```env
# Database
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net
DB_NAME=ismaila_db

# Email
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password

# Salesforce
SF_WEBHOOK_URL=https://hook.make.com/webhooks/...

# NLP / Recherche sémantique
NLP_THRESHOLD=0.75
EMBEDDING_MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIM=384
VECTOR_INDEX_NAME=autoembed_index

# LLM (catégorisation HF — optionnel, via st.secrets["llm"]["api_token"])

# App
ADMIN_EMAIL=admin@ism.edu.sn
APP_ENV=production|development
```

---

**Dernière mise à jour** : 2026-06-08 (v7.15 — recherche sémantique Atlas Vector Search)
**Status** : ✅ Stack validée pour MVP
