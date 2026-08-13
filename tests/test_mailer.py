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
    # Neutralise la config d'expéditeur du .env local : sans cela, les tests
    # dépendraient de l'environnement de la machine.
    monkeypatch.setattr(mailer_module, "SMTP_FROM",      None)
    monkeypatch.setattr(mailer_module, "SMTP_FROM_NAME", "ISMaiLa")
    monkeypatch.setattr(mailer_module, "SMTP_REPLY_TO",  "")
    monkeypatch.setattr(mailer_module, "SMTP_SSL",       False)


@pytest.fixture
def mock_smtp():
    """Serveur SMTP factice. Permet d'inspecter le message réellement construit."""
    with patch("smtplib.SMTP") as smtp_class:
        smtp_instance = MagicMock()
        smtp_class.return_value.__enter__.return_value = smtp_instance
        yield smtp_instance


# ══════════════════════════════════════════════════════════════════════
#  Tests _send (utilitaire interne)
# ══════════════════════════════════════════════════════════════════════

class TestSend:
    """`_send` ne doit jamais lever : elle renvoie un booléen quoi qu'il arrive.

    Ses appelants (certification, alerte expert) ne peuvent pas échouer parce
    qu'un email n'est pas parti.
    """

    def test_returns_true_on_success(self, mock_smtp):
        """Envoi nominal."""
        result = _send("dest@test.sn", "Sujet test", "Corps texte")
        assert result is True

    def test_returns_false_when_no_credentials(self, monkeypatch):
        """Mailer non configuré → échec propre, sans tentative de connexion."""
        monkeypatch.setattr(mailer_module, "SMTP_USER", None)
        result = _send("dest@test.sn", "Sujet", "Corps")
        assert result is False

    def test_returns_false_on_smtp_exception(self, monkeypatch):
        """Serveur injoignable → False, l'exception ne remonte pas à l'appelant."""
        monkeypatch.setattr(mailer_module, "SMTP_USER", "user@test.sn")
        with patch("smtplib.SMTP", side_effect=Exception("connexion refusée")):
            result = _send("dest@test.sn", "Sujet", "Corps")
        assert result is False

    def test_calls_starttls_and_login(self, mock_smtp):
        """La connexion est chiffrée et authentifiée — jamais en clair."""
        _send("dest@test.sn", "Sujet", "Corps")
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("test@ismaila.sn", "fake_pass")

    def test_send_message_called(self, mock_smtp):
        """Le message est bien remis au serveur, une seule fois."""
        _send("dest@test.sn", "Sujet", "Corps")
        mock_smtp.send_message.assert_called_once()


class TestEnTetes:
    """En-têtes exigés pour la délivrabilité (Microsoft 365 pénalise leur absence)."""

    def _message(self, mock_smtp):
        """Envoie un message quelconque et retourne l'objet MIME construit."""
        _send("dest@test.sn", "Sujet", "Corps")
        return mock_smtp.send_message.call_args[0][0]

    def test_date_et_message_id_presents(self, mock_smtp):
        """Ces deux en-têtes sont ajoutés par nous : on ne dépend pas du serveur,
        dont le comportement varie selon l'hébergeur."""
        msg = self._message(mock_smtp)
        assert msg["Date"], "En-tête Date manquant"
        assert msg["Message-ID"], "En-tête Message-ID manquant"

    def test_from_par_defaut_sur_le_compte_authentifie(self, mock_smtp):
        """Sans `SMTP_FROM`, l'expéditeur affiché est le compte authentifié —
        la configuration la plus sûre en délivrabilité."""
        msg = self._message(mock_smtp)
        assert "test@ismaila.sn" in msg["From"]

    def test_from_personnalisable(self, mock_smtp, monkeypatch):
        """`SMTP_FROM` et `SMTP_FROM_NAME` composent l'expéditeur affiché."""
        monkeypatch.setattr(mailer_module, "SMTP_FROM", "no-reply@ism.sn")
        monkeypatch.setattr(mailer_module, "SMTP_FROM_NAME", "ISMaiLa Pilote")
        msg = self._message(mock_smtp)
        assert msg["From"] == "ISMaiLa Pilote <no-reply@ism.sn>"

    def test_enveloppe_reste_le_compte_authentifie(self, mock_smtp, monkeypatch):
        """SPF s'évalue sur l'expéditeur d'enveloppe : il doit rester le compte SMTP."""
        monkeypatch.setattr(mailer_module, "SMTP_FROM", "no-reply@ism.sn")
        _send("dest@test.sn", "Sujet", "Corps")
        assert mock_smtp.send_message.call_args[1]["from_addr"] == "test@ismaila.sn"

    def test_reply_to_absent_par_defaut(self, mock_smtp):
        """Pas de `Reply-To` vide : un en-tête inutile nuit au score anti-spam."""
        assert self._message(mock_smtp)["Reply-To"] is None

    def test_reply_to_ajoute_si_configure(self, mock_smtp, monkeypatch):
        """Configuré, il permet de répondre à une boîte ISM même si l'envoi
        technique passe par un compte de service externe."""
        monkeypatch.setattr(mailer_module, "SMTP_REPLY_TO", "support@ism.sn")
        assert self._message(mock_smtp)["Reply-To"] == "support@ism.sn"

    def test_objet_sans_saut_de_ligne(self, mock_smtp):
        """Anti-injection d'en-têtes : un CR/LF dans l'objet est neutralisé."""
        _send("dest@test.sn", "Sujet\r\nBcc: pirate@mal.sn", "Corps")
        msg = mock_smtp.send_message.call_args[0][0]
        assert "\n" not in msg["Subject"] and "\r" not in msg["Subject"]
        assert msg["Bcc"] is None


# ══════════════════════════════════════════════════════════════════════
#  Tests send_answer_to_student
# ══════════════════════════════════════════════════════════════════════

class TestSendAnswerToStudent:
    """Notification de l'étudiant à la certification de sa question.

    C'est la boucle de retour du système : l'étudiant doit retrouver sa
    question, la réponse et l'identité du certificateur.
    """

    def test_returns_true_on_success(self, mock_smtp):
        """Envoi nominal de la réponse certifiée."""
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
        """La réponse est dans le corps du mail : l'étudiant n'a pas à se
        reconnecter pour la lire."""
        captured = []
        with patch("services.mailer._send", side_effect=lambda *a, **kw: captured.append(a) or True):
            send_answer_to_student("e@t.sn", "Q?", "Réponse certifiée ici.", "V")
        assert any("Réponse certifiée ici." in str(arg) for arg in captured[0])

    def test_subject_contains_certified_keyword(self, mock_smtp):
        """L'objet annonce la certification : c'est ce qui distingue ce mail
        d'une simple notification dans une boîte encombrée."""
        captured = []
        with patch("services.mailer._send", side_effect=lambda *a, **kw: captured.append(a) or True):
            send_answer_to_student("e@t.sn", "Q?", "R.", "V")
        subject = captured[0][1]
        assert "certifi" in subject.lower()


# ══════════════════════════════════════════════════════════════════════
#  Tests send_new_question_alert
# ══════════════════════════════════════════════════════════════════════

class TestSendNewQuestionAlert:
    """RG-03 : alerte ciblée vers l'expert d'un domaine.

    Le ciblage lui-même est fait par `search_controller` ; ici on vérifie que
    le message porte l'information dont l'expert a besoin pour trier.
    """

    def test_returns_true_on_success(self, mock_smtp):
        """Envoi nominal de l'alerte."""
        result = send_new_question_alert(
            expert_email = "expert@ism.sn",
            question     = "Y a-t-il des bourses ?",
            category     = "Bourses",
            asked_by     = "prospect@gmail.com",
        )
        assert result is True

    def test_subject_contains_category(self, mock_smtp):
        """La catégorie est dans l'objet : l'expert trie sans ouvrir le message."""
        captured = []
        with patch("services.mailer._send", side_effect=lambda *a, **kw: captured.append(a) or True):
            send_new_question_alert("e@t.sn", "Q?", "MBA", "user@t.sn")
        subject = captured[0][1]
        assert "MBA" in subject

    def test_body_contains_question(self, mock_smtp):
        """La question figure dans le corps : l'expert juge de l'urgence tout de suite."""
        captured = []
        with patch("services.mailer._send", side_effect=lambda *a, **kw: captured.append(a) or True):
            send_new_question_alert("e@t.sn", "Question unique ?", "Général", "u")
        assert any("Question unique ?" in str(arg) for arg in captured[0])


# ══════════════════════════════════════════════════════════════════════
#  Tests send_pending_digest
# ══════════════════════════════════════════════════════════════════════

class TestSendPendingDigest:
    """Digest des questions en attente.

    Fonction bas niveau conservée pour les usages ponctuels ; l'envoi groupé
    est désormais assuré par le Centre de Communication.
    """

    def _sample_questions(self):
        """Trois questions de domaines différents, jeu d'essai des tests."""
        return [
            {"question": "Frais MBA ?",       "category": "MBA"},
            {"question": "Bourses dispo ?",   "category": "Bourses"},
            {"question": "Dates inscription", "category": "Admission"},
        ]

    def test_returns_true_on_success(self, mock_smtp):
        """Envoi nominal du digest."""
        result = send_pending_digest(
            recipient_email = "validateur@ism.sn",
            recipient_name  = "Fatou Diallo",
            pending_count   = 3,
            top_questions   = self._sample_questions(),
            role            = "VALIDATEUR",
        )
        assert result is True

    def test_subject_contains_count(self, mock_smtp):
        """Le nombre de questions est dans l'objet : l'urgence est visible sans
        ouvrir le message."""
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
    """L'alias de compatibilité ascendante doit rester équivalent à la fonction
    qu'il remplace, sous peine de casser `search_controller`."""

    def test_alias_delegates_to_new_question_alert(self, mock_smtp):
        """send_expert_alert doit se comporter comme send_new_question_alert."""
        with patch("services.mailer.send_new_question_alert", return_value=True) as mock_fn:
            result = send_expert_alert("expert@ism.sn", "Question test ?")
        mock_fn.assert_called_once_with("expert@ism.sn", "Question test ?")
        assert result is True