# logger.py (VERSION AIRTABLE)

from datetime import datetime
import streamlit as st
from pyairtable import Table

# --- CONFIGURATION AIRTABLE (Chargement via st.secrets) ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["API_KEY"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["BASE_ID"]
    
    # Noms des tables pour la journalisation
    LOGS_TABLE_NAME = st.secrets["airtable"]["TABLE_LOGS"] # Logs
    NEW_QUESTIONS_TABLE_NAME = st.secrets["airtable"]["TABLE_NEW_QUESTIONS"] # New_Questions

    # Initialisation de la connexion Airtable (si secrets existent)
    AIRTABLE_LOGS_TABLE = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, LOGS_TABLE_NAME)
    AIRTABLE_NEW_QUESTIONS_TABLE = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, NEW_QUESTIONS_TABLE_NAME)

    IS_AIRTABLE_READY = True
except (KeyError, AttributeError, ValueError):
    IS_AIRTABLE_READY = False


def log_to_airtable(table_obj, fields):
    """Fonction générique pour enregistrer une ligne dans une table Airtable."""
    if not IS_AIRTABLE_READY:
        print("Airtable non configuré. Journalisation ignorée.")
        return

    try:
        table_obj.create(fields)
    except Exception as e:
        print(f"ERREUR d'écriture Airtable: {e}")


def log_connection_event(event_type: str, username: str, name: str, profile: str):
    """Enregistre un événement de connexion ou de déconnexion dans la table 'Logs'."""
    fields = {
        "Timestamp": datetime.now().isoformat(),
        "Type": event_type, # LOGIN ou LOGOUT
        "Email": username,
        "Nom": name,
        "Profile": profile
        # Le champ 'Question' et 'Réponse' seront laissés vides pour ces événements
    }
    log_to_airtable(AIRTABLE_LOGS_TABLE, fields)


def log_interaction(user_question: str, bot_response: str, is_handled: bool, profile: str = "GUEST", username: str = "unknown"):
    """Enregistre une interaction (question/réponse) dans la table 'Logs'."""
    fields = {
        "Timestamp": datetime.now().isoformat(),
        "Type": "INTERACTION",
        "Email": username,
        "Profile": profile,
        "Question": user_question,
        "Réponse": bot_response,
        "Géré": is_handled 
    }
    log_to_airtable(AIRTABLE_LOGS_TABLE, fields)


def log_unhandled_question(user_question: str, profile: str, username: str):
    """Enregistre les questions sans réponse trouvée dans la table 'New_Questions'."""
    fields = {
        "Date": datetime.now().isoformat(),
        "Question": user_question,
        "Email": username,
        "Profile": profile,
        "Statut": "À Traiter" # Le statut par défaut dans votre table
    }
    log_to_airtable(AIRTABLE_NEW_QUESTIONS_TABLE, fields)