# 🎓 ISMaiLa — Système de Gestion des Connaissances (KMS) souverain

Assistant conversationnel et base de connaissances certifiée de l'**Institut Supérieur
de Management (ISM)**. Les étudiants posent leurs questions ; les experts métier
proposent et certifient les réponses ; la base s'enrichit en continu.

**Principe fondateur — souveraineté des données** : la compréhension des questions
(embeddings, similarité sémantique) est calculée **localement**, sans envoyer le
contenu à une API tierce.

---

## Démarrage rapide

```bash
# 1. Environnement virtuel
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS

# 2. Dépendances
pip install -r requirements.txt
pip install pytest              # dev uniquement

# 3. Garde-fou secrets — à faire une seule fois (voir SECURITY.md)
git config core.hooksPath .githooks

# 4. Configuration (voir § Variables d'environnement)
cp .env.example .env            # puis renseigner MONGO_URI, SMTP_*, ...

# 5. Lancement
streamlit run app.py
```

> 🔐 **Aucun secret ne doit être committé.** Le hook installé à l'étape 3 refuse
> les commits contenant un identifiant ou un fichier `.env` — voir
> [SECURITY.md](SECURITY.md).

L'application démarre sur <http://localhost:8501>.

> **Mode survie** : si MongoDB est injoignable, l'application ne plante pas — elle
> affiche une bannière d'alerte et le contenu d'urgence de `survival_kit.json`
> (FAQ critique + liens utiles). Voir [services/db_connector.py](services/db_connector.py).

---

## Variables d'environnement

Lues depuis `.env` en local **ou** depuis `st.secrets` sur Streamlit Cloud
(résolution par [`_secret()`](config/settings.py#L7) — à plat ou par section).

### Obligatoires

| Variable | Rôle |
|---|---|
| `MONGO_URI` | Chaîne de connexion MongoDB Atlas (`mongodb+srv://…`) |
| `DB_NAME` | Nom de la base (défaut : `ismaila_db`) |

### Email (RG-03 — alertes, notifications, campagnes)

| Variable | Défaut | Rôle |
|---|---|---|
| `SMTP_SERVER` | `smtp.gmail.com` | Serveur d'envoi |
| `SMTP_PORT` | `587` | 587 (STARTTLS) ou 465 (SSL) |
| `SMTP_USER` | — | Compte authentifié |
| `SMTP_PASS` | — | Mot de passe **d'application** |
| `SMTP_FROM` | = `SMTP_USER` | Adresse affichée au destinataire |
| `SMTP_FROM_NAME` | `ISMaiLa` | Nom affiché |
| `SMTP_REPLY_TO` | — | Adresse de réponse (boîte ISM) |
| `SMTP_SSL` | `false` | `true` → SSL implicite (port 465) |

> ⚠️ **Délivrabilité** : un serveur n'accepte un `SMTP_FROM` différent du compte
> authentifié que s'il s'agit d'un alias vérifié (Gmail) ou d'une boîte du même
> tenant (Microsoft 365). Sinon il réécrit l'en-tête `From` — ou rejette l'envoi.
> L'espace Administration expose un **diagnostic SMTP** qui affiche la config
> réellement vue par l'app, sans jamais révéler les valeurs sensibles.

### Plateforme, NLP et CRM

| Variable | Défaut | Rôle |
|---|---|---|
| `PLATFORM_URL` | `https://ismaila.streamlit.app` | Lien inclus dans les emails. Valeur de repli : modifiable en cours d'exécution depuis l'onglet Communication → « 📝 Textes & lien » |
| `EMBEDDING_MODEL_NAME` | `paraphrase-multilingual-MiniLM-L12-v2` | Modèle d'embedding |
| `EMBEDDING_DIM` | `384` | Dimensions du modèle ci-dessus |
| `VECTOR_INDEX_NAME` | `autoembed_index` | Index Atlas Vector Search |
| `NLP_THRESHOLD` | `0.75` | Seuil RG-01 (sous ce score → alerte expert) |
| `SF_WEBHOOK_URL` | — | Webhook Make/Zapier → Salesforce (RG-06) |
| `SF_TIMEOUT` | `5` | Timeout webhook, en secondes |

> ⚠️ `EMBEDDING_MODEL_NAME` doit être **identique** entre l'indexation
> ([scripts/init_embeddings.py](scripts/init_embeddings.py)) et la recherche
> ([controllers/search_controller.py](controllers/search_controller.py)). Changer
> le modèle impose de **régénérer tous les embeddings**.

---

## Architecture

Architecture **MVC** stricte : les vues n'accèdent jamais à MongoDB directement.

```
Vue (Streamlit)  →  Controller (métier)  →  Service (I/O externes)  →  MongoDB / SMTP / Salesforce
```

| Dossier | Responsabilité |
|---|---|
| [config/](config/) | Constantes, taxonomie des catégories, rôles, permissions, réglages |
| [models/](models/) | Schémas Pydantic (`User`, `Contribution`, `Lead`) |
| [services/](services/) | I/O externes : MongoDB, SMTP, NLP, LLM, Salesforce, audit, notifications |
| [controllers/](controllers/) | Logique métier — le seul endroit qui décide |
| [views/](views/) | Interfaces Streamlit, une par rôle |
| [scripts/](scripts/) | Migrations, diagnostics et jobs planifiés (lancés à la main ou en cron) |
| [tests/](tests/) | Tests pytest |
| [DOCUMENTATION/](DOCUMENTATION/) | Documentation fonctionnelle détaillée |

Point d'entrée : [app.py](app.py) — configuration de la page, mode survie,
préchargement des catégories, puis routage du menu selon le rôle.

---

## Rôles et navigation

Définis dans [config/roles.py](config/roles.py). `normalize_role()` ramène toute
ancienne étiquette (anglaise ou en casse différente) à sa constante canonique.

| Rôle | Dashboard | Assistant | Contribuer | Valider | Administration |
|---|:--:|:--:|:--:|:--:|:--:|
| `ETUDIANT` | ✅ | ✅ | — | — | — |
| `CONTRIBUTEUR` | ✅ | ✅ | ✅ | — | — |
| `VALIDATEUR` | ✅ | ✅ | ✅ | ✅ | — |
| `ADMINISTRATION` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `SUPER_ADMIN` | ✅ | ✅ | ✅ | ✅ | ✅ + droits exclusifs |

L'assistant et l'aide sont également accessibles **sans connexion**.

À la première connexion, `must_change_password` bloque toute navigation tant que
l'utilisateur n'a pas défini son propre mot de passe.

---

## Règles de gestion

| Code | Règle |
|---|---|
| RG-01 | Sous `NLP_THRESHOLD`, la question n'est pas répondue automatiquement → escalade expert |
| RG-03 | Toute question escaladée déclenche une alerte email vers les experts du domaine |
| RG-05 | Au-delà de `LEAD_HOT_THRESHOLD` questions chaudes, le prospect passe en `HOT` |
| RG-06 | Les leads sont synchronisés vers Salesforce via webhook (double écriture) |

Détail dans [DOCUMENTATION/5_LOGIQUE_METIER.md](DOCUMENTATION/5_LOGIQUE_METIER.md).

---

## Tests

```bash
python -m pytest                      # toute la suite
python -m pytest -v                   # détaillé
python -m pytest tests/test_auth.py   # un seul fichier
```

Les tests n'ont pas besoin de MongoDB : `get_collection()` retourne un `MagicMock`
quand la base est absente, et [tests/conftest.py](tests/conftest.py) fournit les
fixtures nécessaires.

---

## Scripts d'exploitation

```bash
python -m scripts.send_scheduled_campaigns   # cron : envoi des campagnes programmées
python -m scripts.init_embeddings            # (re)génère les embeddings de la KB
python -m scripts.create_vector_index        # crée l'index Atlas Vector Search
python -m scripts.check_indexes              # audit des index MongoDB
python -m scripts.normalize_user_emails      # met les emails en minuscules
python -m scripts.seed_users                 # crée les comptes manquants (à blanc)
```

Diagnostics (lecture seule) :

```bash
python -m scripts.diagnostic_smtp            # config SMTP + test de connexion
python -m scripts.diagnostic_nlp             # moteur sémantique
python -m scripts.explore_collections        # structure réelle des collections
```

Chaque script porte un docstring en tête décrivant son objet, ses effets et son
mode de lancement. Certains scripts de recatégorisation (`auto_categorize`,
`migrate_legacy_categories`, `recategorize_hierarchy`) proposent un mode
« à blanc » qui affiche les changements sans les écrire.

---

## Documentation complémentaire

| Fichier | Contenu |
|---|---|
| [SECURITY.md](SECURITY.md) | 🔐 Règles de sécurité, garde-fous, incident en cours |
| [CONVENTION.md](CONVENTION.md) | Conventions de code et patterns du projet |
| [DOCUMENTATION/2_ARCHITECTURE_GLOBALE.md](DOCUMENTATION/2_ARCHITECTURE_GLOBALE.md) | Architecture et flux de données |
| [DOCUMENTATION/4_MODULES_DETAILLES.md](DOCUMENTATION/4_MODULES_DETAILLES.md) | Description module par module |
| [DOCUMENTATION/5_LOGIQUE_METIER.md](DOCUMENTATION/5_LOGIQUE_METIER.md) | Règles de gestion et algorithmes |
| [DOCUMENTATION/7_CHANGELOG_TEMPLATE.md](DOCUMENTATION/7_CHANGELOG_TEMPLATE.md) | Historique des versions |
| [DOCUMENTATION/8_MONGODB_DASHBOARD_SCHEMA.md](DOCUMENTATION/8_MONGODB_DASHBOARD_SCHEMA.md) | Schéma des collections |

---

© 2026 ISM — Direction de l'Innovation Numérique
