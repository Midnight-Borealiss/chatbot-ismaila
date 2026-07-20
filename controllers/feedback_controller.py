from datetime import datetime
from bson.objectid import ObjectId
import streamlit as st
from services.db_connector import db_instance

class FeedbackController:
    def __init__(self):
        self.collection_name = "feedbacks"

    def _get_collection(self):
        return db_instance.get_collection(self.collection_name)

    # Note : les index de la collection `feedbacks` sont créés de façon
    # centralisée par db_instance._ensure_indexes() (config déclarative).

    def get_filtered_feedbacks(self, status=None, feedback_type=None):
        """Récupère les feedbacks filtrés à l'aide de l'index composé."""
        try:
            coll = self._get_collection()
            query = {}
            if status and status != "Tous":
                query["status"] = status
            if feedback_type and feedback_type != "Tous":
                query["type"] = feedback_type
                
            return list(coll.find(query).sort("created_at", -1))
        except Exception as e:
            st.error(f"Erreur de récupération des feedbacks : {e}")
            return []

    def update_status(self, feedback_id, new_status, admin_notes="", priority=None):
        """Met à jour le statut, les notes admin et, optionnellement, la priorité.

        Renseigne `resolved_at` au passage à « Résolu » et le remet à None si
        le feedback est rouvert (statut différent de « Résolu »).
        """
        try:
            coll = self._get_collection()
            changes = {
                "status": new_status,
                "admin_notes": admin_notes,
                "updated_at": datetime.utcnow(),
                "resolved_at": datetime.utcnow() if new_status == "Résolu" else None,
            }
            if priority:
                changes["priority"] = priority
            coll.update_one({"_id": ObjectId(feedback_id)}, {"$set": changes})
            return True
        except Exception as e:
            st.error(f"Erreur lors de la mise à jour du statut : {e}")
            return False

feedback_controller = FeedbackController()