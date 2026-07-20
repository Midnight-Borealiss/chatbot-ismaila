"""
Vue du Dashboard Utilisateur — ISMaiLa.

Affiche un résumé en lecture seule du profil de l'utilisateur connecté :
identité, rôle, structure de rattachement et domaines thématiques assignés.

Le profil est pré-assigné par l'administration (pilote figé) : aucune édition
n'est possible ici. Le changement de mot de passe obligatoire est géré en amont
par l'écran bloquant `render_forced_password_change` (app.py).

Accessible à tous les rôles (SUPER_ADMIN, ADMINISTRATION, VALIDATEUR, CONTRIBUTEUR, ETUDIANT).
"""

import streamlit as st
from services.db_connector import db_instance
from config.roles import is_admin_or_higher
from bson.objectid import ObjectId

# Correspondance niveau technique → libellé affiché (aligné sur admin_view).
LEVEL_TO_LABEL = {"contributor": "Contributeur", "expert": "Expert"}


def render_user_dashboard_view():
    """Point d'entrée appelé par app.py : rend le dashboard de l'utilisateur en session."""
    user = st.session_state.get("user")
    if not user:
        st.error("⛔ Vous devez être connecté pour accéder à votre espace.")
        return
    render_user_dashboard(user)


def render_user_dashboard(user):
    st.title("👤 Mon Espace Co-pilote — ISMaiLa")
    db = db_instance.db

    # La session stocke l'identifiant sous "id" ; les anciens appels utilisaient "_id".
    raw_id = user.get("id") or user.get("_id")
    try:
        user_id = ObjectId(str(raw_id))
    except Exception as e:
        st.error(f"Erreur d'identification : {e}")
        return

    # La session ne porte que id/email/full_name/role/domain_permissions.
    # On relit le document complet pour la structure de rattachement.
    doc = {}
    try:
        doc = db.users.find_one({"_id": user_id}) or {}
    except Exception:
        doc = {}

    full_name = user.get("full_name") or doc.get("full_name") or "—"
    email     = user.get("email") or doc.get("email") or "—"
    role      = user.get("role", "—")

    # Structure de rattachement (SERVICE | INSTITUT), avec repli sur l'ancien champ.
    structural_type = doc.get("structural_type", "")
    scope           = doc.get("scope", {}) or {}
    if structural_type == "SERVICE":
        struct_label = "Service Transversal"
        entities     = scope.get("services", [])
    elif structural_type == "INSTITUT":
        struct_label = "Institut / Entité Académique"
        entities     = scope.get("instituts", [])
    else:
        struct_label = "—"
        entities     = []
    entity_label = ", ".join(e for e in entities if e) or doc.get("departement") or "—"

    # =========================================================================
    # Résumé du profil (lecture seule)
    # =========================================================================
    with st.container(border=True):
        st.markdown("##### 📝 Mon profil")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Nom complet**  \n{full_name}")
            st.markdown(f"**Email**  \n{email}")
        with col2:
            st.markdown(f"**Rôle**  \n{role}")
            st.markdown(f"**Rattachement**  \n{struct_label} — {entity_label}")
        st.caption(
            "ℹ️ Profil pré-assigné par l'administration. Pour toute modification, "
            "contactez un administrateur."
        )

    # =========================================================================
    # Domaines thématiques assignés (lecture seule)
    # =========================================================================
    domain_permissions = user.get("domain_permissions") or doc.get("domain_permissions", {}) or {}
    with st.container(border=True):
        st.markdown("##### 🗂️ Mes domaines")
        if is_admin_or_higher(role):
            st.success("Accès total à tous les domaines (rôle administrateur).")
        elif domain_permissions:
            for sub, level in sorted(domain_permissions.items()):
                st.markdown(f"- **{sub}** — {LEVEL_TO_LABEL.get(level, level)}")
        else:
            st.info("Aucun domaine ne vous est assigné pour le moment.")
