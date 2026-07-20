"""
ISMaiLa — Système de Gestion des Connaissances (KMS) — v7.14
Application principale Streamlit pour le pilote ISM.

Module principal d'orchestration avec routing utilisateurs et pages.
"""

import streamlit as st

from controllers.auth_controller import auth_controller
from services.db_connector import db_instance
from config.roles import ADMIN, SUPER_ADMIN, VALIDATOR, CONTRIBUTOR, is_admin_or_higher


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


def render_forced_password_change(user):
    """
    Écran bloquant de changement de mot de passe à la première connexion.
    Tant que must_change_password est vrai, l'utilisateur ne peut accéder
    à aucune autre page. Seule la déconnexion reste possible.
    """
    st.warning("🔒 Première connexion — vous devez définir un nouveau mot de passe avant de continuer.")
    st.subheader("Définir mon mot de passe")
    with st.form("forced_password_form"):
        new_pass     = st.text_input("Nouveau mot de passe *", type="password",
                                     help="Minimum 8 caractères.")
        confirm_pass = st.text_input("Confirmer le mot de passe *", type="password")
        submit       = st.form_submit_button("🔐 Enregistrer et continuer", type="primary")

    if submit:
        if not new_pass or len(new_pass.strip()) < 8:
            st.error("❌ Le mot de passe doit contenir au moins 8 caractères.")
        elif new_pass != confirm_pass:
            st.error("❌ Les deux mots de passe ne correspondent pas.")
        else:
            if auth_controller.change_password(user["id"], new_pass.strip()):
                st.success("✅ Mot de passe mis à jour. Accès débloqué.")
                st.rerun()
            else:
                st.error("❌ Échec de la mise à jour. Réessayez ou contactez un administrateur.")


def main():
    st.set_page_config(
        page_title="ISMaiLa — KMS Souverain",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if "user" not in st.session_state:
        st.session_state.user = None

    # Bannière + mode survie si MongoDB indisponible
    if not db_instance.is_alive():
        st.warning("⚠️ Base de données temporairement indisponible — Mode survie activé.", icon="🆘")
        faq   = db_instance.get_survival_faq()
        links = db_instance.get_survival_links()
        if faq or links:
            with st.expander("📋 Informations d'urgence disponibles"):
                for item in faq:
                    st.markdown(f"**{item['q']}** : {item['r']}")
                for k, v in links.items():
                    st.markdown(f"🔗 [{k}]({v})")
        st.stop()

    # Charge une seule fois les sous-catégories dynamiques persistées en base
    if not st.session_state.get("_extra_categories_loaded"):
        from config.categories import load_persisted_categories
        load_persisted_categories()
        st.session_state["_extra_categories_loaded"] = True

    st.sidebar.title("🎓 ISMaiLa")

    if st.session_state.user:
        user = st.session_state.user
        st.sidebar.success(f"👤 {user.get('full_name') or user.get('email', 'Utilisateur')}")
        st.sidebar.caption(f"Rôle : **{user['role']}**")
        st.sidebar.divider()

        # Verrou : changement de mot de passe obligatoire à la première connexion
        if user.get("must_change_password"):
            if st.sidebar.button("🚪 Déconnexion"):
                auth_controller.logout()
            render_forced_password_change(user)
            return

        role         = user["role"]
        menu_options = ["📊 Mon Dashboard", "💬 Assistant", "❓ Aide"]
        if role in (CONTRIBUTOR, VALIDATOR, ADMIN, SUPER_ADMIN):
            menu_options.append("✍️ Contribuer")
        if role in (VALIDATOR, ADMIN, SUPER_ADMIN):
            menu_options.append("✅ Valider")
        if is_admin_or_higher(role):
            menu_options.append("🛡️ Administration")

        page = st.sidebar.radio("Navigation", menu_options)
        if st.sidebar.button("🚪 Déconnexion"):
            auth_controller.logout()

        if page == "📊 Mon Dashboard":
            from views.user_dashboard_view import render_user_dashboard_view
            render_user_dashboard_view()
        elif page == "💬 Assistant":
            from views.student_view import render_student_view
            render_student_view()
        elif page == "❓ Aide":
            from views.help_view import render_help_view
            render_help_view()
        elif page == "✍️ Contribuer":
            from views.contributor_view import render_contributor_view
            render_contributor_view()
        elif page == "✅ Valider":
            from views.validator_view import render_validator_view
            render_validator_view()
        elif page == "🛡️ Administration":
            from views.admin_view import render_admin_view
            render_admin_view()
    else:
        tab_help, tab_chat, tab_login = st.tabs(["❓ Aide", "💬 Poser une question", "🔐 Connexion"])
        with tab_help:
            from views.help_view import render_help_view
            render_help_view()
        with tab_chat:
            from views.student_view import render_student_view
            render_student_view()
        with tab_login:
            render_login_form()


if __name__ == "__main__":
    main()