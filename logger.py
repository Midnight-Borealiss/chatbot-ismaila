# logger.py (VERSION AIRTABLE FINALE AVEC GESTION D'ERREUR)

from datetime import datetime
import streamlit as st
from pyairtable import Table

# Initialisation des variables globales de connexion
AIRTABLE_LOGS_TABLE = None
AIRTABLE_NEW_QUESTIONS_TABLE = None
IS_AIRTABLE_READY = False

# --- CONFIGURATION AIRTABLE (Chargement via st.secrets) ---
try:
    # 1. Charger les clés
    AIRTABLE_API_KEY = st.secrets["airtable"]["API_KEY"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["BASE_ID"]
    
    # 2. Charger les noms de tables (assurez-vous que la casse est correcte dans secrets.toml)
    LOGS_TABLE_NAME = st.secrets["airtable"]["TABLE_LOGS"] 
    NEW_QUESTIONS_TABLE_NAME = st.secrets["airtable"]["TABLE_NEW_QUESTIONS"] 

    # 3. Vérifier que toutes les clés sont présentes
    if AIRTABLE_API_KEY and AIRTABLE_BASE_ID and LOGS_TABLE_NAME and NEW_QUESTIONS_TABLE_NAME:
        # 4. Initialisation des objets Table
        # La connexion échoue souvent ici si les clés sont invalides ou si la base/table n'existe pas.
        AIRTABLE_LOGS_TABLE = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, LOGS_TABLE_NAME)
        AIRTABLE_NEW_QUESTIONS_TABLE = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, NEW_QUESTIONS_TABLE_NAME)
        
        IS_AIRTABLE_READY = True
        print("Airtable: Connexion établie et tables initialisées.")
    else:
        print("Airtable: Des secrets sont manquants ou vides. Journalisation désactivée.")

except Exception as e:
    # Si le chargement des secrets ou l'initialisation de Table échoue
    print(f"================================================================")
    print(f"!!! ÉCHEC DE LA CONFIGURATION AIRTABLE (DÉMARRAGE) !!!")
    print(f"L'application DÉMARRE mais ne peut pas logger. Erreur: {e}") 
    print(f"Vérifiez l'API_KEY, BASE_ID et les noms de tables dans secrets.toml.")
    print(f"================================================================")
    IS_AIRTABLE_READY = False


# --- FONCTIONS DE JOURNALISATION ---

def log_to_airtable(table_obj, fields):
    """Fonction générique pour enregistrer une ligne dans une table Airtable."""
    if not IS_AIRTABLE_READY:
        print("Airtable non prêt. Log ignoré.")
        return

    # Vérification secondaire pour s'assurer que l'objet Table n'est pas None
    if table_obj is None:
        print(f"Airtable: L'objet Table cible est None pour les données: {fields}. Log ignoré.")
        return

    try:
        # Enregistrement des données
        table_obj.create(fields)
        # print("Airtable: Log enregistré avec succès.") # (Optionnel : peut surcharger les logs)

    except Exception as e:
        # Affiche l'erreur complète de l'API Airtable dans les logs Streamlit
        print(f"================================================================")
        print(f"!!! ERREUR D'ÉCRITURE AIRTABLE !!!")
        print(f"Tentative d'écriture dans la table: {table_obj.table_name}")
        print(f"Détails de l'erreur Airtable: {e}") 
        print(f"Les causes fréquentes sont: nom de colonne incorrect ou permissions insuffisantes du jeton.")
        print(f"Données envoyées: {fields}")
        print(f"================================================================")


def log_connection_event(event_type: str, username: str, name: str, profile: str):
    """Enregistre un événement de connexion ou de déconnexion dans la table 'Logs'."""
    # Assurez-vous que les noms des champs correspondent aux colonnes de votre table Logs
    fields = {
        "Timestamp": datetime.now().isoformat(),
        "Type": event_type, # LOGIN ou LOGOUT
        "Email": username,
        "Nom": name,
        "Profile": profile
    }
    log_to_airtable(AIRTABLE_LOGS_TABLE, fields)


def log_interaction(user_question: str, bot_response: str, is_handled: bool, profile: str = "GUEST", username: str = "unknown"):
    """Enregistre une interaction (question/réponse) dans la table 'Logs'."""
    # Assurez-vous que les noms des champs correspondent aux colonnes de votre table Logs
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
    # Assurez-vous que les noms des champs correspondent aux colonnes de votre table New_Questions
    fields = {
        "Date": datetime.now().isoformat(), 
        "Question": user_question,
        "Email": username,
        "Profile": profile,
        "Statut": "À Traiter" 
    }
    log_to_airtable(AIRTABLE_NEW_QUESTIONS_TABLE, fields)