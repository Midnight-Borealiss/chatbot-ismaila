import torch
import streamlit as st
from sentence_transformers import SentenceTransformer, util

from config.settings import NLP_MODEL_NAME
from config.categories import normalize_category, CATEGORY_SYNONYMS


class NLPEngine:
    """
    Moteur sémantique souverain (RG-02).
    Chargé une seule fois via get_nlp_engine() + @st.cache_resource.
    """

    def __init__(self):
        self.model = SentenceTransformer(NLP_MODEL_NAME)

        # Phrases représentatives par catégorie pour la classification sémantique
        self._category_anchors: dict[str, list[str]] = {
            "MBA":           ["master of business administration", "frais MBA", "programme master management"],
            "Admission":     ["comment s'inscrire", "dossier d'admission", "concours d'entrée", "conditions d'admission"],
            "Bourses":       ["bourse d'études", "aide financière", "financement des études"],
            "Scolarité":     ["dates des examens", "emploi du temps", "relevé de notes", "calendrier scolaire"],
            "Cybersécurité": ["formation cybersécurité", "sécurité informatique", "réseau et systèmes"],
            "Licence_Pro":   ["licence professionnelle", "bts", "programme licence pro"],
            "Vie_Campus":    ["logement étudiant", "restaurant universitaire", "vie sur le campus"],
            "Général":       ["information générale", "question diverse"],
        }
        # Encodages des ancres (calculés une seule fois)
        self._anchor_embeddings: dict = {}
        self._anchor_labels: list[str] = []
        self._all_anchor_embs = None

    def _ensure_anchors_encoded(self):
        """Encode les ancres à la première utilisation (lazy init)."""
        if self._all_anchor_embs is not None:
            return
        phrases, labels = [], []
        for cat, anchors in self._category_anchors.items():
            for a in anchors:
                phrases.append(a)
                labels.append(cat)
        self._all_anchor_embs = self.model.encode(phrases, convert_to_tensor=True)
        self._anchor_labels   = labels

    # ------------------------------------------------------------------ #
    #  API publique                                                        #
    # ------------------------------------------------------------------ #

    def get_similarity_score(self, query: str, reference_texts: list) -> tuple:
        """
        Retourne (index_meilleure_réponse, score_cosinus).
        Score entre 0.0 et 1.0 — seuil RG-01 : 0.75.
        """
        if not reference_texts:
            return None, 0.0

        query_emb = self.model.encode(query, convert_to_tensor=True)
        ref_embs  = self.model.encode(reference_texts, convert_to_tensor=True)
        scores    = util.cos_sim(query_emb, ref_embs)[0]
        best_idx  = torch.argmax(scores).item()
        return best_idx, scores[best_idx].item()

    def classify_category(self, query: str) -> str:
        """
        Catégorise automatiquement une question par similarité sémantique.
        Combine : correspondance mot-clé (rapide) + similarité NLP (fallback).
        Retourne toujours une catégorie canonique normalisée.
        """
        # 1. Correspondance par mots-clés (fast path)
        q_lower = query.lower()
        for cat, synonyms in CATEGORY_SYNONYMS.items():
            if any(s in q_lower for s in synonyms):
                return normalize_category(cat)

        # 2. Fallback sémantique (NLP)
        self._ensure_anchors_encoded()
        query_emb = self.model.encode(query, convert_to_tensor=True)
        scores    = util.cos_sim(query_emb, self._all_anchor_embs)[0]
        best_idx  = torch.argmax(scores).item()
        best_score = scores[best_idx].item()

        if best_score >= 0.45:   # Seuil bas — on préfère Général si incertain
            return normalize_category(self._anchor_labels[best_idx])
        return "Général"

    def classify_intent(self, query: str) -> str:
        """Classifie l'intention : HOT | WARM | COLD (RG-05)."""
        hot_kw  = ["inscription", "frais", "bourse", "admission", "master", "mba", "coût", "prix", "tarif"]
        warm_kw = ["programme", "débouchés", "durée", "diplôme", "formation", "cursus"]
        q = query.lower()
        if any(k in q for k in hot_kw):
            return "HOT"
        if any(k in q for k in warm_kw):
            return "WARM"
        return "COLD"

    def get_nlp_precision(self, logs: list) -> float:
        """
        Calcule le taux de précision NLP = part des requêtes avec status SUCCÈS.
        """
        if not logs:
            return 0.0
        success = sum(1 for l in logs if l.get("status") == "SUCCÈS")
        return round(success / len(logs) * 100, 1)
from sentence_transformers import SentenceTransformer

class NLPEngine:
    def __init__(self):
        # Modèle multilingue léger (parfait pour le français et ton EliteBook)
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

    def get_embedding(self, text: str):
        """Transforme une question en vecteur numérique."""
        return self.model.encode(text).tolist()

nlp_engine = NLPEngine()

@st.cache_resource(show_spinner="Chargement du moteur NLP…")
def get_nlp_engine() -> NLPEngine:
    return NLPEngine()