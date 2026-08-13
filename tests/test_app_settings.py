"""
Tests des réglages applicatifs modifiables depuis l'interface.

Enjeux couverts :
  - le lien est résolu à l'usage (pas au chargement du module) ;
  - une valeur invalide n'atteint jamais un attribut href d'email ;
  - un incident MongoDB laisse un lien exploitable.
"""

from unittest.mock import MagicMock

import pytest

from services import app_settings


@pytest.fixture(autouse=True)
def cache_propre():
    """Le cache est un état de module : il ne doit pas fuir entre les tests."""
    app_settings.invalidate_cache()
    yield
    app_settings.invalidate_cache()


@pytest.fixture
def col(monkeypatch):
    """Fausse collection `app_settings`, plus `logs_admin` pour l'audit."""
    reglages = MagicMock(name="app_settings")
    reglages.find_one.return_value = None
    reglages.update_one.return_value = MagicMock(modified_count=1)
    reglages.delete_one.return_value = MagicMock(deleted_count=1)
    journal = MagicMock(name="logs_admin")

    from services.db_connector import db_instance
    monkeypatch.setattr(
        db_instance, "get_collection",
        lambda name: journal if name == "logs_admin" else reglages,
    )
    reglages.journal = journal
    return reglages


# ══════════════════════════════════════════════════════════════════════
#  Validation de l'URL
# ══════════════════════════════════════════════════════════════════════

class TestNormalisation:

    def test_url_https_conservee(self):
        url, err = app_settings.normalize_platform_url("https://ismaila.streamlit.app")
        assert (url, err) == ("https://ismaila.streamlit.app", "")

    def test_espaces_autour_retires(self):
        url, err = app_settings.normalize_platform_url("  https://ism.sn  ")
        assert (url, err) == ("https://ism.sn", "")

    def test_schema_ajoute_si_absent(self):
        """Sans schéma, le lien serait relatif dans l'email et donc mort."""
        url, err = app_settings.normalize_platform_url("ismaila.streamlit.app")
        assert (url, err) == ("https://ismaila.streamlit.app", "")

    def test_http_accepte(self):
        url, err = app_settings.normalize_platform_url("http://192.168.1.10:8501")
        assert (url, err) == ("http://192.168.1.10:8501", "")

    def test_vide_refuse(self):
        _, err = app_settings.normalize_platform_url("   ")
        assert "vide" in err.lower()

    @pytest.mark.parametrize("mauvais", [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "data:text/html,<h1>x</h1>",
        "mailto:admin@ism.sn",
        "file:///etc/passwd",
        "ftp://ism.sn",
    ])
    def test_schemas_non_http_refuses(self, mauvais):
        """L'URL atterrit dans un href : un schéma script serait exécutable.

        Piège : sans « :// », préfixer aveuglément « https:// » transformerait
        « javascript:alert(1) » en URL acceptée.
        """
        url, err = app_settings.normalize_platform_url(mauvais)
        assert err and url == "", f"{mauvais} aurait dû être refusé"

    def test_domaine_avec_port_sans_schema_accepte(self):
        """« host:8501 » n'est pas un schéma : les deux-points portent un port."""
        url, err = app_settings.normalize_platform_url("ismaila.local:8501")
        assert (url, err) == ("https://ismaila.local:8501", "")

    def test_domaine_avec_port_et_chemin_sans_schema(self):
        url, err = app_settings.normalize_platform_url("ismaila.local:8501/app")
        assert (url, err) == ("https://ismaila.local:8501/app", "")

    def test_guillemet_refuse(self):
        """Un guillemet refermerait l'attribut href du gabarit HTML."""
        _, err = app_settings.normalize_platform_url('https://ism.sn" onclick="x')
        assert err != ""

    def test_chevron_refuse(self):
        _, err = app_settings.normalize_platform_url("https://ism.sn<script>")
        assert err != ""

    def test_sans_domaine_refuse(self):
        _, err = app_settings.normalize_platform_url("https://")
        assert err != ""


# ══════════════════════════════════════════════════════════════════════
#  Lecture
# ══════════════════════════════════════════════════════════════════════

class TestLecture:

    def test_sans_surcharge_on_obtient_la_valeur_env(self, col):
        assert app_settings.get_platform_url() == app_settings.PLATFORM_URL_ENV

    def test_la_surcharge_en_base_prime(self, col):
        col.find_one.return_value = {"key": "platform_url", "value": "https://pilote.ism.sn"}
        assert app_settings.get_platform_url() == "https://pilote.ism.sn"

    def test_incident_mongodb_retombe_sur_env(self, col):
        col.find_one.side_effect = Exception("MongoDB down")
        assert app_settings.get_platform_url() == app_settings.PLATFORM_URL_ENV

    def test_valeur_non_textuelle_ignoree(self, col):
        """Un document corrompu ne doit pas remonter jusque dans un email."""
        col.find_one.return_value = {"key": "platform_url", "value": {"oups": 1}}
        assert app_settings.get_platform_url() == app_settings.PLATFORM_URL_ENV

    def test_valeur_vide_en_base_ignoree(self, col):
        col.find_one.return_value = {"key": "platform_url", "value": "   "}
        assert app_settings.get_platform_url() == app_settings.PLATFORM_URL_ENV

    def test_le_cache_evite_une_lecture_par_destinataire(self, col):
        """`_dispatch` personnalise le message pour chaque personne."""
        for _ in range(50):
            app_settings.get_platform_url()
        assert col.find_one.call_count == 1

    def test_detail_signale_une_surcharge(self, col):
        col.find_one.return_value = {"key": "platform_url", "value": "https://pilote.ism.sn"}
        detail = app_settings.platform_url_detail()
        assert detail["personnalise"] is True
        assert detail["effectif"] == "https://pilote.ism.sn"
        assert detail["env"] == app_settings.PLATFORM_URL_ENV

    def test_detail_sans_surcharge(self, col):
        detail = app_settings.platform_url_detail()
        assert detail["personnalise"] is False
        assert detail["effectif"] == detail["env"]


# ══════════════════════════════════════════════════════════════════════
#  Écriture
# ══════════════════════════════════════════════════════════════════════

class TestEcriture:

    def test_enregistrement_upsert(self, col):
        ok, err = app_settings.set_platform_url("https://pilote.ism.sn", "admin@ism.sn")
        assert ok and err == ""
        assert col.update_one.call_args.kwargs["upsert"] is True
        assert col.update_one.call_args[0][1]["$set"]["value"] == "https://pilote.ism.sn"

    def test_valeur_normalisee_avant_ecriture(self, col):
        app_settings.set_platform_url("  ismaila.streamlit.app ", "admin@ism.sn")
        enregistre = col.update_one.call_args[0][1]["$set"]["value"]
        assert enregistre == "https://ismaila.streamlit.app"

    def test_valeur_invalide_n_ecrit_rien(self, col):
        ok, err = app_settings.set_platform_url("javascript:alert(1)", "admin@ism.sn")
        assert not ok and err
        col.update_one.assert_not_called()

    def test_lecture_immediate_apres_ecriture(self, col):
        """Le cache est rafraîchi par l'écriture, sans attendre le TTL."""
        app_settings.set_platform_url("https://pilote.ism.sn", "admin@ism.sn")
        assert app_settings.get_platform_url() == "https://pilote.ism.sn"

    def test_modification_tracee(self, col):
        app_settings.set_platform_url("https://pilote.ism.sn", "admin@ism.sn")
        trace = col.journal.insert_one.call_args[0][0]
        assert trace["admin"] == "admin@ism.sn"
        assert trace["action"] == "app_setting_saved"

    def test_echec_mongodb_remonte_l_erreur(self, col):
        col.update_one.side_effect = Exception("MongoDB down")
        ok, err = app_settings.set_platform_url("https://pilote.ism.sn", "admin@ism.sn")
        assert not ok and "MongoDB down" in err

    def test_reinitialisation_supprime_et_purge_le_cache(self, col):
        app_settings.set_platform_url("https://pilote.ism.sn", "admin@ism.sn")
        ok, _ = app_settings.reset_platform_url("admin@ism.sn")
        assert ok
        col.delete_one.assert_called_once_with({"key": "platform_url"})
        assert app_settings.get_platform_url() == app_settings.PLATFORM_URL_ENV
