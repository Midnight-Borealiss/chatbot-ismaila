# streamlit_app.py (VERSION SIMPLIFIÉE AVEC SAISIE NOM/EMAIL)

import streamlit as st
import yaml
from yaml.loader import SafeLoader
import time # Utile pour simuler une petite attente après la saisie

from agent import get_agent_response

# --- Configuration et Chargement des Données ---
try:
    with open('config.yaml') as file:
        config = yaml.load(file, Loader=SafeLoader)
except FileNotFoundError:
    st.error("Erreur: Le fichier config.yaml est introuvable. Veuillez le créer.")
    st.stop()


# --- Configuration de la Page Streamlit ---
st.set_page_config(page_title="Chatbot ISMAILA", layout="wide")


# --- Initialisation des États de Session ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None # Sera l'email saisi
if "name" not in st.session_state:
    st.session_state["name"] = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_profile" not in st.session_state: 
    st.session_state.user_profile = config.get('default_profile', 'GUEST')


# --- Fonctions de Gestion de Profil et Vues ---

def get_user_profile_from_email(user_email):
    """Détermine le profil basé sur l'email lu dans config.yaml."""
    profiles = config.get('user_profiles', {})
    user_email_lower = user_email.lower().strip()
    
    for profile, emails in profiles.items():
        if user_email_lower in [e.lower().strip() for e in emails]:
            return profile
            
    # Retourne le profil par défaut
    return config.get('default_profile', 'GUEST')

def logout():
    """Déconnecte l'utilisateur et efface l'état de session."""
    st.session_state["logged_in"] = False
    st.session_state["username"] = None
    st.session_state["name"] = None
    st.session_state.messages = []
    st.session_state.user_profile = config.get('default_profile', 'GUEST')
    st.rerun()

def render_login_page():
    """Affiche la page de saisie du pseudonyme et de l'email."""
    st.title("Votre Chatbot ISMAILA 👤")
    st.markdown("Veuillez saisir votre nom et votre email pour démarrer la conversation.")
    
    with st.form("access_form"):
        # Le nom sera affiché en clair
        user_name = st.text_input("Votre Nom/Pseudonyme", key="input_name")
        # L'email servira d'identifiant pour le profil
        user_email = st.text_input("Votre Email (ex: nom@ism.edu)", key="input_email")
        
        submitted = st.form_submit_button("Démarrer le Chat")
        
        if submitted:
            if not user_name or "@" not in user_email:
                st.error("Veuillez remplir le nom et saisir un email valide.")
            else:
                with st.spinner("Vérification du profil..."):
                    time.sleep(0.5) 
                    
                # Détermination du profil basé sur l'email
                user_profile = get_user_profile_from_email(user_email)
                
                # Stockage des données dans l'état de session
                st.session_state.logged_in = True
                st.session_state.username = user_email # L'email sert d'ID unique
                st.session_state.name = user_name
                st.session_state.user_profile = user_profile 
                
                # Message de bienvenue
                st.session_state.messages.append({"role": "assistant", "content": f"Bonjour {user_name}  ! Bienvenue sur le Chatbot ISMAILA. Comment puis-je vous aider ?"})
                st.rerun() 


def render_chatbot_page():
    """Affiche l'interface du chatbot."""
    
    st.sidebar.markdown(f"**Utilisateur:** {st.session_state['name']}")
    #st.sidebar.markdown(f"**Profil:** {st.session_state.user_profile}")
    st.sidebar.button('Changer d\'utilisateur 🚪', on_click=logout)
    
    st.title("Chatbot ISMAILA - Espace Étudiant")
    
    # Afficher les messages précédents
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Champ de saisie
    if prompt := st.chat_input("Posez votre question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Obtenir la réponse de l'agent
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