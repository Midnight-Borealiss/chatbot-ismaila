"""
FeedbackController — Modération des retours utilisateurs ISMaiLa.

Alimente l'onglet de modération de l'espace Administration. Les feedbacks sont
créés par `views/feedback_view.py` (bouton « 💬 Signaler / Avis », accessible à
tous, y compris hors connexion) et traités ici.

Collection MongoDB : `feedbacks`. Les index sont créés de façon centralisée par
`db_instance._ensure_indexes()` — ne pas les recréer ici.

Statuts : « Ouvert » → « En cours » → « Résolu ».
"""

from datetime import datetime
from bson.objectid import ObjectId
import streamlit as st
from services.db_connector import db_instance

class FeedbackController:
    """Lecture filtrée et changement de statut des feedbacks."""

    def __init__(self):
        self.collection_name = "feedbacks"

    def _get_collection(self):
        """Résout la collection à chaque appel plutôt qu'à l'instanciation.

        Le singleton est construit à l'import : si MongoDB était injoignable à ce
        moment-là, une référence figée resterait un mock pour toute la session.
        """
        return db_instance.get_collection(self.collection_name)

    # Note : les index de la collection `feedbacks` sont créés de façon
    # centralisée par db_instance._ensure_indexes() (config déclarative).

    def get_filtered_feedbacks(self, status=None, feedback_type=None):
        """Feedbacks filtrés, les plus récents d'abord (index composé
        `status + type`).

        La valeur « Tous » vaut absence de filtre — c'est le libellé du
        sélecteur de l'interface, passé tel quel.
        """
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