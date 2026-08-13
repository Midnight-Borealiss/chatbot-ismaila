"""
Tests du Centre de Communication.

Ce contrôleur est le plus sensible de l'application : il envoie des messages en
masse et **réinitialise des mots de passe**. Les garde-fous qu'il embarque
(exclusion de l'expéditeur, rédaction du mot de passe en notification, refus du
mode programmé, réclamation atomique des campagnes) ne sont pas des détails
d'implémentation : ce sont des propriétés de sécurité. Ils sont testés ici pour
qu'une refonte future ne puisse pas les retirer en silence.

Aucun accès réel à MongoDB ni à SMTP — tout est mocké.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from config.roles import ADMIN, SUPER_ADMIN, VALIDATOR, CONTRIBUTOR, STUDENT
from controllers.communication_controller import (
    CommunicationController, default_blocks, unknown_variables,
    BLOCK_DEFINITIONS, VARIABLES_CONNUES,
)


# ══════════════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def cols():
    """Une fausse collection distincte par nom, inspectable individuellement.

    Le mock partagé de `conftest` ne convient pas ici : plusieurs tests doivent
    vérifier qu'on écrit dans `campaigns` sans toucher à `users`.
    """
    store = {}
    for name in ("users", "contributions", "campaigns", "message_templates",
                 "message_blocks", "logs_admin"):
        col = MagicMock(name=name)
        col.find.return_value = []
        col.find_one.return_value = None
        col.insert_one.return_value = MagicMock(inserted_id="camp_1")
        col.update_one.return_value = MagicMock(modified_count=1)
        col.find_one_and_update.return_value = None
        col.count_documents.return_value = 0
        col.delete_one.return_value = MagicMock(deleted_count=1)
        store[name] = col
    return store


@pytest.fixture
def cc(cols, monkeypatch):
    """Contrôleur neuf, branché sur les fausses collections."""
    from services.db_connector import db_instance
    monkeypatch.setattr(db_instance, "get_collection", lambda name: cols[name])
    return CommunicationController()


@pytest.fixture
def mock_canaux():
    """Neutralise les deux canaux de sortie : email et notification in-app."""
    with patch("controllers.communication_controller.send_campaign_email_ex") as mail, \
         patch("controllers.communication_controller.notification_instance") as notif:
        mail.return_value = (True, "")
        notif.create_notification.return_value = "notif_1"
        yield {"mail": mail, "notif": notif}


@pytest.fixture
def expediteur():
    """L'administrateur qui déclenche la campagne."""
    return {"email": "admin@ism.sn", "full_name": "Awa Ndiaye", "role": ADMIN}


# ══════════════════════════════════════════════════════════════════════
#  Assainissement de l'objet
# ══════════════════════════════════════════════════════════════════════

class TestSanitizeSubject:
    """Un objet contenant un CR/LF permettrait d'injecter des en-têtes SMTP
    arbitraires (Bcc caché, faux expéditeur)."""

    def test_supprime_les_sauts_de_ligne(self):
        """Le vecteur d'injection d'en-têtes."""
        propre = CommunicationController._sanitize_subject(
            "Bonjour\r\nBcc: pirate@ailleurs.com"
        )
        assert "\r" not in propre and "\n" not in propre
        assert "Bcc:" in propre  # neutralisé, pas censuré : il reste dans l'objet

    def test_borne_la_longueur(self):
        """Un objet démesuré est tronqué à 200 caractères."""
        assert len(CommunicationController._sanitize_subject("a" * 500)) == 200

    def test_accepte_une_valeur_vide(self):
        """Ne doit pas lever sur None (l'appelant substitue ensuite un défaut)."""
        assert CommunicationController._sanitize_subject(None) == ""


# ══════════════════════════════════════════════════════════════════════
#  Ciblage
# ══════════════════════════════════════════════════════════════════════

class TestResolveRecipients:
    """Le ciblage décide qui reçoit un message de masse : une erreur ici est
    visible par toute l'école."""

    def test_mode_all_ne_filtre_rien(self, cc, cols):
        """« Tout le monde » doit interroger la base sans critère."""
        cc.resolve_recipients({"mode": "all"})
        assert cols["users"].find.call_args[0][0] == {}

    def test_mode_person_cible_les_emails(self, cc, cols):
        """Envoi nominatif."""
        cc.resolve_recipients({"mode": "person", "emails": ["a@ism.sn"]})
        assert cols["users"].find.call_args[0][0] == {"email": {"$in": ["a@ism.sn"]}}

    def test_mode_services_interroge_le_scope(self, cc, cols):
        """Le rattachement est stocké sous `scope.services`."""
        cc.resolve_recipients({"mode": "services", "services": ["Scolarité"]})
        assert cols["users"].find.call_args[0][0] == {"scope.services": {"$in": ["Scolarité"]}}

    def test_mode_instituts_interroge_le_scope(self, cc, cols):
        """Idem pour les instituts."""
        cc.resolve_recipients({"mode": "instituts", "instituts": ["Institut Droit"]})
        assert cols["users"].find.call_args[0][0] == {"scope.instituts": {"$in": ["Institut Droit"]}}

    def test_mode_roles_etend_aux_anciennes_orthographes(self, cc, cols):
        """Régression : les comptes créés avant l'alignement des rôles portent
        encore l'étiquette anglaise. Les oublier revient à ne pas prévenir une
        partie des contributeurs."""
        cc.resolve_recipients({"mode": "roles", "roles": [CONTRIBUTOR]})
        vals = cols["users"].find.call_args[0][0]["role"]["$in"]
        assert "CONTRIBUTEUR" in vals
        assert "CONTRIBUTOR" in vals

    def test_mode_inconnu_retombe_sur_tout(self, cc, cols):
        """Une cible mal formée ne doit pas lever."""
        cc.resolve_recipients({"mode": "n_importe_quoi"})
        assert cols["users"].find.call_args[0][0] == {}

    def test_cible_absente_ne_leve_pas(self, cc):
        """`target` à None est toléré."""
        assert cc.resolve_recipients(None) == []

    def test_deduplique_les_adresses(self, cc, cols):
        """Un utilisateur présent deux fois (doublon en base) ne doit recevoir
        qu'un seul message."""
        cols["users"].find.return_value = [
            {"email": "a@ism.sn", "full_name": "A"},
            {"email": "a@ism.sn", "full_name": "A bis"},
        ]
        assert len(cc.resolve_recipients({"mode": "all"})) == 1

    def test_normalise_la_casse_des_adresses(self, cc, cols):
        """« A@ISM.SN » et « a@ism.sn » sont la même personne."""
        cols["users"].find.return_value = [
            {"email": "  A@ISM.SN  ", "full_name": "A"},
            {"email": "a@ism.sn", "full_name": "A"},
        ]
        result = cc.resolve_recipients({"mode": "all"})
        assert len(result) == 1
        assert result[0]["email"] == "a@ism.sn"

    def test_ignore_les_utilisateurs_sans_email(self, cc, cols):
        """Un compte sans adresse ne doit pas produire un envoi vide."""
        cols["users"].find.return_value = [{"full_name": "Sans adresse"}, {"email": "b@ism.sn"}]
        assert [u["email"] for u in cc.resolve_recipients({"mode": "all"})] == ["b@ism.sn"]

    def test_nom_par_defaut_sur_l_email(self, cc, cols):
        """Sans `full_name`, l'email sert de nom d'affichage."""
        cols["users"].find.return_value = [{"email": "b@ism.sn"}]
        assert cc.resolve_recipients({"mode": "all"})[0]["full_name"] == "b@ism.sn"

    def test_base_indisponible_retourne_liste_vide(self, cc, cols):
        """Mode survie : MongoDB injoignable ne doit pas propager d'exception."""
        cols["users"].find.side_effect = Exception("MongoDB down")
        assert cc.resolve_recipients({"mode": "all"}) == []

    def test_count_recipients_compte_les_uniques(self, cc, cols):
        """L'aperçu affiché avant envoi doit refléter la déduplication."""
        cols["users"].find.return_value = [
            {"email": "a@ism.sn"}, {"email": "a@ism.sn"}, {"email": "b@ism.sn"},
        ]
        assert cc.count_recipients({"mode": "all"}) == 2


# ══════════════════════════════════════════════════════════════════════
#  Personnalisation
# ══════════════════════════════════════════════════════════════════════

class TestPersonalize:
    """Les variables du message sont substituées avant envoi."""

    def test_remplace_prenom_nom_email(self):
        """Cas nominal."""
        texte = CommunicationController.personalize(
            "{prenom} / {nom} / {email}",
            {"full_name": "Fatou Diallo", "email": "f@ism.sn"},
        )
        assert texte == "Fatou / Fatou Diallo / f@ism.sn"

    def test_remplace_le_lien_par_l_url_plateforme(self):
        """`{lien}` est résolu au moment de l'envoi, pas au chargement du module :
        un lien redéfini dans l'interface doit s'appliquer sans redémarrage."""
        with patch("controllers.communication_controller.get_platform_url",
                   return_value="https://pilote.ism.sn"):
            texte = CommunicationController.personalize("{lien}", {"email": "f@ism.sn"})
        assert texte == "https://pilote.ism.sn"

    def test_ne_remplace_pas_le_mot_de_passe(self):
        """Garde-fou : la substitution de `{motdepasse}` dépend du canal et est
        faite dans `_dispatch`. Si `personalize` s'en chargeait, le mot de passe
        se retrouverait dans la notification persistée en base."""
        assert "{motdepasse}" in CommunicationController.personalize(
            "{motdepasse}", {"email": "f@ism.sn"}
        )

    def test_utilisateur_sans_nom_retombe_sur_l_email(self):
        """Pas de « Bonjour , » disgracieux."""
        assert CommunicationController.personalize("{prenom}", {"email": "f@ism.sn"}) == "f@ism.sn"

    def test_texte_vide_ne_leve_pas(self):
        """None est toléré."""
        assert CommunicationController.personalize(None, {"email": "f@ism.sn"}) == ""


# ══════════════════════════════════════════════════════════════════════
#  Récap automatique
# ══════════════════════════════════════════════════════════════════════

class TestBuildPendingRecap:
    """Le bloc « récap » est généré depuis la base, jamais saisi à la main."""

    def test_aucune_question_en_attente(self, cc, cols):
        """Message positif plutôt qu'un bloc vide."""
        cols["contributions"].find.return_value = []
        assert "aucune question" in cc.build_pending_recap().lower()

    def test_regroupe_par_pole(self, cc, cols):
        """Le récap compte les questions par pôle parent."""
        cols["contributions"].find.return_value = [
            {"question": "q1", "parent_category": "Scolarité"},
            {"question": "q2", "parent_category": "Scolarité"},
            {"question": "q3", "parent_category": "Admission"},
        ]
        recap = cc.build_pending_recap()
        assert "3 question(s)" in recap
        assert "Scolarité : 2 question(s)" in recap
        assert "Admission : 1 question(s)" in recap

    def test_ne_lit_que_les_questions_en_attente(self, cc, cols):
        """Une réponse déjà certifiée n'a rien à faire dans le récap."""
        cc.build_pending_recap()
        assert cols["contributions"].find.call_args[0][0] == {"status": "en_attente"}

    def test_base_indisponible_ne_leve_pas(self, cc, cols):
        """Mode survie."""
        cols["contributions"].find.side_effect = Exception("MongoDB down")
        assert isinstance(cc.build_pending_recap(), str)


# ══════════════════════════════════════════════════════════════════════
#  Distribution — le mot de passe ne doit pas fuir en base
# ══════════════════════════════════════════════════════════════════════

class TestDispatch:
    """`_dispatch` traite les deux canaux différemment, et c'est délibéré."""

    def test_mot_de_passe_en_clair_dans_l_email(self, cc, mock_canaux):
        """L'email est le seul véhicule légitime du mot de passe temporaire."""
        cc._dispatch("Objet", "Code : {motdepasse}",
                     [{"email": "a@ism.sn", "full_name": "A"}],
                     ["email"], temp_password="Temporaire2026")
        corps = mock_canaux["mail"].call_args[0][2]
        assert "Temporaire2026" in corps

    def test_mot_de_passe_redige_dans_la_notification(self, cc, mock_canaux):
        """**Garde-fou central** : la notification in-app est persistée dans
        MongoDB. Y écrire le mot de passe en clair annulerait le hachage bcrypt."""
        cc._dispatch("Objet", "Code : {motdepasse}",
                     [{"email": "a@ism.sn", "full_name": "A"}],
                     ["inapp"], temp_password="Temporaire2026")
        message = mock_canaux["notif"].create_notification.call_args.kwargs["message"]
        assert "Temporaire2026" not in message
        assert "(voir votre email)" in message

    def test_canal_email_seul_n_ecrit_aucune_notification(self, cc, mock_canaux):
        """Le choix des canaux est respecté."""
        cc._dispatch("Objet", "Corps", [{"email": "a@ism.sn", "full_name": "A"}], ["email"])
        mock_canaux["notif"].create_notification.assert_not_called()

    def test_canal_inapp_seul_n_envoie_aucun_email(self, cc, mock_canaux):
        """Symétrique."""
        cc._dispatch("Objet", "Corps", [{"email": "a@ism.sn", "full_name": "A"}], ["inapp"])
        mock_canaux["mail"].assert_not_called()

    def test_echec_email_conserve_la_cause(self, cc, mock_canaux):
        """Sans la cause exacte, un échec d'envoi est indiagnosticable — c'est
        précisément ce qui avait rendu l'incident de délivrabilité opaque."""
        mock_canaux["mail"].return_value = (False, "Adresse refusée par le serveur")
        records = cc._dispatch("Objet", "Corps",
                               [{"email": "a@ism.sn", "full_name": "A"}], ["email"])
        assert records[0]["email_status"] == "failed"
        assert records[0]["email_error"] == "Adresse refusée par le serveur"

    def test_personnalise_chaque_destinataire(self, cc, mock_canaux):
        """Chacun reçoit son propre prénom, pas celui du premier de la liste."""
        cc._dispatch("Objet", "Bonjour {prenom}", [
            {"email": "a@ism.sn", "full_name": "Awa Ndiaye"},
            {"email": "b@ism.sn", "full_name": "Moussa Sow"},
        ], ["email"])
        corps = [c[0][2] for c in mock_canaux["mail"].call_args_list]
        assert "Bonjour Awa" in corps[0]
        assert "Bonjour Moussa" in corps[1]


# ══════════════════════════════════════════════════════════════════════
#  Réinitialisation des mots de passe
# ══════════════════════════════════════════════════════════════════════

class TestResetPasswords:
    """La fonction la plus destructrice du module."""

    @pytest.fixture(autouse=True)
    def _hash(self):
        """Le hachage bcrypt réel est lent et sans intérêt ici."""
        with patch("controllers.auth_controller.AuthController.hash_password",
                   return_value="$2b$12$FAUX_HACHAGE") as h:
            yield h

    def test_stocke_un_hachage_jamais_le_clair(self, cc, cols):
        """Le mot de passe en clair ne doit jamais atteindre MongoDB."""
        cc._reset_passwords([{"email": "a@ism.sn"}], "Temporaire2026")
        maj = cols["users"].update_one.call_args[0][1]["$set"]
        assert maj["password_hash"] == "$2b$12$FAUX_HACHAGE"
        assert "Temporaire2026" not in str(maj)

    def test_force_le_changement_a_la_premiere_connexion(self, cc, cols):
        """Un mot de passe commun à plusieurs personnes doit être éphémère."""
        cc._reset_passwords([{"email": "a@ism.sn"}], "Temporaire2026")
        assert cols["users"].update_one.call_args[0][1]["$set"]["must_change_password"] is True

    def test_exclut_l_expediteur(self, cc, cols):
        """**Garde-fou** : un admin qui réinitialise tout le monde ne doit pas se
        verrouiller hors de la plateforme."""
        cc._reset_passwords(
            [{"email": "admin@ism.sn"}, {"email": "a@ism.sn"}],
            "Temporaire2026", exclude_email="admin@ism.sn",
        )
        cibles = [c[0][0]["email"] for c in cols["users"].update_one.call_args_list]
        assert cibles == ["a@ism.sn"]

    def test_exclusion_insensible_a_la_casse(self, cc, cols):
        """L'expéditeur saisi en majuscules reste protégé."""
        cc._reset_passwords([{"email": "admin@ism.sn"}], "Temporaire2026",
                            exclude_email="ADMIN@ISM.SN")
        cols["users"].update_one.assert_not_called()

    def test_sans_mot_de_passe_ne_touche_a_rien(self, cc, cols):
        """Une campagne ordinaire ne doit modifier aucun compte."""
        assert cc._reset_passwords([{"email": "a@ism.sn"}], "") == 0
        cols["users"].update_one.assert_not_called()

    def test_un_echec_n_interrompt_pas_les_autres(self, cc, cols):
        """Un compte en erreur ne doit pas priver les suivants de leurs accès."""
        cols["users"].update_one.side_effect = [
            Exception("écriture refusée"), MagicMock(modified_count=1),
        ]
        assert cc._reset_passwords(
            [{"email": "a@ism.sn"}, {"email": "b@ism.sn"}], "Temporaire2026"
        ) == 1


# ══════════════════════════════════════════════════════════════════════
#  Envoi de campagne
# ══════════════════════════════════════════════════════════════════════

class TestSendCampaign:
    """Validation, modes d'envoi et incompatibilités."""

    def test_refuse_un_message_vide(self, cc, expediteur):
        """Rien à dire, rien à envoyer."""
        res = cc.send_campaign(sender=expediteur, subject="S", body="   ",
                               target={"mode": "all"}, channels=["email"],
                               send_type="immediate")
        assert res["status"] == "error"

    def test_refuse_l_absence_de_canal(self, cc, expediteur):
        """Sans canal, l'envoi serait silencieusement perdu."""
        res = cc.send_campaign(sender=expediteur, subject="S", body="Corps",
                               target={"mode": "all"}, channels=[],
                               send_type="immediate")
        assert res["status"] == "error"

    def test_refuse_mot_de_passe_en_mode_programme(self, cc, expediteur):
        """**Garde-fou** : le mot de passe temporaire n'est jamais persisté. Une
        campagne programmée devrait le stocker en base pour l'envoyer plus tard —
        la combinaison est donc interdite, pas contournée."""
        res = cc.send_campaign(sender=expediteur, subject="S", body="Corps",
                               target={"mode": "all"}, channels=["email"],
                               send_type="scheduled",
                               scheduled_at=datetime.now() + timedelta(days=1),
                               temp_password="Temporaire2026")
        assert res["status"] == "error"
        assert "programm" in res["message"].lower()

    def test_programme_sans_date_est_refuse(self, cc, expediteur):
        """Une échéance manquante rendrait la campagne inenvoyable."""
        res = cc.send_campaign(sender=expediteur, subject="S", body="Corps",
                               target={"mode": "all"}, channels=["email"],
                               send_type="scheduled")
        assert res["status"] == "error"

    def test_programme_enregistre_sans_envoyer(self, cc, expediteur, mock_canaux):
        """Une campagne programmée ne part pas tout de suite."""
        res = cc.send_campaign(sender=expediteur, subject="S", body="Corps",
                               target={"mode": "all"}, channels=["email"],
                               send_type="scheduled",
                               scheduled_at=datetime.now() + timedelta(days=1))
        assert res["status"] == "scheduled"
        mock_canaux["mail"].assert_not_called()

    def test_mode_test_n_ecrit_qu_a_l_expediteur(self, cc, cols, expediteur, mock_canaux):
        """Le mode test doit rester sans conséquence, même si la cible est
        « tout le monde »."""
        cols["users"].find.return_value = [
            {"email": "etudiant1@ism.sn"}, {"email": "etudiant2@ism.sn"},
        ]
        cc.send_campaign(sender=expediteur, subject="S", body="Corps",
                         target={"mode": "all"}, channels=["email"], send_type="test")
        destinataires = [c[0][0] for c in mock_canaux["mail"].call_args_list]
        assert destinataires == ["admin@ism.sn"]

    def test_mode_test_ne_reinitialise_aucun_mot_de_passe(self, cc, cols, expediteur, mock_canaux):
        """Un test doit pouvoir être lancé sans crainte."""
        cc.send_campaign(sender=expediteur, subject="S", body="Corps",
                         target={"mode": "all"}, channels=["email"],
                         send_type="test", temp_password="Temporaire2026")
        cols["users"].update_one.assert_not_called()

    def test_refuse_une_cible_vide(self, cc, expediteur, mock_canaux):
        """Mieux vaut une erreur explicite qu'une campagne fantôme en base."""
        res = cc.send_campaign(sender=expediteur, subject="S", body="Corps",
                               target={"mode": "all"}, channels=["email"],
                               send_type="immediate")
        assert res["status"] == "error"

    def test_envoi_immediat_enregistre_et_journalise(self, cc, cols, expediteur, mock_canaux):
        """Non-répudiation : toute campagne laisse une trace admin."""
        cols["users"].find.return_value = [{"email": "a@ism.sn", "full_name": "A"}]
        res = cc.send_campaign(sender=expediteur, subject="S", body="Corps",
                               target={"mode": "all"}, channels=["email"],
                               send_type="immediate")
        assert res["status"] == "sent"
        cols["campaigns"].insert_one.assert_called_once()
        actions = [c[0][0]["action"] for c in cols["logs_admin"].insert_one.call_args_list]
        assert "campaign_sent" in actions

    def test_objet_assaini_avant_enregistrement(self, cc, cols, expediteur, mock_canaux):
        """L'objet stocké est le même que celui envoyé : déjà neutralisé."""
        cols["users"].find.return_value = [{"email": "a@ism.sn", "full_name": "A"}]
        cc.send_campaign(sender=expediteur, subject="S\r\nBcc: pirate@ailleurs.com",
                         body="Corps", target={"mode": "all"}, channels=["email"],
                         send_type="immediate")
        objet = cols["campaigns"].insert_one.call_args[0][0]["subject"]
        assert "\r" not in objet and "\n" not in objet

    def test_objet_vide_recoit_un_defaut(self, cc, cols, expediteur, mock_canaux):
        """Un email sans objet est un signal de spam."""
        cols["users"].find.return_value = [{"email": "a@ism.sn", "full_name": "A"}]
        cc.send_campaign(sender=expediteur, subject="", body="Corps",
                         target={"mode": "all"}, channels=["email"],
                         send_type="immediate")
        assert cols["campaigns"].insert_one.call_args[0][0]["subject"] == "Message ISMaiLa"

    def test_reinitialisation_journalisee_a_part(self, cc, cols, expediteur, mock_canaux):
        """Une réinitialisation de masse mérite sa propre entrée d'audit."""
        cols["users"].find.return_value = [{"email": "a@ism.sn", "full_name": "A"}]
        with patch("controllers.auth_controller.AuthController.hash_password",
                   return_value="$2b$12$FAUX"):
            cc.send_campaign(sender=expediteur, subject="S", body="Corps",
                             target={"mode": "all"}, channels=["email"],
                             send_type="immediate", temp_password="Temporaire2026")
        actions = [c[0][0]["action"] for c in cols["logs_admin"].insert_one.call_args_list]
        assert "campaign_password_reset" in actions

    def test_base_de_logs_indisponible_ne_bloque_pas_l_envoi(self, cc, cols, expediteur, mock_canaux):
        """Pattern « non bloquant » : l'audit est secondaire, la communication non."""
        cols["logs_admin"].insert_one.side_effect = Exception("MongoDB down")
        cols["users"].find.return_value = [{"email": "a@ism.sn", "full_name": "A"}]
        res = cc.send_campaign(sender=expediteur, subject="S", body="Corps",
                               target={"mode": "all"}, channels=["email"],
                               send_type="immediate")
        assert res["status"] == "sent"


# ══════════════════════════════════════════════════════════════════════
#  Statistiques
# ══════════════════════════════════════════════════════════════════════

class TestComputeStats:
    """Les compteurs affichés à l'admin après envoi."""

    def test_agrege_succes_et_echecs(self):
        """Cas nominal."""
        stats = CommunicationController._compute_stats([
            {"email_status": "sent", "notif_id": "n1"},
            {"email_status": "failed", "notif_id": None},
            {"email_status": "sent", "notif_id": "n2"},
        ], ["email", "inapp"])
        assert stats == {"total": 3, "email_sent": 2, "email_failed": 1, "inapp": 2}

    def test_liste_vide(self):
        """Aucun destinataire : tous les compteurs à zéro."""
        assert CommunicationController._compute_stats([], [])["total"] == 0


# ══════════════════════════════════════════════════════════════════════
#  Envoi programmé
# ══════════════════════════════════════════════════════════════════════

class TestProcessScheduled:
    """Le cron peut être relancé après un plantage, ou tourner en double."""

    def test_ne_reclame_que_les_campagnes_echues(self, cc, cols):
        """Une campagne prévue demain ne doit pas partir aujourd'hui."""
        maintenant = datetime(2026, 8, 10, 12, 0)
        cc.process_scheduled(now=maintenant)
        filtre = cols["campaigns"].find_one_and_update.call_args[0][0]
        assert filtre["status"] == "scheduled"
        assert filtre["scheduled_at"] == {"$lte": maintenant}

    def test_reclamation_atomique_avant_envoi(self, cc, cols, mock_canaux):
        """**Garde-fou** : le passage `scheduled → sending` est fait par la
        requête de sélection elle-même. Deux crons concurrents ne peuvent pas
        envoyer la même campagne deux fois."""
        cols["campaigns"].find_one_and_update.side_effect = [
            {"_id": "c1", "subject": "S", "body": "B",
             "target": {"mode": "all"}, "channels": ["email"], "created_by": "admin@ism.sn"},
            None,
        ]
        cols["users"].find.return_value = [{"email": "a@ism.sn", "full_name": "A"}]
        cc.process_scheduled(now=datetime(2026, 8, 10, 12, 0))
        maj = cols["campaigns"].find_one_and_update.call_args_list[0][0][1]["$set"]
        assert maj["status"] == "sending"

    def test_marque_la_campagne_envoyee(self, cc, cols, mock_canaux):
        """Fin de cycle : la campagne passe à `sent` avec ses statistiques."""
        cols["campaigns"].find_one_and_update.side_effect = [
            {"_id": "c1", "subject": "S", "body": "B",
             "target": {"mode": "all"}, "channels": ["email"], "created_by": "admin@ism.sn"},
            None,
        ]
        cols["users"].find.return_value = [{"email": "a@ism.sn", "full_name": "A"}]
        res = cc.process_scheduled(now=datetime(2026, 8, 10, 12, 0))
        assert res["processed"] == 1
        assert cols["campaigns"].update_one.call_args[0][1]["$set"]["status"] == "sent"

    def test_aucune_campagne_a_traiter(self, cc, cols):
        """Le cas de très loin le plus fréquent : le cron ne fait rien."""
        assert cc.process_scheduled(now=datetime(2026, 8, 10, 12, 0)) == {"processed": 0}

    def test_base_indisponible_interrompt_proprement(self, cc, cols):
        """Une panne MongoDB ne doit pas faire boucler le cron indéfiniment."""
        cols["campaigns"].find_one_and_update.side_effect = Exception("MongoDB down")
        assert cc.process_scheduled(now=datetime(2026, 8, 10, 12, 0)) == {"processed": 0}


# ══════════════════════════════════════════════════════════════════════
#  Modèles réutilisables
# ══════════════════════════════════════════════════════════════════════

class TestTemplates:
    """Gabarits enregistrés par les administrateurs."""

    def test_refuse_un_nom_vide(self, cc, cols):
        """Un modèle sans nom serait irrécupérable (la clé est le nom)."""
        assert cc.save_template("   ", "S", "B", "admin@ism.sn") is False
        cols["message_templates"].update_one.assert_not_called()

    def test_enregistre_en_upsert(self, cc, cols):
        """Réenregistrer sous le même nom met à jour au lieu de dupliquer."""
        assert cc.save_template("Invitation", "S", "B", "admin@ism.sn") is True
        assert cols["message_templates"].update_one.call_args.kwargs["upsert"] is True

    def test_base_indisponible_retourne_false(self, cc, cols):
        """L'interface doit pouvoir signaler l'échec sans planter."""
        cols["message_templates"].update_one.side_effect = Exception("MongoDB down")
        assert cc.save_template("Invitation", "S", "B", "admin@ism.sn") is False

    def test_liste_vide_si_base_indisponible(self, cc, cols):
        """Mode survie."""
        cols["message_templates"].find.side_effect = Exception("MongoDB down")
        assert cc.get_templates() == []

    def test_suppression_par_nom(self, cc, cols):
        """Le nom est la clé."""
        assert cc.delete_template("Invitation") is True
        cols["message_templates"].delete_one.assert_called_once_with({"name": "Invitation"})


# ══════════════════════════════════════════════════════════════════════
#  Blocs par défaut
# ══════════════════════════════════════════════════════════════════════

class TestDefaultBlocks:
    """Les textes pré-remplis proposés à l'administrateur."""

    def test_le_bloc_connexion_porte_les_trois_variables(self):
        """Sans l'une d'elles, l'utilisateur ne peut pas se connecter."""
        connexion = default_blocks()["connexion"]
        for variable in ("{email}", "{motdepasse}", "{lien}"):
            assert variable in connexion

    def test_aucun_bloc_ne_contient_de_mot_de_passe_en_dur(self):
        """Un mot de passe écrit dans un gabarit finirait dans le dépôt Git."""
        for texte in default_blocks().values():
            assert "motdepasse" not in texte.replace("{motdepasse}", "")

    def test_les_blocs_sont_reconstruits_a_chaque_appel(self):
        """`default_blocks()` est une fonction, pas une constante : éditer un
        bloc dans l'interface ne doit pas contaminer la campagne suivante."""
        premier = default_blocks()
        premier["libre"] = "modifié"
        assert default_blocks()["libre"] == ""

    def test_l_objet_n_est_pas_un_bloc_de_corps(self):
        """L'objet par défaut est éditable mais ne doit pas s'ajouter au corps."""
        assert "objet" not in default_blocks()


# ══════════════════════════════════════════════════════════════════════
#  Blocs personnalisés depuis l'interface
# ══════════════════════════════════════════════════════════════════════

class TestBlocsPersonnalises:
    """Textes éditables depuis Streamlit, stockés dans `message_blocks`."""

    def test_sans_surcharge_on_obtient_les_textes_d_usine(self, cc):
        textes = cc.get_block_texts()
        assert textes["invitation_test"] == BLOCK_DEFINITIONS["invitation_test"]["text"]
        assert textes["objet"] == BLOCK_DEFINITIONS["objet"]["text"]

    def test_la_surcharge_en_base_prime(self, cc, cols):
        cols["message_blocks"].find.return_value = [
            {"key": "invitation_test", "text": "Texte maison"}
        ]
        assert cc.get_block_texts()["invitation_test"] == "Texte maison"

    def test_une_cle_inconnue_en_base_est_ignoree(self, cc, cols):
        """Un document résiduel ne doit pas injecter de bloc fantôme."""
        cols["message_blocks"].find.return_value = [{"key": "obsolete", "text": "x"}]
        assert "obsolete" not in cc.get_block_texts()

    def test_incident_mongodb_retombe_sur_les_textes_d_usine(self, cc, cols):
        cols["message_blocks"].find.side_effect = Exception("MongoDB down")
        assert cc.get_block_texts()["libre"] == ""

    def test_un_texte_vide_reste_une_surcharge_valide(self, cc, cols):
        """Vider un bloc est un choix légitime — pas un retour au texte d'usine."""
        cols["message_blocks"].find.return_value = [
            {"key": "invitation_test", "text": ""}
        ]
        assert cc.get_block_texts()["invitation_test"] == ""

    def test_enregistrement_upsert(self, cc, cols):
        ok, err = cc.save_block("libre", "Nouveau texte", "admin@ism.sn")
        assert ok and err == ""
        assert cols["message_blocks"].update_one.call_args.kwargs["upsert"] is True

    def test_le_journal_admin_ne_contient_pas_le_texte(self, cc, cols):
        """Un bloc mal rédigé pourrait contenir un mot de passe en clair."""
        cc.save_block("connexion", "Mot de passe : Secret123", "admin@ism.sn")
        trace = cols["logs_admin"].insert_one.call_args[0][0]
        assert "Secret123" not in str(trace)
        assert trace["details"]["bloc"] == "connexion"

    def test_objet_vide_refuse(self, cc):
        ok, err = cc.save_block("objet", "   ", "admin@ism.sn")
        assert not ok and "vide" in err.lower()

    def test_objet_debarrasse_des_sauts_de_ligne(self, cc, cols):
        """Anti-injection d'en-têtes SMTP, comme à l'envoi."""
        cc.save_block("objet", "Bonjour\r\nBcc: pirate@mal.sn", "admin@ism.sn")
        enregistre = cols["message_blocks"].update_one.call_args[0][1]["$set"]["text"]
        assert "\n" not in enregistre and "\r" not in enregistre

    def test_bloc_inconnu_refuse(self, cc):
        ok, err = cc.save_block("inexistant", "x", "admin@ism.sn")
        assert not ok and "inconnu" in err.lower()

    def test_reinitialisation_supprime_la_surcharge(self, cc, cols):
        ok, _ = cc.reset_block("connexion", "admin@ism.sn")
        assert ok
        cols["message_blocks"].delete_one.assert_called_once_with({"key": "connexion"})

    def test_detail_signale_un_bloc_personnalise(self, cc, cols):
        cols["message_blocks"].find.return_value = [
            {"key": "libre", "text": "Perso", "updated_by": "admin@ism.sn"}
        ]
        par_cle = {b["key"]: b for b in cc.get_blocks_detail()}
        assert par_cle["libre"]["personnalise"] is True
        assert par_cle["libre"]["texte_usine"] == ""
        assert par_cle["invitation_test"]["personnalise"] is False

    def test_detail_couvre_tous_les_blocs(self, cc):
        assert {b["key"] for b in cc.get_blocks_detail()} == set(BLOCK_DEFINITIONS)


# ══════════════════════════════════════════════════════════════════════
#  Variables de personnalisation
# ══════════════════════════════════════════════════════════════════════

class TestVariablesInconnues:
    """Détection des fautes de frappe avant un envoi de masse."""

    def test_variable_valide_non_signalee(self):
        assert unknown_variables("Bonjour {prenom}, voici {lien}") == []

    def test_faute_de_frappe_signalee(self):
        assert unknown_variables("Bonjour {prenoms}") == ["{prenoms}"]

    def test_doublons_dedupliques_et_tries(self):
        assert unknown_variables("{b} {a} {b}") == ["{a}", "{b}"]

    def test_texte_sans_variable(self):
        assert unknown_variables("Aucune variable ici") == []
        assert unknown_variables("") == []

    def test_toutes_les_variables_documentees_sont_reconnues(self):
        """Le message d'aide de l'interface liste VARIABLES_CONNUES : il ne doit
        pas promettre une variable que `personalize` ne remplacerait pas."""
        assert unknown_variables(" ".join(VARIABLES_CONNUES)) == []
