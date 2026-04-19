import streamlit as st

from controllers.kb_controller import kb_controller
from config.roles import VALIDATOR, ADMIN


def render_validator_view():
    """
    Vue réservée aux Validateurs (Chefs de Services) et Admins.
    Guard de rôle appliqué en entrée.
    """
    user = st.session_state.get("user")
    if not user or user.get("role") not in (VALIDATOR, ADMIN):
        st.error("⛔ Accès refusé. Cette page est réservée aux validateurs.")
        st.stop()

    st.header("✅ Espace Validateur — Certification des Connaissances")
    st.markdown(
        "Vérifiez et certifiez les réponses proposées par les contributeurs. "
        "Seules les réponses **certifiées** sont publiées dans le chatbot."
    )

    pending = kb_controller.get_pending()

    if not pending:
        st.success("🎉 Aucune question en attente. La base est à jour !")
        return

    st.info(f"📋 {len(pending)} question(s) en attente de validation.")

    for item in pending:
        # ObjectId doit être converti en str pour les keys Streamlit
        item_id = str(item["_id"])

        with st.expander(f"❓ {item['question']}", expanded=False):
            st.caption(
                f"Soumis par : **{item.get('user_email', 'anonyme')}** — "
                f"Catégorie : {item.get('category', 'Général')} — "
                f"Date : {item.get('created_at', 'N/A')}"
            )

            # Pré-remplissage si une réponse a été proposée par un contributeur
            current_resp = item.get("response", "") if item.get("response") != "En attente" else ""

            resp = st.text_area(
                "✍️ Réponse certifiée (modifiable avant publication)",
                value=current_resp,
                height=120,
                key=f"resp_{item_id}",   # str, pas ObjectId
            )

            col1, col2 = st.columns([2, 1])
            with col1:
                if st.button("✅ Certifier et Publier", key=f"btn_val_{item_id}"):
                    if resp.strip():
                        kb_controller.update_contribution(
                            item_id, resp, user["email"]
                        )
                        st.success("Connaissance certifiée et disponible dans le chatbot !")
                        st.rerun()
                    else:
                        st.error("La réponse ne peut pas être vide avant certification.")
            with col2:
                if st.button("🗄️ Archiver", key=f"btn_arc_{item_id}"):
                    kb_controller.archive(item_id)
                    st.info("Question archivée.")
                    st.rerun()