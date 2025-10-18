# logger.py (Version Finale)

import csv
import os
from datetime import datetime

# Journal des interactions
LOG_FILE_INTERACTIONS = "chatbot_interactions.csv"
HEADERS_INTERACTIONS = ["timestamp", "user_question", "bot_response", "is_handled", "profile", "username"] 

# Journal des connexions
LOG_FILE_CONNECTIONS = "user_logins.csv"
HEADERS_CONNECTIONS = ["timestamp", "event_type", "username", "name", "profile"]

def initialize_log_file(file_path, headers):
    """Initialise un fichier CSV de log si nécessaire."""
    if not os.path.exists(file_path):
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

def log_interaction(user_question: str, bot_response: str, is_handled: bool, profile: str = "GUEST", username: str = "unknown"):
    """Enregistre une interaction (question/réponse) dans le fichier CSV."""
    initialize_log_file(LOG_FILE_INTERACTIONS, HEADERS_INTERACTIONS)
    try:
        with open(LOG_FILE_INTERACTIONS, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            timestamp = datetime.now().isoformat()
            writer.writerow([timestamp, user_question, bot_response, str(is_handled), profile, username])
    except Exception:
        pass 

def log_connection_event(event_type: str, username: str, name: str, profile: str):
    """Enregistre un événement de connexion ou de déconnexion pour le suivi."""
    initialize_log_file(LOG_FILE_CONNECTIONS, HEADERS_CONNECTIONS)
    try:
        with open(LOG_FILE_CONNECTIONS, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            timestamp = datetime.now().isoformat()
            writer.writerow([timestamp, event_type, username, name, profile])
    except Exception:
        pass