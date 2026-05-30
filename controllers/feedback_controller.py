from datetime import datetime
from bson.objectid import ObjectId
import streamlit as st
from services.db_connector import db_instance

class FeedbackController:
    def __init__(self):
        self.collection_name = "feedbacks"

    def _get_collection(self):
        return db_instance.get_collection(self.collection_name)

    def ensure_indexes(self):
        """Crée l'index composé optimisé selon le modèle v7.13."""
        try:
            coll = self._get_collection()
            coll.create_index([("status", 1), ("type", 1), ("created_at", -1)])
            return True
        except Exception as e:
            st.error(f"Erreur lors de la création de l'index feedback : {e}")
            return False

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

    def update_status(self, feedback_id, new_status, admin_notes=""):
        """Met à jour le statut et ajoute les notes de l'administrateur."""
        try:
            coll = self._get_collection()
            coll.update_one(
                {"_id": ObjectId(feedback_id)},
                {
                    "$set": {
                        "status": new_status,
                        "admin_notes": admin_notes,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return True
        except Exception as e:
            st.error(f"Erreur lors de la mise à jour du statut : {e}")
            return False

feedback_controller = FeedbackController()