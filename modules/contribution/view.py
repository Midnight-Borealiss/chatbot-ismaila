import streamlit as st
from db_connector import mongo_db

def render_contribution_page():
    st.title("🌍 Contribuer à ISMaiLa")
    st.write("Proposez une nouvelle question et sa réponse pour enrichir la base.")

    # Liste des catégories
    CATEGORIES = [
        "Scolarité & Inscriptions",
        "Examens & Évaluations",
        "Vie Étudiante",
        "Stages & Emplois",
        "Technique & Plateforme",
        "Autre"
    ]

    # Utilisation d'un formulaire qui se vide après soumission (clear_on_submit)
    with st.form("contribution_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox("Catégorie", CATEGORIES)
        with col2:
            # On utilise le nom de la session, mais on laisse la possibilité de modifier
            user_name = st.text_input("Auteur", value=st.session_state.name)

        # Champs séparés pour Question et Réponse
        question = st.text_area("La Question :", placeholder="Ex: Comment obtenir un relevé de notes ?")
        response = st.text_area("La Réponse suggérée :", placeholder="Ex: Vous devez faire la demande au service de la scolarité...")

        submitted = st.form_submit_button("Enregistrer la contribution")

        if submitted:
            if question.strip() and response.strip():
                # Préparation des données
                new_doc = {
                    "question": question.strip(),
                    "response": response.strip(),
                    "category": category,
                    "user_name": user_name,
                    "status": "en_attente",
                    "submitted_by": st.session_state.username
                }
                
                # Insertion MongoDB
                mongo_db.contributions.insert_one(new_doc)
                
                # Notification de succès (Toast est plus discret et élégant pour des saisies multiples)
                st.toast("✅ Contribution enregistrée avec succès !", icon='🎉')
                
                # Note: Le formulaire se vide déjà grâce à clear_on_submit=True
                # On ne fait pas de rerun immédiat ici pour laisser l'utilisateur voir le toast
            else:
                st.error("⚠️ Veuillez remplir à la fois la question et la réponse.")

    st.info("💡 Vos contributions seront visibles par tous une fois validées par un administrateur.")