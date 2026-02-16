import streamlit as st
from db_connector import mongo_db

def render_contribution_page():
    st.title("🌍 Contribuer à ISMaiLa")
    st.write("Posez une question ou proposez une réponse.")

    # 1. Gestion des catégories (Statique + Dynamique)
    LISTE_BASE = ["Scolarité", "Examens", "Vie Étudiante", "Stages", "Technique", "Autre..."]
    
    with st.form("contribution_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            choix_cat = st.selectbox("Thématique", LISTE_BASE)
            # Si "Autre..." est sélectionné, on affiche un champ texte
            custom_cat = ""
            if choix_cat == "Autre...":
                custom_cat = st.text_input("Précisez la catégorie :", placeholder="Ex: Bibliothèque")
        
        with col2:
            # CORRECTION : On force l'utilisation du nom en session
            # On utilise st.session_state.name (défini lors du login)
            nom_auteur = st.session_state.get('name', 'Utilisateur')
            st.info(f"Auteur : **{nom_auteur}**")

        question = st.text_area("Votre Question *")
        response = st.text_area("Votre Réponse (optionnel)")

        submitted = st.form_submit_button("Envoyer la contribution")

        if submitted:
            if question.strip():
                # Détermination de la catégorie finale
                categorie_finale = custom_cat.strip() if choix_cat == "Autre..." and custom_cat.strip() else choix_cat
                
                # Réponse par défaut si vide
                reponse_finale = response.strip() if response.strip() else "En attente de réponse admin..."
                
                contribution_doc = {
                    "question": question.strip(),
                    "response": reponse_finale,
                    "category": categorie_finale,
                    "user_name": nom_auteur, # Utilise le nom de la session
                    "status": "en_attente",
                    "submitted_by": st.session_state.username # Email de la session
                }
                
                mongo_db.contributions.insert_one(contribution_doc)
                st.toast(f"✅ Enregistré dans '{categorie_finale}'", icon='📩')
            else:
                st.error("⚠️ La question ne peut pas être vide.")

    st.info("💡 Vos contributions aident toute la communauté !")