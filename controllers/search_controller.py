from datetime import datetime
import re

from services.db_connector import db_instance
from services.nlp_engine import get_nlp_engine
from services.mailer import send_new_question_alert
from config.settings import NLP_THRESHOLD, LEAD_HOT_THRESHOLD
from config.categories import normalize_category
from config.permissions import get_domain_level, is_expert_asking


class SearchController:
    """
    Moteur de recherche sémantique matriciel enrichi (Phase 3).
    Aiguillage intelligent : Institution × Service × Public.
    Indexation croisée pondérée (Questions + Variantes + Réponses).
    Fusion automatique des requêtes redondantes en attente.
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
        user_info = user_info or {}

        # ── 1. FILTRAGE MATRICIEL EN AMONT (Sécurité & Cloisonnement) ──
        query_filter = {"status": "valide"}
        
        # Si c'est un utilisateur connecté non-expert, on restreint à sa matrice métier
        user_role = user_info.get("role")
        if user_role and user_role != "expert" and user_info.get("service") != "Direction":
            query_filter.update({
                "institution": {"$in": user_info.get("institutions", [])},
                "service": user_info.get("service"),
                "public_target": {"$in": user_info.get("public_target", [])}
            })

        validated_docs = list(self.kb.find(query_filter))
        category = normalize_category(nlp.classify_category(user_query))

        if not validated_docs:
            # Si le périmètre filtré est vide, on tente une recherche de secours globale
            validated_docs = list(self.kb.find({"status": "valide"}))

        # ── 2. INDEXATION CROISÉE ET CORRESPONDANCE PONDÉRÉE (Niveau 2) ──
        if validated_docs:
            texts_to_embed = []
            doc_mapping = []

            for doc in validated_docs:
                # Question principale (Poids Fort)
                texts_to_embed.append(doc["question"])
                doc_mapping.append({"doc": doc, "type": "question"})
                
                # Variantes sémantiques générées (Poids Fort)
                for variant in doc.get("question_variants", []):
                    texts_to_embed.append(variant)
                    doc_mapping.append({"doc": doc, "type": "variant"})
                    
                # Contenu de la réponse (Poids Modéré)
                if doc.get("response"):
                    texts_to_embed.append(doc["response"])
                    doc_mapping.append({"doc": doc, "type": "response"})

            # Calcul de similarité sur le super-tableau aplati
            idx, raw_score = nlp.get_similarity_score(user_query, texts_to_embed)
            
            # Ajustement du score selon la nature de la correspondance
            match_meta = doc_mapping[idx]
            matched_doc = match_meta["doc"]
            
            if match_meta["type"] == "response":
                score = raw_score * 0.85  # Pénalisation par précaution sur la réponse brute
            else:
                score = raw_score * 1.0
        else:
            score = 0.0

        # ── 3. DÉCISION ET TRAITEMENT DU FLUX ──
        if score >= NLP_THRESHOLD and validated_docs:
            response = matched_doc["response"]
            status = "SUCCÈS"
        else:
            # Échec sémantique → Gestion des nouvelles demandes ou suggestions
            if is_expert_asking(user_info, category):
                response, status = self._handle_expert_question(user_query, user_info, category)
            else:
                # RECHERCHE DE DOUBLON EN ATTENTE (Fusion automatique > 90%)
                pending_duplicates = list(self.kb.find({"status": "en_attente"}))
                merged_id = None
                
                if pending_duplicates:
                    pending_questions = [p["question"] for p in pending_duplicates]
                    p_idx, p_score = nlp.get_similarity_score(user_query, pending_questions)
                    
                    if p_score >= 0.90:
                        merged_id = pending_duplicates[p_idx]["_id"]
                        self.kb.update_one(
                            {"_id": merged_id},
                            {
                                "$push": {"merged_queries": user_query},
                                "$inc": {"occurrence_count": 1},
                                "$set": {"last_occurrence": datetime.now()}
                            }
                        )

                if merged_id:
                    response = ("Une question similaire est actuellement en cours de traitement par nos services. "
                                "Votre demande a été regroupée avec cette dernière pour accélérer sa validation.")
                    status = "FUSION_DOUBLON"
                else:
                    # Création d'un nouveau ticket classique si aucun doublon en attente n'est détecté
                    response = ("Je n'ai pas encore de réponse certifiée à cette question. "
                                "Elle a été transmise à nos experts qui vous répondront sous 48h.")
                    status = "ATTENTE"
                    ticket = self._create_ticket(user_query, user_info, category)
                    self._alert_experts_by_topic(user_query, category, user_info, ticket)

        # ── 4. CAPTURE DE LEAD, LOGS ET PERSISTANCE ──
        intent = nlp.classify_intent(user_query)
        hot_count = sum(1 for h in session_history if h.get("intent") == "HOT")
        trigger_capture = (
            (hot_count + (1 if intent == "HOT" else 0)) >= LEAD_HOT_THRESHOLD
            and not user_info.get("role")
        )

        self._log_query(user_query, response, score, status, intent, category, user_info)
        self._persist_exchange(user_info, user_query, response, score, intent, category)

        return self._build_result(response, score, status, intent, trigger_capture, category)

    # ------------------------------------------------------------------ #
    #  Gestion spéciale : expert posant une question dans son domaine     #
    # ------------------------------------------------------------------ #

    def _handle_expert_question(self, query: str, user: dict, category: str) -> tuple:
        self.kb.insert_one({
            "question":      query,
            "response":      "En attente",
            "status":        "en_attente",
            "category":      category,
            "institution":   user.get("institutions", ["Général"])[0] if user.get("institutions") else "Général",
            "service":       user.get("service", "Scolarité"),
            "public_target": user.get("public_target", ["Étudiants"]),
            "user_email":    user.get("email", "anonyme"),
            "source":        "expert_suggestion",
            "occurrence_count": 1,
            "created_at":    datetime.now(),
        })
        response = (
            "Merci pour votre question ! En tant qu'expert de ce domaine, "
            "votre question a été enregistrée comme suggestion d'enrichissement "
            "de la base de connaissances. Elle sera examinée et pourra être "
            "ajoutée si elle apporte de la valeur."
        )
        return response, "SUGGESTION_EXPERT"

    # ------------------------------------------------------------------ #
    #  Historique persistant                                             #
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
    #  Méthodes privées                                                  #
    # ------------------------------------------------------------------ #

    def _create_ticket(self, query: str, user: dict, category: str = "Général") -> dict:
        doc = {
            "question":   query,
            "response":   "En attente",
            "status":     "en_attente",
            "category":   category,
            "institution": user.get("institutions", ["Général"])[0] if isinstance(user, dict) and user.get("institutions") else "Général",
            "service":     user.get("service", "Scolarité") if isinstance(user, dict) else "Scolarité",
            "public_target": user.get("public_target", ["Étudiants"]) if isinstance(user, dict) else ["Étudiants"],
            "user_email": user.get("email", "anonyme") if isinstance(user, dict) else "anonyme",
            "source":     "user_question",
            "occurrence_count": 1,
            "merged_queries": [],
            "created_at": datetime.now(),
        }
        result = self.kb.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def _alert_experts_by_topic(self, query: str, category: str, user: dict, ticket: dict):
        asked_by = user.get("email", "un utilisateur") if isinstance(user, dict) else "un utilisateur"
        try:
            # Recherche mise à jour selon la matrice de permissions Phase 3
            experts = list(self.users.find({
                "role": {"$in": ["VALIDATEUR", "expert"]},
                "service": ticket.get("service")
            }))
            
            # Fallback thématique historique
            if not experts:
                experts = list(self.users.find({
                    "role": {"$in": ["VALIDATEUR", "ADMINISTRATION"]},
                    "expert_topics": category,
                }))
            
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