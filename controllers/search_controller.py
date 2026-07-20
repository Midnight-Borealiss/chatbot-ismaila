from datetime import datetime
import logging
import re

from services.db_connector import db_instance
from services.nlp_engine import nlp_engine
from services.mailer import send_new_question_alert
from config.settings import NLP_THRESHOLD, LEAD_HOT_THRESHOLD, VECTOR_INDEX_NAME
from config.categories import normalize_category, get_parent_category
from config.permissions import get_domain_level, is_expert_asking

logger = logging.getLogger(__name__)

class SearchController:
    """
    Moteur de recherche sémantique matriciel enrichi.
    Aiguillage intelligent : Institution × Service × Public.

    Recherche sémantique via Atlas Vector Search ($vectorSearch sur
    question_embedding). Repli gracieux sur une correspondance textuelle
    légère (chevauchement de tokens) si les embeddings ou l'index ne sont
    pas disponibles — l'application ne plante jamais.
    """

    def __init__(self):
        self.kb       = db_instance.get_collection("contributions")
        self.logs     = db_instance.get_collection("logs_interactions")
        self.users    = db_instance.get_collection("users")
        self.sessions = db_instance.get_collection("chat_sessions")

    def _calculate_text_similarity(self, query: str, texts: list) -> tuple:
        """Algorithme léger remplaçant les embeddings vectoriels pour le MVP."""
        def tokenize(text):
            return set(re.findall(r'\w+', text.lower()))
            
        q_tokens = tokenize(query)
        if not q_tokens:
            return 0, 0.0
            
        best_idx, best_score = 0, 0.0
        for idx, text in enumerate(texts):
            t_tokens = tokenize(text)
            if not t_tokens: continue
            
            # Calcul du chevauchement de mots
            intersection = len(q_tokens.intersection(t_tokens))
            score = intersection / len(q_tokens) 
            
            if score > best_score:
                best_score = score
                best_idx = idx
                
        return best_idx, best_score

    # ── Correspondance sémantique ────────────────────────────────────────────
    def _find_best_answer(self, user_query: str, query_filter: dict):
        """
        Retourne (doc, score, accepted).
        Tente d'abord Atlas Vector Search ; à défaut, repli sur le token-overlap.
        """
        doc, score = self._vector_search(user_query, query_filter)
        if doc is not None:
            # Score Atlas cosine normalisé dans [0,1] (1 = parfait)
            return doc, score, score >= NLP_THRESHOLD
        return self._token_match(user_query, query_filter)

    def _vector_search(self, user_query: str, query_filter: dict):
        """
        $vectorSearch Atlas sur question_embedding. Retourne (doc, score) ou
        (None, 0.0) si indisponible / aucun candidat.

        L'index (autoembed_index) ne déclare pas de champ de filtre : on
        récupère les meilleurs candidats puis on POST-FILTRE en Python
        (status + filtre matriciel quand les champs existent sur le document).
        """
        q_vec = nlp_engine.embed(user_query)
        if q_vec is None:
            return None, 0.0

        pipeline = [
            {"$vectorSearch": {
                "index":         VECTOR_INDEX_NAME,
                "path":          "question_embedding",
                "queryVector":   q_vec,
                "numCandidates": 150,
                "limit":         20,
            }},
            {"$addFields": {"vs_score": {"$meta": "vectorSearchScore"}}},
        ]
        try:
            results = list(self.kb.aggregate(pipeline))
        except Exception as e:
            logger.warning(f"Vector search indisponible — repli token : {e}")
            return None, 0.0

        for doc in results:
            if self._matches_filter(doc, query_filter):
                return doc, float(doc.get("vs_score", 0.0))
        return None, 0.0

    @staticmethod
    def _matches_filter(doc: dict, query_filter: dict) -> bool:
        """
        Applique le filtre matriciel côté Python. Un critère est ignoré si le
        document ne porte pas le champ (rétro-compatibilité : les docs actuels
        n'ont pas institution/service/public_target).
        """
        for field, cond in query_filter.items():
            if field not in doc:
                continue
            value = doc[field]
            if isinstance(cond, dict) and "$in" in cond:
                allowed = cond["$in"]
                if isinstance(value, list):
                    if not any(v in allowed for v in value):
                        return False
                elif value not in allowed:
                    return False
            elif value != cond:
                return False
        return True

    def _token_match(self, user_query: str, query_filter: dict):
        """Repli léger (chevauchement de tokens). Retourne (doc, score, accepted)."""
        validated_docs = list(self.kb.find(query_filter))
        if not validated_docs:
            validated_docs = list(self.kb.find({"status": "valide"}))
        if not validated_docs:
            return None, 0.0, False

        texts, mapping = [], []
        for doc in validated_docs:
            texts.append(doc["question"])
            mapping.append({"doc": doc, "type": "question"})
            for variant in doc.get("question_variants", []):
                texts.append(variant)
                mapping.append({"doc": doc, "type": "variant"})
            if doc.get("response"):
                texts.append(doc["response"])
                mapping.append({"doc": doc, "type": "response"})

        idx, raw_score = self._calculate_text_similarity(user_query, texts)
        meta = mapping[idx]
        score = raw_score * (0.85 if meta["type"] == "response" else 1.0)
        # Seuil abaissé : le token-overlap est moins généreux que le sémantique.
        accepted = score >= NLP_THRESHOLD * 0.7
        return meta["doc"], score, accepted

    def seek_answer(self, user_query: str, user_info: dict,
                    session_history: list = None) -> dict:
        session_history = session_history or []
        user_info = user_info or {}

        # ── 1. FILTRAGE MATRICIEL EN AMONT ──
        query_filter = {"status": "valide"}
        
        user_role = user_info.get("role")
        if user_role and user_role != "expert" and user_info.get("service") != "Direction":
            query_filter.update({
                "institution": {"$in": user_info.get("institutions", [])},
                "service": user_info.get("service"),
                "public_target": {"$in": user_info.get("public_target", [])}
            })

        # Classification à la source + score de confiance (Phase 3).
        clf = nlp_engine.assess_confidence(user_query)
        category = normalize_category(clf["category"])
        parent_category = clf.get("parent_category") or get_parent_category(category)

        # Base de connaissances vide → message dédié
        if self.kb.count_documents({"status": "valide"}) == 0:
            return self._build_result(
                "La base de connaissances est vide. Veuillez contacter un administrateur.",
                0.0, "VIDE", "COLD", False, category
            )

        # ── 2. CORRESPONDANCE SÉMANTIQUE (vector search + repli token) ──
        matched_doc, score, accepted = self._find_best_answer(user_query, query_filter)

        # ── 3. DÉCISION ET TRAITEMENT DU FLUX ──
        if accepted and matched_doc is not None:
            response = matched_doc.get("response", "")
            status = "SUCCÈS"
        else:
            if is_expert_asking(user_info, category):
                response, status = self._handle_expert_question(user_query, user_info, category, parent_category, clf)
            else:
                pending_duplicates = list(self.kb.find({"status": "en_attente"}))
                merged_id = None
                
                if pending_duplicates:
                    pending_questions = [p["question"] for p in pending_duplicates]
                    p_idx, p_score = self._calculate_text_similarity(user_query, pending_questions)
                    
                    if p_score >= 0.80: # Seuil ajusté pour la fusion
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
                    response = ("Je n'ai pas encore de réponse certifiée à cette question. "
                                "Elle a été transmise à nos experts qui vous répondront sous 48h.")
                    status = "ATTENTE"
                    ticket = self._create_ticket(user_query, user_info, category, parent_category, clf)
                    self._alert_experts_by_topic(user_query, category, user_info, ticket)

        # ── 4. CAPTURE DE LEAD, LOGS ET PERSISTANCE ──
        intent = nlp_engine.classify_intent(user_query)
        hot_count = sum(1 for h in session_history if h.get("intent") == "HOT")
        trigger_capture = (
            (hot_count + (1 if intent == "HOT" else 0)) >= LEAD_HOT_THRESHOLD
            and not user_info.get("role")
        )

        self._log_query(user_query, response, score, status, intent, category, user_info)
        self._persist_exchange(user_info, user_query, response, score, intent, category)

        return self._build_result(response, score, status, intent, trigger_capture, category)

    def _handle_expert_question(self, query: str, user: dict, category: str,
                                parent_category: str = "", clf: dict = None) -> tuple:
        clf = clf or {}
        self.kb.insert_one({
            "question":         query,
            "response":         "",
            "status":           "en_attente",
            "category":         category,
            "parent_category":  parent_category,
            "ai_confidence":    clf.get("confidence", 0.0),
            "ai_source":        clf.get("source", ""),
            "needs_review":     clf.get("needs_review", False),
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

    def _create_ticket(self, query: str, user: dict, category: str = "",
                       parent_category: str = "", clf: dict = None) -> dict:
        clf = clf or {}
        doc = {
            "question":   query,
            "response":   "",
            "status":     "en_attente",
            "category":   category,
            "parent_category": parent_category,
            "ai_confidence":   clf.get("confidence", 0.0),
            "ai_source":       clf.get("source", ""),
            "needs_review":    clf.get("needs_review", False),
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
            experts = list(self.users.find({
                "role": {"$in": ["VALIDATEUR", "expert"]},
                "service": ticket.get("service")
            }))
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