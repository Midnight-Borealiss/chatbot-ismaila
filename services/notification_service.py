"""
Service de gestion des notifications utilisateur pour ISMaiLa.

Gère la création, récupération, marquage et suppression des notifications
stockées dans MongoDB avec une collection `user_notifications`.
"""

import logging
from datetime import datetime, UTC
from typing import Optional, Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from services.db_connector import db_instance

logger = logging.getLogger(__name__)

# Types de notifications acceptés
NOTIFICATION_TYPES = {"info", "warning", "success", "action_required"}


class NotificationService:
    """
    Service centralisé pour gérer les notifications utilisateur dans MongoDB.

    Collection `user_notifications` :
    {
        "_id": ObjectId,
        "recipient_email": "email@domain",
        "type": "info|warning|success|action_required",
        "title": "Titre court",
        "message": "Message détaillé",
        "action_url": "/path/to/action" (optional),
        "created_at": datetime.utcnow(),
        "read_at": None (null = non-lue) ou datetime (lue)
    }
    """

    def __init__(self):
        """Initialise le service et crée les index nécessaires."""
        self.collection = db_instance.get_collection("user_notifications")
        self._ensure_indexes()

    # ── Gestion des index ────────────────────────────────────────────────────

    def _ensure_indexes(self) -> None:
        """
        Crée les index sur la collection user_notifications.
        
        Index créés :
        - recipient_email + read_at (pour récupérer rapidement les non-lues)
        - recipient_email + created_at (pour trier chronologiquement)
        - created_at (pour nettoyage par TTL éventuel)
        """
        try:
            self.collection.create_index(
                [("recipient_email", ASCENDING)],
                name="idx_recipient_email"
            )
            self.collection.create_index(
                [("recipient_email", ASCENDING), ("read_at", ASCENDING)],
                name="idx_recipient_read_status",
                sparse=True
            )
            self.collection.create_index(
                [("recipient_email", ASCENDING), ("created_at", DESCENDING)],
                name="idx_recipient_created"
            )
            logger.debug("Indexes de user_notifications créés/vérifiés")
        except Exception as e:
            logger.warning(f"Impossible de créer les index : {e}")

    # ── Création de notifications ────────────────────────────────────────────

    def create_notification(
        self,
        recipient_email: str,
        notif_type: str,
        title: str,
        message: str,
        action_url: Optional[str] = None
    ) -> Optional[str]:
        """
        Crée une nouvelle notification pour un utilisateur.

        Args:
            recipient_email: Email du destinataire
            notif_type: Type de notification (info, warning, success, action_required)
            title: Titre court de la notification
            message: Message détaillé
            action_url: URL optionnelle pour une action associée

        Returns:
            ID de la notification créée (str), ou None en cas d'erreur

        Example:
            >>> notif_id = service.create_notification(
            ...     "user@example.com",
            ...     "success",
            ...     "Contribution validée",
            ...     "Votre contribution a été approuvée par l'admin."
            ... )
        """
        if notif_type not in NOTIFICATION_TYPES:
            logger.warning(
                f"Type de notification invalide : {notif_type}. "
                f"Types acceptés : {NOTIFICATION_TYPES}"
            )
            return None

        try:
            document = {
                "recipient_email": recipient_email,
                "type": notif_type,
                "title": title,
                "message": message,
                "action_url": action_url,
                "created_at": datetime.now(UTC),
                "read_at": None,
            }

            result = self.collection.insert_one(document)
            notification_id = str(result.inserted_id)

            logger.debug(
                f"Notification créée pour {recipient_email} : "
                f"{notification_id} ({notif_type})"
            )
            return notification_id

        except Exception as e:
            logger.error(f"Erreur lors de la création de la notification : {e}")
            return None

    # ── Récupération de notifications ────────────────────────────────────────

    def get_user_notifications(
        self,
        user_email: str,
        unread_only: bool = False,
        limit: int = 50
    ) -> list[dict]:
        """
        Récupère les notifications d'un utilisateur.

        Args:
            user_email: Email de l'utilisateur
            unread_only: Si True, retourne seulement les notifications non-lues
            limit: Nombre maximum de notifications à retourner (défaut 50)

        Returns:
            Liste des notifications formatées (les plus récentes d'abord)

        Example:
            >>> notifications = service.get_user_notifications("user@example.com")
            >>> unread = service.get_user_notifications("user@example.com", unread_only=True)
        """
        try:
            query = {"recipient_email": user_email}

            if unread_only:
                query["read_at"] = None

            notifications = list(
                self.collection.find(query)
                .sort("created_at", DESCENDING)
                .limit(limit)
            )

            return [self._format_notification(notif) for notif in notifications]

        except Exception as e:
            logger.error(
                f"Erreur lors de la récupération des notifications pour "
                f"{user_email} : {e}"
            )
            return []

    def get_unread_count(self, user_email: str) -> int:
        """
        Compte le nombre de notifications non-lues pour un utilisateur.

        Args:
            user_email: Email de l'utilisateur

        Returns:
            Nombre de notifications non-lues

        Example:
            >>> count = service.get_unread_count("user@example.com")
            >>> print(f"Vous avez {count} notifications non-lues")
        """
        try:
            count = self.collection.count_documents({
                "recipient_email": user_email,
                "read_at": None
            })
            return count
        except Exception as e:
            logger.error(f"Erreur lors du comptage des non-lues pour {user_email} : {e}")
            return 0

    # ── Marquage des notifications ───────────────────────────────────────────

    def mark_as_read(self, notification_id: str) -> bool:
        """
        Marque une notification comme lue.

        Args:
            notification_id: ID de la notification

        Returns:
            True si succès, False sinon

        Example:
            >>> success = service.mark_as_read("507f1f77bcf86cd799439011")
        """
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(notification_id)},
                {"$set": {"read_at": datetime.now(UTC)}}
            )
            if result.modified_count > 0:
                logger.debug(f"Notification {notification_id} marquée comme lue")
                return True
            return False
        except Exception as e:
            logger.error(f"Erreur lors du marquage comme lue : {e}")
            return False

    def mark_as_unread(self, notification_id: str) -> bool:
        """
        Marque une notification comme non-lue.

        Args:
            notification_id: ID de la notification

        Returns:
            True si succès, False sinon

        Example:
            >>> success = service.mark_as_unread("507f1f77bcf86cd799439011")
        """
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(notification_id)},
                {"$set": {"read_at": None}}
            )
            if result.modified_count > 0:
                logger.debug(f"Notification {notification_id} marquée comme non-lue")
                return True
            return False
        except Exception as e:
            logger.error(f"Erreur lors du marquage comme non-lue : {e}")
            return False

    # ── Suppression de notifications ─────────────────────────────────────────

    def delete_notification(self, notification_id: str) -> bool:
        """
        Supprime une notification.

        Args:
            notification_id: ID de la notification

        Returns:
            True si succès, False sinon

        Example:
            >>> success = service.delete_notification("507f1f77bcf86cd799439011")
        """
        try:
            result = self.collection.delete_one({"_id": ObjectId(notification_id)})
            if result.deleted_count > 0:
                logger.debug(f"Notification {notification_id} supprimée")
                return True
            return False
        except Exception as e:
            logger.error(f"Erreur lors de la suppression de la notification : {e}")
            return False

    # ── Méthodes utilitaires ─────────────────────────────────────────────────

    def _format_notification(self, doc: dict) -> dict:
        """
        Formate un document MongoDB en dictionnaire JSON-serializable.

        Args:
            doc: Document MongoDB brut

        Returns:
            Dictionnaire formaté avec _id en string et datetimes au format ISO

        Example:
            >>> formatted = service._format_notification(raw_doc)
        """
        if not doc:
            return {}

        return {
            "id": str(doc.get("_id")),
            "recipient_email": doc.get("recipient_email"),
            "type": doc.get("type"),
            "title": doc.get("title"),
            "message": doc.get("message"),
            "action_url": doc.get("action_url"),
            "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
            "read_at": doc.get("read_at").isoformat() if doc.get("read_at") else None,
            "is_read": doc.get("read_at") is not None,
        }


# Instance singleton
notification_instance = NotificationService()


# ── Test rapide au chargement du module ──────────────────────────────────────

if __name__ == "__main__":
    """Test rapide du service de notifications."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("\n" + "="*70)
    print("TEST DU SERVICE DE NOTIFICATIONS")
    print("="*70 + "\n")

    # Test 1 : Créer une notification
    print("1️⃣  Création d'une notification...")
    test_email = "test@example.com"
    notif_id = notification_instance.create_notification(
        recipient_email=test_email,
        notif_type="success",
        title="Test de création",
        message="Ceci est un message de test pour vérifier la création.",
        action_url="/admin/test"
    )

    if notif_id:
        print(f"✓ Notification créée avec l'ID : {notif_id}\n")

        # Test 2 : Récupérer les notifications
        print("2️⃣  Récupération des notifications...")
        notifications = notification_instance.get_user_notifications(test_email)
        print(f"✓ {len(notifications)} notification(s) trouvée(s)")
        for notif in notifications:
            print(f"   - {notif['title']} [{notif['type']}]")
        print()

        # Test 3 : Compter les non-lues
        print("3️⃣  Comptage des notifications non-lues...")
        unread_count = notification_instance.get_unread_count(test_email)
        print(f"✓ {unread_count} notification(s) non-lue(s)\n")

        # Test 4 : Marquer comme lue
        print("4️⃣  Marquage de la notification comme lue...")
        marked = notification_instance.mark_as_read(notif_id)
        if marked:
            print("✓ Notification marquée comme lue\n")

            # Test 5 : Vérifier le changement
            unread_after = notification_instance.get_unread_count(test_email)
            print(f"5️⃣  Vérification : {unread_after} notification(s) non-lue(s) restante(s)\n")

            # Test 6 : Récupérer seulement les non-lues (devrait être vide)
            print("6️⃣  Récupération des notifications non-lues uniquement...")
            unread_notifications = notification_instance.get_user_notifications(
                test_email,
                unread_only=True
            )
            print(f"✓ {len(unread_notifications)} notification(s) non-lue(s) trouvée(s)\n")

            # Test 7 : Marquer comme non-lue
            print("7️⃣  Marquage de la notification comme non-lue...")
            unmarked = notification_instance.mark_as_unread(notif_id)
            if unmarked:
                print("✓ Notification marquée comme non-lue\n")

            # Test 8 : Supprimer la notification
            print("8️⃣  Suppression de la notification...")
            deleted = notification_instance.delete_notification(notif_id)
            if deleted:
                print("✓ Notification supprimée\n")

                # Test 9 : Vérifier la suppression
                remaining = notification_instance.get_user_notifications(test_email)
                print(f"9️⃣  Vérification : {len(remaining)} notification(s) restante(s)\n")
            else:
                print("✗ Erreur lors de la suppression\n")
        else:
            print("✗ Erreur lors du marquage comme lue\n")
    else:
        print("✗ Erreur lors de la création de la notification\n")

    print("="*70)
    print("TEST TERMINÉ")
    print("="*70)
