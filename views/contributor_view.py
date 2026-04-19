import streamlit as st
from datetime import datetime

from services.db_connector import db_instance
from config.roles import CONTRIBUTOR, VALIDATOR, ADMIN


def render_contributor_view():
    """
    Vue Contributeur : propose des réponses aux questions sans réponse.
    Les réponses soumises passent au statut 'en_attente' pour validation.
    """
    user = st.session_state.get("user")
    if not user or user.get("role") not in (CONTRIBUTOR, VALIDATOR, ADMIN):
        st.error("⛔ Accès refusé. Cette page est réservée aux contributeurs.")
        st.stop()

    kb_col = db_instance.get_collection("contributions")

    st.header("✍️ Espace Contributeur")
    st.markdown(
        "Aidez à enrichir la base de connaissances en proposant des réponses "
        "aux questions posées par les étudiants. Vos réponses seront relues "
        "et certifiées par un chef de service avant publication."
    )

    tabs = st.tabs(["📋 Questions sans réponse", "➕ Proposer une nouvelle Q/R"])

    # ------------------------------------------------------------------ #
    #  TAB 1 — Répondre aux questions existantes                         #
    # ------------------------------------------------------------------ #
    with tabs[0]:
        pending = list(kb_col.find({"status": "en_attente", "response": "En attente"}))

        if not pending:
            st.success("✅ Aucune question sans réponse pour le moment !")
        else:
            st.info(f"📋 {len(pending)} question(s) sans réponse proposée.")
            for item in pending:
                item_id = str(item["_id"])
                with st.expander(f"❓ {item['question']}", expanded=False):
                    st.caption(
                        f"Catégorie : {item.get('category', 'Général')} — "
                        f"Posée le : {item.get('created_at', 'N/A')}"
                    )
                    proposed = st.text_area(
                        "Votre réponse proposée",
                        height=100,
                        key=f"contrib_{item_id}",
                        placeholder="Rédigez une réponse claire et précise...",
                    )
                    if st.button("📤 Soumettre pour validation", key=f"sub_{item_id}"):
                        if proposed.strip():
                            kb_col.update_one(
                                {"_id": item["_id"]},
                                {"$set": {
                                    "response":     proposed,
                                    "author_email": user["email"],
                                    "updated_at":   datetime.now(),
                                    # Reste en_attente — sera certifié par le validateur
                                }}
                            )
                            st.success("Réponse soumise ! Elle sera vérifiée avant publication.")
                            st.rerun()
                        else:
                            st.error("La réponse ne peut pas être vide.")

    # ------------------------------------------------------------------ #
    #  TAB 2 — Proposer une nouvelle paire Q/R                           #
    # ------------------------------------------------------------------ #
    with tabs[1]:
        st.markdown("Proposez une nouvelle entrée dans la base de connaissances.")
        with st.form("new_contribution_form"):
            question = st.text_input("Question *", placeholder="Ex : Quels sont les frais du MBA ?")
            category = st.selectbox(
                "Catégorie *",
                ["Admission", "Bourses", "MBA", "Licence_Pro", "Cybersécurité",
                 "Vie campus", "Scolarité", "Général"]
            )
            response = st.text_area(
                "Réponse proposée *",
                height=120,
                placeholder="Rédigez une réponse claire et précise..."
            )
            submitted = st.form_submit_button("📤 Soumettre pour validation")

            if submitted:
                if question.strip() and response.strip():
                    kb_col.insert_one({
                        "question":     question.strip(),
                        "response":     response.strip(),
                        "status":       "en_attente",
                        "category":     category,
                        "author_email": user["email"],
                        "created_at":   datetime.now(),
                        "validated_by": None,
                    })
                    st.success(
                        "✅ Contribution soumise ! Un chef de service va la certifier avant publication."
                    )
                else:
                    st.error("La question et la réponse sont obligatoires.")