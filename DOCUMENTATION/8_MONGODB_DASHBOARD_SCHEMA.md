# Schéma MongoDB — Collections pour le Dashboard Utilisateur

## 📋 Vue d'ensemble

Le dashboard utilisateur utilise 3 collections MongoDB pour afficher les permissions, historique et notifications.

---

## 1️⃣ Collection: `user_audit_logs`

**Objectif:** Tracer toutes les actions effectuées par chaque utilisateur (login, contributions, validations, etc.)

### Schéma du document

```javascript
{
  "_id": ObjectId,                      // ID unique MongoDB
  "user_email": "user@domain.com",      // Email utilisateur (indexed)
  "action": "LOGIN",                    // Type d'action (voir liste ci-dessous)
  "description": "Connexion utilisateur", // Description lisible
  "timestamp": ISODate("2026-05-26T..."), // Quand l'action a eu lieu (indexed)
  "metadata": {                         // Données additionnelles (flexible)
    "ip": "192.168.1.1",               // Optionnel: adresse IP
    "question_id": "q123",             // Optionnel: ID de la question (si applicable)
    "contribution_id": "c456",         // Optionnel: ID de la contribution
    "category": "MBA",                 // Optionnel: domaine d'action
    "details": "Contribution proposée sur MBA" // Optionnel: détails
  }
}
```

### Types d'actions supportées

| Action | Description | Quand | Metadata typique |
|--------|-------------|-------|------------------|
| `LOGIN` | Connexion utilisateur | auth_controller.login() | ip |
| `LOGOUT` | Déconnexion utilisateur | auth_controller.logout() | — |
| `QUESTION_ASKED` | Question posée au chat | search_controller.search() | question_id, category |
| `CONTRIBUTION_PROPOSED` | Contribution proposée | admin_controller.propose() | contribution_id, category |
| `CONTRIBUTION_VALIDATED` | Contribution validée | admin_controller.validate() | contribution_id |
| `CONTRIBUTION_REJECTED` | Contribution rejetée | admin_controller.reject() | contribution_id |
| `ANSWER_PROVIDED` | Réponse fournie pour une question | admin_controller.answer() | question_id, contribution_id |
| `ACCOUNT_CREATED` | Compte créé | admin_controller.create_user() | — |

### Indexes recommandés

```python
db.user_audit_logs.create_index("user_email")
db.user_audit_logs.create_index([("user_email", 1), ("timestamp", -1)])
db.user_audit_logs.create_index("action")
```

### Utilisation dans le code

```python
from services.audit_service import audit_instance

# Logger une action
audit_instance.log_action(
    user_email="student@example.com",
    action="QUESTION_ASKED",
    description="Étudiant a posé une question",
    metadata={"question_id": "q123", "category": "MBA"}
)

# Récupérer les actions d'un utilisateur
actions = audit_instance.get_user_actions("student@example.com", limit=30)

# Filtrer par type d'action
logins = audit_instance.get_actions_by_type("student@example.com", "LOGIN")
```

---

## 2️⃣ Collection: `user_notifications`

**Objectif:** Stocker les notifications reçues par chaque utilisateur (notifications in-app + email)

### Schéma du document

```javascript
{
  "_id": ObjectId,                      // ID unique MongoDB
  "recipient_email": "user@domain.com", // Email du destinataire (indexed)
  "type": "success",                    // Type: "info" | "warning" | "success" | "action_required"
  "title": "Votre contribution a été validée!", // Titre court (visible dans le badge)
  "message": "Votre réponse sur 'MBA' a été approuvée par l'équipe d'experts.", // Message détaillé
  "action_url": "/admin/validations#contrib123", // URL optionnelle pour action directe
  "created_at": ISODate("2026-05-26T..."), // Quand créée (indexed)
  "read_at": null                       // null = non-lue; ISODate("...") = lue le...
}
```

### Types de notifications

| Type | Emoji | Cas d'usage |
|------|-------|-----------|
| `info` | ℹ️ | Information générale (bienvenue, mise à jour) |
| `warning` | ⚠️ | Avertissement (limite atteinte, révision recommandée) |
| `success` | ✅ | Action réussie (contribution validée, question répondre) |
| `action_required` | 🔔 | Demande d'action (validation en attente, commentaire reçu) |

### Indexes recommandés

```python
db.user_notifications.create_index("recipient_email")
db.user_notifications.create_index([("recipient_email", 1), ("created_at", -1)])
db.user_notifications.create_index("read_at")  # Pour compter non-lues rapidement
```

### Exemples de documents

**Notification: Contribution validée**
```javascript
{
  "_id": ObjectId("..."),
  "recipient_email": "contributor@domain.com",
  "type": "success",
  "title": "✅ Votre contribution a été validée!",
  "message": "Votre réponse sur 'Bourses' a été approuvée par l'équipe d'experts et est maintenant visible à tous.",
  "action_url": "/admin/validations#12345",
  "created_at": ISODate("2026-05-26T14:30:00Z"),
  "read_at": ISODate("2026-05-26T14:35:00Z")  // Lue
}
```

**Notification: Bienvenue**
```javascript
{
  "_id": ObjectId("..."),
  "recipient_email": "newuser@domain.com",
  "type": "info",
  "title": "🎉 Bienvenue sur ISMaiLa!",
  "message": "Vous êtes maintenant inscrit comme CONTRIBUTEUR. Explorez la base de connaissances et commencez à proposer des réponses.",
  "action_url": null,
  "created_at": ISODate("2026-05-26T10:00:00Z"),
  "read_at": null  // Non-lue
}
```

### Utilisation dans le code

```python
from views.shared_dashboard_components import create_notification

# Créer une notification
create_notification(
    recipient_email="user@example.com",
    notif_type="success",
    title="Contribution validée!",
    message="Votre réponse a été approuvée par l'équipe d'experts.",
    action_url="/admin/validations#123"
)

# Récupérer les notifications d'un utilisateur
notifications = db_instance.get_collection("user_notifications").find(
    {"recipient_email": "user@example.com"}
).sort("created_at", -1).limit(50)

# Compter les non-lues
unread_count = db_instance.get_collection("user_notifications").count_documents({
    "recipient_email": "user@example.com",
    "read_at": None
})

# Marquer comme lue
db_instance.get_collection("user_notifications").update_one(
    {"_id": ObjectId("...")},
    {"$set": {"read_at": datetime.now(timezone.utc)}}
)
```

---

## 3️⃣ Collection: `users` (existante)

**Modifications pour supporter le dashboard:**

Ajouter ces champs optionnels au profil utilisateur pour enrichir le dashboard:

```javascript
{
  "_id": ObjectId,
  "email": "user@domain.com",
  "full_name": "Nom Complet",
  "password_hash": "bcrypt$...",               // Hash bcrypt (champ: password_hash)
  "password_changed_at": ISODate("..."),       // NOUVEAU v7.15: dernier changement
  "role": "VALIDATEUR",
  "created_at": ISODate("2026-01-01T..."),
  "last_login": ISODate("2026-05-25T..."),    // Dernière connexion
  "profile_configured": true,                  // Profil figé pré-assigné par l'admin (v7.15)
  "structural_type": "INSTITUT",               // SERVICE | INSTITUT
  "entity": "Institut Management",             // Entité / département
  "job_level": "Responsable",                  // Opérationnel | Responsable
  "permissions": {                             // Permissions figées (lecture seule côté user)
    "can_read": true, "can_propose": true, "can_validate": true
  },
  "expert_topics": ["MBA", "Admission"],      // Legacy
  "domain_permissions": {                      // Legacy / granulaire
    "MBA": "expert",
    "Bourses": "contributor"
  }
}
```

> ⚠️ Le champ d'authentification est **`password_hash`** (et non `password`).

---

## 4️⃣ Collection: `contributions` — champs sémantiques (v7.15)

```javascript
{
  "_id": ObjectId,
  "question": "Comment trouver ma classe ?",
  "response": "...",
  "status": "valide",                          // en_attente | valide | archive
  "category": "Déroulement et Planning de cours", // SOUS-catégorie (tag fin)
  "parent_category": "Pédagogie",              // Catégorie parente (v7.15)
  "question_embedding": [0.01, -0.04, ...]      // Vecteur 384 dim (Atlas Vector Search, v7.15)
}
```

**Index Atlas Vector Search** : `autoembed_index` (type `vectorSearch`, `question_embedding`, 384 dim, cosine).
Créé/listé via `python scripts/create_vector_index.py`. Vecteurs générés via `scripts/init_embeddings.py`.

---

## 🔧 Scripts d'initialisation

### Créer les indexes (exécuter une fois)

```python
# Indexes pour user_audit_logs
db.user_audit_logs.create_index("user_email")
db.user_audit_logs.create_index([("user_email", 1), ("timestamp", -1)])
db.user_audit_logs.create_index("action")

# Indexes pour user_notifications
db.user_notifications.create_index("recipient_email")
db.user_notifications.create_index([("recipient_email", 1), ("created_at", -1)])
db.user_notifications.create_index("read_at")
```

### Tester avec des données de test

```python
from datetime import datetime, timezone
from bson import ObjectId

# Insérer un log d'audit de test
db.user_audit_logs.insert_one({
    "user_email": "test@example.com",
    "action": "LOGIN",
    "description": "Connexion utilisateur",
    "timestamp": datetime.now(timezone.utc),
    "metadata": {"ip": "127.0.0.1"}
})

# Insérer une notification de test
db.user_notifications.insert_one({
    "recipient_email": "test@example.com",
    "type": "success",
    "title": "✅ Test réussi!",
    "message": "Ceci est une notification de test.",
    "created_at": datetime.now(timezone.utc),
    "read_at": None
})
```

---

## 📊 Requêtes courantes

### Récupérer l'historique des actions d'un utilisateur

```python
logs = db.user_audit_logs.find(
    {"user_email": "user@example.com"}
).sort("timestamp", -1).limit(30)
```

### Compter les actions par type pour un utilisateur

```python
db.user_audit_logs.aggregate([
    {"$match": {"user_email": "user@example.com"}},
    {"$group": {"_id": "$action", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}}
])
```

### Récupérer les notifications non-lues

```python
unread = db.user_notifications.find({
    "recipient_email": "user@example.com",
    "read_at": None
}).sort("created_at", -1)
```

### Compter les notifications non-lues par utilisateur

```python
db.user_notifications.aggregate([
    {"$match": {"read_at": None}},
    {"$group": {"_id": "$recipient_email", "unread_count": {"$sum": 1}}},
    {"$sort": {"unread_count": -1}}
])
```

### Nettoyer les vieilles notifications (> 90 jours)

```python
from datetime import datetime, timedelta, timezone

cutoff = datetime.now(timezone.utc) - timedelta(days=90)
db.user_notifications.delete_many({
    "created_at": {"$lt": cutoff}
})
```

---

## 🔐 Bonnes pratiques

1. **Indexation**: Tous les champs interrogés fréquemment doivent être indexés
2. **TTL (optionnel)**: Configurer un index TTL sur `user_audit_logs` pour auto-nettoyer après X jours
3. **Timestamps**: Toujours utiliser `datetime.now(timezone.utc)` pour la cohérence
4. **Email**: Utiliser `email` (minuscules) comme clé de jointure avec `users`
5. **Rétention**: Garder les logs audit pendant 1-2 ans pour conformité
6. **Notifications**: Garder les notifications pendant 90 jours puis archiver/supprimer

---

## 🚀 Intégration avec les vues

### Dashboard utilisateur

```python
from views.shared_dashboard_components import render_user_profile_metrics

# Dans n'importe quelle vue Streamlit
render_user_profile_metrics(st.session_state.user)
```

### Créer une notification depuis un contrôleur

```python
from views.shared_dashboard_components import create_notification

# Après valider une contribution
create_notification(
    recipient_email="contributor@example.com",
    notif_type="success",
    title="✅ Votre contribution a été validée!",
    message="Votre réponse sur 'MBA' a été approuvée.",
    action_url="/admin/validations#123"
)
```

### Logger une action depuis un contrôleur

```python
from services.audit_service import audit_instance

# Après chaque action utilisateur
audit_instance.log_action(
    user_email=user["email"],
    action="CONTRIBUTION_PROPOSED",
    description="Contribution proposée",
    metadata={"contribution_id": "c123", "category": "MBA"}
)
```
