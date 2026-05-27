"""
Audit Service ISMaiLa — Journalisation centralisée des actions utilisateur.

Fournit un mécanisme de logging d'audit pour tracer :
  - Connexions/Déconnexions
  - Questions posées
  - Contributions proposées/validées/rejetées
  - Réponses fournies
  - Créations de compte
  - Et toute autre action utilisateur

Chaque action est enregistrée dans MongoDB avec :
  - Email utilisateur (indexed)
  - Type d'action (LOGIN, LOGOUT, QUESTION_ASKED, etc.)
  - Description lisible
  - Timestamp
  - Métadonnées additionnelles (question_id, contribution_id, etc.)
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List, Any

from services.db_connector import db_instance

# Use UTC for timestamps (avoids deprecation warning with utcnow())
UTC = datetime.UTC if hasattr(datetime, 'UTC') else None

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
#  Types d'actions supportées
# ══════════════════════════════════════════════════════════════════════

ACTION_TYPES = {
    "LOGIN": "Connexion utilisateur",
    "LOGOUT": "Déconnexion utilisateur",
    "QUESTION_ASKED": "Question posée au chat",
    "CONTRIBUTION_PROPOSED": "Contribution proposée",
    "CONTRIBUTION_VALIDATED": "Contribution validée",
    "CONTRIBUTION_REJECTED": "Contribution rejetée",
    "ANSWER_PROVIDED": "Réponse fournie pour une question",
    "ACCOUNT_CREATED": "Compte créé",
}


# ══════════════════════════════════════════════════════════════════════
#  Service d'audit
# ══════════════════════════════════════════════════════════════════════

class AuditService:
    """
    Service centralisé pour journaliser les actions utilisateur dans MongoDB.

    Chaque action est enregistrée de manière silencieuse (pas de logs console
    sauf erreurs) pour éviter du bruit verbose. Les erreurs sont loggées
    gracieusement sans interrompre le flux applicatif.
    """

    def __init__(self):
        """Initialise le service avec accès à la collection MongoDB."""
        self._collection = db_instance.get_collection("user_audit_logs")

    # ────────────────────────────────────────────────────────────────────────────
    #  Interface publique — Logging
    # ────────────────────────────────────────────────────────────────────────────

    def log_action(
        self,
        user_email: str,
        action: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Enregistre une action utilisateur dans le journal d'audit.

        Args:
            user_email (str): Email de l'utilisateur qui effectue l'action
            action (str): Type d'action (LOGIN, QUESTION_ASKED, etc.)
            description (str): Description lisible et claire de l'action
            metadata (dict, optional): Données supplémentaires (question_id, etc.)

        Returns:
            bool: True si l'enregistrement réussit, False en cas d'erreur

        Exemple:
            >>> audit = AuditService()
            >>> audit.log_action(
            ...     user_email="student@example.com",
            ...     action="QUESTION_ASKED",
            ...     description="Étudiant a posé une question sur les fractions",
            ...     metadata={"question_id": "q123", "category": "math"}
            ... )
            True
        """
        try:
            doc = {
                "user_email": user_email,
                "action": action,
                "description": description,
                "timestamp": datetime.now(UTC) if UTC else datetime.utcnow(),
                "metadata": metadata or {},
            }
            result = self._collection.insert_one(doc)
            return bool(result.inserted_id)
        except Exception as e:
            logger.error(
                f"Erreur audit log_action ({user_email}, {action}): {e}"
            )
            return False

    # ────────────────────────────────────────────────────────────────────────────
    #  Interface publique — Lecture
    # ────────────────────────────────────────────────────────────────────────────

    def get_user_actions(
        self,
        user_email: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Récupère les actions d'un utilisateur, les plus récentes d'abord.

        Args:
            user_email (str): Email de l'utilisateur
            limit (int): Nombre maximum d'actions à retourner (défaut: 50)

        Returns:
            list: Liste de documents d'audit formatés, les 50 derniers par défaut

        Exemple:
            >>> audit = AuditService()
            >>> actions = audit.get_user_actions("student@example.com")
            >>> for action in actions:
            ...     print(f"{action['timestamp']}: {action['description']}")
        """
        try:
            docs = list(
                self._collection.find({"user_email": user_email})
                .sort("timestamp", -1)
                .limit(limit)
            )
            return self._format_documents(docs)
        except Exception as e:
            logger.error(
                f"Erreur audit get_user_actions ({user_email}): {e}"
            )
            return []

    def get_actions_by_type(
        self,
        user_email: str,
        action_type: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Récupère les actions d'un utilisateur filtrées par type.

        Args:
            user_email (str): Email de l'utilisateur
            action_type (str): Type d'action à filtrer (LOGIN, QUESTION_ASKED, etc.)
            limit (int): Nombre maximum d'actions à retourner (défaut: 50)

        Returns:
            list: Actions filtrées par type, les 50 dernières par défaut

        Exemple:
            >>> audit = AuditService()
            >>> login_actions = audit.get_actions_by_type(
            ...     "student@example.com",
            ...     "LOGIN"
            ... )
            >>> print(f"Utilisateur connecté {len(login_actions)} fois")
        """
        try:
            docs = list(
                self._collection.find({
                    "user_email": user_email,
                    "action": action_type,
                })
                .sort("timestamp", -1)
                .limit(limit)
            )
            return self._format_documents(docs)
        except Exception as e:
            logger.error(
                f"Erreur audit get_actions_by_type ({user_email}, {action_type}): {e}"
            )
            return []

    def get_recent_actions_all_users(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Récupère les actions récentes de tous les utilisateurs (admin).

        Args:
            limit (int): Nombre maximum d'actions à retourner (défaut: 100)

        Returns:
            list: Actions récentes de tous les utilisateurs, triées par date

        Exemple:
            >>> audit = AuditService()
            >>> recent = audit.get_recent_actions_all_users(limit=50)
            >>> for action in recent:
            ...     print(f"{action['user_email']}: {action['description']}")
        """
        try:
            docs = list(
                self._collection.find()
                .sort("timestamp", -1)
                .limit(limit)
            )
            return self._format_documents(docs)
        except Exception as e:
            logger.error(f"Erreur audit get_recent_actions_all_users(): {e}")
            return []

    def get_action_count_by_type(
        self,
        user_email: str,
    ) -> Dict[str, int]:
        """
        Compte le nombre d'actions par type pour un utilisateur.

        Args:
            user_email (str): Email de l'utilisateur

        Returns:
            dict: Dictionnaire avec action_type -> count

        Exemple:
            >>> audit = AuditService()
            >>> counts = audit.get_action_count_by_type("student@example.com")
            >>> print(f"Connexions: {counts.get('LOGIN', 0)}")
            >>> print(f"Questions: {counts.get('QUESTION_ASKED', 0)}")
        """
        try:
            pipeline = [
                {"$match": {"user_email": user_email}},
                {"$group": {"_id": "$action", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
            results = list(self._collection.aggregate(pipeline))
            return {doc["_id"]: doc["count"] for doc in results}
        except Exception as e:
            logger.error(
                f"Erreur audit get_action_count_by_type ({user_email}): {e}"
            )
            return {}

    # ────────────────────────────────────────────────────────────────────────────
    #  Utilitaires privés
    # ────────────────────────────────────────────────────────────────────────────

    def _format_documents(
        self,
        docs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Formate les documents MongoDB pour l'API (convertit ObjectId en string).

        Args:
            docs (list): Documents MongoDB bruts

        Returns:
            list: Documents formatés avec _id en string et timestamp lisible
        """
        formatted = []
        for doc in docs:
            formatted_doc = {
                "id": str(doc.get("_id", "")),
                "user_email": doc.get("user_email", ""),
                "action": doc.get("action", ""),
                "description": doc.get("description", ""),
                "timestamp": doc.get("timestamp", datetime.now(UTC) if UTC else datetime.utcnow()),
                "metadata": doc.get("metadata", {}),
            }
            formatted.append(formatted_doc)
        return formatted


# ══════════════════════════════════════════════════════════════════════
#  Singleton — une seule instance pour toute l'app
# ══════════════════════════════════════════════════════════════════════

audit_instance = AuditService()
