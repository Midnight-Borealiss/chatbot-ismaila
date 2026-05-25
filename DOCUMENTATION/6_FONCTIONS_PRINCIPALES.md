# Fonctions Principales

## 1. Gestion de la connexion DB
- **services/db_connector.py**
  - Fallback `MagicMock` lorsqu’une connexion MongoDB n’est pas disponible, permettant le démarrage en mode dégradé.

## 2. Détection d’une réponse vide ou en attente
- **controllers/kb_controller.py**
  - Méthode statique `is_empty_or_pending(response: str) -> bool`
    - Retourne `True` si la chaîne est vide, ne contient que des espaces, ou commence par `"En attente"` (ex. "En attente de réponse admin…").
    - Centralise la logique utilisée par plusieurs contrôleurs (`AdminController`, `SearchController`).

## 3. Traitement de l’état de recherche
- **controllers/search_controller.py**
  - Retour explicite du statut `"VIDE"` lorsqu’aucune donnée n’est trouvée.
  - Utilise `KBController.is_empty_or_pending` pour déterminer si une réponse doit être considérée comme vide.

## 4. Sécurité des mots de passe
- **services/auth.py** (ou module similaire)
  - Utilise `bcrypt` pour le hachage et la vérification des mots de passe.

## 5. Notification et emails
- **services/mailer.py**
  - Envoi de digests, alertes et emails de bienvenue.

## 6. Statistiques et logs
- `AdminController.get_full_stats` et `AdminController.get_contribution_stats_by_user` pour les tableaux de bord admin.

---
**Remarque** : La documentation complète de chaque fonction peut être enrichie au besoin.
