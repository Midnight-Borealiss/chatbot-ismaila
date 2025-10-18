# streamlit_app.py (VERSION SANS YAML ET AVEC JOURNAL DE CONNEXION)

import streamlit as st
# REMPLACER le yaml par la définition des règles directement dans le code
import time 

from agent import get_agent_response
# Importation de la nouvelle fonction de journalisation
from logger import log_connection_event 


# --- DÉFINITION DES RÈGLES DE PROFIL (Anciennement config.yaml) ---
# Les emails doivent être en minuscules pour garantir la correspondance
USER_PROFILES_RULES = {
    "ADMINISTRATION": [
        "admin@ism.edu",
        "votre.email@gmail.com"
    ],
    "ENSEIGNANT": [
        "prof.info@ism.edu"
    ]
}
DEFAULT_PROFILE = "ÉTUDIANT"


# --- Configuration de la Page Streamlit ---
st.set_page_config(page_title="Chatbot ISMAILA", layout="wide")


# --- Initialisation des États de Session ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None 
if "name" not in st.session_state:
    st.session_state["name"] = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_profile" not in st.session_state: 
    st.session_state.user_profile = DEFAULT_PROFILE


# --- Fonctions de Gestion de Profil et Vues ---

def get_user_profile_from_email(user_email):
    """Détermine le profil basé sur l'email saisi et les règles codées."""
    user_email_lower = user_email.lower().strip()
    
    for profile, emails in USER_PROFILES_RULES.items():
        if user_email_lower in [e.lower().strip() for e in emails]:
            return profile
            
    # Retourne le profil par défaut
    return DEFAULT_PROFILE

def logout():
    """Déconnecte l'utilisateur et journalise l'événement."""
    # 1. Journaliser la déconnexion AVANT de vider l'état
    log_connection_event(
        event_type="LOGOUT",
        username=st.session_state.username,
        name=st.session_state.name,
        profile=st.session_state.user_profile
    )
    
    # 2. Vider l'état
    st.session_state["logged_in"] = False
    st.session_state["username"] = None
    st.session_state["name"] = None
    st.session_state.messages = []
    st.session_state.user_profile = DEFAULT_PROFILE
    st.rerun()

def render_login_page():
    """Affiche la page de saisie du pseudonyme et de l'email."""
    st.title("Accès au Chatbot ISMAILA 👤")
    st.markdown("Veuillez saisir votre nom et votre email pour démarrer la conversation.")
    
    with st.form("access_form"):
        user_name = st.text_input("Votre Nom/Pseudonyme", key="input_name")
        user_email = st.text_input("Votre Email (ex: nom@ism.edu)", key="input_email")
        
        submitted = st.form_submit_button("Démarrer le Chat")
        
        if submitted:
            if not user_name or "@" not in user_email:
                st.error("Veuillez remplir le nom et saisir un email valide.")
            else:
                with st.spinner("Vérification du profil..."):
                    time.sleep(0.5) 
                    
                # Détermination du profil
                user_profile = get_user_profile_from_email(user_email)
                
                # Stockage des données
                st.session_state.logged_in = True
                st.session_state.username = user_email
                st.session_state.name = user_name
                st.session_state.user_profile = user_profile 
                
                # JOURNALISER LA CONNEXION
                log_connection_event(
                    event_type="LOGIN",
                    username=user_email,
                    name=user_name,
                    profile=user_profile
                )
                
                # Message de bienvenue
                st.session_state.messages.append({"role": "assistant", "content": f"Bonjour {user_name} (Profil: {user_profile}) ! Bienvenue sur le Chatbot ISMAILA. Comment puis-je vous aider ?"})
                st.rerun() 


def render_chatbot_page():
    """Affiche l'interface du chatbot."""
    
    st.sidebar.markdown(f"**Utilisateur:** {st.session_state['name']}")
    st.sidebar.markdown(f"**Profil:** {st.session_state.user_profile}")
    st.sidebar.button('Changer d\'utilisateur 🚪', on_click=logout)
    
    st.title("Chatbot ISMAILA - Aide Étudiant")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Posez votre question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.spinner("Recherche de la réponse..."):
            response, is_handled = get_agent_response(
                prompt, 
                st.session_state.user_profile,
                st.session_state.username
            )
            
            with st.chat_message("assistant"):
                st.markdown(response)
                
            st.session_state.messages.append({"role": "assistant", "content": response})


# --- Logique Principale d'Affichage ---

if st.session_state.logged_in:
    render_chatbot_page()
else:
    render_login_page()