"""
Vue du Dashboard Utilisateur — ISMaiLa.

Affiche le profil, les permissions et permet de sécuriser le compte
(changement de mot de passe) pour l'utilisateur connecté.

⚠️ Pilote : les profils et permissions sont PRÉ-ASSIGNÉS par l'administration.
L'auto-qualification (formulaire de permission) est désactivée — le profil
est affiché en lecture seule. Seul le mot de passe reste modifiable par
l'utilisateur. Toute modification de profil passe par l'espace Administration.

Accessible à tous les rôles (SUPER_ADMIN, ADMINISTRATION, VALIDATEUR, CONTRIBUTEUR, ETUDIANT).
"""

from datetime import datetime
import streamlit as st
from controllers.auth_controller import AuthController
from services.db_connector import db_instance
from bson.objectid import ObjectId


def _render_readonly_profile(profile: dict, user: dict):
    """Affiche le profil et les permissions en lecture seule (figé pour le pilote)."""
    full_name      = profile.get("full_name") or user.get("full_name") or user.get("email", "—")
    role           = profile.get("role") or user.get("role", "—")
    structural     = profile.get("structural_type") or "—"
    entity         = profile.get("entity") or profile.get("departement") or "—"
    job_level      = profile.get("job_level") or "—"
    configured     = profile.get("profile_configured", False)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Nom complet :** {full_name}")
        st.markdown(f"**Rôle :** {role}")
        st.markdown(f"**Type de structure :** {structural}")
    with col2:
        st.markdown(f"**Entité / Département :** {entity}")
        st.markdown(f"**Niveau de poste :** {job_level}")

    # Permissions accordées (figées par l'admin)
    permissions = profile.get("permissions") or {}
    if permissions:
        st.markdown("##### 🛡️ Permissions accordées")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Lecture", "✅" if permissions.get("can_read") else "❌")
        with c2:
            st.metric("Proposition", "✅" if permissions.get("can_propose") else "❌")
        with c3:
            st.metric("Validation", "✅" if permissions.get("can_validate") else "❌")

    if not configured:
        st.warning(
            "⚠️ Votre profil n'a pas encore été configuré par l'administration. "
            "Vous pouvez vous connecter mais certaines fonctionnalités resteront "
            "limitées tant qu'un administrateur n'a pas défini votre périmètre."
        )


def render_user_dashboard(user):
    st.title("👤 Mon Espace Co-pilote — ISMaiLa")
    db = db_instance.db

    # Résolution robuste de l'ID : la session d'auth stocke "id" (string).
    user_id_str = user.get("id") or user.get("_id")
    if not user_id_str:
        st.error("❌ Erreur d'identification : identifiant utilisateur manquant.")
        return
    try:
        user_id = ObjectId(str(user_id_str))
    except Exception as e:
        st.error(f"Erreur d'identification : {e}")
        return

    # Recharger le profil complet depuis la base (source de vérité pour le pilote).
    profile = {}
    if db is not None:
        try:
            profile = db.users.find_one({"_id": user_id}) or {}
        except Exception:
            profile = {}

    # =========================================================================
    # PROFIL EN LECTURE SEULE — figé pour le pilote
    # L'auto-qualification (formulaire de permission) est désactivée.
    # =========================================================================
    st.info(
        "🔒 Pendant le pilote, votre profil et vos permissions sont gérés par "
        "l'administration. Pour toute modification, contactez un administrateur."
    )
    _render_readonly_profile(profile, user)

    st.divider()

    # =========================================================================
    # SÉCURITÉ DU COMPTE — seul élément modifiable par l'utilisateur
    # =========================================================================
    with st.expander("🔒 Sécuriser mon compte (Changement de mot de passe)", expanded=True):
        st.markdown(
            "Pour finaliser la sécurité de votre accès au pilote, veuillez remplacer "
            "le mot de passe temporaire par un mot de passe personnel de votre choix."
        )

        with st.form(key="secure_password_form"):
            new_pass     = st.text_input("Nouveau mot de passe *", type="password", help="Minimum 6 caractères")
            confirm_pass = st.text_input("Confirmer le mot de passe *", type="password")

            submit_password = st.form_submit_button("🔐 Mettre à jour le mot de passe")

            if submit_password:
                if not new_pass or len(new_pass.strip()) < 6:
                    st.error("❌ Le mot de passe doit contenir au moins 6 caractères.")
                elif new_pass != confirm_pass:
                    st.error("❌ Les deux mots de passe ne correspondent pas.")
                else:
                    try:
                        # Hachage bcrypt + écriture dans le bon champ (password_hash).
                        hashed_pw = AuthController.hash_password(new_pass)
                        db.users.update_one(
                            {"_id": user_id},
                            {
                                "$set": {
                                    "password_hash": hashed_pw,
                                    "password_changed_at": datetime.utcnow(),
                                }
                            }
                        )
                        st.success(
                            "🎉 Votre mot de passe a été sécurisé avec succès ! "
                            "Vous pouvez à présent utiliser les fonctionnalités du pilote."
                        )
                    except Exception as e:
                        st.error(f"Erreur lors de la mise à jour du mot de passe : {e}")


def render_user_dashboard_view():
    """Wrapper appelé par app.py — récupère l'utilisateur en session."""
    if "user" not in st.session_state or not st.session_state.user:
        st.error("❌ Erreur d'authentification.")
        return
    render_user_dashboard(st.session_state.user)
