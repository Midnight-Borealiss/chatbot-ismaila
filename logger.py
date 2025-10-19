# logger.py (Mise à jour pour un meilleur contrôle d'erreur)

from datetime import datetime
import streamlit as st
from pyairtable import Table

# Initialisation des variables globales de connexion
AIRTABLE_LOGS_TABLE = None
AIRTABLE_NEW_QUESTIONS_TABLE = None
IS_AIRTABLE_READY = False

try:
    # 1. Charger les clés
    AIRTABLE_API_KEY = st.secrets["airtable"]["API_KEY"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["BASE_ID"]
    
    # 2. Charger les noms de tables
    LOGS_TABLE_NAME = st.secrets["airtable"]["TABLE_LOGS"] 
    NEW_QUESTIONS_TABLE_NAME = st.secrets["airtable"]["TABLE_NEW_QUESTIONS"] 

    # 3. Vérifier que toutes les clés sont présentes
    if AIRTABLE_API_KEY and AIRTABLE_BASE_ID and LOGS_TABLE_NAME and NEW_QUESTIONS_TABLE_NAME:
        # 4. Initialisation des objets Table
        AIRTABLE_LOGS_TABLE = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, LOGS_TABLE_NAME)
        AIRTABLE_NEW_QUESTIONS_TABLE = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, NEW_QUESTIONS_TABLE_NAME)
        
        IS_AIRTABLE_READY = True
        print("Airtable: Connexion établie.")
    else:
        print("Airtable: Des secrets sont manquants ou vides.")

except Exception as e:
    # Si le chargement des secrets échoue
    print(f"Airtable: Échec de la configuration des secrets: {e}")
    IS_AIRTABLE_READY = False

# Les fonctions log_to_airtable, log_connection_event, etc. restent les mêmes,
# elles dépendent toutes de 'IS_AIRTABLE_READY' pour fonctionner.