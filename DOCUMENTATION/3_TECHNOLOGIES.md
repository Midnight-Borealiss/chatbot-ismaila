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
| **requests** | 2.32+ | Webhook Salesforce, HF Inference |
| **pymongo** | 4.7+ | Driver MongoDB |
| **dnspython** | 2.6+ | Résolution SRV (`mongodb+srv://`) et MX (diagnostic mailer) |
| **pydantic[email]** | 2.7+ | Validation des modèles |
| **pandas** | 2.2+ | Tableaux du dashboard admin |

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

**Source de vérité** : [../.env.example](../.env.example) — modèle complet et
commenté. Description de chaque variable dans [../README.md](../README.md).

Toutes les clés sont lisibles depuis `.env` (local) **ou** `st.secrets`
(Streamlit Cloud), via `config.settings._secret()`.

| Groupe | Clés |
|---|---|
| Base | `MONGO_URI`, `DB_NAME` |
| Plateforme | `PLATFORM_URL` |
| Email | `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_FROM_NAME`, `SMTP_REPLY_TO`, `SMTP_SSL` |
| NLP | `EMBEDDING_MODEL_NAME`, `EMBEDDING_DIM`, `VECTOR_INDEX_NAME`, `NLP_THRESHOLD` |
| Salesforce | `SF_WEBHOOK_URL`, `SF_TIMEOUT` |
| LLM (optionnel) | `st.secrets["llm"]["api_token"]` pour HF Inference |

---

**Dernière mise à jour** : 2026-08-06 (v7.36)
**Status** : ✅ Stack validée pour MVP
