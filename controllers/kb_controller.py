from datetime import datetime

from bson import ObjectId

from services.db_connector import db_instance


class KBController:
    """Gestion de la base de connaissances — workflow de validation."""

    def __init__(self):
        self.col = db_instance.get_collection("contributions")

    def get_pending(self) -> list:
        return list(self.col.find({"status": "en_attente"}))

    def get_validated(self) -> list:
        return list(self.col.find({"status": "valide"}))

    def update_contribution(self, c_id: str, response: str, validator_email: str):
        self.col.update_one(
            {"_id": ObjectId(c_id)},
            {"$set": {
                "response":      response,
                "status":        "valide",
                "validated_by":  validator_email,
                "updated_at":    datetime.now(),
            }}
        )

    def archive(self, c_id: str):
        self.col.update_one(
            {"_id": ObjectId(c_id)},
            {"$set": {"status": "archive", "archived_at": datetime.now()}}
        )

    def get_stats(self) -> dict:
        return {
            "en_attente": self.col.count_documents({"status": "en_attente"}),
            "valide":     self.col.count_documents({"status": "valide"}),
            "archive":    self.col.count_documents({"status": "archive"}),
        }


kb_controller = KBController()