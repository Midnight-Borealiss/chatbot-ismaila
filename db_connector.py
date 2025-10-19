# db_connector.py

import streamlit as st
import pandas as pd
from pyairtable import Table

# --- CONFIGURATION AIRTABLE ---
# L'initialisation se fait via les fonctions du logger pour la sécurité
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["API_KEY"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["BASE_ID"]
    FAQ_TABLE_NAME = st.secrets["airtable"]["TABLE_FAQ"]
except KeyError:
    # Si les secrets manquent, les noms de tables ne seront pas définis
    AIRTABLE_API_KEY = None
    AIRTABLE_BASE_ID = None
    FAQ_TABLE_NAME = None


# Utilisation de st.cache_resource pour garantir que la base n'est chargée qu'une seule fois
# et que les erreurs d'API sont gérées.
@st.cache_resource
def get_airtable_table(table_name):
    """Charge un objet Table Airtable en toute sécurité et le met en cache."""
    # Cette fonction est normalement définie dans logger.py, mais nous la redéfinissons
    # ici pour l'utiliser lors du chargement de la FAQ, si vous ne pouvez pas l'importer.
    # Si vous pouvez importer get_airtable_table depuis logger.py, utilisez l'import.
    
    # Si vous ne pouvez pas faire l'import :
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID or not table_name:
        print(f"DEBUG DB: Clés Airtable ou nom de table '{table_name}' manquants.")
        return None

    try:
        table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, table_name)
        return table
    except Exception as e:
        print(f"======================================================")
        print(f"!!! ÉCHEC FATAL DE LA CONNEXION AIRTABLE FAQ !!!")
        print(f"Tentative de connexion à la table : {table_name}")
        print(f"CAUSE PROBABLE: API_KEY ou BASE_ID incorrects ou expirés.")
        print(f"ERREUR AIRTABLE: {e}") 
        print(f"======================================================")
        return None

# --- FONCTION PRINCIPALE DE CHARGEMENT DE LA BASE DE CONNAISSANCES ---

@st.cache_data(ttl=3600)  # Mise en cache des données lues
def get_knowledge_base():
    """Charge et prépare la base de connaissances FAQ depuis Airtable."""
    knowledge_base = []
    
    # Récupérer l'objet Table pour la FAQ
    faq_table = get_airtable_table(FAQ_TABLE_NAME)

    if faq_table is None:
        print("DEBUG DB: Base de connaissances FAQ non chargée car la connexion Airtable a échoué.")
        return []

    try:
        # Récupérer tous les enregistrements
        records = faq_table.all()
        
        for record in records:
            # Assurez-vous que les noms des champs correspondent exactement à la casse de vos colonnes Airtable
            fields = record.get("fields", {})
            
            # Ici, on ne filtre que si 'Statut' est présent et n'est pas 'Archivé'
            # Adaptez cette condition si vos colonnes ont des noms différents.
            if fields.get("Statut") != "Archivé": 
                knowledge_base.append({
                    "id": record.get("id"),
                    "question": fields.get("Questions"),         # Assurez-vous que "Questions" est le nom exact
                    "formulations": fields.get("Formulations"),  # Assurez-vous que "Formulations" est le nom exact
                    "reponse": fields.get("Réponses"),           # Assurez-vous que "Réponses" est le nom exact
                    "mots_cles": fields.get("Mots-clés")         # Assurez-vous que "Mots-clés" est le nom exact
                })
        
        # Affichage du statut dans les logs Streamlit Cloud
        print(f"DEBUG DB: Succès. Base de connaissances chargée avec {len(knowledge_base)} entrées actives.")
        
    except Exception as e:
        # Ceci capture les erreurs de lecture de la table (ex: champ non trouvé)
        print(f"======================================================")
        print(f"!!! ÉCHEC DE LECTURE DE LA BASE AIRTABLE FAQ !!!")
        print(f"CAUSE PROBABLE: Nom de colonne incorrect dans la table '{FAQ_TABLE_NAME}'.")
        print(f"ERREUR AIRTABLE: {e}") 
        print(f"======================================================")
        knowledge_base = []
        
    return knowledge_base
knowledge_base = get_knowledge_base()

# Le code suivant est nécessaire pour s'assurer que la base est chargée au démarrage
# et affichera les messages de débogage.
# knowledge_base = get_knowledge_base()