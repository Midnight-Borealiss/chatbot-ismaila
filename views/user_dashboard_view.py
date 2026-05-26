"""
Vue du Dashboard Utilisateur — ISMaiLa.

Affiche le profil, les permissions, l'historique et les notifications
de l'utilisateur connecté.

Accessible à tous les rôles (SUPER_ADMIN, ADMINISTRATION, VALIDATEUR, CONTRIBUTEUR, ETUDIANT).
"""

import streamlit as st
from views.shared_dashboard_components import render_user_profile_metrics


def render_user_dashboard_view():
    """Affiche le dashboard utilisateur complet."""
    
    # Vérification utilisateur connecté
    if "user" not in st.session_state or not st.session_state.user:
        st.error("❌ Vous devez être connecté pour accéder au dashboard.")
        st.stop()
    
    user = st.session_state.user
    st.title(f"📊 Mon Dashboard — {user.get('full_name', user.get('email', 'Utilisateur'))}")
    st.caption(f"Bienvenue sur votre espace personnel • {user.get('email', 'N/A')}")
    
    st.divider()
    
    # Afficher le composant réutilisable
    render_user_profile_metrics(user)
    
    st.divider()
    st.caption("🔐 Vos données personnelles sont sécurisées et accessibles uniquement par vous-même.")
