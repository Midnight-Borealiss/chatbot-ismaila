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
- `_secret(name, section, key)` : lit un paramètre depuis, dans l'ordre,
  la variable d'environnement / `.env`, puis `st.secrets` (clé à plat, puis
  section `[section].key`). Permet de fonctionner en local **et** sur Streamlit
  Cloud sans dépendre d'une seule source. Lecture défensive : `st.secrets` lève
  une exception s'il n'existe aucun `secrets.toml`.
- NLP : `EMBEDDING_MODEL_NAME`, `EMBEDDING_DIM`, `VECTOR_INDEX_NAME`, `NLP_THRESHOLD`
- Base : `MONGO_URI`, `DB_NAME`
- Plateforme : `PLATFORM_URL` (lien inclus dans les emails — depuis v7.35).
  Sert de **valeur de repli** : le lien effectif est désormais modifiable depuis
  l'interface via `services/app_settings.py` (voir ci-dessous)
- SMTP : `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`,
  `SMTP_FROM_NAME`, `SMTP_REPLY_TO`, `SMTP_SSL`
- Salesforce : `SF_WEBHOOK_URL`, `SF_TIMEOUT`, `SF_CAMPAIGN_MAPPING`
- Métier : `KB_TTL_DAYS`, `SESSION_TIMEOUT_MINUTES`, `LEAD_HOT_THRESHOLD`

> ⚠️ `EMBEDDING_MODEL_NAME` doit être identique entre l'indexation
> (`scripts/init_embeddings.py`) et la recherche (`search_controller`) sous peine
> d'incohérence des vecteurs. Liste complète et valeurs par défaut : voir
> [../README.md](../README.md) et [../.env.example](../.env.example).

### `roles.py`
**Responsabilité** : Énumérations et constantes de rôles
- Définitions rôles utilisateur (`ADMIN`, `SUPER_ADMIN`, `VALIDATOR`, `CONTRIBUTOR`, `STUDENT`)
- Niveaux d'accès : `ADMIN_ROLES`, `MODERATOR_ROLES`, helpers `is_admin_or_higher()`, `is_moderator_or_higher()`, `is_super_admin()`
- **Alignement des rôles (depuis v7.35)** : `ROLE_ALIASES` est la source unique de
  normalisation des anciennes étiquettes (anglaises ou en casse différente)
  - `normalize_role(raw)` → constante canonique (retourne la valeur d'origine si inconnue)
  - `role_query_values(canonical)` → toutes les orthographes stockables, pour cibler
    en base des comptes créés avant l'alignement : `{"role": {"$in": role_query_values(CONTRIBUTOR)}}`

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

### `feedback_controller.py`
**Responsabilité** : Modération des retours utilisateurs (collection `feedbacks`)

**Fonctions principales** :
- `ensure_indexes()` → Crée l'index composé `(status, type, created_at DESC)`
- `get_filtered_feedbacks(status, feedback_type)` → Liste triée (récents d'abord)
- `update_status(feedback_id, new_status, admin_notes, priority)` → Changement de statut, notes admin et priorité
- Instance singleton : `feedback_controller`

### `app_settings.py`
**Responsabilité** : réglages modifiables depuis l'interface, sans redéploiement
(collection `app_settings`)

**Résolution** : valeur enregistrée en base → `.env` / `st.secrets` → défaut du code.
Un incident MongoDB retombe silencieusement sur les niveaux suivants.

- `get_platform_url()` → lien effectif. **À appeler au moment de l'usage**, jamais au
  chargement d'un module : sinon la modification n'est prise en compte qu'au redémarrage
- `set_platform_url(raw, author)`, `reset_platform_url(author)`, `platform_url_detail()`
- `normalize_platform_url(raw)` → validation : http/https uniquement, ni espace ni
  guillemet ni chevron (le lien est injecté dans un attribut `href` d'email), schéma
  `https://` ajouté s'il manque
- Cache de 60 s invalidé à l'écriture : `_dispatch` personnalise le message par
  destinataire et interrogerait sinon la base une fois par personne

### `communication_controller.py` *(depuis v7.35)*
**Responsabilité** : Centre de Communication — remplace l'ancien « digest »

**Fonctions principales** :
- `BLOCK_DEFINITIONS` → définition des blocs de contenu (objet par défaut, invitation
  à tester, invitation à contribuer, infos de connexion, texte libre) avec leur
  **texte d'usine**, qui sert de référence et de point de retour arrière
- `default_blocks()` → textes d'usine des blocs de corps (objet exclu), sans lecture base
- `get_block_texts()` → textes réellement utilisés à l'envoi : usine surchargé par la
  version enregistrée en base (`message_blocks`). Retombe sur l'usine si MongoDB tombe
- `get_blocks_detail()`, `save_block(key, text, author)`, `reset_block(key, author)` →
  édition des textes depuis l'onglet « 📝 Textes des blocs », sans modification du code
- `unknown_variables(text)` → variables entre accolades qui ne seront pas remplacées
  à l'envoi (garde-fou contre `{prenoms}` au lieu de `{prenom}`)
- `resolve_recipients(target)` → liste dédupliquée d'utilisateurs selon le mode de
  ciblage : `all` | `person` | `services` | `instituts` | `roles`. Le mode `roles`
  étend chaque rôle canonique à ses anciennes orthographes (`role_query_values`)
- `build_pending_recap()` → récapitulatif automatique des questions en attente, groupé par pôle
- `personalize(text, user)` → remplace `{prenom}`, `{nom}`, `{email}`, `{lien}`
- `send_campaign(...)` → envoi `immediate` | `test` | `scheduled` ;
  retourne `{"status", "message", "campaign_id", "stats"}`
- `get_campaigns()`, `get_read_stats()`, `get_recipients_read_state()` → suivi et accusés de réception
- `resend_unread(campaign_id, sender)` → relance des destinataires n'ayant pas lu leur notification
- `save_template()` / `get_templates()` / `delete_template()` → modèles réutilisables
- `process_scheduled(now)` → appelé par le cron ; réclame chaque campagne de façon
  **atomique** (`scheduled → sending`) pour interdire un double envoi
- `smtp_diagnostic()` → présence et source de la configuration SMTP, **sans jamais
  révéler les valeurs**

**Sécurité** :
- `_sanitize_subject()` neutralise les CR/LF de l'objet (anti-injection d'en-têtes SMTP)
- `_reset_passwords()` applique un mot de passe temporaire commun sous forme de
  **hachage bcrypt** avec `must_change_password = True` ; l'expéditeur est exclu
  pour éviter de se verrouiller. Le mot de passe n'est jamais persisté en clair —
  la notification in-app affiche « (voir votre email) »
- Toute campagne est tracée dans `logs_admin` via `_log_admin()`

**Instance singleton** : `communication_controller`

### `kb_controller.py`
**Responsabilité** : Cycle de vie des contributions (base de connaissances)

**Fonctions principales** :
- `get_pending()` / `get_validated()` → files de traitement
- `submit_proposal(c_id, response, author_email, new_category)` → proposition de réponse
- `update_contribution(c_id, response, validator_email)` → certification, génération
  de l'embedding (`_ensure_question_embedding`) et notification de l'étudiant
- `recategorize()`, `invalidate()`, `archive()`, `move_to_test()`, `delete()`
- `add_comment()` → annotation interne (staff)
- `find_similar_questions()` → détection de doublons avant enregistrement
- `is_empty_or_pending(response)` → détecte les réponses vides ou en placeholder

### `admin_controller.py`
**Responsabilité** : Opérations réservées au rôle ADMINISTRATION

**Fonctions principales** :
- `get_full_stats()` → indicateurs du dashboard
- `get_contribution_stats_by_user()` → contributions et validations par utilisateur
- `get_nlp_precision(days)` → taux de précision NLP sur N jours
- `get_filtered_pending(...)`, `get_recent_validated()`, `get_categories()`
- `get_all_users()`, `deactivate_user()`, `send_welcome_email()`
- `notify_experts_for_question()` → relance manuelle des experts
- Toute action est tracée par `_log_admin_action()`

### `rating_controller.py`
**Responsabilité** : Votes 👍 / 👎 sur les réponses du chat

**Fonctions principales** :
- `save_rating(...)` → enregistre ou met à jour le vote d'un utilisateur
- `get_global_stats()` → nombre de votes et taux de satisfaction

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
Abstraction MongoDB, singleton `db_instance`.
- **Mode survie** : si la base est injoignable, `get_collection()` retourne un
  `MagicMock` et l'app sert le contenu d'urgence de `survival_kit.json`
  (`get_survival_faq()`, `get_survival_links()`) au lieu de planter.
- **Index déclaratifs** : `INDEX_DEFINITIONS` décrit, par collection, les clés,
  les options (`unique`, `sparse`, `expireAfterSeconds`) et surtout un champ
  `reason` justifiant chaque index. `_ensure_indexes()` les crée au démarrage —
  opération idempotente, tolérante à l'échec unitaire.
- **TTL** : `chat_sessions.last_activity` expire après 90 jours.
- `get_index_report()` → état des index, affiché dans le dashboard admin.

> **Règle** : toute nouvelle requête filtrée ou triée s'accompagne de son entrée
> dans `INDEX_DEFINITIONS`.

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

### `ollama_service.py` *(depuis v7.38)*
Accès au **LLM local souverain** (Ollama / Mistral), singleton `ollama_service`.
Contrairement à `llm_service` (cloud), aucune donnée ne quitte la machine :
c'est ce service qu'il faut utiliser dès qu'un contenu étudiant est en jeu.
- `is_available()` → serveur joignable **et** modèle présent (distingue les deux)
- `generate(prompt, temperature)` → texte, ou None
- `categorize(question)` → `{category, parent_category, confidence, reasoning,
  source, low_confidence}` ; contraint aux sous-catégories canoniques — une
  catégorie inventée est rejetée et remplacée par le défaut
- Configuration : `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`

Dégradation gracieuse : sans Ollama installé, `is_available()` renvoie False et
`categorize()` retourne un résultat neutre marqué `low_confidence` — aucune
exception ne remonte.

> ⚠️ Ollama charge ~4 Go en mémoire : **il ne tourne pas sur Streamlit Cloud**.
> Réservé au back-office tant que l'hébergement n'est pas arbitré —
> voir [11_PLAN_INTEGRATION_LLM.md](11_PLAN_INTEGRATION_LLM.md).

### `llm_engine.py`
Génération augmentée (RAG) via `ollama_service`. **Module non branché** : le chat
sert aujourd'hui la réponse certifiée verbatim. Point d'entrée prévu pour
l'étape 3 du plan d'intégration.
- `build_rag_prompt(query, context_docs)` → prompt interdisant d'ajouter tout
  fait absent du contexte
- `get_rag_response(query, context_docs)` → retourne toujours une chaîne
  affichable ; sans contexte ou sans LLM, un message d'escalade experte

### `mailer.py`
Envoi SMTP centralisé — toutes les notifications passent par ici.
- `send_answer_to_student()` → réponse certifiée à l'étudiant (appelé par `kb_controller`)
- `send_new_question_alert()` → alerte expert ciblé par topic (RG-03)
- `send_pending_digest()` → résumé des questions en attente (bas niveau, conservé)
- `send_expert_alert()` → alias de compatibilité ascendante
- `send_campaign_email()` / `send_campaign_email_ex()` → emails du Centre de
  Communication ; la variante `_ex` retourne `(succès, message d'erreur)` afin que
  l'appelant puisse afficher la cause exacte d'un échec
- `check_recipient(email)` → interroge le MX du domaine et interrompt le dialogue
  SMTP après `RCPT TO` : **aucun message n'est envoyé**. Distingue « adresse
  inexistante » (550) de « adresse acceptée mais filtrée côté destinataire »

**Délivrabilité** — points d'attention :
- Les en-têtes `Date` et `Message-ID` sont ajoutés systématiquement : leur absence
  est lourdement pénalisée par les filtres anti-spam (Microsoft 365 en particulier).
- L'expéditeur d'enveloppe reste **toujours** le compte authentifié (`SMTP_USER`) :
  c'est lui que SPF évalue et qui reçoit les rapports de non-remise.
- ⚠️ `SMTP_FROM` ne peut différer de `SMTP_USER` que s'il s'agit d'un alias vérifié
  (Gmail) ou d'une boîte du même tenant (Microsoft 365) — sinon le serveur réécrit
  l'en-tête `From`, voire rejette l'envoi (`SMTPSenderRefused`).
- ⚠️ Le port 25 sortant étant généralement bloqué en hébergement Cloud,
  `check_recipient()` n'est fiable qu'en exécution locale.

### `audit_service.py`
Journalisation centralisée des actions utilisateur (collection `user_audit_logs`),
singleton `audit_instance`.
- `log_action(user_email, action, description, metadata)` → trace une action
- `get_user_actions()`, `get_actions_by_type()`, `get_recent_actions_all_users()`,
  `get_action_count_by_type()`
- Appelé en mode **non bloquant** : un échec d'audit ne doit jamais empêcher
  l'action métier (connexion, validation…) d'aboutir.

### `notification_service.py`
Notifications in-app (collection `user_notifications`), singleton `notification_instance`.
- `create_notification(recipient_email, notif_type, title, message, action_url)`
- `get_user_notifications()`, `get_unread_count()`
- `mark_as_read()` / `mark_as_unread()` / `delete_notification()`
- Le champ `read_at` alimente les accusés de réception du Centre de Communication.

### `sf_connector.py`
Intégration Salesforce (RG-06 Store then Forward)
- `build_sf_payload(lead_doc)` → objet Lead au format Salesforce (champs `ISM_*__c`)
- `sync_to_salesforce(lead_doc)` → double écriture : MongoDB **d'abord**, webhook
  ensuite, avec timeout strict pour ne jamais bloquer l'UX
- `retry_failed_leads()` → job de rattrapage (bouton « Resync » du dashboard admin)

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

### `qualification_view.py` — SUPPRIMÉ (v7.20)
Ancien formulaire d'auto-qualification des utilisateurs. Désactivé depuis v7.15
puis **supprimé en v7.20** (code mort, jamais appelé). L'assignation des
profils/permissions se fait exclusivement via l'admin (`admin_view.py`).

### `feedback_view.py`
Collecte de feedback en temps réel (depuis v7.16). Bouton sidebar « 💬 Signaler / Avis »
**accessible à tous** (connectés ou anonymes), appelé par `app.py`.
- `render_feedback_sidebar()` → bouton sidebar (point d'entrée public)
- `_feedback_dialog()` → dialogue modal `@st.dialog` (type, description ≥ 10 car., aperçu du contexte capturé)
- `_capture_user_context()` → snapshot silencieux (email, rôle, permissions, vue courante, timestamp UTC ; `anonyme`/`PUBLIC` si non connecté)
- `save_feedback(data)` → persistance MongoDB (`feedbacks`), priorité auto via `_infer_priority`
- Modération côté admin : `admin_view._render_feedback_moderation_tab()`

### `communication_view.py` *(depuis v7.35)*
Onglet « Communication » de l'espace Administration, monté par
`admin_view._render_communication_subtab()`.
- `_render_compose()` → ciblage, blocs de contenu, canaux, mode d'envoi
- `_render_deliverability_test()` → vérifie une adresse précise et affiche le
  diagnostic SMTP (présence et source des identifiants, jamais les valeurs)
- `_render_history()` → campagnes passées, accusés de réception, relance des non-lus
- `_render_templates()` → gestion des modèles réutilisables

### `help_view.py`
Page d'aide statique, **accessible sans connexion**. Décrit les capacités par
profil (public, étudiant, contributeur, validateur, administration).

### `ai_categorization_view.py`
Onglet admin de pilotage de l'auto-catégorisation IA (Ollama/Mistral).

### `shared_components.py`
Briques transverses : en-tête, pied de page, et `render_comments_and_delete()`
(fil de commentaires internes + suppression d'un document).

### `shared_dashboard_components.py`
Briques du dashboard utilisateur : permissions par rôle, historique d'audit,
notifications, formatage (`format_timestamp`, `get_action_emoji`,
`get_notification_icon`) et `render_user_profile_metrics()`.

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

### `migrate_legacy_categories.py`
Migre les libellés hérités vers la hiérarchie actuelle (« Plaquette d'enseignement
- UE » → « Formations »). Mode à blanc par défaut, `--apply` pour écrire.

### `review_recategorizations.py`
Revue **interactive** des reclassements proposés avant application (Phase 2, étape 2).

### `audit_categories.py`
Audit **read-only** de la catégorisation : compare les voies (mots-clés, sémantique,
LLM), affiche la matrice de confusion pôle→pôle et distingue l'accord réel de
l'accord par défaut.

### `send_scheduled_campaigns.py` *(depuis v7.35)*
Job cron : envoie les campagnes `status="scheduled"` dont l'échéance est atteinte,
via `communication_controller.process_scheduled()`.
```bash
python -m scripts.send_scheduled_campaigns
```

### `normalize_user_emails.py`
Passe tous les emails de la collection `users` en minuscules (sans espaces).
Nécessaire car la connexion et les notifications in-app s'appuient sur l'email
normalisé : un compte stocké avec une majuscule devenait inaccessible.
Le script détecte et signale les **collisions** avant d'écrire.

### `check_indexes.py`
Rapport des index MongoDB existants, détection des index manquants par rapport à
`INDEX_DEFINITIONS`, création idempotente et statistiques de taille par collection.

### `migrate_users.py` / `migrate_pilot_accounts.py`
Audit puis correction des documents utilisateurs : rôles non canoniques, mots de
passe non hachés, champs `name` → `full_name`, `must_change_password`.

### `seed_users.py`
Crée les comptes manquants du pilote. Mode à blanc par défaut, `--apply` pour
écrire. Les comptes existants ne sont **jamais écrasés** (`$setOnInsert`) ;
`--update-roles` réaligne en plus nom, rôle et domaines. Le mot de passe
temporaire vient de `SEED_PASSWORD` ou est généré aléatoirement et affiché une
seule fois — jamais dans le code source.

### `diagnostic_smtp.py`
Affiche la configuration SMTP résolue (sans révéler les valeurs) puis teste une
connexion authentifiée, sans envoyer de message.

### `explore_collections.py`
Liste les collections, leur volume et la structure d'un document type.
Lecture seule.

### `validate_staging.py`
Suite de vérifications de bout en bout avant mise en production (connexion
MongoDB, audit, hiérarchie des rôles, permissions, notifications, dashboard).

> `controllers/kb_controller.py` : `update_contribution()` génère automatiquement
> l'embedding de la question à la certification (`_ensure_question_embedding`).

---

**Dernière mise à jour** : 2026-08-06 (v7.36 — Centre de Communication et délivrabilité email)
