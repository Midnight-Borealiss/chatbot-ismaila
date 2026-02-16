import streamlit as st
from db_connector import mongo_db

def render_contribution_page():
    st.title("🌍 Contribuer à ISMaiLa")
    st.write("Posez une question ou proposez une réponse pour enrichir la base.")

    # Liste des catégories (tu peux en ajouter d'autres ici)
    CATEGORIES = [
        "Scolarité & Inscriptions",
        "Examens & Évaluations",
        "Vie Étudiante",
        "Stages & Emplois",
        "Technique & Plateforme",
        "Autre"
    ]

    # Formulaire avec vidage automatique après soumission
    with st.form("contribution_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            # L'utilisateur choisit obligatoirement une catégorie
            category = st.selectbox("Catégorie de votre question", CATEGORIES)
        with col2:
            user_name = st.text_input("Votre nom", value=st.session_state.name)

        # La question est OBLIGATOIRE
        question = st.text_area("Votre Question *", placeholder="Ex: Quelle est la date limite pour le dépôt des mémoires ?")
        
        # La réponse est FACULTATIVE
        response = st.text_area("Votre Réponse (si vous la connaissez)", 
                                placeholder="Laissez vide si vous ne connaissez pas la réponse.")

        submitted = st.form_submit_button("Envoyer la contribution")

        if submitted:
            if question.strip():
                # On prépare le document pour MongoDB
                # Si la réponse est vide, on met un texte par défaut pour l'admin
                final_response = response.strip() if response.strip() else "En attente de réponse admin..."
                
                contribution_doc = {
                    "question": question.strip(),
                    "response": final_response,
                    "category": category,
                    "user_name": user_name,
                    "status": "en_attente",
                    "submitted_by": st.session_state.username
                }
                
                # Enregistrement en base de données
                mongo_db.contributions.insert_one(contribution_doc)
                
                # Notification visuelle
                st.toast(f"✅ Question enregistrée dans '{category}'", icon='📩')
            else:
                st.error("⚠️ La question est obligatoire pour pouvoir l'enregistrer.")

    st.info("💡 Si vous ne mettez pas de réponse, un administrateur se chargera d'y répondre prochainement.")