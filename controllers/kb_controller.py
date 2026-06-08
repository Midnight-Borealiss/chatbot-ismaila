from datetime import datetime

from bson import ObjectId

from services.db_connector import db_instance
from services.mailer import send_answer_to_student
from typing import Optional
from config.categories import normalize_category, get_all_canonical


class KBController:
    """
    Gestion de la base de connaissances.
    Nouveautés : recatégorisation (point 6), normalisation des catégories (point 8).
    """

    @staticmethod
    def is_empty_or_pending(response: Optional[str]) -> bool:
        """Retourne True si la réponse est vide ou contient un placeholder d'attente.
        Le placeholder actuel est « En attente de réponse admin… ». Tous les textes
        commençant par « En attente » sont considérés comme aucune réponse valable.
        """
        if not response:
            return True
        r = response.strip()
        return not r or r.startswith("En attente")

    def __init__(self):
        self.col = db_instance.get_collection("contributions")

    def clear_placeholder_responses(self) -> int:
        """Supprime le texte placeholder « En attente de réponse admin… » des documents.
        Pour chaque contribution dont la réponse commence par ce texte, on vide la
        réponse et on remet le statut à "en_attente". La fonction retourne le nombre
        de documents modifiés.
        """
        placeholder_prefix = "En attente de réponse admin"
        query = {"response": {"$regex": f"^{placeholder_prefix}"}}
        update = {"$set": {"response": "", "status": "en_attente"}}
        result = self.col.update_many(query, update)
        return result.modified_count

    def get_pending(self) -> list:
        return list(self.col.find({"status": "en_attente"}).sort("created_at", -1))

    def get_validated(self) -> list:
        return list(self.col.find({"status": "valide"}).sort("updated_at", -1))

    def _ensure_question_embedding(self, c_id: str, question: str):
        """
        Génère et stocke l'embedding de la question pour la recherche vectorielle.
        Non bloquant : une erreur (modèle indisponible) n'empêche pas la validation.
        Le repli token prend le relais tant que l'embedding manque.
        """
        if not question:
            return
        try:
            from services.nlp_engine import nlp_engine
            vector = nlp_engine.embed(question)
            if vector:
                self.col.update_one(
                    {"_id": ObjectId(c_id)},
                    {"$set": {"question_embedding": vector}},
                )
        except Exception:
            pass  # silencieux : la validation ne doit jamais échouer pour ça

    def update_contribution(self, c_id: str, response: str, validator_email: str):
        """Certifie + génère l'embedding + notifie l'étudiant."""
        ticket = self.col.find_one({"_id": ObjectId(c_id)})
        self.col.update_one(
            {"_id": ObjectId(c_id)},
            {"$set": {
                "response":     response,
                "status":       "valide",
                "validated_by": validator_email,
                "updated_at":   datetime.now(),
            }}
        )
        # Auto-embedding : la question devient interrogeable en recherche sémantique.
        if ticket:
            self._ensure_question_embedding(c_id, ticket.get("question", ""))
        if ticket:
            student_email = ticket.get("user_email", "")
            if student_email and student_email not in ("anonyme", "public", ""):
                send_answer_to_student(
                    student_email=student_email,
                    question=ticket.get("question", ""),
                    answer=response,
                    validator_name=validator_email,
                )

    def recategorize(self, c_id: str, new_category: str, author_email: str):
        """
        Point 6 : le contributeur peut recatégoriser une question existante.
        La catégorie est normalisée avant sauvegarde (point 8).
        """
        canonical = normalize_category(new_category)
        self.col.update_one(
            {"_id": ObjectId(c_id)},
            {"$set": {
                "category":       canonical,
                "recategorized_by": author_email,
                "recategorized_at": datetime.now(),
            }}
        )

    def submit_proposal(self, c_id: str, response: str, author_email: str,
                        new_category: Optional[str] = None):
        """
        Soumet une proposition de réponse + recatégorisation optionnelle.
        Déclenche st.rerun() via le flag retourné (point 9).
        """
        update = {
            "response":     response,
            "author_email": author_email,
            "updated_at":   datetime.now(),
        }
        if new_category:
            update["category"] = normalize_category(new_category)
        self.col.update_one({"_id": ObjectId(c_id)}, {"$set": update})

    def invalidate(self, c_id: str):
        self.col.update_one(
            {"_id": ObjectId(c_id)},
            {"$set": {"status": "en_attente", "updated_at": datetime.now()}}
        )

    def archive(self, c_id: str):
        self.col.update_one(
            {"_id": ObjectId(c_id)},
            {"$set": {"status": "archive", "archived_at": datetime.now()}}
        )

    def delete(self, c_id: str):
        self.col.delete_one({"_id": ObjectId(c_id)})

    def get_stats(self) -> dict:
        return {
            "en_attente": self.col.count_documents({"status": "en_attente"}),
            "valide":     self.col.count_documents({"status": "valide"}),
            "archive":    self.col.count_documents({"status": "archive"}),
        }

    def get_categories_in_db(self) -> list[str]:
        """Catégories canoniques effectivement présentes en base."""
        raw = self.col.distinct("category")
        return sorted({normalize_category(c) for c in raw if c})


# Import optionnel pour éviter circular import
from typing import Optional

kb_controller = KBController()