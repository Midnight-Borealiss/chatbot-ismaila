"""
Tests du module sf_connector.
Couvre : construction du payload, envoi webhook, gestion timeout,
         mise à jour flag is_synced_sf, job de rattrapage retry.
Aucun vrai appel HTTP ni MongoDB.
"""

import pytest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from datetime import datetime


@pytest.fixture
def sample_lead():
    return {
        "_id":          ObjectId(),
        "email":        "modou@gmail.com",
        "full_name":    "Modou Diallo",
        "phone":        "+221771234567",
        "interest":     "MBA",
        "intent_score": "HOT",
        "nlp_score":    0.91,
        "chat_history": [
            {"question": "Frais MBA ?",  "response": "2 500 000 FCFA"},
            {"question": "Bourses ?",    "response": "Oui, 3 types"},
        ],
        "is_synced_sf": False,
    }


@pytest.fixture
def mock_leads_col(monkeypatch):
    col = MagicMock()
    col.find.return_value = iter([])
    col.update_one.return_value = MagicMock(modified_count=1)

    mock_db = MagicMock()
    mock_db.get_collection.return_value = col
    monkeypatch.setattr("services.db_connector.db_instance", mock_db)
    return col


# ══════════════════════════════════════════════════════════════════════
#  build_sf_payload
# ══════════════════════════════════════════════════════════════════════

class TestBuildSFPayload:

    def test_payload_contains_email(self, sample_lead):
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert payload["Email"] == "modou@gmail.com"

    def test_payload_splits_fullname(self, sample_lead):
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert payload["FirstName"] == "Modou"
        assert payload["LastName"]  == "Diallo"

    def test_payload_maps_campaign(self, sample_lead):
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert "MBA" in payload["ISM_Campaign__c"]

    def test_payload_maps_hot_to_salesforce_rating(self, sample_lead):
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert payload["Rating"] == "Hot"

    def test_payload_maps_warm(self, sample_lead):
        from services.sf_connector import build_sf_payload
        sample_lead["intent_score"] = "WARM"
        payload = build_sf_payload(sample_lead)
        assert payload["Rating"] == "Warm"

    def test_payload_includes_question_count(self, sample_lead):
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert payload["ISM_Questions__c"] == 2

    def test_payload_includes_nlp_score(self, sample_lead):
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert payload["ISM_Score_NLP__c"] == 0.91

    def test_payload_lead_source(self, sample_lead):
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert payload["LeadSource"] == "ISMaiLa Chatbot"

    def test_description_contains_conversation_summary(self, sample_lead):
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert "Frais MBA ?" in payload["Description"]

    def test_payload_general_fallback_category(self, sample_lead, monkeypatch):
        from services import sf_connector
        sample_lead["interest"] = "CategorieinconnueXYZ"
        payload = sf_connector.build_sf_payload(sample_lead)
        assert "General" in payload["ISM_Campaign__c"]


# ══════════════════════════════════════════════════════════════════════
#  sync_to_salesforce
# ══════════════════════════════════════════════════════════════════════

class TestSyncToSalesforce:

    def test_returns_false_when_no_webhook_url(self, sample_lead, mock_leads_col, monkeypatch):
        from services import sf_connector
        monkeypatch.setattr(sf_connector, "SF_WEBHOOK_URL", None)
        result = sf_connector.sync_to_salesforce(sample_lead)
        assert result is False

    def test_returns_true_on_200(self, sample_lead, mock_leads_col, monkeypatch):
        from services import sf_connector
        monkeypatch.setattr(sf_connector, "SF_WEBHOOK_URL", "https://hook.make.com/test")
        mock_response = MagicMock(status_code=200)
        with patch("requests.post", return_value=mock_response):
            result = sf_connector.sync_to_salesforce(sample_lead)
        assert result is True

    def test_returns_false_on_non_200(self, sample_lead, mock_leads_col, monkeypatch):
        from services import sf_connector
        monkeypatch.setattr(sf_connector, "SF_WEBHOOK_URL", "https://hook.make.com/test")
        mock_response = MagicMock(status_code=500)
        with patch("requests.post", return_value=mock_response):
            result = sf_connector.sync_to_salesforce(sample_lead)
        assert result is False

    def test_returns_false_on_timeout(self, sample_lead, mock_leads_col, monkeypatch):
        import requests as req_module
        from services import sf_connector
        monkeypatch.setattr(sf_connector, "SF_WEBHOOK_URL", "https://hook.make.com/test")
        with patch("requests.post", side_effect=req_module.exceptions.Timeout):
            result = sf_connector.sync_to_salesforce(sample_lead)
        assert result is False

    def test_updates_is_synced_sf_on_success(self, sample_lead, mock_leads_col, monkeypatch):
        from services import sf_connector
        monkeypatch.setattr(sf_connector, "SF_WEBHOOK_URL", "https://hook.make.com/test")
        mock_response = MagicMock(status_code=200)
        with patch("requests.post", return_value=mock_response):
            sf_connector.sync_to_salesforce(sample_lead)
        mock_leads_col.update_one.assert_called_once()
        update_set = mock_leads_col.update_one.call_args[0][1]["$set"]
        assert update_set["is_synced_sf"] is True

    def test_does_not_update_on_failure(self, sample_lead, mock_leads_col, monkeypatch):
        import requests as req_module
        from services import sf_connector
        monkeypatch.setattr(sf_connector, "SF_WEBHOOK_URL", "https://hook.make.com/test")
        with patch("requests.post", side_effect=req_module.exceptions.Timeout):
            sf_connector.sync_to_salesforce(sample_lead)
        mock_leads_col.update_one.assert_not_called()


# ══════════════════════════════════════════════════════════════════════
#  retry_failed_leads
# ══════════════════════════════════════════════════════════════════════

class TestRetryFailedLeads:

    def test_retries_all_unsynced_leads(self, mock_leads_col, monkeypatch):
        from bson import ObjectId
        from services import sf_connector

        unsynced = [
            {"_id": ObjectId(), "email": f"u{i}@t.sn", "full_name": f"User {i}",
             "interest": "MBA", "intent_score": "WARM", "chat_history": []}
            for i in range(3)
        ]
        mock_leads_col.find.return_value = iter(unsynced)
        monkeypatch.setattr(sf_connector, "SF_WEBHOOK_URL", "https://hook.make.com/test")

        with patch("requests.post", return_value=MagicMock(status_code=200)):
            msg = sf_connector.retry_failed_leads()

        assert "3" in msg

    def test_returns_error_message_on_db_failure(self, monkeypatch):
        from services import sf_connector
        mock_db = MagicMock()
        mock_db.get_collection.side_effect = RuntimeError("DB down")
        monkeypatch.setattr("services.db_connector.db_instance", mock_db)

        msg = sf_connector.retry_failed_leads()
        assert "Erreur" in msg or "❌" in msg