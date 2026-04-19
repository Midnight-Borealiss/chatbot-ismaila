from datetime import datetime

from services.db_connector import db_instance
from services.nlp_engine import nlp_engine
from services.mailer import send_expert_alert
from config.settings import NLP_THRESHOLD, LEAD_HOT_THRESHOLD


class SearchController:
    """
    Moteur de recherche sémantique.
    Gère : RG-01 (seuil NLP), RG-03 (alerte expert), RG-05 (scoring intent).
    """

    def __init__(self):
        self.kb   = db_instance.get_collection("contributions")
        self.logs = db_instance.get_collection("logs_interactions")

    def seek_answer(self, user_query: str, user_info: dict, session_history: list = None) -> dict:
        """
        Cherche une réponse certifiée et retourne un dict enrichi :
        {response, score, status, intent, trigger_capture}
        """
        session_history = session_history or []

        # 1. Récupération des connaissances validées uniquement
        validated_docs = list(self.kb.find({"status": "valide"}))

        if not validated_docs:
            return self._build_result(
                "Désolé, ma base de connaissances est vide pour le moment.",
                0.0, "VIDE", "COLD", False
            )

        questions      = [d["question"] for d in validated_docs]
        idx, score     = nlp_engine.get_similarity_score(user_query, questions)

        # 2. Décision RG-01
        if score >= NLP_THRESHOLD:
            response = validated_docs[idx]["response"]
            status   = "SUCCÈS"
        else:
            response = (
                "Je n'ai pas encore de réponse certifiée à cette question. "
                "Elle a été transmise à nos experts qui vous répondront sous 48h."
            )
            status = "ATTENTE"
            self._create_ticket(user_query, user_info)
            self._alert_experts(user_query, user_info)

        # 3. Scoring d'intention (RG-05)
        intent          = nlp_engine.classify_intent(user_query)
        hot_count       = sum(1 for h in session_history if h.get("intent") == "HOT")
        trigger_capture = (hot_count + (1 if intent == "HOT" else 0)) >= LEAD_HOT_THRESHOLD

        # 4. Traçabilité
        self._log_query(user_query, response, score, status, intent, user_info)

        return self._build_result(response, score, status, intent, trigger_capture)

    # ------------------------------------------------------------------ #
    #  Méthodes privées                                                    #
    # ------------------------------------------------------------------ #

    def _create_ticket(self, query: str, user: dict):
        self.kb.insert_one({
            "question":   query,
            "response":   "En attente",
            "status":     "en_attente",
            "user_email": user.get("email", "anonyme"),
            "created_at": datetime.now(),
        })

    def _alert_experts(self, query: str, user: dict):
        """Envoie une alerte mail aux experts si SMTP configuré (RG-03)."""
        try:
            experts = db_instance.get_collection("users").find(
                {"role": "VALIDATEUR"}
            )
            for expert in experts:
                send_expert_alert(expert["email"], query)
        except Exception as e:
            print(f"Alerte expert non envoyée : {e}")

    def _log_query(self, q, r, sc, st_val, intent, u):
        self.logs.insert_one({
            "timestamp": datetime.now(),
            "query":     q,
            "response":  r[:200],
            "score":     sc,
            "status":    st_val,
            "intent":    intent,
            "user":      u.get("email", "anonyme"),
        })

    @staticmethod
    def _build_result(response, score, status, intent, trigger_capture) -> dict:
        return {
            "response":        response,
            "score":           score,
            "status":          status,
            "intent":          intent,
            "trigger_capture": trigger_capture,
        }


search_controller = SearchController()