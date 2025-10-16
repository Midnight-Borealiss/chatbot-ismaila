# logger.py

import csv
import os
from datetime import datetime

LOG_FILE = "chatbot_interactions.csv"
HEADERS = ["timestamp", "user_question", "bot_response", "is_handled", "profile", "username"] 

def initialize_log_file():
    """Initialise le fichier CSV de log si nécessaire."""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(HEADERS)

def log_interaction(user_question: str, bot_response: str, is_handled: bool, profile: str = "GUEST", username: str = "unknown"):
    """Enregistre une interaction dans le fichier CSV, y compris le profil et le nom d'utilisateur."""
    initialize_log_file()
    try:
        with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            timestamp = datetime.now().isoformat()
            writer.writerow([timestamp, user_question, bot_response, str(is_handled), profile, username])
    except Exception:
        pass