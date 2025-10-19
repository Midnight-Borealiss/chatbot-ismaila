# db_connector.py (VERSION AIRTABLE)

import streamlit as st
from pyairtable import Table

# --- CONFIGURATION AIRTABLE (Chargement via st.secrets) ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["API_KEY"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["BASE_ID"]
    # Table des questions/réponses
    AIRTABLE_FAQ_TABLE = st.secrets["airtable"]["TABLE_FAQ"] # FAQ

except (KeyError, AttributeError):
    # Gestion d'erreur si les secrets ne sont pas trouvés (utile en développement local)
    AIRTABLE_API_KEY = None
    AIRTABLE_BASE_ID = None
    AIRTABLE_FAQ_TABLE = None

# --- VARIABLE GLOBALE ---
knowledge_base = [] 


def load_knowledge_base_from_airtable():
    """Charge la base de connaissances depuis la table Airtable 'FAQ'."""
    global knowledge_base
    
    if not (AIRTABLE_API_KEY and AIRTABLE_BASE_ID and AIRTABLE_FAQ_TABLE):
        print("ERREUR: Les secrets Airtable ne sont pas configurés.")
        knowledge_base = []
        return knowledge_base
        
    try:
        # Initialisation de la connexion
        table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_FAQ_TABLE)
        
        # Récupération de tous les enregistrements
        records = table.all()
        
        knowledge_base_data = []
        
        for record in records:
            # Assurez-vous que les noms des champs correspondent EXACTEMENT à ceux de votre table FAQ
            fields = record.get('fields', {})
            
            reponse = fields.get('Réponses', '').strip()
            # On suppose que les questions et formulations sont dans un seul champ texte ou sont concaténées
            questions_text = fields.get('Questions', '') + " " + fields.get('Formulations (Input RAG)', '')
            
            if reponse and questions_text:
                # Créer des entrées séparées pour la recherche (si vous avez plusieurs questions/formulations)
                # Nous simplifions ici en utilisant tout le texte des questions pour la recherche
                
                context = {
                    "id": record['id'], 
                    "search_text": questions_text.lower(), 
                    "answer": reponse, 
                }
                knowledge_base_data.append(context)
        
        knowledge_base = knowledge_base_data
        print(f"Base de connaissances chargée : {len(knowledge_base)} entrées.")
        return knowledge_base

    except Exception as e:
        print(f"ERREUR lors du chargement Airtable : {e}")
        knowledge_base = []
        return knowledge_base

load_knowledge_base_from_airtable()