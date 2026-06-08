"""
Tests du SearchController.
Couvre : RG-01 (seuil NLP), RG-03 (alerte expert), RG-05 (scoring intent),
         création de ticket, logging, mode KB vide.
Le NLP engine et MongoDB sont mockés — pas de modèle chargé en test.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from bson import ObjectId


# ══════════════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def validated_doc():
    return {
        "_id":      ObjectId(),
        "question": "Quels sont les frais du MBA ?",
        "response": "Le MBA coûte 2 500 000 FCFA par an.",
        "status":   "valide",
        "category": "MBA",
    }


@pytest.fixture
def mock_nlp():
    nlp = MagicMock()
    nlp.get_similarity_score.return_value = (0, 0.90)   # score > seuil par défaut
    nlp.classify_intent.return_value = "HOT"
    nlp.classify_category.return_value = "Scolarité"
    nlp.classify_category_full.return_value = ("Scolarité", "Service Administratif")
    nlp.embed.return_value = None
    return nlp


@pytest.fixture
def search_ctrl(monkeypatch, validated_doc, mock_nlp):
    """SearchController avec MongoDB et NLP complètement mockés."""
    from services.db_connector import db_instance
    mock_kb   = MagicMock()
    mock_logs = MagicMock()
    mock_users = MagicMock()

    mock_kb.find.return_value   = [validated_doc]
    mock_kb.count_documents.return_value = 1   # base non vide par défaut
    mock_kb.insert_one.return_value = MagicMock(inserted_id=ObjectId())
    mock_logs.insert_one.return_value = MagicMock()
    mock_users.find.return_value = []

    def get_col(name):
        return {"contributions": mock_kb, "logs_interactions": mock_logs, "users": mock_users}.get(name, MagicMock())

    monkeypatch.setattr(db_instance, "get_collection", get_col)
    monkeypatch.setattr(db_instance, "is_alive", lambda: True)
    monkeypatch.setattr(db_instance, "db", MagicMock())
    # Nouveau moteur : singleton nlp_engine importé dans le module.
    monkeypatch.setattr("controllers.search_controller.nlp_engine", mock_nlp)

    from controllers.search_controller import SearchController
    from config.settings import NLP_THRESHOLD
    ctrl = SearchController()

    # Stub du moteur de correspondance : le score est piloté par le mock NLP
    # (get_similarity_score), ce qui préserve les scénarios de seuil par test.
    def fake_find(query, query_filter):
        _, score = ctrl._mock_nlp.get_similarity_score.return_value
        return validated_doc, score, score >= NLP_THRESHOLD
    ctrl._find_best_answer = fake_find

    ctrl._mock_kb    = mock_kb
    ctrl._mock_logs  = mock_logs
    ctrl._mock_users = mock_users
    ctrl._mock_nlp   = mock_nlp
    return ctrl


# ══════════════════════════════════════════════════════════════════════
#  RG-01 : Seuil de confiance NLP
# ══════════════════════════════════════════════════════════════════════

class TestRG01:

    def test_score_above_threshold_returns_certified_answer(self, search_ctrl, validated_doc):
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.90)
        result = search_ctrl.seek_answer("Frais MBA ?", {"email": "user@t.sn"})
        assert result["status"]   == "SUCCÈS"
        assert result["response"] == validated_doc["response"]

    def test_score_below_threshold_returns_waiting_message(self, search_ctrl):
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.40)
        result = search_ctrl.seek_answer("Question obscure", {"email": "user@t.sn"})
        assert result["status"] == "ATTENTE"
        assert "expert" in result["response"].lower()

    def test_empty_kb_returns_empty_status(self, search_ctrl):
        search_ctrl._mock_kb.count_documents.return_value = 0
        result = search_ctrl.seek_answer("Une question", {"email": "user@t.sn"})
        assert result["status"] == "VIDE"

    def test_score_at_threshold_is_success(self, search_ctrl):
        """Score exactement à 0.75 → SUCCÈS (limite incluse)."""
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.75)
        result = search_ctrl.seek_answer("Q?", {"email": "u@t.sn"})
        assert result["status"] == "SUCCÈS"

    def test_score_just_below_threshold_is_attente(self, search_ctrl):
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.74)
        result = search_ctrl.seek_answer("Q?", {"email": "u@t.sn"})
        assert result["status"] == "ATTENTE"


# ══════════════════════════════════════════════════════════════════════
#  RG-03 : Création de ticket + alerte experts
# ══════════════════════════════════════════════════════════════════════

class TestRG03:

    def test_ticket_created_when_no_answer(self, search_ctrl):
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.40)
        search_ctrl.seek_answer("Question sans réponse", {"email": "user@t.sn"})
        search_ctrl._mock_kb.insert_one.assert_called_once()

    def test_ticket_not_created_when_answer_found(self, search_ctrl):
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.90)
        search_ctrl.seek_answer("Frais MBA ?", {"email": "user@t.sn"})
        search_ctrl._mock_kb.insert_one.assert_not_called()

    def test_expert_alert_sent_when_no_answer(self, search_ctrl):
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.40)
        expert = {"email": "expert@ism.sn", "role": "VALIDATEUR"}
        search_ctrl._mock_users.find.return_value = [expert]

        with patch("controllers.search_controller.send_new_question_alert") as mock_mail:
            search_ctrl.seek_answer("Question sans réponse", {"email": "u@t.sn"})
        mock_mail.assert_called_once_with(
            "expert@ism.sn", "Question sans réponse", "Scolarité", "u@t.sn"
        )

    def test_expert_not_alerted_when_answer_found(self, search_ctrl):
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.90)
        with patch("controllers.search_controller.send_new_question_alert") as mock_mail:
            search_ctrl.seek_answer("Frais MBA ?", {"email": "u@t.sn"})
        mock_mail.assert_not_called()

    def test_ticket_contains_user_email(self, search_ctrl):
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.40)
        search_ctrl.seek_answer("Q?", {"email": "prospect@test.sn"})
        call_kwargs = search_ctrl._mock_kb.insert_one.call_args[0][0]
        assert call_kwargs["user_email"] == "prospect@test.sn"

    def test_anonymous_user_logged_as_anonyme(self, search_ctrl):
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.40)
        search_ctrl.seek_answer("Q?", {})   # pas d'email
        call_kwargs = search_ctrl._mock_kb.insert_one.call_args[0][0]
        assert call_kwargs["user_email"] == "anonyme"


# ══════════════════════════════════════════════════════════════════════
#  RG-05 : Scoring d'intention et déclenchement capture
# ══════════════════════════════════════════════════════════════════════

class TestRG05:

    def test_trigger_capture_false_below_threshold(self, search_ctrl):
        search_ctrl._mock_nlp.classify_intent.return_value = "HOT"
        # Session avec seulement 1 question HOT → pas encore 3
        history = [{"intent": "HOT"}, {"intent": "COLD"}]
        result  = search_ctrl.seek_answer("Frais ?", {"email": "u@t.sn"}, history)
        assert result["trigger_capture"] is False

    def test_trigger_capture_true_at_threshold(self, search_ctrl):
        search_ctrl._mock_nlp.classify_intent.return_value = "HOT"
        # 2 HOT en historique + 1 HOT actuel = 3 → déclenchement
        history = [{"intent": "HOT"}, {"intent": "HOT"}]
        result  = search_ctrl.seek_answer("Inscription MBA ?", {"email": "u@t.sn"}, history)
        assert result["trigger_capture"] is True

    def test_cold_intent_does_not_trigger_capture(self, search_ctrl):
        search_ctrl._mock_nlp.classify_intent.return_value = "COLD"
        history = [{"intent": "COLD"}, {"intent": "COLD"}]
        result  = search_ctrl.seek_answer("Horaires campus ?", {"email": "u@t.sn"}, history)
        assert result["trigger_capture"] is False

    def test_intent_returned_in_result(self, search_ctrl):
        search_ctrl._mock_nlp.classify_intent.return_value = "WARM"
        result = search_ctrl.seek_answer("Programme ?", {"email": "u@t.sn"})
        assert result["intent"] == "WARM"


# ══════════════════════════════════════════════════════════════════════
#  Traçabilité
# ══════════════════════════════════════════════════════════════════════

class TestLogging:

    def test_every_query_is_logged(self, search_ctrl):
        search_ctrl.seek_answer("Une question", {"email": "u@t.sn"})
        search_ctrl._mock_logs.insert_one.assert_called_once()

    def test_log_contains_score(self, search_ctrl):
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.88)
        search_ctrl.seek_answer("Q?", {"email": "u@t.sn"})
        logged = search_ctrl._mock_logs.insert_one.call_args[0][0]
        assert abs(logged["score"] - 0.88) < 0.001

    def test_log_contains_intent(self, search_ctrl):
        search_ctrl._mock_nlp.classify_intent.return_value = "HOT"
        search_ctrl.seek_answer("Q?", {"email": "u@t.sn"})
        logged = search_ctrl._mock_logs.insert_one.call_args[0][0]
        assert logged["intent"] == "HOT"