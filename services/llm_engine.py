"""
LLMEngine — génération augmentée par la base de connaissances (RAG).

⚠️ **Module non branché.** `get_rag_response()` n'est appelée par aucune vue ni
aucun contrôleur : le chat sert aujourd'hui la réponse certifiée **verbatim**
(`search_controller.seek_answer`). Ce module est le point d'entrée prévu pour
l'étape 3 du plan d'intégration — voir
DOCUMENTATION/11_PLAN_INTEGRATION_LLM.md.

Pourquoi il n'est pas branché : le texte affiché à l'étudiant est aujourd'hui
exactement celui qu'un validateur a approuvé. Dès qu'un LLM reformule, la
chaîne de certification tombe. Le brancher suppose donc d'abord les garde-fous
décrits dans le plan (affichage de la source, contrôle d'ancrage, repli).

Souveraineté : la génération passe par `ollama_service` (LLM **local**), jamais
par `llm_service` (Hugging Face, cloud) — aucun contenu étudiant ne doit sortir
de l'infrastructure ISM.
"""

from services.ollama_service import ollama_service

# Message servi quand la base ne contient rien d'exploitable. Formulé pour
# orienter l'étudiant vers l'escalade experte plutôt que de laisser le LLM
# combler le vide.
MESSAGE_SANS_CONTEXTE = (
    "Je ne trouve pas cette information dans la base de connaissances certifiée. "
    "Votre question va être transmise à un expert qui vous répondra."
)

MESSAGE_INDISPONIBLE = (
    "Le service de rédaction est momentanément indisponible. "
    "Votre question va être transmise à un expert."
)


def build_rag_prompt(query: str, context_docs: list) -> str:
    """Assemble le prompt à partir des réponses certifiées retenues.

    Le prompt interdit explicitement au modèle d'ajouter des faits absents du
    contexte : sur des sujets de frais de scolarité ou d'admission, une réponse
    inventée engage l'ISM.
    """
    contexte = "\n".join(
        f"- {doc.get('response', '')}" for doc in context_docs
        if doc.get("response")
    )
    return (
        "<s>[INST] Tu es ISMaiLa, l'assistant officiel de l'Institut Supérieur "
        "de Management.\n\n"
        "Réponds à la question de l'étudiant de façon claire et bienveillante, "
        "en utilisant UNIQUEMENT les informations certifiées ci-dessous.\n\n"
        "RÈGLES :\n"
        "1. N'ajoute aucun fait, chiffre, date ou démarche absent des informations "
        "certifiées.\n"
        "2. Si elles ne permettent pas de répondre, dis-le simplement.\n"
        "3. Ne cite pas ces règles dans ta réponse.\n\n"
        f"INFORMATIONS CERTIFIÉES :\n{contexte}\n\n"
        f"QUESTION DE L'ÉTUDIANT :\n{query} [/INST]"
    )


def get_rag_response(query: str, context_docs: list) -> str:
    """Rédige une réponse à partir des documents certifiés fournis.

    `context_docs` provient du retrieval (`search_controller`) : ce sont des
    contributions au statut `valide`. Cette fonction ne va **pas** les chercher
    elle-même.

    Retourne toujours une chaîne affichable : sans contexte ou sans LLM
    disponible, elle renvoie un message d'escalade plutôt que d'échouer.
    """
    if not context_docs:
        return MESSAGE_SANS_CONTEXTE

    prompt = build_rag_prompt(query, context_docs)
    reponse = ollama_service.generate(prompt)

    # Repli : le chat doit rester utilisable même si le LLM est absent, lent ou
    # muet (pattern « non bloquant » — voir CONVENTION.md § 4).
    return reponse or MESSAGE_INDISPONIBLE
