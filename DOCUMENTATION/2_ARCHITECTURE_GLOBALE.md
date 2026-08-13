# 🏗️ Architecture Globale - ISMaiLa

## Vue d'ensemble du Système

ISMaiLa est une plateforme de gestion des connaissances basée sur Streamlit avec une architecture en couches :

```
┌──────────────────────────────────────────────────────────┐
│            INTERFACE UTILISATEUR (Streamlit)              │
│  ├─ student_view.py         (Assistant / chat public)    │
│  ├─ contributor_view.py     (Contributions)              │
│  ├─ validator_view.py       (Certification)              │
│  ├─ admin_view.py           (Administration)             │
│  │   ├─ communication_view.py     (Centre de Communication)
│  │   └─ ai_categorization_view.py (Auto-catégorisation)  │
│  ├─ user_dashboard_view.py  (Mon espace)                 │
│  ├─ feedback_view.py        (Signaler / Avis)            │
│  └─ help_view.py            (Aide, accès public)         │
└────────────────┬─────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│           COUCHE CONTRÔLEURS (Controllers)                │
│  ├─ auth_controller.py          → Authentification       │
│  ├─ kb_controller.py            → Base de connaissances  │
│  ├─ search_controller.py        → Recherche sémantique   │
│  ├─ mkt_controller.py           → Marketing / Leads      │
│  ├─ admin_controller.py         → Administration         │
│  ├─ communication_controller.py → Campagnes (v7.35)      │
│  ├─ feedback_controller.py      → Modération des retours │
│  └─ rating_controller.py        → Votes 👍 / 👎           │
└────────────────┬─────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│            COUCHE SERVICES (Services)                     │
│  ├─ db_connector.py         → MongoDB + index + survie   │
│  ├─ nlp_engine.py           → Embeddings (souverain)     │
│  ├─ llm_engine.py           → Ollama / Mistral (RAG)     │
│  ├─ llm_service.py          → HF Inference (optionnel)   │
│  ├─ mailer.py               → Emails SMTP                │
│  ├─ audit_service.py        → Journal des actions        │
│  ├─ notification_service.py → Notifications in-app       │
│  └─ sf_connector.py         → Salesforce Webhook         │
└────────────────┬─────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────┐
│          COUCHE DONNÉES & RESSOURCES                      │
│  ├─ MongoDB (contributions, users, leads, campaigns, …)  │
│  ├─ survival_kit.json  (mode survie)                     │
│  └─ config/  (settings, roles, permissions, categories)  │
└──────────────────────────────────────────────────────────┘
```

**Règle d'architecture** : une vue n'accède jamais à MongoDB ni au SMTP
directement — elle passe toujours par un contrôleur. Voir
[../CONVENTION.md](../CONVENTION.md).

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

### 3. Flux : Contribution → Certification

```
Contributeur soumet une réponse
         │
         ▼
    KB Controller · submit_proposal()
         │
         ▼
    MongoDB · contributions
    status = "en_attente"
         │
         ▼
    Validateur examine (validator_view)
         │
    ├─ Certifier → KB Controller · update_contribution()
    │              • status = "valide"
    │              • génération de l'embedding de la question
    │              • enregistrement d'une ancre apprise (learned_anchors)
    │              • mailer.send_answer_to_student()
    │
    ├─ Invalider → status = "en_attente" (retour en file)
    ├─ Archiver  → status = "archive"
    └─ Hors sujet → status = "test"
```

> Statuts réellement stockés : `en_attente` | `valide` | `archive` | `test`.

### 4. Flux : Campagne de communication (v7.35)

```
Admin compose (communication_view)
    • cible : all | person | services | instituts | roles
    • blocs : invitation, récap auto, infos de connexion, texte libre
    • canaux : email et/ou notification in-app
         │
         ▼
    Communication Controller · send_campaign()
         │
    ├─ "test"      → envoi à l'expéditeur uniquement
    │
    ├─ "immediate" → resolve_recipients()
    │                • si mot de passe temporaire : _reset_passwords()
    │                  (hachage bcrypt + must_change_password)
    │                • _dispatch() → mailer + notification_service
    │                • trace dans logs_admin
    │
    └─ "scheduled" → enregistré dans campaigns (status = "scheduled")
                     │
                     ▼
              cron : scripts/send_scheduled_campaigns.py
                     │
                     ▼
              process_scheduled()
              • réclamation ATOMIQUE scheduled → sending
                (interdit le double envoi)
              • dispatch, puis status = "sent"
         │
         ▼
    Accusés de réception : email_status + read_at (in-app)
         │
         ▼
    resend_unread() → relance des non-lus
```

---

## 👥 Modèle de Rôles & Accès

```
┌──────────────────┐
│   SUPER_ADMIN    │  → Accès total + droits exclusifs
├──────────────────┤
│  ADMINISTRATION  │  → Accès total
├──────────────────┤
│   VALIDATEUR     │  → Certifier les contributions
├──────────────────┤
│   CONTRIBUTEUR   │  → Proposer des réponses
├──────────────────┤
│   ETUDIANT       │  → Assistant + Mon espace
├──────────────────┤
│  PUBLIC (anon)   │  → Assistant + Aide + capture lead
└──────────────────┘
```

Constantes canoniques dans `config/roles.py`. Les documents créés par d'anciennes
versions peuvent porter une étiquette anglaise (`STUDENT`, `VALIDATOR`…) :
`normalize_role()` les ramène à la constante, `role_query_values()` permet de les
cibler en base.

**Matrice d'accès détaillée dans LOGIQUE_METIER.md**

---

## 📊 Modèles de Données Principaux

> Les modèles Pydantic ([models/](../models/)) décrivent le contrat d'écriture.
> Les documents réellement en base peuvent contenir des champs additionnels
> ajoutés par les contrôleurs — schéma complet dans
> [8_MONGODB_DASHBOARD_SCHEMA.md](8_MONGODB_DASHBOARD_SCHEMA.md).

### Model: User — collection `users`
```
{
  _id: ObjectId
  email: str (unique, TOUJOURS en minuscules)
  full_name: str                      # ancien schéma : "name"
  password_hash: str (bcrypt)
  role: "ADMINISTRATION" | "SUPER_ADMIN" | "VALIDATEUR" | "CONTRIBUTEUR" | "ETUDIANT"
  domain_permissions: dict            # permissions fines par domaine
  expert_topics: List[str]            # ancien schéma, migré vers domain_permissions
  scope: { services: [...], instituts: [...] }   # rattachement, sert au ciblage
  must_change_password: bool          # bloque la navigation à la 1re connexion
  created_at: datetime
  last_login: datetime
  active: bool
}
```

### Model: Contribution — collection `contributions`
```
{
  _id: ObjectId
  question: str
  response: str
  status: "en_attente" | "valide" | "archive" | "test"
  author_email: str
  user_email: str                     # auteur de la question d'origine
  category: str                       # sous-catégorie canonique
  parent_category: str                # pôle (4 catégories parentes)
  needs_review: bool                  # classification incertaine (Phase 3)
  question_embedding: List[float]     # 384 dim, généré à la certification
  validated_by: str
  comments: List[dict]                # annotations internes (staff)
  created_at / updated_at: datetime
}
```

### Model: Lead — collection `leads`
```
{
  _id: ObjectId
  email: EmailStr
  full_name: str
  phone: str (optional)
  interest: str                       # catégorie détectée
  intent_score: "HOT" | "WARM" | "COLD"        # RG-05
  nlp_score: float
  chat_history: List[dict]
  campaign: str (optional)            # campagne Salesforce (RG-06)
  is_synced_sf: bool
  sf_error: str (optional)
  created_at: datetime
}
```

### Campaign — collection `campaigns` *(v7.35)*
```
{
  _id: ObjectId
  created_by: str                     # email de l'admin expéditeur
  subject / body: str
  target: { mode, emails, services, instituts, roles }
  channels: ["email", "inapp"]
  send_type: "immediate" | "test" | "scheduled"
  scheduled_at: datetime (optional)
  status: "scheduled" | "sending" | "sent" | "test"
  recipients: [{ email, full_name, email_status, email_error, notif_id }]
  stats: { total, email_sent, email_failed, inapp }
  password_reset_count: int
}
```

---

## 🔐 Sécurité

- **Authentification** : bcrypt + sessions Streamlit. `must_change_password`
  impose un mot de passe personnel à la première connexion.
- **Base de données** : MongoDB avec authentification, index `unique` sur `email`.
- **Emails** : SMTP authentifié (STARTTLS ou SSL implicite) ; objets nettoyés de
  leurs CR/LF (anti-injection d'en-têtes) ; texte utilisateur échappé avant
  insertion dans le gabarit HTML.
- **Secrets** : variables d'environnement (`.env`) ou Streamlit secrets, via
  `config.settings._secret()`. Les écrans de diagnostic n'exposent que la
  **présence** et la **source** d'une valeur, jamais la valeur.
- **Souveraineté NLP** : aucun appel externe pour les embeddings.
- **Audit** : `user_audit_logs` (actions utilisateur) et `logs_admin` (actions
  d'administration, campagnes) — écriture en mode non bloquant.

---

## 🛡️ Résilience

| Défaillance | Comportement |
|---|---|
| MongoDB injoignable | Bannière « mode survie » + contenu d'urgence (`survival_kit.json`) ; `get_collection()` retourne un mock |
| `sentence-transformers` / `torch` absents | Repli sur la classification par mots-clés |
| Préchargement catégories/ancres en échec | Démarrage quand même, sans préchargement (v7.32) |
| SMTP en échec | Cause exacte remontée à l'appelant (`send_campaign_email_ex`) et journalisée par destinataire |
| Webhook Salesforce en échec | Lead conservé en base (`is_synced_sf = False`) pour rattrapage |
| Audit / notification en échec | Ignoré — l'action métier aboutit malgré tout |

---

## 🌐 Intégrations Externes

### Salesforce
- **Type** : Webhook (Store then Forward)
- **Déclenchement** : Nouvel lead capture (RG-06)
- **Donnée** : Lead details
- **Reconnexion** : Queue locale en cas d'échec

### SMTP Email
- **Type** : envois transactionnels et campagnes
- **Utilisé pour** :
  - Alertes experts (score NLP < `NLP_THRESHOLD`) — RG-03
  - Réponse certifiée à l'étudiant
  - Campagnes du Centre de Communication (v7.35)
- **Points d'attention délivrabilité** : en-têtes `Date` / `Message-ID`
  obligatoires, expéditeur d'enveloppe = compte authentifié (SPF), `SMTP_FROM`
  limité aux alias vérifiés. Détail dans
  [4_MODULES_DETAILLES.md](4_MODULES_DETAILLES.md#mailerpy).

### Ollama
- **Type** : LLM local
- **Utilisé pour** : génération augmentée (RAG) et auto-catégorisation
- **Mode fallback** : classification par mots-clés si indisponible

---

**Dernière mise à jour** : 2026-08-06 (v7.36)
**Version** : MVP 7 - Pilote V3
