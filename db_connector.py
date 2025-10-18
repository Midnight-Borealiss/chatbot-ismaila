# db_connector.py

import json
import os 

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
        return []
    except Exception:
        return []

load_knowledge_base_from_json()