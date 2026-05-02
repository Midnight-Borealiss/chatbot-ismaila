"""
Tests du module mailer.
Tous les envois SMTP sont mockés — aucun email réel n'est envoyé.
On vérifie : construction du message, routing, gestion des erreurs.
"""

import pytest
from unittest.mock import patch, MagicMock, call

import services.mailer as mailer_module
from services.mailer import (
    send_answer_to_student,
    send_new_question_alert,
    send_pending_digest,
    send_expert_alert,
    _send,
)


# ══════════════════════════════════════════════════════════════════════
#  Helper : patch SMTP + variables d'env
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def patch_smtp_config(monkeypatch):
    """Injecte de faux credentials SMTP pour tous les tests du fichier."""
    monkeypatch.setattr(mailer_module, "SMTP_USER",   "test@ismaila.sn")
    monkeypatch.setattr(mailer_module, "SMTP_PASS",   "fake_pass")
    monkeypatch.setattr(mailer_module, "SMTP_SERVER", "smtp.test.sn")
    monkeypatch.setattr(mailer_module, "SMTP_PORT",   587)


@pytest.fixture
def mock_smtp():
    with patch("smtplib.SMTP") as smtp_class:
        smtp_instance = MagicMock()
        smtp_class.return_value.__enter__.return_value = smtp_instance
        yield smtp_instance


# ══════════════════════════════════════════════════════════════════════
#  Tests _send (utilitaire interne)
# ══════════════════════════════════════════════════════════════════════

class TestSend:

    def test_returns_true_on_success(self, mock_smtp):
        result = _send("dest@test.sn", "Sujet test", "Corps texte")
        assert result is True

    def test_returns_false_when_no_credentials(self, monkeypatch):
        monkeypatch.setattr(mailer_module, "SMTP_USER", None)
        result = _send("dest@test.sn", "Sujet", "Corps")
        assert result is False

    def test_returns_false_on_smtp_exception(self, monkeypatch):
        monkeypatch.setattr(mailer_module, "SMTP_USER", "user@test.sn")
        with patch("smtplib.SMTP", side_effect=Exception("connexion refusée")):
            result = _send("dest@test.sn", "Sujet", "Corps")
        assert result is False

    def test_calls_starttls_and_login(self, mock_smtp):
        _send("dest@test.sn", "Sujet", "Corps")
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("test@ismaila.sn", "fake_pass")

    def test_send_message_called(self, mock_smtp):
        _send("dest@test.sn", "Sujet", "Corps")
        mock_smtp.send_message.assert_called_once()


# ══════════════════════════════════════════════════════════════════════
#  Tests send_answer_to_student
# ══════════════════════════════════════════════════════════════════════

class TestSendAnswerToStudent:

    def test_returns_true_on_success(self, mock_smtp):
        result = send_answer_to_student(
            student_email  = "etudiant@test.sn",
            question       = "Quels sont les frais du MBA ?",
            answer         = "Le MBA coûte 2 500 000 FCFA par an.",
            validator_name = "Dr. Diallo",
        )
        assert result is True

    def test_message_contains_question(self, mock_smtp):
        """Le corps du mail doit mentionner la question posée."""
        captured = []
        original_send = _send
        with patch("services.mailer._send", side_effect=lambda *a, **kw: captured.append(a) or True):
            send_answer_to_student(
                "e@t.sn", "Question test ?", "Réponse test.", "Validateur"
            )
        assert any("Question test ?" in str(arg) for arg in captured[0])

    def test_message_contains_answer(self, mock_smtp):
        captured = []
        with patch("services.mailer._send", side_effect=lambda *a, **kw: captured.append(a) or True):
            send_answer_to_student("e@t.sn", "Q?", "Réponse certifiée ici.", "V")
        assert any("Réponse certifiée ici." in str(arg) for arg in captured[0])

    def test_subject_contains_certified_keyword(self, mock_smtp):
        captured = []
        with patch("services.mailer._send", side_effect=lambda *a, **kw: captured.append(a) or True):
            send_answer_to_student("e@t.sn", "Q?", "R.", "V")
        subject = captured[0][1]
        assert "certifi" in subject.lower()


# ══════════════════════════════════════════════════════════════════════
#  Tests send_new_question_alert
# ══════════════════════════════════════════════════════════════════════

class TestSendNewQuestionAlert:

    def test_returns_true_on_success(self, mock_smtp):
        result = send_new_question_alert(
            expert_email = "expert@ism.sn",
            question     = "Y a-t-il des bourses ?",
            category     = "Bourses",
            asked_by     = "prospect@gmail.com",
        )
        assert result is True

    def test_subject_contains_category(self, mock_smtp):
        captured = []
        with patch("services.mailer._send", side_effect=lambda *a, **kw: captured.append(a) or True):
            send_new_question_alert("e@t.sn", "Q?", "MBA", "user@t.sn")
        subject = captured[0][1]
        assert "MBA" in subject

    def test_body_contains_question(self, mock_smtp):
        captured = []
        with patch("services.mailer._send", side_effect=lambda *a, **kw: captured.append(a) or True):
            send_new_question_alert("e@t.sn", "Question unique ?", "Général", "u")
        assert any("Question unique ?" in str(arg) for arg in captured[0])


# ══════════════════════════════════════════════════════════════════════
#  Tests send_pending_digest
# ══════════════════════════════════════════════════════════════════════

class TestSendPendingDigest:

    def _sample_questions(self):
        return [
            {"question": "Frais MBA ?",       "category": "MBA"},
            {"question": "Bourses dispo ?",   "category": "Bourses"},
            {"question": "Dates inscription", "category": "Admission"},
        ]

    def test_returns_true_on_success(self, mock_smtp):
        result = send_pending_digest(
            recipient_email = "validateur@ism.sn",
            recipient_name  = "Fatou Diallo",
            pending_count   = 3,
            top_questions   = self._sample_questions(),
            role            = "VALIDATEUR",
        )
        assert result is True

    def test_subject_contains_count(self, mock_smtp):
        captured = []
        with patch("services.mailer._send", side_effect=lambda *a, **kw: captured.append(a) or True):
            send_pending_digest("e@t.sn", "Fatou", 7, self._sample_questions())
        subject = captured[0][1]
        assert "7" in subject

    def test_contributor_action_word(self, mock_smtp):
        """Pour un contributeur, le message doit parler de 'proposer'."""
        captured = []
        with patch("services.mailer._send", side_effect=lambda *a, **kw: captured.append(a) or True):
            send_pending_digest("e@t.sn", "Moussa", 2, self._sample_questions(), role="CONTRIBUTEUR")
        body = str(captured[0])
        assert "proposer" in body.lower()

    def test_validator_action_word(self, mock_smtp):
        """Pour un validateur, le message doit parler de 'certifier'."""
        captured = []
        with patch("services.mailer._send", side_effect=lambda *a, **kw: captured.append(a) or True):
            send_pending_digest("e@t.sn", "Fatou", 2, self._sample_questions(), role="VALIDATEUR")
        body = str(captured[0])
        assert "certifier" in body.lower()

    def test_only_first_five_questions_shown(self, mock_smtp):
        """Maximum 5 questions dans le digest même si on en passe plus."""
        many_questions = [{"question": f"Q{i}?", "category": "Général"} for i in range(10)]
        captured = []
        with patch("services.mailer._send", side_effect=lambda *a, **kw: captured.append(a) or True):
            send_pending_digest("e@t.sn", "X", 10, many_questions)
        body = str(captured[0])
        # Q5..Q9 ne doivent pas apparaître
        assert "Q6?" not in body
        assert "Q0?" in body


# ══════════════════════════════════════════════════════════════════════
#  Tests send_expert_alert (alias)
# ══════════════════════════════════════════════════════════════════════

class TestSendExpertAlertAlias:

    def test_alias_delegates_to_new_question_alert(self, mock_smtp):
        """send_expert_alert doit se comporter comme send_new_question_alert."""
        with patch("services.mailer.send_new_question_alert", return_value=True) as mock_fn:
            result = send_expert_alert("expert@ism.sn", "Question test ?")
        mock_fn.assert_called_once_with("expert@ism.sn", "Question test ?")
        assert result is True