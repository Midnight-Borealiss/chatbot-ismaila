import streamlit as st
import pandas as pd
from db_connector import mongo_db
from datetime import datetime

def render_contribution_page():
    st.title("🌍 Contribuer à ISMaiLa")
    st.markdown("""
    Aidez l'assistant à s'enrichir. Précisez le contexte (École, Niveau) pour des réponses plus précises.
    """)

    # --- 1. INFOS DE SESSION & CATÉGORIE ---
    nom_session = st.session_state.get('name') or st.session_state.get('username') or "Contributeur"
    email_session = st.session_state.get('username', 'non_identifie')

    LISTE_BASE = ["Scolarité", "Examens", "Vie Étudiante", "admission", "Accès", "Autre..."]
    
    col_cat, col_auth = st.columns(2)
    
    with col_cat:
        choix_cat = st.selectbox("Sélectionnez une thématique :", LISTE_BASE, key="cat_selector")
        categorie_finale = choix_cat
        if choix_cat == "Autre...":
            categorie_finale = st.text_input("✍️ Nommez votre thématique :", placeholder="Ex: Bibliothèque...")

    with col_auth:
        st.info(f"👤 Auteur : **{nom_session}**")

    # --- 2. LE FORMULAIRE DE SAISIE ---
    with st.form("contribution_form", clear_on_submit=True):
        st.subheader("Contenu de la contribution")
        
        question = st.text_area("Votre Question *", placeholder="Ex: Quel est le planning des examens ?")
        response = st.text_area("Votre Réponse (Optionnel)", placeholder="Laissez vide si inconnu.")

        # --- NOUVEAU : SECTION CONTEXTE (ÉCOLE, NIVEAU, SPÉCIALITÉ) ---
        st.markdown("---")
        st.write("📍 **Contexte (Optionnel)** - *Aidez-nous à cibler la réponse*")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            ecole = st.text_input("École", placeholder="Ex: ISM, ISEG...")
        with c2:
            niveau = st.text_input("Niveau", placeholder="Ex: Licence 1, Master...")
        with c3:
            specialite = st.text_input("Spécialité", placeholder="Ex: Management, IT...")

        submitted = st.form_submit_button("🚀 Envoyer la contribution")

        if submitted:
            if not question.strip():
                st.error("⚠️ Le champ 'Question' est obligatoire.")
            elif choix_cat == "Autre..." and not categorie_finale.strip():
                st.error("⚠️ Veuillez nommer votre catégorie.")
            else:
                reponse_finale = response.strip() if response.strip() else "En attente de réponse admin..."
                
                # CRÉATION DU DOCUMENT AVEC LES NOUVEAUX CHAMPS
                contribution_doc = {
                    "question": question.strip(),
                    "response": reponse_finale,
                    "category": categorie_finale.strip(),
                    "context": {
                        "ecole": ecole.strip(),
                        "niveau": niveau.strip(),
                        "specialite": specialite.strip()
                    },
                    "user_name": nom_session,
                    "submitted_by": email_session,
                    "status": "en_attente",
                    "timestamp": datetime.now(),
                    "heure": datetime.now().hour
                }
                
                try:
                    mongo_db.contributions.insert_one(contribution_doc)
                    st.toast(f"✅ Merci {nom_session} ! Contribution enregistrée.", icon='🎉')
                    st.success(f"Enregistré ! Contexte : {ecole} {niveau} {specialite}")
                except Exception as e:
                    st.error(f"Erreur technique : {e}")

    st.markdown("---")
    with st.expander("ℹ️ Pourquoi préciser l'école ou le niveau ?"):
        st.write("Certaines règles (examens, stages) varient selon les écoles ou les niveaux. Ces précisions permettent à l'IA de donner la bonne réponse à la bonne personne.")