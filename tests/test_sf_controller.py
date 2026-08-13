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
    """Lead complet et représentatif : prospect chaud avec un historique."""
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
    """Collection `leads` factice — aucun accès à une vraie base."""
    from services.db_connector import db_instance
    col = MagicMock()
    col.find.return_value = iter([])
    col.update_one.return_value = MagicMock(modified_count=1)

    monkeypatch.setattr(db_instance, "get_collection", lambda name: col)
    monkeypatch.setattr(db_instance, "is_alive", lambda: True)
    monkeypatch.setattr(db_instance, "db", MagicMock())
    return col


# ══════════════════════════════════════════════════════════════════════
#  build_sf_payload
# ══════════════════════════════════════════════════════════════════════

class TestBuildSFPayload:
    """Le lead ISMaiLa doit se traduire fidèlement au format Salesforce."""

    def test_payload_contains_email(self, sample_lead):
        """L'email, clé de rapprochement côté CRM, est transmis tel quel."""
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert payload["Email"] == "modou@gmail.com"

    def test_payload_splits_fullname(self, sample_lead):
        """Salesforce exige prénom et nom séparés ; ISMaiLa ne stocke qu'un nom complet."""
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert payload["FirstName"] == "Modou"
        assert payload["LastName"]  == "Diallo"

    def test_payload_maps_campaign(self, sample_lead):
        """La catégorie d'intérêt détermine la campagne de recrutement."""
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert "MBA" in payload["ISM_Campaign__c"]

    def test_payload_maps_hot_to_salesforce_rating(self, sample_lead):
        """Un prospect HOT devient « Hot » — le vocabulaire Rating de Salesforce."""
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert payload["Rating"] == "Hot"

    def test_payload_maps_warm(self, sample_lead):
        """Idem pour WARM, l'autre valeur courante."""
        from services.sf_connector import build_sf_payload
        sample_lead["intent_score"] = "WARM"
        payload = build_sf_payload(sample_lead)
        assert payload["Rating"] == "Warm"

    def test_payload_includes_question_count(self, sample_lead):
        """Le nombre de questions posées mesure l'engagement du prospect."""
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert payload["ISM_Questions__c"] == 2

    def test_payload_includes_nlp_score(self, sample_lead):
        """Le score NLP est transmis sans arrondi, pour l'analyse côté CRM."""
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert payload["ISM_Score_NLP__c"] == 0.91

    def test_payload_lead_source(self, sample_lead):
        """La source est fixe : elle permet d'isoler les leads issus du chatbot."""
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert payload["LeadSource"] == "ISMaiLa Chatbot"

    def test_description_contains_conversation_summary(self, sample_lead):
        """Le commercial doit retrouver la conversation dans la description."""
        from services.sf_connector import build_sf_payload
        payload = build_sf_payload(sample_lead)
        assert "Frais MBA ?" in payload["Description"]

    def test_payload_general_fallback_category(self, sample_lead, monkeypatch):
        """Une catégorie hors référentiel retombe sur la campagne générale
        plutôt que de produire un nom de campagne inexistant côté Salesforce."""
        from services import sf_connector
        sample_lead["interest"] = "CategorieinconnueXYZ"
        payload = sf_connector.build_sf_payload(sample_lead)
        assert "General" in payload["ISM_Campaign__c"]


# ══════════════════════════════════════════════════════════════════════
#  sync_to_salesforce
# ══════════════════════════════════════════════════════════════════════

class TestSyncToSalesforce:
    """RG-06 : la synchronisation est « best effort » et ne perd jamais un lead."""

    def test_returns_false_when_no_webhook_url(self, sample_lead, mock_leads_col, monkeypatch):
        """Sans webhook configuré, la synchro est désactivée — sans lever d'erreur."""
        from services import sf_connector
        monkeypatch.setattr(sf_connector, "SF_WEBHOOK_URL", None)
        result = sf_connector.sync_to_salesforce(sample_lead)
        assert result is False

    def test_returns_true_on_200(self, sample_lead, mock_leads_col, monkeypatch):
        """Seul un HTTP 200 vaut succès."""
        from services import sf_connector
        monkeypatch.setattr(sf_connector, "SF_WEBHOOK_URL", "https://hook.make.com/test")
        mock_response = MagicMock(status_code=200)
        with patch("requests.post", return_value=mock_response):
            result = sf_connector.sync_to_salesforce(sample_lead)
        assert result is True

    def test_returns_false_on_non_200(self, sample_lead, mock_leads_col, monkeypatch):
        """Une erreur serveur ne doit pas être prise pour un succès."""
        from services import sf_connector
        monkeypatch.setattr(sf_connector, "SF_WEBHOOK_URL", "https://hook.make.com/test")
        mock_response = MagicMock(status_code=500)
        with patch("requests.post", return_value=mock_response):
            result = sf_connector.sync_to_salesforce(sample_lead)
        assert result is False

    def test_returns_false_on_timeout(self, sample_lead, mock_leads_col, monkeypatch):
        """Un webhook lent est abandonné sans propager l'exception : l'interface
        ne doit jamais rester bloquée sur Salesforce."""
        import requests as req_module
        from services import sf_connector
        monkeypatch.setattr(sf_connector, "SF_WEBHOOK_URL", "https://hook.make.com/test")
        with patch("requests.post", side_effect=req_module.exceptions.Timeout):
            result = sf_connector.sync_to_salesforce(sample_lead)
        assert result is False

    def test_updates_is_synced_sf_on_success(self, sample_lead, mock_leads_col, monkeypatch):
        """Le succès est tracé en base — sinon le lead serait renvoyé indéfiniment."""
        from services import sf_connector
        monkeypatch.setattr(sf_connector, "SF_WEBHOOK_URL", "https://hook.make.com/test")
        mock_response = MagicMock(status_code=200)
        with patch("requests.post", return_value=mock_response):
            sf_connector.sync_to_salesforce(sample_lead)
        mock_leads_col.update_one.assert_called_once()
        update_set = mock_leads_col.update_one.call_args[0][1]["$set"]
        assert update_set["is_synced_sf"] is True

    def test_does_not_update_on_failure(self, sample_lead, mock_leads_col, monkeypatch):
        """En cas d'échec, `is_synced_sf` reste False : le lead sera repris par
        le job de rattrapage."""
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
    """Le rattrapage doit reprendre tous les leads en attente et rester silencieux
    face à une panne de base."""

    def test_retries_all_unsynced_leads(self, mock_leads_col, monkeypatch):
        """Chaque lead non synchronisé est renvoyé, et le compte-rendu le dit."""
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
        """Base indisponible → message d'erreur lisible, pas une exception
        remontée jusqu'au dashboard admin."""
        from services import sf_connector
        from services.db_connector import db_instance
        def raise_err(name):
            raise RuntimeError("DB down")
        monkeypatch.setattr(db_instance, "get_collection", raise_err)

        msg = sf_connector.retry_failed_leads()
        assert "Erreur" in msg or "❌" in msg