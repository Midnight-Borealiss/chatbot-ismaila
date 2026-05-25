# Fonctions Principales

## 1. Gestion de la connexion DB
- **services/db_connector.py**
  - Fallback `MagicMock` lorsqu'une connexion MongoDB n'est pas disponible
  - Permet le démarrage en mode dégradé/mode survie

## 2. Détection d'une réponse réelle vs placeholder (v7.4+)
- **config/response_helpers.py**
  - `has_real_response(response: str) -> bool`
    - Retourne `True` si réponse valide (non-vide, pas placeholder)
    - Placeholders : "", "En attente", "En attente de réponse admin...", etc.
  - `has_no_real_response(response: str) -> bool` (inverse)
  - **Centralise** la logique remplaçant `KBController.is_empty_or_pending()`
  - Utilisée dans : AdminController, SearchController, Views

## 3. Traitement de l'état de recherche
- **controllers/search_controller.py**
  - Retour explicite `"VIDE"` si aucune réponse
  - Crée tickets avec `response=""` (pas placeholder)
  - Utilise `has_real_response()` pour statut réel

## 4. Sécurité des mots de passe
- **services/auth.py**
  - `bcrypt` pour hachage + vérification

## 5. Notification et emails
- **services/mailer.py**
  - `send_pending_digest(email, name, count, questions, role, custom_template=None)`
  - Support templates default ou custom
  - Envoi digests, alertes, emails bienvenue

## 6. Templates digest personnalisables (v7.6+)
- **config/digest_templates.py**
  - `DEFAULT_CONTRIBUTOR_DIGEST` : Template par défaut contributeurs
  - `DEFAULT_VALIDATOR_DIGEST` : Template par défaut validateurs
  - `format_digest_template(template, **variables)` : Substitution {full_name}, {count}, {questions_list}, {platform_url}
  - `build_questions_list(questions)` : Formatage questions

## 7. Filtres statut & catégorie (v7.6+)
- **Views : contributor, validator, admin, ai_categorization**
  - Sélecteurs UI : Statut + Catégorie
  - Mapping UI→BD : {"En attente"→"en_attente", "Validée"→"valide", "Archivée"→"archive"}
  - Queries MongoDB avec filtres appliqués
  - Utilise helpers `has_real_response/has_no_real_response`

## 8. Statistiques et logs
- **AdminController**
  - `get_full_stats()` : KPIs (logs, automation_rate, KB state)
  - `get_contribution_stats_by_user()` : Récap contributions/validations
  - `get_nlp_precision(days=30)` : Taux succès NLP
  - `send_digest_to_all(admin_email, contributor_template, validator_template)` : Envoi digests

## 9. Page Help statique (v7.7+)
- **views/help_view.py**
  - Visible pour tous (connectés + publics)
  - **Tab 1** - Objectif & Vision : Explique ISMaiLa, importance, workflow
  - **Tab 2** - Rôles & Permissions : 5 profils (Public, Contributeur, Validateur, Admin) avec droits
  - **Tab 3** - Guide par profil : Instructions personnalisées (détecte role)
  - **Tab 4** - FAQ : 8 Q&R communes

## 10. Nettoyage base de données
- **scripts/cleanup_placeholders.py** (v7.5+)
  - Supprime placeholders connus → ""
  - Idempotent (ré-exécutable)
- **clean_db.py** (v7.6+)
  - Utilitaires nettoyage manuel

---
**Dernière mise à jour** : 2026-05-25
**Mainteneur** : Équipe ISMaiLa
