"""
╔══════════════════════════════════════════════════════════════════════╗
║           LLM ENGINE — EN VEILLE (Phase 2)                          ║
║                                                                      ║
║  Ce module est réservé à la Phase 2 d'ISMaiLa : le passage en mode  ║
║  RAG (Retrieval-Augmented Generation) avec un LLM souverain local.  ║
║                                                                      ║
║  En Phase 1, le moteur sémantique (nlp_engine.py) suffit :          ║
║  il cherche la meilleure réponse CERTIFIÉE dans MongoDB.            ║
║  Aucun LLM génératif n'est nécessaire ni importé pour l'instant.    ║
╚══════════════════════════════════════════════════════════════════════╝

ARCHITECTURE CIBLE (Phase 2 — RAG Souverain)
─────────────────────────────────────────────
Question utilisateur
        │
        ▼
[nlp_engine] → Retrieval : trouve les 3 meilleurs contextes dans MongoDB
        │
        ▼
[llm_engine] → Generation : rédige une réponse fluide basée sur ces contextes
        │
        ▼
Réponse naturelle et certifiée

OPTIONS LLM SOUVERAINES & GRATUITES ÉVALUÉES
──────────────────────────────────────────────
1. Ollama (local)
   - Modèles : mistral, llama3, gemma2
   - Installation : https://ollama.com
   - Avantage : 100% local, zéro coût, zéro fuite de données
   - Commande : ollama pull mistral

2. Groq API (cloud gratuit)
   - Modèles : llama3-8b-8192, mixtral-8x7b
   - Free tier généreux (6000 req/min)
   - Avantage : rapide, gratuit pour prototype
   - URL : https://console.groq.com

3. Hugging Face Inference API (gratuit)
   - Modèles : HuggingFaceH4/zephyr-7b-beta
   - Free tier limité mais suffisant pour MVP
   - URL : https://huggingface.co/inference-api

TODO — À IMPLÉMENTER EN PHASE 2
─────────────────────────────────
[ ] Choisir et installer un LLM souverain (recommandé : Ollama + Mistral)
[ ] Implémenter LLMService.generate(prompt) ci-dessous
[ ] Connecter search_controller.find_context() au retrieval
[ ] Tester la qualité des réponses vs Phase 1 (réponses certifiées)
[ ] Ajouter un garde-fou : si le LLM hallucine, fallback sur réponse certifiée
"""

"""
LLM ENGINE — ACTIVE (Phase 1.5 - MVP)
Pipeline RAG : Retrieval (via mots-clés MongoDB) -> Generation (via API Mistral)
"""

from services.llm_service import llm_service
# Remplace search_controller par l'import de ta fonction de recherche textuelle MongoDB existante

def get_rag_response(query: str, context_docs: list) -> str:
    """
    Construit le prompt avec le contexte ISM et interroge le LLM.
    """
    if not context_docs:
        return "Je ne trouve pas d'information exacte dans mes archives. Je vous invite à ouvrir un ticket pour qu'un expert vous réponde."

    # On fusionne les réponses validées trouvées dans la base
    context_text = "\n".join([f"- {doc.get('response', '')}" for doc in context_docs])

    prompt = f"""<s>[INST] Tu es ISMaiLa, l'assistant virtuel officiel.
Réponds de façon claire et bienveillante à la question de l'étudiant, en utilisant UNIQUEMENT les faits issus des archives ci-dessous. 
Ne propose pas d'étapes qui ne sont pas dans les archives.

ARCHIVES DE L'INSTITUT :
{context_text}

QUESTION DE L'ÉTUDIANT :
{query} [/INST]"""

    llm_result = llm_service.generate_response(prompt)
    
    return llm_result["text"]