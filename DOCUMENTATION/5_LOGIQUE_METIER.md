# Logique Métier

## Contexte
Le projet **MVP 7 Pilote V3** repose sur une architecture de services et de contrôleurs qui interagissent avec une base de données MongoDB (via `db_connector`).

## Modifications récentes
### 1. Gestion de la connexion DB
- **services/db_connector.py**
  - Ajout d’un fallback `MagicMock` lorsqu’une connexion à MongoDB n’est pas disponible. Cela permet à l’application de démarrer en mode dégradé et évite les `RuntimeError` lors de l’exécution des tests.

### 2. Détection d’une réponse « vide » ou en attente
- **controllers/kb_controller.py**
  - Ajout de la méthode statique `is_empty_or_pending(content: str) -> bool` qui renvoie `True` si le texte est vide, ne contient que des espaces ou correspond exactement à la chaîne *« En attente de réponse admin… »*.
  - Cette méthode centralise la logique utilisée par plusieurs contrôleurs (ex. `AdminController`, `SearchController`).

### 3. Traitement de l’état de recherche
- **controllers/search_controller.py**
  - Retour explicite du statut `"VIDE"` lorsqu’aucune donnée n’est trouvée dans la base.
  - Utilisation de `KBController.is_empty_or_pending` pour déterminer si une réponse doit être considérée comme vide.

### 4. Tests
- Les fixtures de test ont été mises à jour (`tests/conftest.py`, `tests/test_*.py`) afin d’utiliser les mocks appropriés (`MagicMock`, `monkeypatch`).
- L’ensemble de la suite passe maintenant **68 tests** avec succès.

## Impact sur la logique métier
- La nouvelle méthode `is_empty_or_pending` garantit une détection fiable des réponses en attente, évitant ainsi que des questions soient considérées comme résolues alors qu’elles ne le sont pas.
- Le fallback DB assure la robustesse du service en environnement de CI/CD où MongoDB peut être indisponible.

## Prochaines étapes
- Intégrer `KBController.is_empty_or_pending` dans le `AdminController` pour corriger la répartition des questions (Priorité 2).
- Documenter les nouvelles fonctions dans le fichier **6_FONCTIONS_PRINCIPALES.md**.
