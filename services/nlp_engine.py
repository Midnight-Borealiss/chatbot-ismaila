import torch
from sentence_transformers import SentenceTransformer, util

from config.settings import NLP_MODEL_NAME


class NLPEngine:
    """
    Moteur sémantique souverain (RG-02).
    Le modèle est chargé une seule fois en mémoire.
    Sur Streamlit Cloud, utiliser @st.cache_resource autour de l'instanciation.
    """

    def __init__(self):
        self.model = SentenceTransformer(NLP_MODEL_NAME)

    def get_similarity_score(self, query: str, reference_texts: list) -> tuple:
        """
        Retourne (index_meilleure_réponse, score_cosinus).
        Score entre 0.0 et 1.0 — seuil RG-01 : 0.75.
        """
        if not reference_texts:
            return None, 0.0

        query_emb = self.model.encode(query, convert_to_tensor=True)
        ref_embs  = self.model.encode(reference_texts, convert_to_tensor=True)

        scores   = util.cos_sim(query_emb, ref_embs)[0]
        best_idx = torch.argmax(scores).item()
        return best_idx, scores[best_idx].item()

    def classify_intent(self, query: str) -> str:
        """
        Classifie l'intention de la question (RG-05).
        Retourne : HOT | WARM | COLD
        """
        hot_keywords  = ["inscription", "frais", "bourse", "admission", "master", "mba", "coût", "prix", "tarif"]
        warm_keywords = ["programme", "débouchés", "durée", "diplôme", "formation", "cursus"]

        q_lower = query.lower()
        if any(k in q_lower for k in hot_keywords):
            return "HOT"
        if any(k in q_lower for k in warm_keywords):
            return "WARM"
        return "COLD"


nlp_engine = NLPEngine()