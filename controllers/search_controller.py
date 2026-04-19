from datetime import datetime

from services.db_connector import db_instance
from services.nlp_engine import nlp_engine
from services.mailer import send_new_question_alert
from config.settings import NLP_THRESHOLD, LEAD_HOT_THRESHOLD


class SearchController:
    """
    Moteur de recherche sémantique.
    RG-01 : seuil NLP | RG-03 : alerte expert ciblée par topic | RG-05 : scoring intent.
    """

    def __init__(self):
        self.kb    = db_instance.get_collection("contributions")
        self.logs  = db_instance.get_collection("logs_interactions")
        self.users = db_instance.get_collection("users")

    def seek_answer(self, user_query: str, user_info: dict, session_history: list = None) -> dict:
        session_history = session_history or []

        validated_docs = list(self.kb.find({"status": "valide"}))
        if not validated_docs:
            return self._build_result(
                "Désolé, ma base de connaissances est vide pour le moment.",
                0.0, "VIDE", "COLD", False
            )

        questions  = [d["question"] for d in validated_docs]
        idx, score = nlp_engine.get_similarity_score(user_query, questions)

        if score >= NLP_THRESHOLD:
            response = validated_docs[idx]["response"]
            status   = "SUCCÈS"
        else:
            response = (
                "Je n'ai pas encore de réponse certifiée à cette question. "
                "Elle a été transmise à nos experts qui vous répondront sous 48h."
            )
            status = "ATTENTE"
            # Détection de catégorie pour le ciblage RG-03
            intent   = nlp_engine.classify_intent(user_query)
            category = self._intent_to_category(intent, user_query)
            ticket   = self._create_ticket(user_query, user_info, category)
            self._alert_experts_by_topic(user_query, category, user_info, ticket)

        intent          = nlp_engine.classify_intent(user_query)
        hot_count       = sum(1 for h in session_history if h.get("intent") == "HOT")
        trigger_capture = (hot_count + (1 if intent == "HOT" else 0)) >= LEAD_HOT_THRESHOLD

        self._log_query(user_query, response, score, status, intent, user_info)
        return self._build_result(response, score, status, intent, trigger_capture)

    # ------------------------------------------------------------------ #
    #  Méthodes privées                                                    #
    # ------------------------------------------------------------------ #

    def _create_ticket(self, query: str, user: dict, category: str = "Général") -> dict:
        doc = {
            "question":   query,
            "response":   "En attente",
            "status":     "en_attente",
            "category":   category,
            "user_email": user.get("email", "anonyme"),
            "created_at": datetime.now(),
        }
        result = self.kb.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def _alert_experts_by_topic(self, query: str, category: str, user: dict, ticket: dict):
        """
        RG-03 ciblé : n'alerte que les experts dont expert_topics contient la catégorie.
        Fallback sur tous les validateurs si aucun expert ciblé trouvé.
        """
        asked_by = user.get("email", "un utilisateur")
        try:
            # Ciblage précis
            experts = list(self.users.find({
                "role":          {"$in": ["VALIDATEUR", "ADMINISTRATION"]},
                "expert_topics": category,
            }))
            # Fallback
            if not experts:
                experts = list(self.users.find({"role": "VALIDATEUR"}))

            for expert in experts:
                send_new_question_alert(expert["email"], query, category, asked_by)
        except Exception as e:
            print(f"⚠️ Alerte expert non envoyée : {e}")

    def _intent_to_category(self, intent: str, query: str) -> str:
        """Déduit la catégorie KB depuis l'intention NLP et les mots-clés."""
        q = query.lower()
        if any(k in q for k in ["mba", "master", "management"]):
            return "MBA"
        if any(k in q for k in ["bourse", "financement", "aide"]):
            return "Bourses"
        if any(k in q for k in ["admission", "inscription", "dossier"]):
            return "Admission"
        if any(k in q for k in ["cyber", "sécurité", "réseau"]):
            return "Cybersécurité"
        if any(k in q for k in ["licence", "pro", "bts"]):
            return "Licence_Pro"
        return "Général"

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