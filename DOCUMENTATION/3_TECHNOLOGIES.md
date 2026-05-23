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
| **Sentence-Transformers** | 2.2+ | Embeddings NLP | Souveraineté (local) |
| **all-MiniLM-L6-v2** | - | Modèle embedding | ~22MB, rapide, bon score |
| **Ollama** | Latest | LLM local | Génération texte, catégorisation |
| **PyTorch** | Latest | Backend ML | Inference embeddings |

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

# Ollama
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# Salesforce
SF_WEBHOOK_URL=https://hook.make.com/webhooks/...

# NLP
NLP_THRESHOLD=0.75

# App
ADMIN_EMAIL=admin@ism.edu.sn
APP_ENV=production|development
```

---

**Dernière mise à jour** : 2026-05-23
**Status** : ✅ Stack validée pour MVP
