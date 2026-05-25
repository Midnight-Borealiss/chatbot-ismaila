# Logique Métier

## Contexte
Le projet **MVP 7 Pilote V3** repose sur une architecture de services et de contrôleurs qui interagissent avec une base de données MongoDB (via `db_connector`).

## Modifications Récentes (v7.4 - v7.7)

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

### 4. Filtres Statut & Catégorie + Templates Digest (v7.6)
- **Filtrage avancé** dans toutes les vues
  - Views : contributor_view, validator_view, admin_view, ai_categorization_view
  - Sélecteurs UI pour filtrer par Statut (En attente / Validée / Archivée) et Catégorie
  - Mapping UI→BD : {"En attente"→"en_attente", "Validée"→"valide", "Archivée"→"archive"}
  - Queries MongoDB appliquant les filtres

- **Templates digest personnalisables**
  - **config/digest_templates.py** (NOUVEAU)
    - DEFAULT_CONTRIBUTOR_DIGEST et DEFAULT_VALIDATOR_DIGEST
    - Fonctions : `format_digest_template()`, `build_questions_list()`
    - Variables disponibles : {full_name}, {count}, {questions_list}, {platform_url}
  - **Admin Notifications UI**
    - Sous-onglets : "Envoi rapide" (template défaut) vs "Personnaliser template" (custom)
    - Aperçu live de rendu digest
  - **AdminController.send_digest_to_all()** signature étendue
    - Paramètres : `contributor_template=None`, `validator_template=None`

### 5. Page Help Statique (v7.7)
- **views/help_view.py** (NOUVEAU)
  - Visible pour TOUS : utilisateurs connectés + publics
  - **Tab 1** - Objectif & Vision
    - Explique ISMaiLa (KMS souveraine)
    - Importance : réduction support, amélioration continue, transparence
    - Workflow : 6 étapes (question → réponse → validation → intégration)
  - **Tab 2** - Rôles & Permissions
    - 5 profils : Public, Contributeur, Validateur, Admin
    - Détail des droits (✅ peut) et restrictions (❌ ne peut pas)
  - **Tab 3** - Guide par profil
    - Contenu personnalisé selon `st.session_state.user["role"]`
    - Instructions étape-par-étape + bonnes pratiques
  - **Tab 4** - FAQ
    - 8 Q&R : délais, modifications, récompenses, catégorisation, IA, rejet, hors-sujet, export
- **Integration dans app.py**
  - Menu navigation : "❓ Aide" (connectés)
  - Page publique : Tab "❓ Aide" avant login

### 6. Anciennes Modifications (Conservées)
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
- Intégrer template email générique avec lien + identifiants (point 1 priorité)
- Dashboard utilisateurs (permissions + historique + notifications) — point 5 priorité
- Bulle feedback pilote (chat → admin) — point 7 priorité
- Déduplication Ollama (complexe) — point 8 priorité
- Créer comptes test par profil — point 9 priorité

## Configuration du digest dans l'interface admin

Dans l'onglet **Notifications** du tableau de bord admin, une nouvelle interface permet de :

- sélectionner les éléments à inclure dans le digest via trois cases à cocher,
- choisir la fréquence (Quotidien, Hebdomadaire, Mensuel) avec un menu déroulant,
- sauvegarder les paramètres de façon persistante dans la collection `admin_settings` de MongoDB.

Ces réglages sont chargés au chargement de la page grâce à `admin_controller.get_digest_settings` et enregistrés via `admin_controller.set_digest_settings`. Le bouton « Envoyer le digest à tous » utilise ces paramètres lors de la génération du résumé.

Cette fonctionnalité a été ajoutée dans la version v7.6.

---

## Résumé des Statuts de Modifications (Priorité)

D'après la liste fournie par l'utilisateur, voici l'état d'avancement :

| # | Feature | Priorité | Statut | Version |
|----|---------|----------|--------|---------|
| 1 | Message générique (template email) | 🔴 | ⏳ Planifiée | v7.8+ |
| 2 | Questionnaire Google Form | 🟡 | ⏳ Planifiée | v8.0+ |
| 3 | Page Help statique | 🟡 | ✅ DÉPLOYÉE | v7.7 |
| 4 | Modification admin_view (fusion onglets) | 🟡 | 🟢 Partielle | v7.6 |
| 5 | Dashboard utilisateurs | 🔴 | ⏳ Planifiée | v8.0+ |
| 6 | Ajout catégorie dans toutes les vues | 🟡 | ✅ DÉPLOYÉE | v7.6 |
| 7 | Bulle feedback pilote (chat → admin) | 🔴 | ⏳ Planifiée | v8.0+ |
| 8 | Déduplication Ollama | 🔴 | ⏳ Planifiée | v8.1+ |
| 9 | Créer comptes test par profil | 🟢 | ⏳ Planifiée | v7.8 |
| 10 | Résoudre fausses réponses | 🔴 | ✅ RÉSOLU | v7.4-v7.5 |

**Légende** : 🔴 Élevée | 🟡 Moyenne | 🟢 Basse | ✅ Fait | ⏳ En attente
