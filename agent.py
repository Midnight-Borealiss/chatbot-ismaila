# agent.py (Version Finale)

# Importe le module json uniquement pour la fonction de lecture dans db_connector
import json 
import os
import csv 
from logger import log_interaction 

# Simule la lecture de la base de connaissances (doit être définie ici pour l'agent)
knowledge_base = [] 
JSON_FILE_PATH = "infos.json"

def load_knowledge_base_from_json():
    """
    Charge la base de connaissances depuis le fichier infos.json
    où plusieurs questions sont associées à une seule réponse.
    """
    global knowledge_base
    
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data_json = json.load(f)

        knowledge_base_data = []
        
        for block in data_json:
            reponse = str(block.get('answer', '')).strip() 
            questions_list = block.get('questions', [])

            if reponse:
                
                for question in questions_list:
                    question_text = str(question).strip() 
                    
                    if not question_text:
                        continue 
                        
                    context = {
                        "id": None, 
                        "search_text": question_text.lower(), 
                        "answer": reponse, 
                    }
                    knowledge_base_data.append(context)
        
        knowledge_base = knowledge_base_data
        return knowledge_base

    except FileNotFoundError:
        # Gère l'erreur de fichier manquant
        return []
    except json.JSONDecodeError:
        # Gère l'erreur de format JSON
        return []
    except Exception:
        return []

load_knowledge_base_from_json() 

DEFAULT_FALLBACK_ANSWER = "Désolé, je n'ai pas trouvé de réponse pertinente à votre question. Je l'ai notée pour nos administrateurs."

def get_agent_response(user_question: str, user_profile: str = "GUEST", username: str = "unknown") -> tuple[str, bool]:
    """
    Fonction principale qui cherche la réponse à la question de l'utilisateur, 
    adapte la réponse selon le profil, et journalise l'interaction.
    """
    
    processed_question = user_question.lower().strip()
    best_match_answer = None
    
    # Vérifie si la base a été chargée (réponse à l'erreur précédente)
    if not knowledge_base:
        bot_response = "La base de connaissances n'a pas pu être chargée. Veuillez contacter l'administrateur."
        log_interaction(user_question, bot_response, False, user_profile, username)
        return bot_response, False
        
    # Logique de Recherche Simple par Mot-Clé
    for entry in knowledge_base:
        search_text_entry = entry['search_text'] 
        
        if processed_question == search_text_entry or processed_question in search_text_entry:
            best_match_answer = entry['answer']
            break
        
        if search_text_entry in processed_question:
             best_match_answer = entry['answer']
             break

    # Génération de la Réponse et Adaptation
    if best_match_answer:
        bot_response = best_match_answer
        
        # Exemple: Adapter l'aide pour un administrateur
        if user_profile == "ADMINISTRATION" and "certificat de scolarité" in processed_question:
             bot_response += "\n\n(Note Admin: Le processus interne se trouve dans le drive partagé 'Documents Administratifs')"

        is_handled = True
    else:
        bot_response = DEFAULT_FALLBACK_ANSWER
        is_handled = False
        
    # Journalisation de l'interaction
    log_interaction(user_question, bot_response, is_handled, user_profile, username)
    
    return bot_response, is_handled