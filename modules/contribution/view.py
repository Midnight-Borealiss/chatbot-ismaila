import streamlit as st
from db_connector import mongo_db

def render_contribution_page():
    st.title("🌍 Contribuer à la connaissance d'ISMaiLa")
    st.write("Aidez l'assistant à devenir plus intelligent en proposant des questions/réponses.")

    # Liste des catégories prédéfinies
    CATEGORIES = [
        "Scolarité & Inscriptions",
        "Examens & Évaluations",
        "Vie Étudiante",
        "Stages & Emplois",
        "Technique & Plateforme",
        "Autre"
    ]

    with st.form("contribution_form"):
        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox("Catégorie", CATEGORIES) # <-- Menu déroulant
        with col2:
            user_name = st.text_input("Votre nom (optionnel)", value=st.session_state.name)

        question = st.text_area("La question (soyez précis)")
        response = st.text_area("La réponse suggérée")

        if st.form_submit_button("Soumettre la contribution"):
            if question.strip() and response.strip():
                contribution = {
                    "question": question.strip(),
                    "response": response.strip(),
                    "category": category,
                    "user_name": user_name,
                    "status": "en_attente",
                    "submitted_by": st.session_state.username
                }
                mongo_db.contributions.insert_one(contribution)
                st.success("Merci ! Votre contribution est en attente de validation.")
            else:
                st.error("Veuillez remplir tous les champs.")