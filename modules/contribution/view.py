import streamlit as st
import pandas as pd
from db_connector import mongo_db
from datetime import datetime

def render_contribution_page():
    st.title("🌍 Contribuer à ISMaiLa")
    st.markdown("""
    Aidez l'assistant à s'enrichir. Vous pouvez poser une question seule ou proposer un duo Question/Réponse. 
    *Toute contribution sera validée par un modérateur avant d'être publiée.*
    """)

    # --- 1. RÉCUPÉRATION DES INFOS DE SESSION (Correction du Nom) ---
    # On récupère le nom complet, sinon le username, sinon "Contributeur"
    nom_session = st.session_state.get('name') or st.session_state.get('username') or "Contributeur"
    email_session = st.session_state.get('username', 'non_identifie')

    # --- 2. GESTION DE LA CATÉGORIE (INTERACTIF) ---
    LISTE_BASE = ["Scolarité", "Examens", "Vie Étudiante", "Stages", "Technique", "Autre..."]
    
    col_cat, col_auth = st.columns(2)
    
    with col_cat:
        choix_cat = st.selectbox("Sélectionnez une thématique :", LISTE_BASE, key="cat_selector")
        
        categorie_finale = choix_cat
        if choix_cat == "Autre...":
            custom_cat = st.text_input("✍️ Nommez votre nouvelle thématique :", placeholder="Ex: Bibliothèque, Cantine...")
            categorie_finale = custom_cat

    with col_auth:
        # On affiche le nom qui sera réellement enregistré dans MongoDB
        st.info(f"👤 Auteur : **{nom_session}**")

    # --- 3. LE FORMULAIRE DE SAISIE ---
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
            if choix_cat == "Autre..." and (not categorie_finale or not categorie_finale.strip()):
                st.error("⚠️ Veuillez préciser le nom de la nouvelle catégorie.")
            
            elif not question.strip():
                st.error("⚠️ Le champ 'Question' ne peut pas être vide.")
                
            else:
                # Préparation du contenu
                reponse_finale = response.strip() if response.strip() else "En attente de réponse admin..."
                
                # CRÉATION DU DOCUMENT (Structure identique à ce que l'Admin attend)
                contribution_doc = {
                    "question": question.strip(),
                    "response": reponse_finale,
                    "category": categorie_finale.strip(),
                    "user_name": nom_session,      # Clé critique pour l'affichage Admin
                    "submitted_by": email_session, # Pour le suivi technique
                    "status": "en_attente",
                    "timestamp": datetime.now(),
                    "heure": datetime.now().hour
                }
                
                try:
                    # Insertion MongoDB
                    mongo_db.contributions.insert_one(contribution_doc)
                    
                    # Notifications
                    st.toast(f"✅ Merci {nom_session}, enregistré !", icon='🎉')
                    st.success(f"Félicitations ! Votre contribution dans '{categorie_finale}' a été envoyée.")
                    
                except Exception as e:
                    st.error(f"Une erreur est survenue lors de l'enregistrement : {e}")

    # --- 4. PIED DE PAGE ---
    st.markdown("---")
    with st.expander("ℹ️ Comment ça marche ?"):
        st.write("""
        1. **Envoi** : Votre question est stockée avec le statut 'en attente'.
        2. **Validation** : L'équipe admin vérifie l'information.
        3. **Publication** : Une fois validée, l'IA ISMaiLa pourra répondre à cette question.
        """)