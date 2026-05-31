"""
NLPEngine — Moteur sémantique (Version Allégée MVP)
La recherche vectorielle (SentenceTransformer) a été retirée pour le déploiement Cloud.
La classification s'appuie désormais sur des heuristiques par mots-clés.
"""

from config.categories import normalize_category, CATEGORY_SYNONYMS

class NLPEngine:
    def __init__(self):
        # Plus de chargement de modèle lourd ici
        pass

    def classify_category_by_keywords(self, query: str) -> str:
        """Classifie la question par mots-clés (ancien fallback de ollama_service)."""
        q_lower = query.lower()
        for cat, synonyms in CATEGORY_SYNONYMS.items():
            if any(s in q_lower for s in synonyms):
                return normalize_category(cat)
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
        """Calcule le taux de précision."""
        if not logs:
            return 0.0
        success = sum(1 for l in logs if l.get("status") == "SUCCÈS")
        return round(success / len(logs) * 100, 1)

# Singleton allégé
nlp_engine = NLPEngine()