import streamlit as st
import logging
logging.getLogger("streamlit.watcher.local_sources_watcher").setLevel(logging.ERROR)

from controllers.auth_controller import auth_controller
from views.feedback_view import render_feedback_sidebar
from services.db_connector import db_instance
from config.roles import ADMIN, SUPER_ADMIN, VALIDATOR, CONTRIBUTOR, is_admin_or_higher

# --- IMPORTS GLOBAUX DES VUES ---
from views.user_dashboard_view import render_user_dashboard
from views.student_view import render_student_view
from views.help_view import render_help_view
from views.contributor_view import render_contributor_view
from views.validator_view import render_validator_view
from views.admin_view import render_admin_view

def render_login_form():
    st.subheader("🔐 Connexion")
    with st.form("login_form"):
        email    = st.text_input("Email")
        password = st.text_input("Mot de passe", type="password")
        submit   = st.form_submit_button("Se connecter")
    if submit:
        if auth_controller.login(email, password):
            st.success("Connexion réussie !")
            st.rerun()
        else:
            st.error("Email ou mot de passe incorrect.")

def main():
    st.set_page_config(page_title="ISMaiLa — KMS Souverain", page_icon="🎓", layout="wide")
    if "user" not in st.session_state: st.session_state.user = None

    if st.session_state.user:
        user = st.session_state.user
        page = st.sidebar.radio("Navigation", ["📊 Mon Dashboard", "💬 Assistant", "❓ Aide", "✍️ Contribuer", "✅ Valider", "🛡️ Administration"])
        if st.sidebar.button("🚪 Déconnexion"): auth_controller.logout()

        if page == "📊 Mon Dashboard": render_user_dashboard(user)
        elif page == "💬 Assistant": render_student_view()
        elif page == "❓ Aide": render_help_view()
        elif page == "✍️ Contribuer": render_contributor_view()
        elif page == "✅ Valider": render_validator_view()
        elif page == "🛡️ Administration": render_admin_view()
    else:
        tab_help, tab_chat, tab_login = st.tabs(["❓ Aide", "💬 Poser une question", "🔐 Connexion"])
        with tab_help: render_help_view()
        with tab_chat: render_student_view()
        with tab_login: render_login_form()
    
    render_feedback_sidebar()

if __name__ == "__main__":
    main()