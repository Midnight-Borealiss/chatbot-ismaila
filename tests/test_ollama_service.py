"""
Tests du service LLM local (Ollama).

Aucun appel réel : le client Ollama est mocké. Les tests doivent passer sur une
machine où Ollama n'est **pas** installé — c'est justement le cas à couvrir en
priorité, puisque l'application doit fonctionner sans LLM.
"""

import pytest
from unittest.mock import MagicMock

from config.categories import DEFAULT_CATEGORY, get_all_canonical
from services.ollama_service import OllamaService, CONFIDENCE_MIN


@pytest.fixture
def service():
    """Service neuf pour chaque test — le client est mis en cache par instance."""
    return OllamaService()


@pytest.fixture
def categorie_valide():
    """Une sous-catégorie réellement présente dans le référentiel."""
    return get_all_canonical()[0]


def _client_avec_modele(service, modele=None, reponse=None):
    """Branche un faux client Ollama : modèle présent et réponse donnée."""
    client = MagicMock()
    client.list.return_value = {"models": [{"model": modele or service.model}]}
    client.generate.return_value = {"response": reponse or ""}
    service._client = client
    return client


# ══════════════════════════════════════════════════════════════════════
#  Disponibilité — le cas « pas d'Ollama » doit être propre
# ══════════════════════════════════════════════════════════════════════

class TestDisponibilite:
    """Sans Ollama, le service se désactive sans jamais lever d'exception."""

    def test_client_absent_rend_indisponible(self, service):
        """Import du client impossible → service indisponible, pas d'erreur."""
        service._client_failed = True
        assert service.is_available() is False

    def test_serveur_injoignable_rend_indisponible(self, service):
        """Serveur muet → False plutôt qu'une exception réseau remontée."""
        client = MagicMock()
        client.list.side_effect = ConnectionError("connexion refusée")
        service._client = client
        assert service.is_available() is False

    def test_modele_absent_rend_indisponible(self, service):
        """Ollama installé mais `ollama pull` oublié : cas courant, à distinguer."""
        _client_avec_modele(service, modele="llama3:latest")
        assert service.is_available() is False

    def test_modele_present_rend_disponible(self, service):
        """Serveur joignable et modèle présent."""
        _client_avec_modele(service)
        assert service.is_available() is True

    def test_variante_de_tag_acceptee(self, service):
        """« mistral:latest » vaut « mistral:7b-instruct-q4_0 » : Ollama renomme
        les modèles selon la façon dont ils ont été tirés."""
        service.model = "mistral:7b-instruct-q4_0"
        _client_avec_modele(service, modele="mistral:latest")
        assert service.is_available() is True

    def test_echec_client_memorise(self, service):
        """Un import raté n'est pas retenté à chaque appel."""
        service._client_failed = True
        service.get_client()
        service.get_client()
        assert service._client is None


# ══════════════════════════════════════════════════════════════════════
#  Génération brute
# ══════════════════════════════════════════════════════════════════════

class TestGenerate:
    """`generate` retourne du texte ou None — jamais d'exception."""

    def test_retourne_le_texte(self, service):
        """Cas nominal."""
        _client_avec_modele(service, reponse="  Bonjour  ")
        assert service.generate("une question") == "Bonjour"

    def test_prompt_vide_retourne_none(self, service):
        """On n'interroge pas le modèle pour rien."""
        _client_avec_modele(service, reponse="peu importe")
        assert service.generate("") is None

    def test_client_absent_retourne_none(self, service):
        """Sans client, pas de plantage."""
        service._client_failed = True
        assert service.generate("une question") is None

    def test_erreur_modele_retourne_none(self, service):
        """Une panne du modèle est absorbée."""
        client = _client_avec_modele(service)
        client.generate.side_effect = RuntimeError("modèle planté")
        assert service.generate("une question") is None

    def test_reponse_vide_retourne_none(self, service):
        """Une réponse blanche vaut absence de réponse, pas une chaîne vide."""
        _client_avec_modele(service, reponse="   ")
        assert service.generate("une question") is None


# ══════════════════════════════════════════════════════════════════════
#  Extraction du JSON produit par le modèle
# ══════════════════════════════════════════════════════════════════════

class TestExtractionJson:
    """Les modèles encadrent souvent le JSON de texte malgré la consigne."""

    def test_json_nu(self, service):
        """Cas idéal."""
        assert service._extract_json('{"a": 1}') == {"a": 1}

    def test_json_entoure_de_texte(self, service):
        """Bavardage avant et après : on récupère quand même l'objet."""
        brut = 'Voici ma réponse :\n{"a": 1}\nJ\'espère que cela aide.'
        assert service._extract_json(brut) == {"a": 1}

    def test_json_dans_un_bloc_markdown(self, service):
        """Balises ```json — très fréquent."""
        assert service._extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_objet_imbrique(self, service):
        """L'équilibrage des accolades doit gérer l'imbrication."""
        assert service._extract_json('{"a": {"b": 2}}') == {"a": {"b": 2}}

    def test_absence_de_json(self, service):
        """Texte sans objet → None."""
        assert service._extract_json("aucun objet ici") is None

    def test_json_malforme(self, service):
        """Objet non parsable → None, pas d'exception."""
        assert service._extract_json('{"a": }') is None

    def test_texte_vide(self, service):
        """Entrée vide → None."""
        assert service._extract_json("") is None


# ══════════════════════════════════════════════════════════════════════
#  Catégorisation — contrat attendu par scripts/auto_categorize.py
# ══════════════════════════════════════════════════════════════════════

class TestCategorize:
    """`categorize` retourne toujours un dict complet, jamais None.

    Toute anomalie (LLM absent, réponse illisible, catégorie inventée) doit
    produire la catégorie par défaut avec `low_confidence = True` : aucune
    décision automatique ne sera prise sur cette base.
    """

    CLES = {"category", "parent_category", "confidence",
            "reasoning", "source", "low_confidence"}

    def test_contrat_de_sortie(self, service, categorie_valide):
        """Les six clés attendues par les appelants sont toujours présentes."""
        _client_avec_modele(
            service,
            reponse=f'{{"category": "{categorie_valide}", "confidence": 0.9, "reasoning": "ok"}}',
        )
        assert set(service.categorize("Quels sont les frais ?")) == self.CLES

    def test_categorisation_reussie(self, service, categorie_valide):
        """Une réponse conforme est reprise telle quelle."""
        _client_avec_modele(
            service,
            reponse=f'{{"category": "{categorie_valide}", "confidence": 0.92, "reasoning": "motif"}}',
        )
        res = service.categorize("Quels sont les frais du MBA ?")
        assert res["category"] == categorie_valide
        assert res["confidence"] == 0.92
        assert res["source"] == "ollama"
        assert res["low_confidence"] is False

    def test_categorie_inventee_rejetee(self, service):
        """Une catégorie hors référentiel est une hallucination : on la refuse
        plutôt que de créer une catégorie fantôme en base."""
        _client_avec_modele(
            service,
            reponse='{"category": "CategorieQuiNexistePas", "confidence": 0.99}',
        )
        res = service.categorize("une question")
        assert res["category"] == DEFAULT_CATEGORY
        assert res["source"] == "error"
        assert res["low_confidence"] is True

    def test_llm_indisponible(self, service):
        """Sans Ollama, on renvoie un résultat neutre — surtout pas une erreur."""
        service._client_failed = True
        res = service.categorize("une question")
        assert res["category"] == DEFAULT_CATEGORY
        assert res["source"] == "unavailable"
        assert res["low_confidence"] is True

    def test_reponse_illisible(self, service):
        """Le modèle bavarde sans produire de JSON exploitable."""
        _client_avec_modele(service, reponse="Je pense que c'est une question de scolarité.")
        res = service.categorize("une question")
        assert res["source"] == "error"
        assert res["low_confidence"] is True

    def test_question_vide(self, service):
        """On n'interroge pas le modèle sur une question vide."""
        res = service.categorize("   ")
        assert res["source"] == "error"
        assert res["category"] == DEFAULT_CATEGORY

    def test_confiance_faible_marquee(self, service, categorie_valide):
        """Sous le seuil, la décision est signalée comme à revoir."""
        faible = CONFIDENCE_MIN - 0.1
        _client_avec_modele(
            service,
            reponse=f'{{"category": "{categorie_valide}", "confidence": {faible}}}',
        )
        assert service.categorize("une question")["low_confidence"] is True

    def test_confiance_bornee(self, service, categorie_valide):
        """Une confiance aberrante (> 1) est ramenée dans [0, 1]."""
        _client_avec_modele(
            service,
            reponse=f'{{"category": "{categorie_valide}", "confidence": 42}}',
        )
        assert service.categorize("une question")["confidence"] == 1.0

    def test_confiance_non_numerique(self, service, categorie_valide):
        """Une confiance textuelle ne fait pas planter la catégorisation."""
        _client_avec_modele(
            service,
            reponse=f'{{"category": "{categorie_valide}", "confidence": "haute"}}',
        )
        res = service.categorize("une question")
        assert res["confidence"] == 0.0
        assert res["low_confidence"] is True

    def test_parent_renseigne(self, service, categorie_valide):
        """Le pôle parent accompagne la sous-catégorie, comme en base."""
        _client_avec_modele(
            service,
            reponse=f'{{"category": "{categorie_valide}", "confidence": 0.8}}',
        )
        assert service.categorize("une question")["parent_category"]

    def test_prompt_contient_les_categories(self, service, categorie_valide):
        """Le référentiel est injecté dans le prompt : sans cela, le modèle
        n'a aucun moyen de s'y tenir."""
        prompt = service._build_categorization_prompt("une question")
        assert categorie_valide in prompt
        assert DEFAULT_CATEGORY in prompt
