"""
ISMaiLa — Système de Gestion des Connaissances (KMS) — v7.14
Application principale Streamlit pour le pilote ISM.

Module principal d'orchestration avec routing utilisateurs et pages.
"""

import logging

import streamlit as st

from controllers.auth_controller import auth_controller
from services.db_connector import db_instance
from config.roles import ADMIN, SUPER_ADMIN, VALIDATOR, CONTRIBUTOR, is_admin_or_higher
from views.feedback_view import render_feedback_sidebar


def render_login_form():
    """Formulaire de connexion de l'onglet public.

    En cas d'échec, le message reste volontairement générique (« Email ou mot
    de passe incorrect ») : distinguer les deux cas révélerait quels comptes
    existent.
    """
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
    """Point d'entrée Streamlit : garde-fous, puis routage selon le rôle.

    Séquence de démarrage, dans l'ordre :
      1. mode survie si MongoDB est injoignable — l'exécution s'arrête là ;
      2. préchargement des catégories et ancres apprises (non bloquant) ;
      3. verrou `must_change_password` : tant qu'il est levé, seule la
         déconnexion reste possible ;
      4. construction du menu selon le rôle, puis rendu de la page choisie.

    Les vues sont importées **à l'intérieur** des branches : cela évite de
    charger toutes les pages (et leurs dépendances lourdes) à chaque rerun.
    """
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

    # Charge une seule fois les sous-catégories dynamiques + les ancres apprises
    # (boucle d'apprentissage) persistées en base. Chargement NON CRITIQUE :
    # l'app doit démarrer même s'il échoue (base indisponible, déploiement
    # transitoire, etc.) — on dégrade gracieusement sans préchargement.
    if not st.session_state.get("_extra_categories_loaded"):
        try:
            from config.categories import load_persisted_categories, load_learned_anchors
            load_persisted_categories()
            load_learned_anchors()
        except Exception as e:
            logging.warning(f"Préchargement catégories/ancres ignoré : {e}")
        st.session_state["_extra_categories_loaded"] = True

    st.sidebar.title("🎓 ISMaiLa")

    if st.session_state.user:
        user = st.session_state.user
        st.sidebar.success(f"👤 {user.get('full_name') or user.get('email', 'Utilisateur')}")
        st.sidebar.caption(f"Rôle : **{user['role']}**")
        # Bouton « Signaler / Avis » — juste sous les infos utilisateur, visible par tous
        render_feedback_sidebar()
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
        # Mémorise la page courante → capturée dans le contexte des feedbacks
        st.session_state["current_view"] = page
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
        # Utilisateur non connecté : bouton « Signaler / Avis » disponible aussi (visible par tous)
        st.session_state["current_view"] = "Accueil public (non connecté)"
        render_feedback_sidebar()
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