# Logique Métier

## Contexte
Le projet **MVP 7 Pilote V3** repose sur une architecture de services et de contrôleurs qui interagissent avec une base de données MongoDB (via `db_connector`).

## Modifications Récentes (v7.4 - v7.5)

### 1. Centralisation de la Détection de Réponses Réelles (v7.4)
- **config/response_helpers.py** (NOUVEAU)
  - Helper centralisé `has_real_response(response: str) -> bool`
  - Identifie si une réponse contient du contenu réel (pas un placeholder)
  - Placeholders gérés : "En attente", "En attente de réponse admin...", ""
  - Utilisé dans 5 fichiers pour une logique cohérente

### 2. Correction Filtrage Questions Admin (v7.4)
- **controllers/admin_controller.py**
  - Méthode `send_digest_to_all()` : Utilise maintenant `has_real_response()`
  - Méthode `get_filtered_pending()` : Filtre précis avec has_proposal=True/False
  - Résultat : Admin voit uniquement vraies propositions

- **views/validator_view.py, views/contributor_view.py, views/admin_view.py**
  - Filtre "Avec proposition" : Utilise `has_real_response()`
  - Filtre "Sans réponse" : Utilise `has_no_real_response()`
  - Impact : Répartition exacte des questions en attente

### 3. Nettoyage Base de Données (v7.5)
- **scripts/cleanup_placeholders.py** (NOUVEAU)
  - Script utilitaire supprimant tous placeholders existants
  - Exécution : 166 documents corrigés (70 "En attente" + 96 "En attente de réponse admin...")
- **controllers/search_controller.py**
  - Nouvelles questions créées avec `response: ""` au lieu de placeholder
  - Méthodes affectées : `_handle_expert_question()`, `_create_ticket()`

### 4. Anciennes Modifications (Conservées)
- **services/db_connector.py**
  - Fallback `MagicMock` pour tests en environnement sans MongoDB
  
- **controllers/kb_controller.py** (antérieur)
  - Méthode `is_empty_or_pending()` (predecesseur de `has_real_response()`)

## Impact sur la Logique Métier

### Avant v7.4
❌ Questions "En attente de réponse admin..." comptées comme répondues
❌ Filtrage "Avec proposition" contenait des placeholders
❌ Admin voyait données faussées
❌ Logique dupliquée dans 5 endroits

### Après v7.5
✅ Détection centralisée via `has_real_response()`
✅ Filtrage exact : "Avec proposition" = vraies réponses uniquement
✅ Base nettoyée : 166 placeholders supprimés
✅ Nouvelles questions sans placeholders
✅ Code maintenable et cohérent

## Respect des Règles de Gestion (RG)
- **RG-01** (Expert alert) : Filtre correct pour déterminer questions non répondues
- **RG-03** (Email routing) : Digest envoyé uniquement à contributeurs avec vraies questions
- **RG-05** (Lead capture) : Basé sur questions réelles, pas placeholders

## Prochaines Étapes
- Intégrer template email générique avec lien + identifiants (v7.6)
- Ajouter catégorie dans toutes les vues (v7.7)
