import streamlit as st
import pandas as pd
from db_connector import mongo_db

def render_contribution_page():
    st.title("🌍 Contribuer à ISMaiLa")
    st.markdown("""
    Aidez l'assistant à s'enrichir. Vous pouvez poser une question seule ou proposer un duo Question/Réponse. 
    *Toute contribution sera validée par un modérateur avant d'être publiée.*
    """)

    # --- 1. GESTION DE LA CATÉGORIE (INTERACTIF) ---
    # On sort cette partie du formulaire pour que le champ "Autre" apparaisse dynamiquement
    LISTE_BASE = ["Scolarité", "Examens", "Vie Étudiante", "Stages", "Technique", "Autre..."]
    
    col_cat, col_auth = st.columns(2)
    
    with col_cat:
        choix_cat = st.selectbox("Sélectionnez une thématique :", LISTE_BASE)
        
        # Initialisation de la catégorie finale
        categorie_finale = choix_cat
        
        # Si "Autre..." est sélectionné, on affiche un champ de saisie libre
        if choix_cat == "Autre...":
            custom_cat = st.text_input("✍️ Nommez votre nouvelle thématique :", placeholder="Ex: Bibliothèque, Cantine...")
            categorie_finale = custom_cat

    with col_auth:
        # Récupération automatique du nom de l'utilisateur connecté
        nom_auteur = st.session_state.get('name', 'Utilisateur')
        st.info(f"👤 Auteur : **{nom_auteur}**")

    # --- 2. LE FORMULAIRE DE SAISIE (QUESTIONS / RÉPONSES) ---
    # clear_on_submit=True permet de vider les text_area automatiquement après l'envoi
    with st.form("contribution_form", clear_on_submit=True):
        st.subheader("Votre contenu")
        
        question = st.text_area(
            "Votre Question *", 
            placeholder="Ex: Quelles sont les pièces à fournir pour la carte d'étudiant ?"
        )
        
        response = st.text_area(
            "Votre Réponse (Optionnel)", 
            placeholder="Laissez vide si vous ne connaissez pas la réponse officielle."
        )

        st.write("---")
        submitted = st.form_submit_button("🚀 Envoyer la contribution")

        if submitted:
            # Vérifications de sécurité avant envoi
            if choix_cat == "Autre..." and not categorie_finale.strip():
                st.error("⚠️ Veuillez préciser le nom de la nouvelle catégorie.")
            
            elif not question.strip():
                st.error("⚠️ Le champ 'Question' ne peut pas être vide.")
                
            else:
                # Préparation du contenu de la réponse
                reponse_finale = response.strip() if response.strip() else "En attente de réponse admin..."
                
                # Création du document pour MongoDB
                contribution_doc = {
                    "question": question.strip(),
                    "response": reponse_finale,
                    "category": categorie_finale.strip(),
                    "user_name": nom_auteur,
                    "status": "en_attente",
                    "submitted_by": st.session_state.get('username', 'anonyme'),
                    "timestamp": pd.Timestamp.now()
                }
                
                try:
                    # Insertion dans la collection contributions
                    mongo_db.contributions.insert_one(contribution_doc)
                    
                    # Notification de succès
                    st.toast(f"✅ Enregistré avec succès dans '{categorie_finale}' !", icon='🎉')
                    
                    # Petit rappel visuel car clear_on_submit a vidé les champs
                    st.success("Votre contribution a bien été envoyée à l'équipe de modération.")
                    
                except Exception as e:
                    st.error(f"Une erreur est survenue lors de l'enregistrement : {e}")

    # --- 3. PIED DE PAGE ---
    st.markdown("---")
    with st.expander("ℹ️ Comment ça marche ?"):
        st.write("""
        1. Votre question est envoyée dans l'espace **Modération**.
        2. Un administrateur vérifie l'exactitude de la réponse.
        3. Une fois validée, la question devient disponible pour tous les utilisateurs via le Chatbot.
        """)