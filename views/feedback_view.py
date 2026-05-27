"""
Module de Feedback en temps réel — ISMaiLa.

Fournit un composant discret dans la barre latérale pour collecter
les retours utilisateurs (bugs, suggestions, UX) tout en capturant
automatiquement le contexte technique en tâche de fond.

Composants publics :
  - render_feedback_sidebar()  → Bouton sidebar + dialogue modal
  - save_feedback(data)        → Persistance MongoDB (collection `feedbacks`)

Collection MongoDB : `feedbacks`
Statut par défaut : "Ouvert"
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import streamlit as st

from services.db_connector import db_instance
from config.roles import PERMISSIONS

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
#  Constantes
# ══════════════════════════════════════════════════════════════════════

FEEDBACK_TYPES = [
    "🐛 Bug technique",
    "💡 Suggestion d'amélioration",
    "🎨 Problème d'interface (UX/UI)",
    "📚 Contenu inexact ou manquant",
    "⚡ Problème de performance",
    "🔒 Problème de sécurité / accès",
    "❓ Autre",
]

FEEDBACK_COLLECTION = "feedbacks"


# ══════════════════════════════════════════════════════════════════════
#  Capture automatique du contexte technique
# ══════════════════════════════════════════════════════════════════════

def _capture_user_context() -> Dict[str, Any]:
    """
    Intercepte silencieusement le contexte de la session au moment
    du clic pour faciliter le debug côté admin.

    Capture :
      - Identité utilisateur (email, nom, rôle)
      - Permissions actives selon le rôle
      - Page/vue courante
      - Timestamp exact (UTC)
    """
    user = st.session_state.get("user")

    context: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc),
        "is_authenticated": user is not None,
    }

    if user and isinstance(user, dict):
        role = user.get("role", "ETUDIANT")
        context.update({
            "user_email": user.get("email", "inconnu"),
            "user_name": user.get("full_name", ""),
            "user_role": role,
            "permissions": PERMISSIONS.get(role, []),
        })
    else:
        context.update({
            "user_email": "anonyme",
            "user_name": "",
            "user_role": "PUBLIC",
            "permissions": [],
        })

    # Page courante — via session_state si disponible
    context["current_view"] = st.session_state.get(
        "current_view",
        st.session_state.get("current_page", "non_determinée")
    )

    return context


# ══════════════════════════════════════════════════════════════════════
#  Persistance MongoDB
# ══════════════════════════════════════════════════════════════════════

def save_feedback(feedback_data: Dict[str, Any]) -> bool:
    """
    Insère un document feedback dans la collection `feedbacks`.

    Le document contient :
      - type          : catégorie du feedback (bug, suggestion, UX…)
      - description   : texte libre de l'utilisateur
      - status        : "Ouvert" (par défaut)
      - context       : snapshot technique auto-capturé
      - created_at    : timestamp UTC

    Args:
        feedback_data: Dict avec au minimum 'type' et 'description'.

    Returns:
        True si l'insertion a réussi, False sinon.

    Notes:
        - Les exceptions PyMongo sont attrapées et loguées sans
          bloquer l'expérience utilisateur.
        - En cas d'échec, un warning discret est affiché.
    """
    try:
        collection = db_instance.get_collection(FEEDBACK_COLLECTION)

        document = {
            "type": feedback_data.get("type", "Autre"),
            "description": feedback_data.get("description", ""),
            "status": "Ouvert",
            "priority": _infer_priority(feedback_data.get("type", "")),
            "context": feedback_data.get("context", {}),
            "created_at": feedback_data.get("context", {}).get(
                "timestamp", datetime.now(timezone.utc)
            ),
            "updated_at": None,
            "resolved_at": None,
            "admin_notes": "",
        }

        result = collection.insert_one(document)
        logger.info(
            f"Feedback enregistré : {result.inserted_id} "
            f"(type={document['type']}, user={document['context'].get('user_email', '?')})"
        )
        return result.inserted_id is not None

    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement du feedback : {e}")
        return False


def _infer_priority(feedback_type: str) -> str:
    """Déduit une priorité par défaut selon le type de feedback."""
    if "Bug" in feedback_type or "sécurité" in feedback_type.lower():
        return "haute"
    elif "performance" in feedback_type.lower():
        return "moyenne"
    return "normale"


# ══════════════════════════════════════════════════════════════════════
#  Composant UI — Dialog modal
# ══════════════════════════════════════════════════════════════════════

@st.dialog("💬 Signaler un problème / Avis")
def _feedback_dialog():
    """
    Fenêtre modale Streamlit pour la saisie du feedback.
    Capture le contexte technique au moment de la soumission.
    """
    st.markdown(
        "Votre retour est précieux pour améliorer ISMaiLa. "
        "Décrivez votre problème ou suggestion ci-dessous."
    )

    # ── Sélection du type
    feedback_type = st.selectbox(
        "Type de retour",
        options=FEEDBACK_TYPES,
        index=0,
        key="feedback_type_select",
        help="Choisissez la catégorie qui correspond le mieux à votre retour.",
    )

    # ── Description textuelle
    description = st.text_area(
        "Description",
        placeholder="Décrivez le problème rencontré ou votre suggestion…",
        height=150,
        max_chars=2000,
        key="feedback_description_area",
        help="Soyez aussi précis que possible : étapes pour reproduire, résultat attendu vs obtenu.",
    )

    # ── Indicateur de contexte capturé (transparence)
    with st.expander("ℹ️ Informations capturées automatiquement", expanded=False):
        user = st.session_state.get("user")
        if user:
            st.caption(f"👤 **Utilisateur** : {user.get('email', 'inconnu')}")
            st.caption(f"🛡️ **Rôle** : {user.get('role', 'N/A')}")
        else:
            st.caption("👤 **Utilisateur** : Non connecté")
        st.caption("📍 **Page** : capturée au moment de l'envoi")
        st.caption("🕐 **Horodatage** : capturé au moment de l'envoi")

    # ── Boutons d'action
    col_submit, col_cancel = st.columns(2)

    with col_submit:
        if st.button("📤 Envoyer", type="primary", use_container_width=True):
            if not description or len(description.strip()) < 10:
                st.warning("⚠️ Veuillez fournir une description d'au moins 10 caractères.")
                return

            # Capture du contexte au moment exact du clic
            context = _capture_user_context()

            feedback_data = {
                "type": feedback_type,
                "description": description.strip(),
                "context": context,
            }

            with st.spinner("Enregistrement en cours…"):
                success = save_feedback(feedback_data)

            if success:
                st.success("✅ Merci pour votre retour ! Notre équipe l'examinera rapidement.")
                st.balloons()
            else:
                st.error(
                    "❌ Une erreur est survenue lors de l'enregistrement. "
                    "Veuillez réessayer ou contacter un administrateur."
                )

    with col_cancel:
        if st.button("Annuler", use_container_width=True):
            st.rerun()


# ══════════════════════════════════════════════════════════════════════
#  Point d'entrée public — Bouton sidebar
# ══════════════════════════════════════════════════════════════════════

def render_feedback_sidebar():
    """
    Affiche un bouton discret dans la barre latérale pour ouvrir
    le dialogue de feedback.

    À appeler depuis app.py dans le bloc `st.sidebar`.
    """
    st.sidebar.divider()
    if st.sidebar.button(
        "💬 Signaler / Avis",
        use_container_width=True,
        help="Signaler un bug, proposer une amélioration ou donner votre avis.",
        key="feedback_sidebar_btn",
    ):
        _feedback_dialog()
