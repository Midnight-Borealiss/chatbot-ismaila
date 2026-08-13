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
    """Contribution certifiée servant de réponse attendue dans les scénarios."""
    return {
        "_id":      ObjectId(),
        "question": "Quels sont les frais du MBA ?",
        "response": "Le MBA coûte 2 500 000 FCFA par an.",
        "status":   "valide",
        "category": "MBA",
    }


@pytest.fixture
def mock_nlp():
    """Moteur NLP factice : aucun modèle n'est chargé pendant les tests.

    Les valeurs par défaut décrivent le cas nominal (score au-dessus du seuil,
    classification confiante) ; chaque test surcharge ce dont il a besoin.
    """
    nlp = MagicMock()
    nlp.get_similarity_score.return_value = (0, 0.90)   # score > seuil par défaut
    nlp.classify_intent.return_value = "HOT"
    nlp.classify_category.return_value = "Scolarité"
    nlp.classify_category_full.return_value = ("Scolarité", "Service Administratif")
    nlp.assess_confidence.return_value = {
        "category": "Scolarité",
        "parent_category": "Service Administratif",
        "confidence": 0.9,
        "source": "consensus",
        "needs_review": False,
    }
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
    """RG-01 : une réponse n'est servie que si la confiance atteint le seuil.

    En deçà, mieux vaut faire attendre l'étudiant que lui donner une réponse
    approximative sur des sujets de scolarité ou d'admission.
    """

    def test_score_above_threshold_returns_certified_answer(self, search_ctrl, validated_doc):
        """Confiance suffisante → la réponse certifiée est servie telle quelle."""
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.90)
        result = search_ctrl.seek_answer("Frais MBA ?", {"email": "user@t.sn"})
        assert result["status"]   == "SUCCÈS"
        assert result["response"] == validated_doc["response"]

    def test_score_below_threshold_returns_waiting_message(self, search_ctrl):
        """Confiance insuffisante → message d'attente annonçant l'escalade experte."""
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.40)
        result = search_ctrl.seek_answer("Question obscure", {"email": "user@t.sn"})
        assert result["status"] == "ATTENTE"
        assert "expert" in result["response"].lower()

    def test_empty_kb_returns_empty_status(self, search_ctrl):
        """Base vide → message dédié, distinct d'une simple absence de réponse."""
        search_ctrl._mock_kb.count_documents.return_value = 0
        result = search_ctrl.seek_answer("Une question", {"email": "user@t.sn"})
        assert result["status"] == "VIDE"

    def test_score_at_threshold_is_success(self, search_ctrl):
        """Score exactement à 0.75 → SUCCÈS (limite incluse)."""
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.75)
        result = search_ctrl.seek_answer("Q?", {"email": "u@t.sn"})
        assert result["status"] == "SUCCÈS"

    def test_score_just_below_threshold_is_attente(self, search_ctrl):
        """Juste sous le seuil → escalade. Verrouille le sens de la comparaison."""
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.74)
        result = search_ctrl.seek_answer("Q?", {"email": "u@t.sn"})
        assert result["status"] == "ATTENTE"


# ══════════════════════════════════════════════════════════════════════
#  RG-03 : Création de ticket + alerte experts
# ══════════════════════════════════════════════════════════════════════

class TestRG03:
    """RG-03 : toute question sans réponse crée un ticket et alerte les experts.

    C'est le mécanisme qui alimente la base : sans lui, une lacune resterait
    invisible.
    """

    def test_ticket_created_when_no_answer(self, search_ctrl):
        """L'escalade laisse une trace exploitable par les validateurs."""
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.40)
        search_ctrl.seek_answer("Question sans réponse", {"email": "user@t.sn"})
        search_ctrl._mock_kb.insert_one.assert_called_once()

    def test_ticket_not_created_when_answer_found(self, search_ctrl):
        """Une question déjà couverte ne doit pas polluer la file d'attente."""
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.90)
        search_ctrl.seek_answer("Frais MBA ?", {"email": "user@t.sn"})
        search_ctrl._mock_kb.insert_one.assert_not_called()

    def test_expert_alert_sent_when_no_answer(self, search_ctrl):
        """L'expert du domaine est prévenu, avec la question et son auteur."""
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.40)
        expert = {"email": "expert@ism.sn", "role": "VALIDATEUR"}
        search_ctrl._mock_users.find.return_value = [expert]

        with patch("controllers.search_controller.send_new_question_alert") as mock_mail:
            search_ctrl.seek_answer("Question sans réponse", {"email": "u@t.sn"})
        mock_mail.assert_called_once_with(
            "expert@ism.sn", "Question sans réponse", "Scolarité", "u@t.sn"
        )

    def test_expert_not_alerted_when_answer_found(self, search_ctrl):
        """Pas d'alerte quand la base répond : les experts ne doivent pas être
        noyés sous des notifications inutiles."""
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.90)
        with patch("controllers.search_controller.send_new_question_alert") as mock_mail:
            search_ctrl.seek_answer("Frais MBA ?", {"email": "u@t.sn"})
        mock_mail.assert_not_called()

    def test_ticket_contains_user_email(self, search_ctrl):
        """Le ticket retient l'auteur : c'est lui qui sera notifié à la certification."""
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.40)
        search_ctrl.seek_answer("Q?", {"email": "prospect@test.sn"})
        call_kwargs = search_ctrl._mock_kb.insert_one.call_args[0][0]
        assert call_kwargs["user_email"] == "prospect@test.sn"

    def test_anonymous_user_logged_as_anonyme(self, search_ctrl):
        """Un visiteur sans email donne « anonyme », jamais une valeur vide ou nulle."""
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.40)
        search_ctrl.seek_answer("Q?", {})   # pas d'email
        call_kwargs = search_ctrl._mock_kb.insert_one.call_args[0][0]
        assert call_kwargs["user_email"] == "anonyme"


# ══════════════════════════════════════════════════════════════════════
#  RG-05 : Scoring d'intention et déclenchement capture
# ══════════════════════════════════════════════════════════════════════

class TestRG05:
    """RG-05 : le formulaire de contact n'apparaît qu'après un intérêt confirmé.

    Le déclenchement compte les questions HOT de la session, question courante
    comprise, et ne concerne que les visiteurs sans rôle : on ne sollicite pas
    un membre du personnel comme un prospect.
    """

    def test_trigger_capture_false_below_threshold(self, search_ctrl):
        """Sous le seuil de questions chaudes, on n'interrompt pas la conversation."""
        search_ctrl._mock_nlp.classify_intent.return_value = "HOT"
        # Session avec seulement 1 question HOT → pas encore 3
        history = [{"intent": "HOT"}, {"intent": "COLD"}]
        result  = search_ctrl.seek_answer("Frais ?", {"email": "u@t.sn"}, history)
        assert result["trigger_capture"] is False

    def test_trigger_capture_true_at_threshold(self, search_ctrl):
        """Au seuil atteint, le formulaire est proposé — limite incluse."""
        search_ctrl._mock_nlp.classify_intent.return_value = "HOT"
        # 2 HOT en historique + 1 HOT actuel = 3 → déclenchement
        history = [{"intent": "HOT"}, {"intent": "HOT"}]
        result  = search_ctrl.seek_answer("Inscription MBA ?", {"email": "u@t.sn"}, history)
        assert result["trigger_capture"] is True

    def test_cold_intent_does_not_trigger_capture(self, search_ctrl):
        """Le volume seul ne suffit pas : seules les questions chaudes comptent."""
        search_ctrl._mock_nlp.classify_intent.return_value = "COLD"
        history = [{"intent": "COLD"}, {"intent": "COLD"}]
        result  = search_ctrl.seek_answer("Horaires campus ?", {"email": "u@t.sn"}, history)
        assert result["trigger_capture"] is False

    def test_intent_returned_in_result(self, search_ctrl):
        """L'intention est exposée à l'appelant : la vue en a besoin pour le suivi."""
        search_ctrl._mock_nlp.classify_intent.return_value = "WARM"
        result = search_ctrl.seek_answer("Programme ?", {"email": "u@t.sn"})
        assert result["intent"] == "WARM"


# ══════════════════════════════════════════════════════════════════════
#  Traçabilité
# ══════════════════════════════════════════════════════════════════════

class TestLogging:
    """Chaque échange est journalisé : c'est la matière des statistiques admin
    et de la mesure du taux d'automatisation."""

    def test_every_query_is_logged(self, search_ctrl):
        """Aucune question ne passe sans laisser de trace, réponse ou non."""
        search_ctrl.seek_answer("Une question", {"email": "u@t.sn"})
        search_ctrl._mock_logs.insert_one.assert_called_once()

    def test_log_contains_score(self, search_ctrl):
        """Le score est journalisé sans perte : il alimente la distribution
        par tranches du tableau de bord."""
        search_ctrl._mock_nlp.get_similarity_score.return_value = (0, 0.88)
        search_ctrl.seek_answer("Q?", {"email": "u@t.sn"})
        logged = search_ctrl._mock_logs.insert_one.call_args[0][0]
        assert abs(logged["score"] - 0.88) < 0.001

    def test_log_contains_intent(self, search_ctrl):
        """L'intention est journalisée : elle sert au suivi commercial (RG-05)."""
        search_ctrl._mock_nlp.classify_intent.return_value = "HOT"
        search_ctrl.seek_answer("Q?", {"email": "u@t.sn"})
        logged = search_ctrl._mock_logs.insert_one.call_args[0][0]
        assert logged["intent"] == "HOT"