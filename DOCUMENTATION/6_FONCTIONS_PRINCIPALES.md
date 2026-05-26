# Fonctions Principales

## 1. Gestion de la connexion DB
- **services/db_connector.py**
  - Fallback `MagicMock` lorsqu'une connexion MongoDB n'est pas disponible, permettant le démarrage en mode dégradé.

## 2. Détection d'une réponse vide ou en attente
- **config/response_helpers.py**
  - Fonctions `has_real_response()` et `has_no_real_response()`
  - Centralise la détection des placeholders ("En attente", "En attente de réponse admin...")
  - Utilisée par 7+ vues et contrôleurs pour filtrage cohérent

## 3. Traitement de l'état de recherche
- **controllers/search_controller.py**
  - Retour explicite du statut `"VIDE"` lorsqu'aucune donnée n'est trouvée.
  - Utilise `has_real_response()` pour déterminer si une réponse doit être considérée comme vide.

## 4. Gestion des rôles et permissions
- **config/roles.py**
  - Hiérarchie des rôles : `ADMIN_ROLES = [ADMIN, SUPER_ADMIN]`, `MODERATOR_ROLES = [VALIDATOR, ADMIN, SUPER_ADMIN]`
  - Helper functions : `is_admin_or_higher()`, `is_moderator_or_higher()`, `is_super_admin()`
  - SUPER_ADMIN hérite de tous les droits ADMIN + droits exclusifs (création comptes)

## 5. Permissions granulaires par domaine
- **config/permissions.py**
  - Trois niveaux: `learner` (lecture), `contributor` (propose), `expert` (propose + valide)
  - Support legacy `expert_topics` et nouveau modèle `domain_permissions`
  - Migration auto au login via `migrate_expert_topics_to_permissions()`

## 6. Sécurité des mots de passe
- **services/auth.py** (ou module similaire)
  - Utilise `bcrypt` pour le hachage et la vérification des mots de passe.

## 7. Templates et digests personnalisables
- **config/digest_templates.py**
  - Template par défaut pour digests utilisateurs
  - Helper `format_digest_for_email()` pour formater avant envoi
  - Administateurs peuvent personnaliser via onglet Notifications

## 8. Journalisation d'audit
- **services/audit_service.py**
  - Traçage centralisé de toutes les actions (LOGIN, LOGOUT, QUESTION_ASKED, CONTRIBUTION_*, etc.)
  - Collection MongoDB `user_audit_logs`
  - Methods : `log_action()`, `get_user_actions()`, `get_actions_by_type()`
  - Instance singleton : `audit_instance`

## 9. Notifications utilisateur
- **views/shared_dashboard_components.py**
  - Gestion des notifications in-app et emails
  - Collection MongoDB `user_notifications` avec statut lecture (read_at)
  - Helper `create_notification()` pour créer notification depuis contrôleurs
  - Methods : `get_user_notifications()`, `mark_as_read()`, `delete_notification()`

## 10. Dashboard utilisateur
- **views/user_dashboard_view.py** + **views/shared_dashboard_components.py**
  - Composant réutilisable `render_user_profile_metrics()`
  - Onglet 1: **Mes Permissions** — Badges des droits selon rôle + domaines expertise
  - Onglet 2: **Historique de mes actions** — Tableau filtrable des dernières actions
  - Onglet 3: **Mes Notifications** — Flux notifications (lues/non-lues, avec marquage)
  - Accessible à tous les rôles (SUPER_ADMIN, ADMINISTRATION, VALIDATEUR, CONTRIBUTEUR, ETUDIANT)
  - Chaque utilisateur ne voit que son propre dashboard

## 11. Notification et emails
- **services/mailer.py**
  - Envoi de digests, alertes et emails de bienvenue.
  - Support custom templates depuis admin_controller

## 12. Statistiques et logs
- `AdminController.get_full_stats` et `AdminController.get_contribution_stats_by_user` pour les tableaux de bord admin.
- `AuditService.get_action_count_by_type()` pour stats par action
- `AuditService.get_recent_actions_all_users()` pour timeline globale

---
**Mise à jour** : v7.10 — Dashboard utilisateur avec permissions, historique, notifications
**Dernière modification** : 2026-05-26
