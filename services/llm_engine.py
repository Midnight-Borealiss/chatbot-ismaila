# Exemple de ce que deviendra ton controller en mode RAG
def get_rag_response(query):
    # 1. RETRIEVAL : On cherche les infos dans MongoDB (ce que tu fais déjà)
    context = search_controller.find_context(query)
    
    # 2. GENERATION : On demande à l'IA de rédiger
    prompt = f"Basé sur ce contexte : {context}, réponds à la question : {query}"
    response = llm_service.generate(prompt)
    
    return response