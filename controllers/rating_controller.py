"""
Contrôleur des votes 👍 / 👎 sur les réponses du chat — ISMaiLa.

Chaque réponse de l'Assistant peut être appréciée d'un pouce haut/bas.
Ces votes sont stockés dans une collection dédiée `response_ratings`
(volontairement séparée de `feedbacks` pour ne pas polluer la modération
des signalements structurés).

Modèle d'un document `response_ratings` :
    user_email  : str          # auteur du vote (ou "anonyme")
    question    : str          # question posée
    response    : str          # réponse évaluée (tronquée)
    category    : str          # catégorie NLP de la réponse
    score       : float        # score de confiance NLP au moment de la réponse
    rating      : "up"|"down"  # appréciation
    created_at  : datetime
    updated_at  : datetime

Idempotence : upsert sur (user_email, question) → un utilisateur ne crée
pas de doublon en revotant, il met simplement à jour son vote.
"""

import logging
from datetime import datetime

from bson.objectid import ObjectId
from services.db_connector import db_instance

logger = logging.getLogger(__name__)

RATINGS_COLLECTION = "response_ratings"


class RatingController:
    def __init__(self):
        self.collection_name = RATINGS_COLLECTION

    def _get_collection(self):
        return db_instance.get_collection(self.collection_name)

    def save_rating(self, user_email: str, question: str, response: str,
                    rating: str, category: str = "", score: float = 0.0) -> bool:
        """Enregistre (ou met à jour) le vote d'un utilisateur sur une réponse.

        rating attendu : "up" ou "down". Non bloquant : toute erreur est
        loguée sans interrompre l'expérience de chat.
        """
        if rating not in ("up", "down"):
            return False
        try:
            coll = self._get_collection()
            now = datetime.utcnow()
            coll.update_one(
                {"user_email": user_email or "anonyme", "question": question},
                {
                    "$set": {
                        "response":   (response or "")[:500],
                        "category":   category,
                        "score":      round(float(score or 0.0), 3),
                        "rating":     rating,
                        "updated_at": now,
                    },
                    "$setOnInsert": {
                        "user_email": user_email or "anonyme",
                        "question":   question,
                        "created_at": now,
                    },
                },
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error(f"Erreur enregistrement vote réponse : {e}")
            return False

    def get_global_stats(self) -> dict:
        """Statistiques globales : nombre de votes et taux de satisfaction."""
        try:
            coll = self._get_collection()
            up   = coll.count_documents({"rating": "up"})
            down = coll.count_documents({"rating": "down"})
            total = up + down
            satisfaction = round(100 * up / total, 1) if total else 0.0
            return {"up": up, "down": down, "total": total, "satisfaction": satisfaction}
        except Exception as e:
            logger.error(f"Erreur stats votes : {e}")
            return {"up": 0, "down": 0, "total": 0, "satisfaction": 0.0}


rating_controller = RatingController()
