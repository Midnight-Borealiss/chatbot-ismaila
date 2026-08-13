"""
Fixtures partagées entre tous les tests ISMaiLa.
Principe : aucun test ne touche à MongoDB réel ni à SMTP réel.
Tout est mocké via unittest.mock.
"""

import pytest
from unittest.mock import MagicMock, patch


# ══════════════════════════════════════════════════════════════════════
#  Mock MongoDB collection
# ══════════════════════════════════════════════════════════════════════

def make_mock_collection(docs=None):
    """Retourne une fausse collection MongoDB avec find/find_one/insert/update."""
    docs = docs or []
    col = MagicMock()
    col.find.return_value = iter(docs)
    col.find_one.return_value = docs[0] if docs else None
    col.insert_one.return_value = MagicMock(inserted_id="fake_id_123")
    col.update_one.return_value = MagicMock(modified_count=1)
    col.delete_one.return_value = MagicMock(deleted_count=1)
    col.count_documents.return_value = len(docs)
    return col


@pytest.fixture
def mock_db(monkeypatch):
    """
    Patch db_instance.get_collection pour retourner des collections vides.
    Utilisé dans tous les tests qui instancient des controllers.
    """
    from services.db_connector import db_instance
    mock_col = make_mock_collection()
    monkeypatch.setattr(db_instance, "get_collection", lambda name: mock_col)
    monkeypatch.setattr(db_instance, "is_alive", lambda: True)
    monkeypatch.setattr(db_instance, "db", MagicMock())
    return db_instance


@pytest.fixture
def mock_smtp(monkeypatch):
    """Patch smtplib.SMTP pour ne jamais envoyer de vrais emails."""
    with patch("smtplib.SMTP") as mock:
        mock.return_value.__enter__.return_value = MagicMock()
        yield mock


@pytest.fixture
def sample_contribution():
    """Contribution certifiée type, prête à être servie par la recherche."""
    from bson import ObjectId
    return {
        "_id":        ObjectId(),
        "question":   "Quels sont les frais du MBA ?",
        "response":   "Le MBA coûte 2 500 000 FCFA par an.",
        "status":     "valide",
        "category":   "MBA",
        "user_email": "etudiant@test.sn",
        "created_at": "2026-01-01",
    }


@pytest.fixture
def sample_pending():
    """Contribution en attente, avec une réponse encore à l'état de placeholder."""
    from bson import ObjectId
    return {
        "_id":        ObjectId(),
        "question":   "Y a-t-il des logements étudiants ?",
        "response":   "En attente",
        "status":     "en_attente",
        "category":   "Général",
        "user_email": "prospect@test.sn",
        "created_at": "2026-01-15",
    }


@pytest.fixture
def sample_user():
    """Validateur type. Le `password_hash` est factice : aucun mot de passe
    réel ne figure dans les fixtures."""
    return {
        "email":         "validator@ism.sn",
        "full_name":     "Fatou Diallo",
        "role":          "VALIDATEUR",
        "expert_topics": ["MBA", "Admission"],
        "password_hash": "$2b$12$fakehashfakehashfakehashfakehashfakehash",
    }