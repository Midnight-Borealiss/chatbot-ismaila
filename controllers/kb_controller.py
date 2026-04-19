from datetime import datetime

from bson import ObjectId

from services.db_connector import db_instance
from services.mailer import send_answer_to_student


class KBController:
    """
    Gestion de la base de connaissances — workflow de validation.
    Après certification, notifie automatiquement l'étudiant si son email est connu.
    """

    def __init__(self):
        self.col = db_instance.get_collection("contributions")

    def get_pending(self) -> list:
        return list(self.col.find({"status": "en_attente"}))

    def get_validated(self) -> list:
        return list(self.col.find({"status": "valide"}))

    def update_contribution(self, c_id: str, response: str, validator_email: str):
        ticket = self.col.find_one({"_id": ObjectId(c_id)})
        
        # --- AJOUT : Récupérer le vrai nom du validateur ---
        validator_user = db_instance.get_collection("users").find_one({"email": validator_email})
        validator_name = validator_user.get("full_name", validator_email) if validator_user else validator_email

        self.col.update_one(
            {"_id": ObjectId(c_id)},
            {"$set": {
                "response":     response,
                "status":       "valide",
                "validated_by": validator_email,
                "updated_at":   datetime.now(),
            }}
        )

        if ticket:
            student_email = ticket.get("user_email", "")
            if student_email and student_email not in ("anonyme", "public", ""):
                send_answer_to_student(
                    student_email=student_email,
                    question=ticket.get("question", ""),
                    answer=response,
                    validator_name=validator_name, # Nom plus propre
                )
        """
        Certifie une contribution et notifie l'étudiant si son email est disponible.
        """
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

        # Notification à l'étudiant si son email est connu (pas anonyme)
        if ticket:
            student_email = ticket.get("user_email", "")
            if student_email and student_email not in ("anonyme", "public", ""):
                validator_name = validator_email  # Peut être enrichi avec full_name
                send_answer_to_student(
                    student_email=student_email,
                    question=ticket.get("question", ""),
                    answer=response,
                    validator_name=validator_name,
                )

    def invalidate(self, c_id: str):
        """Remet en attente une contribution validée (ex: correction nécessaire)."""
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


kb_controller = KBController()