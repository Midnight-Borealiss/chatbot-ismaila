"""
Composants partagés pour le dashboard utilisateur — ISMaiLa.

Ce module fournit un composant réutilisable `render_user_profile_metrics()`
qui affiche :
  1. 🛡️ Mes Permissions — badges des droits selon le rôle
  2. 📜 Historique de mes actions — tableau des dernières actions
  3. 🔔 Mes Notifications — flux des notifications (lues/non-lues)

Utilise les collections MongoDB :
  - `user_audit_logs` — Historique des actions
  - `user_notifications` — Notifications reçues
  - `users` — Profil utilisateur

Compatible avec tous les rôles (SUPER_ADMIN, ADMINISTRATION, VALIDATEUR, CONTRIBUTEUR, ETUDIANT).
"""

import streamlit as st
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from bson import ObjectId

from services.db_connector import db_instance
from config.roles import PERMISSIONS, ADMIN_ROLES, MODERATOR_ROLES, is_super_admin
from config.permissions import get_user_domains_summary, DOMAIN_HIERARCHY


# ══════════════════════════════════════════════════════════════════════
#  Collections MongoDB — Schéma et indexation
# ══════════════════════════════════════════════════════════════════════

def ensure_dashboard_indexes():
    """Crée les indexes nécessaires pour les collections du dashboard."""
    try:
        logs = db_instance.get_collection("user_audit_logs")
        logs.create_index("user_email")
        logs.create_index([("user_email", 1), ("timestamp", -1)])
        logs.create_index("action")
        
        notif = db_instance.get_collection("user_notifications")
        notif.create_index("recipient_email")
        notif.create_index([("recipient_email", 1), ("created_at", -1)])
        notif.create_index("read_at")
    except Exception as e:
        st.warning(f"⚠️ Erreur création indexes: {e}")


# ══════════════════════════════════════════════════════════════════════
#  Helpers pour les données
# ══════════════════════════════════════════════════════════════════════

def get_user_permissions(role: str) -> Dict[str, Any]:
    """
    Retourne les permissions de l'utilisateur selon son rôle.
    
    Format:
    {
        "role": "VALIDATEUR",
        "permissions": [
            {"name": "read", "description": "Lire la base...", "granted": True},
            {"name": "validate", "description": "Valider les...", "granted": True},
        ]
    }
    """
    role_perms = PERMISSIONS.get(role, ["none"])
    
    all_perms = {
        "all": "Accès complet — toutes les fonctionnalités",
        "super": "Droits super-admin — création de comptes",
        "read": "Lire les questions et réponses",
        "propose": "Proposer des réponses",
        "validate": "Valider les réponses",
    }
    
    permissions_list = []
    for perm_key, perm_desc in all_perms.items():
        granted = perm_key in role_perms
        permissions_list.append({
            "name": perm_key,
            "description": perm_desc,
            "granted": granted
        })
    
    return {
        "role": role,
        "permissions": permissions_list
    }


def get_user_audit_history(user_email: str, limit: int = 30) -> List[Dict]:
    """Récupère l'historique des actions de l'utilisateur."""
    try:
        logs = db_instance.get_collection("user_audit_logs")
        history = list(logs.find(
            {"user_email": user_email},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit))
        return history
    except Exception as e:
        st.warning(f"⚠️ Erreur lecture historique: {e}")
        return []


def get_user_notifications(user_email: str, unread_only: bool = False, limit: int = 50) -> List[Dict]:
    """Récupère les notifications de l'utilisateur."""
    try:
        notif = db_instance.get_collection("user_notifications")
        query = {"recipient_email": user_email}
        if unread_only:
            query["read_at"] = None
        
        notifications = list(notif.find(query, {"_id": 1}).sort("created_at", -1).limit(limit))
        return notifications
    except Exception as e:
        st.warning(f"⚠️ Erreur lecture notifications: {e}")
        return []


def get_unread_notification_count(user_email: str) -> int:
    """Compte les notifications non-lues."""
    try:
        notif = db_instance.get_collection("user_notifications")
        return notif.count_documents({"recipient_email": user_email, "read_at": None})
    except Exception as e:
        return 0


def mark_notification_as_read(notification_id: str):
    """Marque une notification comme lue."""
    try:
        if not ObjectId.is_valid(notification_id):
            return False
        notif = db_instance.get_collection("user_notifications")
        result = notif.update_one(
            {"_id": ObjectId(notification_id)},
            {"$set": {"read_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count > 0
    except Exception as e:
        st.warning(f"⚠️ Erreur marquer notification: {e}")
        return False


def delete_notification(notification_id: str) -> bool:
    """Supprime une notification."""
    try:
        if not ObjectId.is_valid(notification_id):
            return False
        notif = db_instance.get_collection("user_notifications")
        result = notif.delete_one({"_id": ObjectId(notification_id)})
        return result.deleted_count > 0
    except Exception as e:
        return False


# ══════════════════════════════════════════════════════════════════════
#  Formatage pour affichage
# ══════════════════════════════════════════════════════════════════════

def format_timestamp(ts: datetime) -> str:
    """Formate un timestamp pour affichage."""
    if not ts:
        return "—"
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except:
            return ts
    
    try:
        # Format relatif (il y a X minutes, etc)
        delta = datetime.now(timezone.utc) - (ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc))
        if delta.total_seconds() < 60:
            return "À l'instant"
        elif delta.total_seconds() < 3600:
            mins = int(delta.total_seconds() / 60)
            return f"Il y a {mins}m"
        elif delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            return f"Il y a {hours}h"
        else:
            days = int(delta.total_seconds() / 86400)
            return f"Il y a {days}j"
    except:
        return str(ts)[:19]


def get_action_emoji(action: str) -> str:
    """Retourne l'emoji correspondant à une action."""
    emoji_map = {
        "LOGIN": "🔓",
        "LOGOUT": "🚪",
        "QUESTION_ASKED": "❓",
        "CONTRIBUTION_PROPOSED": "✍️",
        "CONTRIBUTION_VALIDATED": "✅",
        "CONTRIBUTION_REJECTED": "❌",
        "ANSWER_PROVIDED": "💬",
        "ACCOUNT_CREATED": "👤",
    }
    return emoji_map.get(action, "•")


def get_notification_icon(notif_type: str) -> str:
    """Retourne l'emoji pour le type de notification."""
    icon_map = {
        "info": "ℹ️",
        "warning": "⚠️",
        "success": "✅",
        "action_required": "🔔",
    }
    return icon_map.get(notif_type, "📬")


# ══════════════════════════════════════════════════════════════════════
#  Composant principal réutilisable
# ══════════════════════════════════════════════════════════════════════

def render_user_profile_metrics(user: Optional[Dict] = None):
    """
    Composant Streamlit réutilisable affichant le dashboard utilisateur complet.
    
    Affiche 3 onglets:
      1. 🛡️ Mes Permissions
      2. 📜 Historique de mes actions
      3. 🔔 Mes Notifications
    
    Args:
        user: Dict utilisateur de st.session_state.user (défaut: st.session_state.user)
    """
    
    # Récupérer l'utilisateur depuis session state si non fourni
    if user is None:
        if "user" not in st.session_state:
            st.warning("⚠️ Vous devez être connecté pour voir le dashboard.")
            return
        user = st.session_state.user
    
    if not user:
        st.warning("⚠️ Vous devez être connecté pour voir le dashboard.")
        return
    
    user_email = user.get("email", user.get("email_"))
    user_role = user.get("role", "ETUDIANT")
    
    # Créer les indexes
    ensure_dashboard_indexes()
    
    # Onglets
    tab1, tab2, tab3 = st.tabs(["🛡️ Mes Permissions", "📜 Historique", "🔔 Notifications"])
    
    # ─────────────────────────────────────────────────────────────────
    #  ONGLET 1: MES PERMISSIONS
    # ─────────────────────────────────────────────────────────────────
    with tab1:
        st.subheader("🛡️ Mes Permissions")
        
        perms_data = get_user_permissions(user_role)
        
        # Afficher le rôle
        col1, col2 = st.columns(2)
        with col1:
            st.metric("📋 Mon Rôle", user_role)
        with col2:
            st.metric("👤 Email", user_email)
        
        st.divider()
        
        # Afficher les permissions sous forme de badges
        st.write("**Permissions octroyées :**")
        
        # Grouper permissions accordées vs non accordées
        granted = [p for p in perms_data["permissions"] if p["granted"]]
        denied = [p for p in perms_data["permissions"] if not p["granted"]]
        
        if granted:
            cols = st.columns(min(3, len(granted)))
            for idx, perm in enumerate(granted):
                with cols[idx % len(cols)]:
                    st.success(f"✅ {perm['name'].upper()}")
                    st.caption(perm["description"])
        
        if denied:
            st.write("**Restrictions :**")
            with st.expander("Voir les permissions non accordées"):
                for perm in denied:
                    st.info(f"❌ {perm['name'].upper()}", icon="ℹ")
                    st.caption(perm["description"])
        
        # Domaines d'expertise (si applicable)
        domains = get_user_domains_summary(user)
        if domains.get("expert") or domains.get("contributor"):
            st.divider()
            st.write("**🎓 Mes domaines d'expertise :**")
            
            if domains.get("expert"):
                with st.expander("🔒 Expert (propose + valide)", expanded=True):
                    st.write(", ".join(domains["expert"]) if domains["expert"] else "Aucun")
            
            if domains.get("contributor"):
                with st.expander("✍️ Contributeur (propose seulement)", expanded=True):
                    st.write(", ".join(domains["contributor"]) if domains["contributor"] else "Aucun")
    
    # ─────────────────────────────────────────────────────────────────
    #  ONGLET 2: HISTORIQUE DES ACTIONS
    # ─────────────────────────────────────────────────────────────────
    with tab2:
        st.subheader("📜 Historique de mes actions")
        
        # Options de filtrage
        col1, col2 = st.columns(2)
        with col1:
            limit = st.slider("Nombre d'actions à afficher", 10, 100, 30)
        with col2:
            action_filter = st.selectbox(
                "Filtrer par type",
                ["Tous"] + list([
                    "LOGIN", "LOGOUT", "QUESTION_ASKED", "CONTRIBUTION_PROPOSED",
                    "CONTRIBUTION_VALIDATED", "CONTRIBUTION_REJECTED", "ANSWER_PROVIDED", "ACCOUNT_CREATED"
                ])
            )
        
        # Récupérer l'historique
        history = get_user_audit_history(user_email, limit=limit)
        
        if not history:
            st.info("📭 Aucune action enregistrée pour le moment.")
        else:
            # Filtrer si nécessaire
            if action_filter != "Tous":
                history = [h for h in history if h.get("action") == action_filter]
            
            if not history:
                st.info(f"📭 Aucune action du type '{action_filter}' trouvée.")
            else:
                # Afficher sous forme de tableau
                history_data = []
                for entry in history:
                    history_data.append({
                        "🕐 Quand": format_timestamp(entry.get("timestamp")),
                        "Action": f"{get_action_emoji(entry.get('action', ''))} {entry.get('description', entry.get('action', 'N/A'))}",
                        "Détails": entry.get("metadata", {}).get("details", "—"),
                    })
                
                st.dataframe(history_data, use_container_width=True, hide_index=True)
                
                # Stats
                st.divider()
                st.write("**📊 Statistiques :**")
                col1, col2, col3 = st.columns(3)
                
                action_counts = {}
                for h in history:
                    action = h.get("action", "UNKNOWN")
                    action_counts[action] = action_counts.get(action, 0) + 1
                
                with col1:
                    st.metric("Total actions", len(history))
                with col2:
                    logins = action_counts.get("LOGIN", 0)
                    st.metric("Connexions", logins)
                with col3:
                    contrib = action_counts.get("CONTRIBUTION_PROPOSED", 0) + action_counts.get("ANSWER_PROVIDED", 0)
                    st.metric("Contributions", contrib)
    
    # ─────────────────────────────────────────────────────────────────
    #  ONGLET 3: NOTIFICATIONS
    # ─────────────────────────────────────────────────────────────────
    with tab3:
        st.subheader("🔔 Mes Notifications")
        
        # Récupérer les notifications
        all_notifs = list(db_instance.get_collection("user_notifications").find(
            {"recipient_email": user_email}
        ).sort("created_at", -1).limit(100))
        
        unread_count = get_unread_notification_count(user_email)
        
        # Badge de non-lues
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**Vous avez {len(all_notifs)} notifications**")
        with col2:
            if unread_count > 0:
                st.metric("Non-lues", unread_count, delta=-unread_count if unread_count > 0 else 0)
        
        st.divider()
        
        # Filtres
        col1, col2 = st.columns(2)
        with col1:
            show_unread = st.checkbox("Afficher seulement non-lues", value=False)
        with col2:
            show_read = st.checkbox("Afficher les lues aussi", value=True)
        
        # Filtrer les notifications
        filtered_notifs = []
        for n in all_notifs:
            is_read = n.get("read_at") is not None
            if show_unread and is_read:
                continue
            if not show_read and is_read:
                continue
            filtered_notifs.append(n)
        
        if not filtered_notifs:
            st.info("📭 Aucune notification à afficher.")
        else:
            # Afficher les notifications
            for notif in filtered_notifs:
                notif_id = str(notif.get("_id"))
                notif_type = notif.get("type", "info")
                title = notif.get("title", "Notification")
                message = notif.get("message", "")
                created_at = notif.get("created_at")
                read_at = notif.get("read_at")
                action_url = notif.get("action_url")
                
                # Déterminer la couleur selon le type et le statut de lecture
                if read_at:
                    container = st.container(border=False)
                    color_class = "info"
                else:
                    container = st.container(border=True)
                    color_class = "success"
                
                with container:
                    # En-tête
                    col1, col2, col3 = st.columns([1, 3, 1])
                    with col1:
                        st.write(f"{get_notification_icon(notif_type)}")
                    with col2:
                        st.write(f"**{title}**")
                    with col3:
                        status = "✓ Lue" if read_at else "🆕 Non-lue"
                        st.caption(status)
                    
                    # Message
                    st.write(message)
                    
                    # Timestamp
                    st.caption(f"📅 {format_timestamp(created_at)}")
                    
                    # Actions
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        if action_url:
                            st.link_button("🔗 Voir", action_url)
                    with col2:
                        if not read_at:
                            if st.button("✓ Marquer lue", key=f"read_{notif_id}"):
                                if mark_notification_as_read(notif_id):
                                    st.success("Marquée comme lue!")
                                    st.rerun()
                    with col3:
                        if st.button("✕ Supprimer", key=f"delete_{notif_id}"):
                            if delete_notification(notif_id):
                                st.success("Notification supprimée!")
                                st.rerun()


# ══════════════════════════════════════════════════════════════════════
#  Fonction pour ajouter une notification (pour les contrôleurs)
# ══════════════════════════════════════════════════════════════════════

def create_notification(recipient_email: str, notif_type: str, title: str, message: str, action_url: str = None) -> bool:
    """
    Crée une notification pour un utilisateur.
    
    Args:
        recipient_email: Email du destinataire
        notif_type: "info", "warning", "success", "action_required"
        title: Titre court de la notification
        message: Message détaillé
        action_url: URL optionnelle pour action
    
    Returns:
        True si succès, False sinon
    """
    try:
        notif = db_instance.get_collection("user_notifications")
        result = notif.insert_one({
            "recipient_email": recipient_email,
            "type": notif_type,
            "title": title,
            "message": message,
            "action_url": action_url,
            "created_at": datetime.now(timezone.utc),
            "read_at": None,
        })
        return result.inserted_id is not None
    except Exception as e:
        st.error(f"Erreur création notification: {e}")
        return False
