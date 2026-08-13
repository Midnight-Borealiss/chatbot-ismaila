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

### Version 7.38 — 2026-08-06

#### 🎯 Objectif
Étape 0 du plan d'intégration LLM : poser un socle **local et souverain**,
réparer les scripts qui l'attendaient, sans toucher au chemin de réponse à
l'étudiant.

#### 📋 Modifications
- **services/ollama_service.py** *(nouveau)* : client du LLM local
  (Ollama / Mistral). `is_available()`, `generate()`, `categorize()`.
  Répare `scripts/auto_categorize.py` et `scripts/audit_categories.py`, qui
  l'importaient alors qu'il **n'existait pas** — ces deux scripts étaient
  inopérants.
- **services/llm_engine.py** : nettoyé. Suppression de la seconde docstring
  (code mort — Python ignore tout bloc après le premier) et **bascule de
  `llm_service` (Hugging Face, cloud) vers `ollama_service` (local)**. Le module
  contredisait le principe de souveraineté du projet.
- **.env.example** : `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`.
- **DOCUMENTATION/10_PLAN_SECURITE.md** *(nouveau)* : travaux de sécurité
  détaillés, avec répartition des rôles.
- **DOCUMENTATION/11_PLAN_INTEGRATION_LLM.md** *(nouveau)* : plan d'intégration
  en 5 étapes, du risque nul au risque élevé.

#### 🔧 Détails Techniques
- `categorize()` contraint la sortie aux sous-catégories canoniques de
  `config/categories.py` : une catégorie inventée par le modèle est **rejetée**
  et remplacée par le défaut, plutôt que de créer une catégorie fantôme en base.
- Extraction JSON tolérante : les modèles encadrent souvent leur réponse de
  texte ou de balises ```json malgré la consigne.
- `is_available()` distingue « serveur injoignable » de « modèle non téléchargé »
  — deux causes fréquentes qu'un booléen unique rendait indiscernables.
- Dégradation gracieuse conforme au pattern du projet : sans Ollama, aucune
  exception ne remonte et `low_confidence = True` interdit toute décision
  automatique.

#### ⚠️ Notes
- **`llm_engine` reste débranché volontairement.** Le chat sert la réponse
  certifiée **verbatim** ; brancher la génération romprait la chaîne de
  certification tant que les garde-fous de l'étape 3 ne sont pas en place.
- ⚠️ **Ollama ne tourne pas sur Streamlit Cloud** (~4 Go en mémoire). L'usage
  reste back-office jusqu'à l'arbitrage d'hébergement avec la DSI.
- Prérequis poste : installer Ollama puis
  `ollama pull mistral:7b-instruct-q4_0`.
- Constat de cadrage : **65 réponses certifiées contre 224 en attente**. Le
  corpus, et non le modèle, est la limite actuelle du système.

#### ✅ Tests
- ✅ `tests/test_ollama_service.py` *(nouveau)* : 29 tests — disponibilité,
  génération, extraction JSON, contrat de `categorize()`.
- ✅ `tests/test_llm_engine.py` *(nouveau)* : 9 tests — prompt, garde-fous, repli.
- ✅ Tous conçus pour passer **sans Ollama installé**, cas prioritaire.
- ✅ Suite complète : 144 tests, aucune régression.

---

### Version 7.37 — 2026-08-06

#### 🎯 Objectif
Documenter l'ensemble du code et corriger les anomalies mises au jour par cette
revue : identifiants exposés, code mort, défauts de schéma.

#### 📋 Modifications — Documentation
- **README.md** *(nouveau)* : installation, configuration, architecture, rôles,
  règles de gestion, scripts.
- **CONVENTION.md** *(nouveau)* : conventions de code et patterns du projet
  (MVC, singletons, « non bloquant », docstrings, sécurité, MongoDB, Git).
- **.env.example** *(nouveau)* : modèle de configuration commenté.
- **DOCUMENTATION/** : architecture, modules et technologies remis à jour ;
  changelog complété de v7.25 à v7.36.
- **Docstrings** : couverture portée de 50 % à 97 % (450/466) ; plus aucun
  module sans docstring.

#### 🔧 Modifications — Sécurité
- **`tests/test_collection.py` → `scripts/explore_collections.py`** : l'URI Atlas
  avec **identifiant et mot de passe en clair** est remplacée par
  `config.settings.MONGO_URI`. Le fichier n'était pas un test (aucune assertion)
  mais ouvrait une connexion à la base de production à chaque `pytest`.
- **`tests/test_system.py` → `scripts/diagnostic_smtp.py`** : l'affichage de
  `SMTP_PASS` en clair est supprimé ; seule la *présence* des valeurs est
  indiquée. N'est plus collecté par pytest (il ouvrait une vraie connexion SMTP
  et ne faisait aucune assertion).
- **scripts/seed_users.py** : réécrit. Plus de mot de passe en clair dans le
  code (variable `SEED_PASSWORD` ou génération aléatoire affichée une fois) ;
  schéma courant (`full_name`, emails normalisés, `must_change_password`) ;
  comptes existants protégés par `$setOnInsert` ; mode à blanc par défaut.

#### 🔧 Modifications — Correctifs
- **models/user.py** : le motif de `role` n'acceptait pas `SUPER_ADMIN`. Il est
  désormais **dérivé des constantes de `config/roles.py`**, ce qui interdit la
  divergence à l'origine du défaut.
- **models/contribution.py**, **models/lead.py** : `created_at = datetime.now()`
  était évalué **à l'import** — toutes les instances partageaient le même
  horodatage. Remplacé par `Field(default_factory=datetime.now)`. Idem pour
  `chat_history`, dont la liste par défaut était partagée entre instances.
- **views/admin_view.py** : suppression de `_render_users_list_and_creation()`
  et `_render_permissions_subtab()`, stubs `pass` sans appelant depuis v7.33.
- **views/shared_components.py** : suppression de `render_header()` (URL de logo
  jamais renseignée) et `render_footer()`, sans appelant.
- **Suppression de `clean_db.py`** (doublon non exécutable de
  `scripts/cleanup_placeholders.py`) et **`test_import.py`** (chemin absolu lié
  à une machine).

#### ⚠️ Notes
- 🔴 **Action requise** : les identifiants Atlas exposés restent présents dans
  l'historique Git. **Faire tourner le mot de passe de l'utilisateur
  `admin_ismaila`** — les retirer du code ne suffit pas.
- `scripts/seed_users.py --apply` ne touche aucun compte existant ; utiliser
  `--update-roles` pour réaligner explicitement rôles et domaines.

#### ✅ Tests
- ✅ 107 tests passent, aucune régression.
- ✅ `seed_users` vérifié à blanc sur la base réelle : 40 comptes existants
  préservés, 15 manquants détectés.

---

### Version 7.36 — 2026-07-27 *(en cours, non commité)*

#### 🎯 Objectif
Fiabiliser la remise des emails et l'accès aux comptes : en-têtes conformes,
diagnostic d'adresse, connexion insensible à la casse.

#### 📋 Modifications
- **services/mailer.py** : ajout systématique des en-têtes `Date` et `Message-ID`
  (leur absence est lourdement pénalisée par les filtres anti-spam Microsoft 365) ;
  `Reply-To` ; support SSL implicite (port 465) ; expéditeur d'enveloppe forcé au
  compte authentifié (alignement SPF) ; nouvelle fonction `check_recipient()`.
- **config/settings.py** : `SMTP_FROM`, `SMTP_FROM_NAME`, `SMTP_REPLY_TO`, `SMTP_SSL`.
- **controllers/auth_controller.py** : `_find_by_email()` — recherche insensible à
  la casse avec normalisation en base à la volée (auto-réparation).
- **scripts/normalize_user_emails.py** *(nouveau)* : passe tous les emails de la
  collection `users` en minuscules.
- **views/communication_view.py** : outil de vérification d'adresse destinataire.
- **requirements.txt** : `dnspython>=2.6.0` (résolution MX du diagnostic).

#### 🔧 Détails Techniques
- `check_recipient(email)` interroge le MX du domaine et interrompt le dialogue
  SMTP après `RCPT TO` : aucun message n'est envoyé. Distingue « adresse
  inexistante » (550) de « adresse acceptée mais filtrée côté destinataire ».
- ⚠️ Le port 25 sortant est généralement bloqué en hébergement Cloud : ce
  diagnostic ne fonctionne de façon fiable qu'en local.

#### ⚠️ Notes
- Action manuelle recommandée : `python -m scripts.normalize_user_emails` une fois,
  pour rattraper les comptes historiques créés avec une majuscule.

#### ✅ Tests
- `tests/test_mailer.py` et `tests/test_auth.py` étendus (en-têtes, casse email).

---

### Version 7.35 — 2026-07-24

#### 🎯 Objectif
Remplacer l'ancien « digest » par un **Centre de Communication** complet :
ciblage, composition par blocs, multicanal, programmation, accusés de réception.

#### 📋 Modifications
- **controllers/communication_controller.py** *(nouveau)* : ciblage
  (`resolve_recipients`), récap automatique des questions en attente,
  personnalisation, envoi (`send_campaign`), relance des non-lus, modèles
  réutilisables, traitement des campagnes programmées.
- **views/communication_view.py** *(nouveau)* : onglet « Communication » de
  l'espace Administration.
- **scripts/send_scheduled_campaigns.py** *(nouveau)* : job cron d'envoi différé.
- **config/roles.py** : `ROLE_ALIASES`, `normalize_role()`, `role_query_values()` —
  alignement des rôles créés avec d'anciennes étiquettes anglaises.
- **config/settings.py** : `PLATFORM_URL` configurable ; lecture des identifiants
  SMTP depuis `.env` **ou** `st.secrets` via `_secret()`.
- **services/mailer.py** : `send_campaign_email()` et `send_campaign_email_ex()`
  (cette dernière retourne la cause exacte d'un échec).
- **Retraits** : `config/digest_templates.py` et le code de digest de
  `admin_controller.py` / `admin_view.py` (remplacés par le Centre).

#### 🔧 Détails Techniques
- Nouvelles collections : `campaigns` (contenu, cible, destinataires, stats) et
  `message_templates`.
- Bloc « infos de connexion » : `{motdepasse}` est un mot de passe temporaire
  **commun**, appliqué en base sous forme de hachage bcrypt avec
  `must_change_password = True`. Il n'est jamais persisté en clair — la
  notification in-app affiche « (voir votre email) ».
- `process_scheduled()` réclame chaque campagne de façon atomique
  (`scheduled → sending`) : un double lancement du cron ne peut pas envoyer deux fois.

#### ⚠️ Notes
- **Breaking** : `config/digest_templates.py` supprimé.
- Le mode « infos de connexion » est **incompatible** avec l'envoi programmé
  (le mot de passe n'étant pas stocké, la réinitialisation doit être synchrone).
- L'expéditeur (`sender_email`) est exclu de la réinitialisation de mot de passe,
  pour éviter de verrouiller l'administrateur qui envoie la campagne.
- Un **diagnostic SMTP** dans l'interface affiche la configuration réellement vue
  par l'application sans jamais révéler les valeurs sensibles.

---

### Version 7.34 — 2026-07-20

#### 🎯 Objectif
Gestion des utilisateurs : afficher les droits dépliés sous le profil.

#### 📋 Modifications
- **views/admin_view.py** : fin de la mise en page à deux colonnes ; les
  permissions par domaine se déroulent sous la fiche du profil.

---

### Version 7.33 — 2026-07-20

#### 🎯 Objectif
Gestion des utilisateurs : passer du tableau à une liste de cartes.

#### 📋 Modifications
- **views/admin_view.py** : la liste des testeurs du pilote est rendue en cartes
  (lisibilité des rôles et permissions).

---

### Version 7.32 — 2026-07-20

#### 🎯 Objectif
Robustesse au démarrage.

#### 📋 Modifications
- **app.py** : le préchargement des catégories persistées et des ancres apprises
  devient **non bloquant**.

#### ⚠️ Notes
- L'application démarre désormais même si la base est momentanément indisponible
  au moment du préchargement — elle dégrade sans préchargement au lieu de planter.

---

### Version 7.31 — 2026-07-20

#### 🎯 Objectif
Phase 3, étape 3a — boucle d'apprentissage : les ancres apprises.

#### 📋 Modifications
- **config/categories.py** : `load_learned_anchors()` et persistance des ancres.
- **controllers/kb_controller.py** : enregistrement d'une ancre à la certification.
- **services/db_connector.py** : collection `learned_anchors` + index unique
  `(category, phrase)` pour la déduplication.
- **app.py** : chargement des ancres au démarrage.

#### 🔧 Détails Techniques
- Nouvelle collection `learned_anchors` : chaque validation enrichit le référentiel
  sémantique utilisé par le classifieur, sans réentraîner de modèle.

#### ✅ Tests
- `tests/test_learned_anchors.py` *(nouveau)*.

---

### Version 7.30 — 2026-07-20

#### 🎯 Objectif
Phase 3, étape 2 — suggérer une catégorie dans le formulaire contributeur.

#### 📋 Modifications
- **views/contributor_view.py** : la catégorie détectée est proposée par défaut,
  le contributeur peut la corriger.

---

### Version 7.29 — 2026-07-20

#### 🎯 Objectif
Phase 3, étape 1 — classifier à la source et signaler les cas incertains.

#### 📋 Modifications
- **services/nlp_engine.py** : score de confiance exposé par la classification.
- **controllers/search_controller.py** : les tickets créés portent un flag
  `needs_review` quand la confiance est insuffisante.
- **views/contributor_view.py** : affichage du flag.

#### ✅ Tests
- `tests/test_nlp_confidence.py` *(nouveau)*, `tests/test_search_controller.py` étendu.

---

### Version 7.28 — 2026-07-20

#### 🎯 Objectif
Phase 2, étape 2 — revue interactive des reclassements proposés.

#### 📋 Modifications
- **scripts/review_recategorizations.py** *(nouveau)* : passe en revue les
  propositions de recatégorisation avant application.

---

### Version 7.27 — 2026-07-20

#### 🎯 Objectif
Phase 2, étape 1 — migrer un libellé hérité vers la taxonomie hiérarchique.

#### 📋 Modifications
- **scripts/migrate_legacy_categories.py** *(nouveau)* : « Plaquette
  d'enseignement - UE » → « Formations ». Mode à blanc par défaut.

---

### Version 7.26 — 2026-07-20

#### 🎯 Objectif
Audit de classification : ne plus confondre un accord réel et un accord par défaut.

#### 📋 Modifications
- **scripts/audit_categories.py** : distingue l'accord positif du repli sur la
  catégorie par défaut, qui gonflait artificiellement le taux de concordance.

---

### Version 7.25 — 2026-07-20

#### 🎯 Objectif
Chantier classification P0 + P1 : correctifs du classifieur et audit en lecture seule.

#### 📋 Modifications
- **services/nlp_engine.py** : correctifs du fast path mots-clés (frontières de
  mots, accents, pluriels).
- **config/categories.py** et **services/llm_service.py** : alignement sur la
  hiérarchie.
- **scripts/audit_categories.py** *(nouveau)* : audit read-only de la
  classification existante.
- **views/ai_categorization_view.py** : ajustements d'affichage.

---

### Version 7.24 — 2026-07-20

#### 🎯 Objectif
Nettoyages P3 du module Feedback (dette technique cosmétique).

#### 📋 Modifications
- **controllers/feedback_controller.py** : suppression de `ensure_indexes()` (code mort — jamais appelé ; les index `feedbacks` sont créés par `db_instance._ensure_indexes()`).
- **views/help_view.py** : libellé des capacités « Utilisateur Public » aligné sur les fonctionnalités réelles (vote 👍/👎 + bouton « 💬 Signaler / Avis »).

#### ✅ Tests
- ✅ Compilation + imports OK ; aucune référence résiduelle à `ensure_indexes`.

---

### Version 7.23 — 2026-07-20

#### 🎯 Objectif
Restaurer et compléter le dispositif de retour utilisateur : bouton « Signaler / Avis » (régression v7.17), vote 👍/👎 sur les réponses du chat, capture de la page courante, historique personnel dans « Mon espace », et corrections de modération.

#### 📋 Modifications
- **app.py** : import + appel `render_feedback_sidebar()` restaurés (supprimés par erreur en v7.17), sous les infos utilisateur (connecté) et en page publique. Mémorisation de `st.session_state["current_view"]` au routage.
- **controllers/rating_controller.py** *(nouveau)* : votes 👍/👎 → collection dédiée `response_ratings` (upsert par utilisateur+question, non bloquant). `get_global_stats()` = taux de satisfaction.
- **views/student_view.py** : `st.feedback("thumbs")` sous chaque réponse de l'Assistant, persistance idempotente ; catégorie ajoutée aux messages.
- **views/user_dashboard_view.py** : section « 🕑 Mon activité » (onglets Avis / Contributions / Validations), lecture seule, pour tous les rôles.
- **controllers/feedback_controller.py** : `update_status()` renseigne `resolved_at` au passage à « Résolu » (et le remet à None si rouvert) + paramètre `priority` optionnel.
- **views/admin_view.py** : selectbox **Priorité** dans la modération ; bandeau satisfaction chat (👍/👎) dans le dashboard feedback.

#### 🔧 Détails Techniques
- Collection `response_ratings` : `{user_email, question, response, category, score, rating: up|down, created_at, updated_at}`. Séparée de `feedbacks` pour ne pas polluer la modération.
- `current_view` : lu par `feedback_view._capture_user_context()` — désormais alimenté, l'admin voit la page d'origine de chaque signalement (fini « Inconnue »).
- Historique : requêtes `feedbacks{context.user_email}`, `contributions{author_email}`, `contributions{validated_by}` (limite 25, tri décroissant).

#### ⚠️ Notes
- Nouvelle collection isolée, aucune migration. Votes anonymes agrégés sous `user_email="anonyme"`.

#### ✅ Tests
- ✅ Compilation `py_compile` + imports complets OK.
- À vérifier en pilote : bouton Avis visible ; vote 👍/👎 persistant ; « Mon activité » alimentée ; page capturée côté admin ; priorité modifiable.

---

### Version 7.22 — 2026-07-20

#### 🎯 Objectif
Éliminer le doublon de changement de mot de passe et supprimer le formulaire de profil self-service du dashboard : le « Mon Espace » devient un résumé de profil en lecture seule.

#### 📋 Modifications
- **views/user_dashboard_view.py** : suppression de l'ÉTAPE 1 (formulaire « Veuillez compléter votre profil ») et de l'ÉTAPE 2 (expander « Sécuriser mon compte » = 2ᵉ changement de MDP redondant). Remplacés par un résumé lecture seule : identité (nom, email, rôle), rattachement (Service/Institut) et domaines assignés (`domain_permissions`).
- **Doublon MDP résolu** : le seul point de changement de mot de passe reste l'écran bloquant `render_forced_password_change` (app.py), déclenché par `must_change_password`.

#### 🔧 Détails Techniques
- Le profil (`structural_type`, `scope`, `departement`) n'est pas porté par la session → relu en base via `db.users.find_one`. Repli sur l'ancien champ `departement` si `scope` absent.
- Accès total affiché pour les rôles admin (`is_admin_or_higher`), sinon liste des sous-catégories assignées (libellés Contributeur/Expert).
- Imports retirés (devenus inutiles) : `datetime`, `AuthController`/`auth_controller`.

#### ⚠️ Notes
- Le profil est désormais **pré-assigné par l'administration** ; l'utilisateur ne peut plus l'éditer depuis son espace.
- Parcours après l'écran bloquant : validation MDP → rerun → « Mon Dashboard » affiche directement le résumé, sans redemander profil ni mot de passe.

#### ✅ Tests
- ✅ Compilation `py_compile` OK (user_dashboard_view.py, app.py).
- À vérifier en pilote : connexion → changement MDP forcé → affichage du résumé de profil.

---

### Version 7.21 — 2026-07-20

#### 🎯 Objectif
Corriger la non-réactivité des menus dépendants (bug : le choix SERVICE/INSTITUT ne changeait pas le libellé ni la liste ; la matrice ne suivait pas le rôle).

#### 📋 Modifications
- **views/admin_view.py** : le formulaire de droits n'est plus un `st.form` (qui bloque les reruns jusqu'à soumission) mais un `st.container` → SERVICE/INSTITUT et Rôle→matrice réagissent en direct. `st.form_submit_button` → `st.button`. Index de selectbox durci (valeur hors-liste → 0).
- **views/user_dashboard_view.py** : formulaire de profil initial idem — la liste dépend du type (services vs instituts), cohérente avec l'admin, réactive.

#### 🔧 Détails Techniques
- Cause racine : dans un `st.form`, les widgets ne déclenchent pas de rerun avant la soumission → les blocs conditionnels utilisent la valeur précédente. Le passage à `st.container` restaure la réactivité.

#### ✅ Tests
- ✅ Suite pytest complète : 87 passed.

---

### Version 7.20 — 2026-07-20

#### 🎯 Objectif
Supprimer le formulaire d'auto-qualification (code mort) et forcer le changement de mot de passe à la première connexion pour tous les comptes du pilote sauf le super admin.

#### 📋 Modifications
- **views/qualification_view.py** : **SUPPRIMÉ** (désactivé depuis v7.15, jamais appelé). L'assignation des profils/droits se fait uniquement via `admin_view.py`.
- **scripts/migrate_pilot_accounts.py** : nouveau mode `--force-reset-all --except <emails>` posant `must_change_password=True` sur tous les comptes sauf ceux exclus.
- **DOCUMENTATION/4_MODULES_DETAILLES.md** : note de suppression.

#### 🔧 Détails Techniques
- Exécuté en base : `must_change_password=True` sur **61 comptes**, exclu `minawade005@gmail.com` (SUPER_ADMIN).
- Chaque collègue devra définir son mot de passe à la 1re connexion (écran bloquant de `app.py`) puis se reconnecter.

#### ⚠️ Notes
- Le super admin conserve son accès sans changement forcé.

#### ✅ Tests
- ✅ Aucune référence Python restante à `qualification_view`.
- ✅ Vérification base : 61 comptes flaggés, super admin intact.

---

### Version 7.19 — 2026-07-20

#### 🎯 Objectif
Persister les sous-catégories ajoutées dynamiquement et fournir un outil de migration des comptes créés avant les correctifs auth/rôles.

#### 📋 Modifications
- **config/categories.py** : `add_category_safe()` persiste désormais dans MongoDB (`categories_extra`) ; nouveaux `load_persisted_categories()` (idempotent, non bloquant) et `_register_subcategory()`. Les sous-catégories ajoutées survivent aux redémarrages.
- **app.py** : chargement unique des sous-catégories persistées au démarrage de session.
- **scripts/migrate_pilot_accounts.py** (nouveau) : audit + migration des comptes — `password` → `password_hash` (hache si en clair), nettoyage des doublons, correction du vocabulaire des rôles, `must_change_password` posé sur les comptes réparés. Dry-run par défaut, `--apply`/`--yes`.

#### 🔧 Détails Techniques
- Collection `categories_extra` : `{name, parent, created_at}` (upsert par `name`).
- Audit réel du pilote : 62 comptes — 0 bloqué, 0 rôle à corriger, 1 doublon à nettoyer.

#### ⚠️ Notes
- La persistance des catégories est non bloquante (mode survie → hiérarchie statique).
- Le script de migration écrit en base : lancer d'abord sans `--apply` (audit).

#### ✅ Tests
- ✅ Suite pytest complète : 87 passed.
- ✅ Audit de migration exécuté en lecture seule sur Atlas.

---

### Version 7.18 — 2026-07-20

#### 🎯 Objectif
Unifier le modèle de permissions pour rendre le filtrage par membre **réellement automatique** (prérequis au partage des accès contribution/validation).

#### 📋 Modifications
- **views/admin_view.py** : le formulaire de droits (master-detail) écrit désormais des **`domain_permissions`** (par sous-catégorie, regroupées par pôle = matrice à deux niveaux) au lieu de l'objet `permissions` (can_read/propose/validate) qui n'était lu par personne. Repli automatique depuis `expert_topics`. Les rôles ADMINISTRATION/SUPER_ADMIN → accès total (aucune assignation).
- **views/admin_view.py** : **vocabulaire des rôles corrigé** — les menus utilisent les constantes canoniques (`ETUDIANT/CONTRIBUTEUR/VALIDATEUR/ADMINISTRATION/SUPER_ADMIN`) au lieu de `USER/CONTRIBUTOR/VALIDATOR` (qui ne matchaient aucun contrôle d'accès → comptes créés inutilisables). Normalisation rétrocompatible via `LEGACY_ROLE_MAP`.
- **views/contributor_view.py** : filtre à deux niveaux (Pôle → Sous-catégorie), cohérent avec le validateur.

#### 🔧 Détails Techniques
- Source de vérité unique du filtrage : `domain_permissions` `{sous-catégorie: "contributor"|"expert"}`, consommé par `config/permissions.py` (`can_answer`, `can_validate`, `get_user_domains_summary`) et les filtres « Mes domaines » (validateur + contributeur).
- `build_domain_permissions_from_form()` construit le dict depuis la matrice (ignore les « — »).

#### ⚠️ Notes
- Les utilisateurs doivent se reconnecter pour que de nouveaux droits prennent effet (chargés au login).
- L'ancien objet `permissions` n'est plus écrit ; `scope`/`structural_type` restent conservés (organisation/affichage).

#### ✅ Tests
- ✅ Suite pytest complète : 87 passed.

---

### Version 7.17 — 2026-07-20

#### 🎯 Objectif
Corriger l'authentification (mot de passe non effectif), renforcer la catégorisation (filtre à deux niveaux + ajout de sous-catégorie dans l'UI), permettre d'écarter les contributions hors-contexte (statut `test`), et visualiser les feedbacks (dashboard in-app).

#### 📋 Modifications
- **controllers/auth_controller.py** : `login()` expose `must_change_password` en session ; nouvelle méthode `change_password(user_id, new_password)` écrivant dans `password_hash` (+ audit).
- **app.py** : écran bloquant `render_forced_password_change()` — changement obligatoire à la première connexion avant tout accès.
- **views/admin_view.py** : création de compte corrigée (écrit `password_hash`, plus `password`) + `must_change_password=True` + garde anti-doublon email + option d'envoi d'email d'identifiants ; ajout de sous-catégorie avec **choix du pôle parent** ; filtre thématique contraint par le pôle ; sous-onglet **🧪 Hors-contexte (Test)** ; **dashboard feedback** (métriques + graphiques type/statut/tendance) ; types de feedback unifiés avec la saisie.
- **views/user_dashboard_view.py** : ajout du wrapper `render_user_dashboard_view()` (attendu par `app.py`) ; identifiant de session (`id`) géré ; changement de mot de passe via `auth_controller.change_password` (écrit `password_hash`).
- **config/categories.py** : `get_subcategories_by_parent(parent)` ; `add_category_safe(new_cat, parent)` (rattachement au pôle choisi).
- **views/validator_view.py** : filtre **Pôle → Sous-catégorie**, statut `Test`, bouton « Marquer hors-contexte ».
- **controllers/kb_controller.py** : `move_to_test(c_id, author_email)` (statut `test`, récupérable) ; `get_stats()` compte les `test`.
- **views/shared_components.py** : `render_comments_and_delete(..., on_mark_test=...)`.

#### 🔧 Détails Techniques
- Champ d'auth canonique confirmé : **`password_hash`** (bcrypt). L'ancien champ `password` n'est plus écrit.
- Nouveau statut de contribution : `test` (exclu des files `en_attente`/`valide`/`archive`, restaurable via « Restaurer »).
- Ajout de sous-catégorie : en **mémoire process** (non persisté au redémarrage) — persistance MongoDB à prévoir.

#### ⚠️ Notes
- **Breaking (données)** : les comptes créés avant ce correctif avec un hash dans `password` ne peuvent pas se connecter — ré-initialiser via `password_hash` (script seed ou recréation).
- Le formulaire admin de droits écrit toujours `scope`/`permissions` (pas `domain_permissions`) : le filtre « Mes domaines » s'appuie sur `domain_permissions` — unification à planifier.

#### ✅ Tests
- ✅ Suite pytest complète : 87 passed.
- ✅ Compilation de tous les fichiers modifiés.

---

### Version 7.16 — 2026-06-22

#### 🎯 Objectif
Activer la collecte de feedback en temps réel pour tous les utilisateurs (pilote) et rétro-documenter le module Feedback complet (vue + contrôleur + modération admin).

#### 📋 Modifications
- **app.py** : `render_feedback_sidebar()` appelé en fin de `main()` → bouton « 💬 Signaler / Avis » accessible à **tous** (connectés ou non).
- **views/feedback_view.py** : composant sidebar + dialogue modal (`@st.dialog`), capture auto du contexte technique, persistance MongoDB.
- **controllers/feedback_controller.py** : CRUD sur la collection `feedbacks`, index composé `(status, type, created_at)`, modération.
- **views/admin_view.py** : `_render_feedback_moderation_tab()` — filtres par statut/type + changement de statut + notes admin.

#### 🔧 Détails Techniques
- Collection MongoDB : `feedbacks` (statut par défaut `"Ouvert"`, priorité auto-déduite via `_infer_priority`).
- Capture silencieuse à la soumission (`_capture_user_context`) : email, nom, rôle, permissions actives, vue courante, timestamp UTC. Utilisateur non connecté → `"anonyme"` / rôle `"PUBLIC"`.
- Validation : description ≥ 10 caractères, max 2000.
- 7 types de feedback (bug, suggestion, UX, contenu, performance, sécurité, autre).
- Index : `feedback_controller.ensure_indexes()` crée `(status, type, created_at DESC)`.
- Dégradation gracieuse : exceptions PyMongo attrapées et loguées, l'UX n'est jamais bloquée.

#### ⚠️ Notes
- Non-breaking : aucune migration de données, nouvelle collection isolée.
- Le bouton est rendu hors du bloc d'authentification → un visiteur anonyme peut signaler un problème.

#### ✅ Tests
- ✅ Module pré-existant (modèle v7.13) ; activation UI validée via la sidebar.
- ✅ RG inchangées.

---

### Version 7.15 — 2026-06-08

#### 🎯 Objectif
1. Figer les profils admin pendant le pilote (désactiver l'auto-qualification).
2. Rétablir une vraie compréhension sémantique via MongoDB Atlas Vector Search.
3. Catégorisation fine via une taxonomie hiérarchique (4 parents × ~16 sous-catégories).

#### 📋 Modifications
- **views/qualification_view.py** : auto-qualification désactivée (`QUALIFICATION_FORM_ENABLED = False`).
- **views/user_dashboard_view.py** : profil en lecture seule + restauration de `render_user_dashboard_view()` + écriture du mot de passe dans `password_hash`.
- **config/categories.py** : référentiel hiérarchique `CATEGORY_HIERARCHY` (remplace le plat).
- **services/nlp_engine.py** : embeddings (sentence-transformers) + `classify_category_full()`, matching mots-clés robuste.
- **controllers/search_controller.py** : `$vectorSearch` Atlas + post-filtre + repli token ; stockage `parent_category`.
- **controllers/kb_controller.py** : auto-embedding à la certification.
- **services/llm_service.py** : `VALID_CATEGORIES` dérivé de la hiérarchie.
- **config/settings.py** : `EMBEDDING_MODEL_NAME`, `EMBEDDING_DIM`, `VECTOR_INDEX_NAME`.
- **scripts/** : `init_embeddings.py` (refonte), `create_vector_index.py` (NEW), `recategorize_hierarchy.py` (NEW).
- **services/audit_service.py** + **tests/test_search_controller.py** : réparation suite de tests.

#### 🔧 Détails Techniques
- Modèle d'embedding : `paraphrase-multilingual-MiniLM-L12-v2` (384 dim, cosine), index Atlas `autoembed_index`.
- `seek_answer()` : `classify_category_full()` → (sous-catégorie, parent) ; matching via `_find_best_answer` (`_vector_search` → `_token_match`).
- Migration BD : 288 contributions ré-embeddées (`question_embedding`) et re-taguées (`category` + `parent_category`).

#### ⚠️ Notes
- BREAKING : l'ancien référentiel plat (MBA, Bourses, Scolarité, Vie_Campus, Général) est remplacé.
- Action manuelle : relancer `scripts/init_embeddings.py` / `scripts/recategorize_hierarchy.py` après un import massif de contributions (sinon repli token en attendant).
- Le module `ollama_service.py` n'existe pas ; la catégorisation LLM passe par `llm_service.py` (HF).

#### ✅ Tests
- ✅ Suite complète : **87 tests passent** (0 erreur).
- ✅ Recherche sémantique validée sur paraphrases (ex. « blazer » ↔ « veste », score 0.86).
- ✅ RG-01 / RG-03 / RG-05 préservées.

---

### Version 7.6 — 2026-05-25

#### 🎯 Objectif
Refactoring majeur de l'architecture de la vue administration pour améliorer l'expérience utilisateur (UX) et optimiser les performances de requêtage MongoDB.

#### 📋 Modifications
- **views/admin_view.py** : Réduction drastique de la taille du fichier (externalisation des composants de rendu).
- **Interface Admin** : Fusion et passage de 5 à 4 onglets principaux avec sous-navigation horizontale par bouton radio.
- **Dossier DOCUMENTATION** : Mise à jour de la documentation d'architecture d'interface utilisateur et de la logique métier.

#### 🔧 Détails Techniques
- `render_admin_view()` : Restructuration complète de la table des onglets Streamlit (indices 0 à 3).
- Implémentation des fonctions privées de rendu modulaire : `_render_pending_questions()`, `_render_users_list_and_creation()`, et `_render_digests_and_logs_subtab()`.

#### ⚠️ Notes
- Aucun changement disruptif (Non-breaking change) sur la base de données.
- Amélioration de la sécurité : l'onglet de configuration du Digest et le journal de sécurité admin sont désormais consolidés sur la même vue d'accès restreint.

#### ✅ Tests
- ✅ Interface Streamlit fluide sans erreur `IndexError` sur les onglets.
- ✅ Isolement des états de formulaires préservé grâce à l'utilisation de clés uniques (`key=`).

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

### Version 7.10 — 2026-05-26

#### 🎯 Objectif
Créer un dashboard personnel pour chaque utilisateur affichant ses permissions, son historique d'actions et ses notifications. Interface unifiée accessible à tous les rôles.

#### 📋 Modifications
- **views/shared_dashboard_components.py** (NEW, 620 lignes) : Composant réutilisable `render_user_profile_metrics()` avec 3 onglets
- **views/user_dashboard_view.py** (NEW, 35 lignes) : Vue Streamlit pour afficher le dashboard
- **app.py** : Ajout menu "📊 Mon Dashboard" en premier item + router
- **DOCUMENTATION/8_MONGODB_DASHBOARD_SCHEMA.md** (NEW) : Schéma complet des collections
- **DOCUMENTATION/9_GUIDE_DASHBOARD_UTILISATEUR.md** (NEW) : Guide utilisateur complet
- **DOCUMENTATION/6_FONCTIONS_PRINCIPALES.md** : Mise à jour avec v7.10

#### 🔧 Détails Techniques
- Collections MongoDB nouvelles : `user_audit_logs`, `user_notifications`
- Indexes : (user_email, timestamp DESC), (recipient_email, created_at DESC)
- Helpers : `render_user_profile_metrics()`, `create_notification()`, `log_action()`
- Timestamps relatifs intelligents : "À l'instant", "Il y a 5m", "Il y a 2h", etc.
- Emojis par type d'action : 🔓 LOGIN, ❓ QUESTION, ✍️ CONTRIBUTION, ✅ VALIDATED, etc.
- Intégration services/audit_service.py (déjà créé v7.9)

#### 🎨 Interface
3 onglets du dashboard :
1. **🛡️ Mes Permissions** : Badges des droits + domaines d'expertise
2. **📜 Historique de mes actions** : Tableau filtrable + stats
3. **🔔 Mes Notifications** : Flux notifications (lues/non-lues)

Composants Streamlit : st.columns, st.dataframe, st.expander, st.status, st.metric

#### ⚠️ Notes
- Chaque utilisateur ne voit que son propre dashboard
- Accessible à TOUS les rôles : SUPER_ADMIN, ADMINISTRATION, VALIDATEUR, CONTRIBUTEUR, ETUDIANT
- Permissions affichées selon `config/roles.py` et `config/permissions.py`
- Domaines d'expertise depuis `domain_permissions` ou `expert_topics` (legacy)

#### ✅ Tests
- ✅ Syntaxe Python validée (py_compile)
- ✅ Imports vérifiés
- ✅ Git push réussi (commit 8dc50cf)
- ✅ Collections MongoDB schema documenté
- ✅ Composant réutilisable validé

---

### Version 7.11 — 2026-05-27

#### 🎯 Objectif
1. Intégrer logging d'audit (LOGIN/LOGOUT) dans auth_controller pour traçabilité complète
2. Valider toutes les features en staging avant déploiement production

#### 📋 Modifications
- **controllers/auth_controller.py** : Ajout logging LOGIN/LOGOUT via audit_instance
- **services/audit_service.py** (NEW) : Service d'audit logging (créé en v7.9, maintenant commité)
- **services/notification_service.py** (NEW) : Service notifications (créé en v7.9, maintenant commité)
- **scripts/validate_staging.py** (NEW) : Suite de tests de validation complète
- **tests/test_audit_integration.py** (NEW) : Tests intégration LOGIN/LOGOUT

#### 🔧 Détails Techniques
- `login()` : Log action LOGIN après authentification réussie
- `logout()` : Log action LOGOUT avant déconnexion
- Gestion d'erreurs : Non-bloquant (déconnexion réussit même si log échoue)
- Audit trail complet : login → [actions] → logout
- Services audit_service et notification_service finalement commités après création v7.9

#### ✅ Tests de Staging (TOUS PASS)
1. **MongoDB Connection** - PASS ✅
2. **Audit Logging** - PASS ✅ (4 actions: LOGIN, QUESTION, CONTRIBUTION, LOGOUT)
3. **Role Hierarchy** - PASS ✅ (7/7 tests de rôles)
4. **Permissions by Role** - PASS ✅
5. **Notifications System** - PASS ✅
6. **Dashboard Components** - PASS ✅ (helpers, timestamps, emojis)

Résultat : **6/6 TESTS PASSED** - Prêt pour production ✅

#### 🐛 Correction
- Résout ModuleNotFoundError sur Streamlit Cloud (audit_service.py, notification_service.py manquaient)

#### ⚠️ Notes
- Chaque action utilisateur créée une trace audit
- Permet réconstruction complète de la session utilisateur
- Historique visible dans Mon Dashboard → Historique
- Tests exécutables via `python scripts/validate_staging.py`

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

**Dernière mise à jour** : 2026-08-06 (v7.38 — socle LLM local souverain)
**Mainteneur** : Équipe ISMaiLa
