from datetime import datetime

from services.db_connector import db_instance
from services.nlp_engine import get_nlp_engine
from services.mailer import send_new_question_alert
from config.settings import NLP_THRESHOLD, LEAD_HOT_THRESHOLD
from config.categories import normalize_category
from config.permissions import get_domain_level, is_expert_asking


class SearchController:
    """
    Moteur de recherche sémantique.
    RG-01 | RG-03 (alerte expert ciblée) | RG-05 (scoring intent).
    Permissions granulaires par domaine : les experts ont un traitement
    spécial quand ils posent des questions dans leur propre domaine.
    """

    def __init__(self):
        self.kb       = db_instance.get_collection("contributions")
        self.logs     = db_instance.get_collection("logs_interactions")
        self.users    = db_instance.get_collection("users")
        self.sessions = db_instance.get_collection("chat_sessions")

    def seek_answer(self, user_query: str, user_info: dict,
                    session_history: list = None) -> dict:
        session_history = session_history or []
        nlp = get_nlp_engine()

        validated_docs = list(self.kb.find({"status": "valide"}))
        if not validated_docs:
            return self._build_result(
                "Désolé, ma base de connaissances est vide pour le moment.",
                0.0, "VIDE", "COLD", False, "Général"
            )

        questions  = [d["question"] for d in validated_docs]
        idx, score = nlp.get_similarity_score(user_query, questions)
        category   = normalize_category(nlp.classify_category(user_query))

        if score >= NLP_THRESHOLD:
            response = validated_docs[idx]["response"]
            status   = "SUCCÈS"
        else:
            # ── Traitement différencié selon le profil de l'utilisateur ──
            if is_expert_asking(user_info, category):
                # Expert posant une question dans son propre domaine
                # → suggestion d'enrichissement, pas d'alerte externe
                response, status = self._handle_expert_question(
                    user_query, user_info, category
                )
            else:
                # Étudiant / learner / contributeur hors domaine → flux normal
                response = (
                    "Je n'ai pas encore de réponse certifiée à cette question. "
                    "Elle a été transmise à nos experts qui vous répondront sous 48h."
                )
                status = "ATTENTE"
                ticket = self._create_ticket(user_query, user_info, category)
                self._alert_experts_by_topic(user_query, category, user_info, ticket)

        intent          = nlp.classify_intent(user_query)
        hot_count       = sum(1 for h in session_history if h.get("intent") == "HOT")
        trigger_capture = (
            (hot_count + (1 if intent == "HOT" else 0)) >= LEAD_HOT_THRESHOLD
            and not user_info.get("role")  # Pas de capture pour les connectés
        )

        self._log_query(user_query, response, score, status, intent, category, user_info)
        self._persist_exchange(user_info, user_query, response, score, intent, category)

        return self._build_result(response, score, status, intent, trigger_capture, category)

    # ------------------------------------------------------------------ #
    #  Gestion spéciale : expert posant une question dans son domaine     #
    # ------------------------------------------------------------------ #

    def _handle_expert_question(self, query: str, user: dict, category: str) -> tuple:
        """
        Un expert pose une question dans son propre domaine.
        → Crée un ticket 'expert_suggestion' visible uniquement dans
          le dashboard admin (pas d'alerte email envoyée).
        → Répond à l'expert qu'on a enregistré sa suggestion.
        """
        self.kb.insert_one({
            "question":    query,
            "response":    "En attente",
            "status":      "en_attente",
            "category":    category,
            "user_email":  user.get("email", "anonyme"),
            "source":      "expert_suggestion",   # Marqueur spécial
            "created_at":  datetime.now(),
        })
        response = (
            "Merci pour votre question ! En tant qu'expert de ce domaine, "
            "votre question a été enregistrée comme suggestion d'enrichissement "
            "de la base de connaissances. Elle sera examinée et pourra être "
            "ajoutée si elle apporte de la valeur."
        )
        return response, "SUGGESTION_EXPERT"

    # ------------------------------------------------------------------ #
    #  Historique persistant                                               #
    # ------------------------------------------------------------------ #

    def get_session_history(self, user_email: str, limit: int = 50) -> list:
        if not user_email or user_email in ("anonyme", "public"):
            return []
        session = self.sessions.find_one({"user_email": user_email})
        if not session:
            return []
        return session.get("exchanges", [])[-limit:]

    def _persist_exchange(self, user: dict, question: str, response: str,
                          score: float, intent: str, category: str):
        email = user.get("email", "anonyme") if isinstance(user, dict) else "anonyme"
        if email in ("anonyme", "public", ""):
            return
        self.sessions.update_one(
            {"user_email": email},
            {
                "$push":        {"exchanges": {
                    "question":  question,
                    "response":  response,
                    "score":     round(float(score), 3),
                    "intent":    intent,
                    "category":  category,
                    "timestamp": datetime.now(),
                }},
                "$set":         {"last_activity": datetime.now()},
                "$setOnInsert": {"user_email": email, "created_at": datetime.now()},
            },
            upsert=True,
        )

    def clear_session_history(self, user_email: str):
        self.sessions.update_one(
            {"user_email": user_email},
            {"$set": {"exchanges": []}}
        )

    # ------------------------------------------------------------------ #
    #  Méthodes privées                                                    #
    # ------------------------------------------------------------------ #

    def _create_ticket(self, query: str, user: dict, category: str = "Général") -> dict:
        doc = {
            "question":   query,
            "response":   "En attente",
            "status":     "en_attente",
            "category":   category,
            "user_email": user.get("email", "anonyme") if isinstance(user, dict) else "anonyme",
            "source":     "user_question",
            "created_at": datetime.now(),
        }
        result = self.kb.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def _alert_experts_by_topic(self, query: str, category: str,
                                 user: dict, ticket: dict):
        asked_by = user.get("email", "un utilisateur") if isinstance(user, dict) else "un utilisateur"
        try:
            experts = list(self.users.find({
                "role":               {"$in": ["VALIDATEUR", "ADMINISTRATION"]},
                "domain_permissions." + category: {"$in": ["expert"]},
            }))
            # Fallback legacy : chercher dans expert_topics
            if not experts:
                experts = list(self.users.find({
                    "role":          {"$in": ["VALIDATEUR", "ADMINISTRATION"]},
                    "expert_topics": category,
                }))
            # Fallback total : tous les validateurs
            if not experts:
                experts = list(self.users.find({"role": "VALIDATEUR"}))

            for expert in experts:
                send_new_question_alert(expert["email"], query, category, asked_by)
        except Exception as e:
            print(f"⚠️ Alerte expert non envoyée : {e}")

    def _log_query(self, q, r, sc, st_val, intent, category, u):
        try:
            self.logs.insert_one({
                "timestamp": datetime.now(),
                "query":     str(q)[:500],
                "response":  str(r)[:200],
                "score":     float(sc),
                "status":    st_val,
                "intent":    intent,
                "category":  category,
                "user":      u.get("email", "anonyme") if isinstance(u, dict) else "anonyme",
            })
        except Exception as e:
            print(f"⚠️ Log non enregistré : {e}")

    @staticmethod
    def _build_result(response, score, status, intent, trigger_capture, category) -> dict:
        return {
            "response":        response,
            "score":           score,
            "status":          status,
            "intent":          intent,
            "trigger_capture": trigger_capture,
            "category":        category,
        }


search_controller = SearchController()