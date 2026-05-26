# 📊 Dashboard Utilisateur — Guide d'utilisation complet

## Vue d'ensemble

Chaque utilisateur connecté (quel que soit son rôle) a accès à un dashboard personnel avec 3 sections :

1. **🛡️ Mes Permissions** — Quels droits vous avez dans l'application
2. **📜 Historique de mes actions** — Toutes vos actions enregistrées (logins, contributions, validations, etc.)
3. **🔔 Mes Notifications** — Les notifications reçues (lues et non-lues)

---

## 🎯 Comment accéder au Dashboard

1. **Connexion** : Connectez-vous à ISMaiLa avec vos identifiants
2. **Menu navigation** : Cliquez sur **"📊 Mon Dashboard"** (premier menu item)
3. **Affichage** : Vous voyez vos 3 onglets personnalisés

---

## 🛡️ Onglet 1 : Mes Permissions

### Affichage

```
📋 Mon Rôle: VALIDATEUR
👤 Email: validator@example.com

Permissions octroyées:
  ✅ READ ✓           ✅ VALIDATE ✓
  Description...      Description...

Restrictions:
  ❌ PROPOSE
  ❌ ALL
```

### Que signifient les permissions ?

| Permission | Signification | Qui a | 
|-----------|-------------|-------|
| **READ** | Lire les questions et réponses | Tous |
| **PROPOSE** | Proposer des réponses | CONTRIBUTEUR, VALIDATEUR, ADMIN, SUPER_ADMIN |
| **VALIDATE** | Valider les réponses | VALIDATEUR, ADMIN, SUPER_ADMIN |
| **ALL** | Accès complet (admin) | ADMIN, SUPER_ADMIN |
| **SUPER** | Créer des comptes | SUPER_ADMIN seulement |

### Domaines d'expertise

Si vous êtes expert ou contributeur dans certains domaines, vous les voyez listés :

```
🎓 Mes domaines d'expertise:

  🔒 Expert (propose + valide)
     MBA, Admission

  ✍️ Contributeur (propose seulement)
     Bourses
```

---

## 📜 Onglet 2 : Historique de mes actions

### Affichage

```
Nombre d'actions à afficher: [====30====]

Filtrer par type: [Tous ▼]

Quand        | Action                        | Détails
─────────────┼──────────────────────────────┼─────────────────
À l'instant  | 🔓 Connexion utilisateur     | —
Il y a 2h    | ❓ Question posée au chat    | —
Il y a 4h    | ✍️ Contribution proposée    | Sur MBA
Il y a 1j    | ✅ Contribution validée     | Réponse #1234

📊 Statistiques:
  Total actions: 48  |  Connexions: 12  |  Contributions: 8
```

### Types d'actions tracées

| Action | Emoji | Description |
|--------|-------|-------------|
| LOGIN | 🔓 | Vous vous êtes connecté |
| LOGOUT | 🚪 | Vous vous êtes déconnecté |
| QUESTION_ASKED | ❓ | Vous avez posé une question |
| CONTRIBUTION_PROPOSED | ✍️ | Vous avez proposé une réponse |
| CONTRIBUTION_VALIDATED | ✅ | Vous avez validé une réponse |
| CONTRIBUTION_REJECTED | ❌ | Vous avez rejeté une réponse |
| ANSWER_PROVIDED | 💬 | Vous avez fourni une réponse |
| ACCOUNT_CREATED | 👤 | Votre compte a été créé |

### Comment filtrer ?

- **Nombre d'actions** : Utilisez le slider pour afficher 10 à 100 actions
- **Filtrer par type** : Sélectionnez un type d'action dans la liste déroulante

### Timestamps intelligents

Les dates s'affichent en format relatif pour plus de clarté :

- "À l'instant" → moins d'une minute
- "Il y a 5m" → 5 minutes
- "Il y a 2h" → 2 heures
- "Il y a 3j" → 3 jours

---

## 🔔 Onglet 3 : Mes Notifications

### Affichage

```
Vous avez 8 notifications
                    Non-lues: 3

Afficher seulement non-lues  ☐
Afficher les lues aussi      ☑

┌─────────────────────────────────────────────┐
│ ✅ Votre contribution a été validée!       │
│ Votre réponse sur 'MBA' a été approuvée    │
│ par l'équipe d'experts.                    │
│ 📅 Il y a 2h                               │
│ [🔗 Voir] [✓ Marquer lue] [✕ Supprimer]  │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ ℹ️ Bienvenue sur ISMaiLa v7.10!             │
│ 🆕 Non-lue                                  │
│ 📅 À l'instant                             │
│ [✓ Marquer lue] [✕ Supprimer]             │
└─────────────────────────────────────────────┘
```

### Types de notifications

| Type | Emoji | Exemple |
|------|-------|---------|
| **info** | ℹ️ | Mise à jour système, bienvenue |
| **warning** | ⚠️ | Limite atteinte, révision recommandée |
| **success** | ✅ | Contribution validée, action réussie |
| **action_required** | 🔔 | Validation attendue, commentaire reçu |

### Actions possibles

Chaque notification a des boutons d'action :

| Bouton | Action | Quand |
|--------|--------|-------|
| 🔗 Voir | Accéder à la page concernée | Si applicable (ex: va à la validation) |
| ✓ Marquer lue | Passer une notification non-lue à lue | Seulement sur notifications non-lues |
| ✕ Supprimer | Supprimer la notification | Toujours disponible |

### Filtres

- **Afficher seulement non-lues** : Cochez cette case pour voir uniquement les notifications non-lues
- **Afficher les lues aussi** : Laissez coché pour voir toutes les notifications

### Badge non-lues

En haut de l'onglet, vous voyez le nombre de notifications non-lues. Ce nombre se met à jour automatiquement quand vous :
- Marquez une notification comme lue
- Supprimez une notification non-lue

---

## ✨ Cas d'usage courants

### "Je veux vérifier quels droits j'ai"
→ Aller à l'onglet **🛡️ Mes Permissions**

### "Je veux vérifier que j'ai posé ma question"
→ Aller à l'onglet **📜 Historique**, filtrer par **QUESTION_ASKED**

### "Combien de contributions ai-je proposées ?"
→ Aller à l'onglet **📜 Historique**, voir les stats en bas

### "Je n'ai pas vu ma notification"
→ Aller à l'onglet **🔔 Notifications**, cocher "Afficher les lues aussi"

### "Je veux valider une réponse urgente"
→ Cliquer sur 🔗 Voir dans la notification pour aller directement à la validation

---

## 🔐 Sécurité et Confidentialité

- **Données personnelles** : Seules VOS données personnelles s'affichent
- **Isolation** : Chaque utilisateur ne voit que son dashboard personnel
- **Audit complet** : Toutes vos actions sont enregistrées pour conformité
- **Notifications** : Vous pouvez supprimer les notifications que vous ne voulez pas garder

---

## 📊 Architecture technique (pour développeurs)

### Collections MongoDB utilisées

**`user_audit_logs`** — Historique des actions
```
{
  user_email: "user@domain.com",
  action: "QUESTION_ASKED",
  description: "Question posée au chat",
  timestamp: ISODate("2026-05-26T..."),
  metadata: { question_id: "q123", category: "MBA" }
}
```

**`user_notifications`** — Notifications reçues
```
{
  recipient_email: "user@domain.com",
  type: "success",
  title: "Votre contribution a été validée!",
  message: "Votre réponse sur 'MBA' a été approuvée.",
  created_at: ISODate("2026-05-26T..."),
  read_at: null (null = non-lue, ou datetime = lue)
}
```

### Fonctions réutilisables

Dans `views/shared_dashboard_components.py` :

```python
# Afficher le dashboard complet (3 onglets)
render_user_profile_metrics(user)

# Créer une notification
create_notification(
    recipient_email="user@example.com",
    notif_type="success",
    title="Contribution validée!",
    message="Votre réponse a été approuvée.",
    action_url="/admin/validations#123"
)

# Logger une action
from services.audit_service import audit_instance
audit_instance.log_action(
    user_email="user@example.com",
    action="QUESTION_ASKED",
    description="Question posée",
    metadata={"question_id": "q123"}
)
```

---

## ❓ FAQ

**Q: Puis-je voir le dashboard d'un autre utilisateur ?**
A: Non, chacun ne voit que son propre dashboard. Les administrateurs peuvent voir les stats globales depuis le menu Administration.

**Q: Mes actions sont-elles supprimées après un certain temps ?**
A: Les logs audit sont conservés pendant 1-2 ans. Les notifications sont conservées 90 jours puis peuvent être archivées.

**Q: Comment puis-je exporter mon historique ?**
A: Actuellement, il faut le copier manuellement depuis l'interface. Une fonctionnalité d'export pourra être ajoutée.

**Q: Quand une notification est-elle créée ?**
A: Quand un événement important se produit (contribution validée, commentaire reçu, etc.). Les administrateurs peuvent ajouter des notifications manuellement.

**Q: Je vois "Non-lue" sur une vieille notification. Comment puis-je la marquer comme lue ?**
A: Cliquez sur le bouton "✓ Marquer lue" dans la notification.

---

**Version** : v7.10
**Dernière mise à jour** : 2026-05-26
**Auteur** : ISMaiLa Team
