"""
Tests du MarketingController.
Couvre : capture lead (double écriture MongoDB + SF), stats, resync.
Salesforce webhook et MongoDB sont mockés.
"""

import pytest
from unittest.mock import MagicMock, patch
from bson import ObjectId


@pytest.fixture
def mkt_ctrl(monkeypatch):
    mock_col = MagicMock()
    mock_col.insert_one.return_value = MagicMock(inserted_id=ObjectId())
    mock_col.count_documents.return_value = 5
    mock_col.find.return_value = iter([])

    mock_db = MagicMock()
    mock_db.get_collection.return_value = mock_col
    monkeypatch.setattr("services.db_connector.db_instance", mock_db)

    from controllers.mkt_controller import MarketingController
    ctrl = MarketingController()
    ctrl._mock_col = mock_col
    return ctrl


class TestCaptureLead:

    def test_lead_always_saved_to_mongodb(self, mkt_ctrl):
        with patch("controllers.mkt_controller.sync_to_salesforce", return_value=True):
            mkt_ctrl.capture_lead("test@t.sn", "Modou Diallo", "MBA")
        mkt_ctrl._mock_col.insert_one.assert_called_once()

    def test_lead_saved_even_if_sf_fails(self, mkt_ctrl):
        """RG-06 : MongoDB toujours écrit, même si Salesforce échoue."""
        with patch("controllers.mkt_controller.sync_to_salesforce", return_value=False):
            result = mkt_ctrl.capture_lead("test@t.sn", "Fatou Sy", "Bourses")
        mkt_ctrl._mock_col.insert_one.assert_called_once()
        assert result is not None

    def test_sf_sync_called_after_mongo_save(self, mkt_ctrl):
        """L'ordre doit être : MongoDB d'abord, SF ensuite."""
        call_order = []
        mkt_ctrl._mock_col.insert_one.side_effect = lambda *a, **kw: call_order.append("mongo") or MagicMock(inserted_id=ObjectId())
        with patch("controllers.mkt_controller.sync_to_salesforce",
                   side_effect=lambda *a, **kw: call_order.append("sf") or True):
            mkt_ctrl.capture_lead("t@t.sn", "X", "MBA")
        assert call_order == ["mongo", "sf"]

    def test_lead_contains_correct_email(self, mkt_ctrl):
        with patch("controllers.mkt_controller.sync_to_salesforce", return_value=True):
            mkt_ctrl.capture_lead("modou@gmail.com", "Modou", "MBA")
        inserted = mkt_ctrl._mock_col.insert_one.call_args[0][0]
        assert inserted["email"] == "modou@gmail.com"

    def test_lead_contains_chat_history(self, mkt_ctrl):
        history = [{"question": "Q?", "response": "R.", "intent": "HOT"}]
        with patch("controllers.mkt_controller.sync_to_salesforce", return_value=True):
            mkt_ctrl.capture_lead("t@t.sn", "X", "MBA", chat_history=history)
        inserted = mkt_ctrl._mock_col.insert_one.call_args[0][0]
        assert inserted["chat_history"] == history

    def test_default_intent_score_is_warm(self, mkt_ctrl):
        with patch("controllers.mkt_controller.sync_to_salesforce", return_value=True):
            mkt_ctrl.capture_lead("t@t.sn", "X", "MBA")
        inserted = mkt_ctrl._mock_col.insert_one.call_args[0][0]
        assert inserted["intent_score"] == "WARM"

    def test_hot_intent_score_preserved(self, mkt_ctrl):
        with patch("controllers.mkt_controller.sync_to_salesforce", return_value=True):
            mkt_ctrl.capture_lead("t@t.sn", "X", "MBA", intent_score="HOT")
        inserted = mkt_ctrl._mock_col.insert_one.call_args[0][0]
        assert inserted["intent_score"] == "HOT"


class TestLeadStats:

    def test_get_lead_stats_returns_dict(self, mkt_ctrl):
        stats = mkt_ctrl.get_lead_stats()
        assert isinstance(stats, dict)
        assert "total" in stats
        assert "synced" in stats
        assert "pending" in stats
        assert "hot" in stats

    def test_resync_calls_retry_failed_leads(self, mkt_ctrl):
        with patch("controllers.mkt_controller.retry_failed_leads", return_value="✅ 3/3 resynchronisés.") as mock_retry:
            msg = mkt_ctrl.resync_failed()
        mock_retry.assert_called_once()
        assert "3" in msg