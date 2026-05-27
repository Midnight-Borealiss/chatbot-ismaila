"""
Tests pour le service d'audit ISMaiLa.

Vérifie que :
  1. log_action() enregistre correctement les actions
  2. get_user_actions() récupère les actions d'un utilisateur
  3. get_actions_by_type() filtre par type d'action
  4. Les métadonnées sont préservées
  5. Les erreurs sont gérées gracieusement
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from services.audit_service import AuditService, audit_service, ACTION_TYPES


class TestAuditService:
    """Tests du service d'audit."""

    @pytest.fixture
    def audit(self):
        """Crée une instance de AuditService pour les tests."""
        return AuditService()

    # ────────────────────────────────────────────────────────────────────────────
    #  Tests de log_action
    # ────────────────────────────────────────────────────────────────────────────

    def test_log_action_success(self, audit):
        """Test que log_action() enregistre une action avec succès."""
        # Mock la collection MongoDB
        audit._collection = MagicMock()
        audit._collection.insert_one.return_value = MagicMock(
            inserted_id="507f1f77bcf86cd799439011"
        )

        result = audit.log_action(
            user_email="test@example.com",
            action="LOGIN",
            description="Utilisateur connecté",
        )

        assert result is True
        audit._collection.insert_one.assert_called_once()

    def test_log_action_with_metadata(self, audit):
        """Test que les métadonnées sont enregistrées correctement."""
        audit._collection = MagicMock()
        audit._collection.insert_one.return_value = MagicMock(
            inserted_id="507f1f77bcf86cd799439011"
        )

        metadata = {"question_id": "q123", "category": "math"}
        audit.log_action(
            user_email="student@example.com",
            action="QUESTION_ASKED",
            description="Question sur les fractions",
            metadata=metadata,
        )

        # Vérifie que le document passé contient les métadonnées
        call_args = audit._collection.insert_one.call_args[0][0]
        assert call_args["metadata"] == metadata

    def test_log_action_empty_metadata(self, audit):
        """Test que metadata vide par défaut ne pose pas de problème."""
        audit._collection = MagicMock()
        audit._collection.insert_one.return_value = MagicMock(
            inserted_id="507f1f77bcf86cd799439011"
        )

        audit.log_action(
            user_email="user@example.com",
            action="LOGOUT",
            description="Déconnexion",
        )

        call_args = audit._collection.insert_one.call_args[0][0]
        assert call_args["metadata"] == {}

    def test_log_action_handles_error(self, audit):
        """Test que log_action() retourne False en cas d'erreur."""
        audit._collection = MagicMock()
        audit._collection.insert_one.side_effect = Exception("DB Error")

        result = audit.log_action(
            user_email="user@example.com",
            action="LOGIN",
            description="Connexion",
        )

        assert result is False

    # ────────────────────────────────────────────────────────────────────────────
    #  Tests de get_user_actions
    # ────────────────────────────────────────────────────────────────────────────

    def test_get_user_actions_success(self, audit):
        """Test que get_user_actions() retourne les actions triées par date."""
        from bson import ObjectId

        mock_docs = [
            {
                "_id": ObjectId(),
                "user_email": "user@example.com",
                "action": "LOGIN",
                "description": "Connexion 1",
                "timestamp": datetime(2024, 1, 3),
                "metadata": {},
            },
            {
                "_id": ObjectId(),
                "user_email": "user@example.com",
                "action": "QUESTION_ASKED",
                "description": "Question 1",
                "timestamp": datetime(2024, 1, 2),
                "metadata": {"question_id": "q1"},
            },
            {
                "_id": ObjectId(),
                "user_email": "user@example.com",
                "action": "LOGIN",
                "description": "Connexion 2",
                "timestamp": datetime(2024, 1, 1),
                "metadata": {},
            },
        ]

        # Mock le find().sort().limit()
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value.limit.return_value = mock_docs
        audit._collection = MagicMock()
        audit._collection.find.return_value = mock_cursor

        actions = audit.get_user_actions("user@example.com")

        # Vérifie les appels
        audit._collection.find.assert_called_once_with(
            {"user_email": "user@example.com"}
        )
        mock_cursor.sort.assert_called_once_with("timestamp", -1)
        mock_cursor.sort.return_value.limit.assert_called_once_with(50)

        # Vérifie le formatage
        assert len(actions) == 3
        assert all("id" in action for action in actions)
        assert all("timestamp" in action for action in actions)

    def test_get_user_actions_empty(self, audit):
        """Test que get_user_actions() retourne [] pour un utilisateur sans actions."""
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value.limit.return_value = []
        audit._collection = MagicMock()
        audit._collection.find.return_value = mock_cursor

        actions = audit.get_user_actions("unknown@example.com")

        assert actions == []

    def test_get_user_actions_handles_error(self, audit):
        """Test que get_user_actions() retourne [] en cas d'erreur."""
        audit._collection = MagicMock()
        audit._collection.find.side_effect = Exception("DB Error")

        actions = audit.get_user_actions("user@example.com")

        assert actions == []

    # ────────────────────────────────────────────────────────────────────────────
    #  Tests de get_actions_by_type
    # ────────────────────────────────────────────────────────────────────────────

    def test_get_actions_by_type_success(self, audit):
        """Test que get_actions_by_type() filtre correctement par type."""
        from bson import ObjectId

        mock_docs = [
            {
                "_id": ObjectId(),
                "user_email": "user@example.com",
                "action": "LOGIN",
                "description": "Connexion 1",
                "timestamp": datetime(2024, 1, 2),
                "metadata": {},
            },
            {
                "_id": ObjectId(),
                "user_email": "user@example.com",
                "action": "LOGIN",
                "description": "Connexion 2",
                "timestamp": datetime(2024, 1, 1),
                "metadata": {},
            },
        ]

        mock_cursor = MagicMock()
        mock_cursor.sort.return_value.limit.return_value = mock_docs
        audit._collection = MagicMock()
        audit._collection.find.return_value = mock_cursor

        actions = audit.get_actions_by_type("user@example.com", "LOGIN")

        # Vérifie le filtre
        audit._collection.find.assert_called_once_with({
            "user_email": "user@example.com",
            "action": "LOGIN",
        })

        assert len(actions) == 2

    def test_get_actions_by_type_no_results(self, audit):
        """Test get_actions_by_type() quand aucune action ne correspond."""
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value.limit.return_value = []
        audit._collection = MagicMock()
        audit._collection.find.return_value = mock_cursor

        actions = audit.get_actions_by_type("user@example.com", "NONEXISTENT")

        assert actions == []

    # ────────────────────────────────────────────────────────────────────────────
    #  Tests de get_recent_actions_all_users
    # ────────────────────────────────────────────────────────────────────────────

    def test_get_recent_actions_all_users(self, audit):
        """Test que get_recent_actions_all_users() retourne les actions récentes."""
        from bson import ObjectId

        mock_docs = [
            {
                "_id": ObjectId(),
                "user_email": "user1@example.com",
                "action": "LOGIN",
                "description": "Connexion",
                "timestamp": datetime(2024, 1, 3),
                "metadata": {},
            },
            {
                "_id": ObjectId(),
                "user_email": "user2@example.com",
                "action": "QUESTION_ASKED",
                "description": "Question",
                "timestamp": datetime(2024, 1, 2),
                "metadata": {},
            },
        ]

        mock_cursor = MagicMock()
        mock_cursor.sort.return_value.limit.return_value = mock_docs
        audit._collection = MagicMock()
        audit._collection.find.return_value = mock_cursor

        actions = audit.get_recent_actions_all_users(limit=50)

        audit._collection.find.assert_called_once_with()
        assert len(actions) == 2

    # ────────────────────────────────────────────────────────────────────────────
    #  Tests de get_action_count_by_type
    # ────────────────────────────────────────────────────────────────────────────

    def test_get_action_count_by_type_success(self, audit):
        """Test que get_action_count_by_type() compte les actions par type."""
        results = [
            {"_id": "LOGIN", "count": 5},
            {"_id": "QUESTION_ASKED", "count": 3},
            {"_id": "LOGOUT", "count": 5},
        ]

        audit._collection = MagicMock()
        audit._collection.aggregate.return_value = results

        counts = audit.get_action_count_by_type("user@example.com")

        assert counts == {
            "LOGIN": 5,
            "QUESTION_ASKED": 3,
            "LOGOUT": 5,
        }

    def test_get_action_count_by_type_empty(self, audit):
        """Test get_action_count_by_type() pour un utilisateur sans actions."""
        audit._collection = MagicMock()
        audit._collection.aggregate.return_value = []

        counts = audit.get_action_count_by_type("unknown@example.com")

        assert counts == {}

    # ────────────────────────────────────────────────────────────────────────────
    #  Tests du formatage
    # ────────────────────────────────────────────────────────────────────────────

    def test_format_documents_converts_objectid(self, audit):
        """Test que _format_documents() convertit ObjectId en string."""
        from bson import ObjectId

        object_id = ObjectId()
        docs = [
            {
                "_id": object_id,
                "user_email": "user@example.com",
                "action": "LOGIN",
                "description": "Connexion",
                "timestamp": datetime(2024, 1, 1),
                "metadata": {"source": "web"},
            }
        ]

        formatted = audit._format_documents(docs)

        assert len(formatted) == 1
        assert formatted[0]["id"] == str(object_id)
        assert formatted[0]["user_email"] == "user@example.com"
        assert formatted[0]["metadata"] == {"source": "web"}

    def test_format_documents_handles_missing_fields(self, audit):
        """Test que _format_documents() gère les champs manquants."""
        docs = [
            {
                "_id": "123",
                "user_email": "user@example.com",
                "action": "LOGIN",
                # 'description', 'timestamp', 'metadata' manquants
            }
        ]

        formatted = audit._format_documents(docs)

        assert len(formatted) == 1
        assert formatted[0]["description"] == ""
        assert formatted[0]["metadata"] == {}


class TestActionTypes:
    """Tests des types d'actions disponibles."""

    def test_action_types_not_empty(self):
        """Test que ACTION_TYPES contient toutes les actions nécessaires."""
        assert len(ACTION_TYPES) > 0

    def test_action_types_include_core_actions(self):
        """Test que les actions essentielles sont définies."""
        core_actions = {
            "LOGIN",
            "LOGOUT",
            "QUESTION_ASKED",
            "CONTRIBUTION_PROPOSED",
            "CONTRIBUTION_VALIDATED",
            "CONTRIBUTION_REJECTED",
            "ANSWER_PROVIDED",
            "ACCOUNT_CREATED",
        }
        for action in core_actions:
            assert action in ACTION_TYPES


class TestAuditServiceSingleton:
    """Tests du singleton audit_service."""

    def test_audit_service_is_instance(self):
        """Test que audit_service est une instance d'AuditService."""
        assert isinstance(audit_service, AuditService)

    def test_audit_service_is_same_instance(self):
        """Test que le singleton retourne toujours la même instance."""
        assert audit_service is audit_service
