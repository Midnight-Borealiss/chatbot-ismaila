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

# ══════════════════════════════════════════════════════════════════════
#  CODE EN VEILLE — NE PAS IMPORTER AVANT LA PHASE 2
# ══════════════════════════════════════════════════════════════════════

# from controllers.search_controller import search_controller  # À décommenter Phase 2
# from services.llm_service import llm_service                 # À créer Phase 2


def get_rag_response(query: str) -> str:
    """
    [EN VEILLE — PHASE 2]

    Pipeline RAG complet :
    1. Retrieval  → Cherche les contextes certifiés dans MongoDB
    2. Generation → Demande au LLM de rédiger une réponse fluide

    Raises:
        NotImplementedError: Tant que la Phase 2 n'est pas déployée
    """
    raise NotImplementedError(
        "LLM Engine en veille — Phase 2 non démarrée. "
        "Utiliser search_controller.seek_answer() en Phase 1."
    )

    # ── Code prévu pour la Phase 2 (décommenter le moment venu) ──────
    #
    # context_docs = search_controller.find_context(query, top_k=3)
    # context_text = "\n".join([doc["response"] for doc in context_docs])
    #
    # prompt = (
    #     "Tu es l'assistant virtuel de l'ISM.\n"
    #     "Réponds UNIQUEMENT en te basant sur le contexte certifié ci-dessous.\n"
    #     "Si le contexte ne contient pas la réponse, dis-le clairement.\n\n"
    #     f"CONTEXTE CERTIFIÉ :\n{context_text}\n\n"
    #     f"QUESTION : {query}\n\n"
    #     "RÉPONSE :"
    # )
    #
    # return llm_service.generate(prompt)