# agent.py

from db_connector import knowledge_base
from logger import log_interaction 

DEFAULT_FALLBACK_ANSWER = "Désolé, je n'ai pas trouvé de réponse pertinente à votre question. Je l'ai notée pour nos administrateurs."

def get_agent_response(user_question: str, user_profile: str = "GUEST", username: str = "unknown") -> tuple[str, bool]:
    """
    Fonction principale qui cherche la réponse à la question de l'utilisateur, 
    adapte la réponse selon le profil, et journalise l'interaction.
    """
    
    processed_question = user_question.lower().strip()
    best_match_answer = None
    
    if not knowledge_base:
        bot_response = "La base de connaissances n'a pas pu être chargée. Veuillez contacter l'administrateur."
        log_interaction(user_question, bot_response, False, user_profile, username)
        return bot_response, False
        
    # Logique de Recherche Simple par Mot-Clé
    for entry in knowledge_base:
        search_text_entry = entry['search_text'] 
        
        # Correspondance exacte ou inclusion
        if processed_question == search_text_entry or processed_question in search_text_entry:
            best_match_answer = entry['answer']
            break
        
        # Correspondance inverse
        if search_text_entry in processed_question:
             best_match_answer = entry['answer']
             break

    # Génération de la Réponse et Adaptation (Exemple)
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