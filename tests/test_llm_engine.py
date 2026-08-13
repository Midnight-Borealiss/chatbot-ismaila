"""
Tests du moteur RAG (génération augmentée).

Le module n'est pas encore branché sur le chat, mais son contrat doit être sûr
avant de l'être : il ne doit jamais lever, jamais renvoyer None, et jamais
inviter le modèle à compléter ce que la base ne contient pas.
"""

import pytest
from unittest.mock import patch

from services.llm_engine import (
    build_rag_prompt, get_rag_response,
    MESSAGE_SANS_CONTEXTE, MESSAGE_INDISPONIBLE,
)


@pytest.fixture
def contextes():
    """Deux réponses certifiées, telles que les fournirait le retrieval."""
    return [
        {"response": "Le MBA coûte 2 500 000 FCFA par an.", "status": "valide"},
        {"response": "Trois types de bourses existent.", "status": "valide"},
    ]


class TestBuildRagPrompt:
    """Le prompt doit interdire au modèle d'inventer."""

    def test_contient_la_question(self, contextes):
        """Sans la question, le modèle n'a rien à répondre."""
        assert "Frais du MBA ?" in build_rag_prompt("Frais du MBA ?", contextes)

    def test_contient_les_contextes(self, contextes):
        """Les réponses certifiées sont bien injectées."""
        prompt = build_rag_prompt("Q ?", contextes)
        assert "2 500 000 FCFA" in prompt
        assert "Trois types de bourses" in prompt

    def test_interdit_explicitement_d_inventer(self, contextes):
        """Garde-fou central : sur des frais ou des dates, une réponse inventée
        engage l'ISM."""
        prompt = build_rag_prompt("Q ?", contextes).lower()
        assert "uniquement" in prompt
        assert "n'ajoute aucun fait" in prompt

    def test_ignore_les_documents_sans_reponse(self):
        """Un document sans texte ne doit pas produire de puce vide."""
        prompt = build_rag_prompt("Q ?", [{"response": ""}, {"response": "Utile."}])
        assert "Utile." in prompt
        assert "- \n" not in prompt


class TestGetRagResponse:
    """La fonction retourne toujours une chaîne affichable."""

    def test_sans_contexte_oriente_vers_l_expert(self):
        """Base muette → escalade, et surtout aucun appel au LLM : on ne lui
        donne pas l'occasion de combler le vide."""
        with patch("services.llm_engine.ollama_service") as mock:
            assert get_rag_response("Q ?", []) == MESSAGE_SANS_CONTEXTE
            mock.generate.assert_not_called()

    def test_reponse_du_modele_servie(self, contextes):
        """Cas nominal."""
        with patch("services.llm_engine.ollama_service") as mock:
            mock.generate.return_value = "Le MBA coûte 2 500 000 FCFA par an."
            assert get_rag_response("Frais ?", contextes) == \
                "Le MBA coûte 2 500 000 FCFA par an."

    def test_llm_indisponible_degrade(self, contextes):
        """LLM absent ou muet → message d'escalade, jamais None ni exception
        (pattern « non bloquant »)."""
        with patch("services.llm_engine.ollama_service") as mock:
            mock.generate.return_value = None
            assert get_rag_response("Q ?", contextes) == MESSAGE_INDISPONIBLE

    def test_retourne_toujours_une_chaine(self, contextes):
        """Contrat de sortie, quel que soit l'état du LLM."""
        with patch("services.llm_engine.ollama_service") as mock:
            for valeur in (None, "", "texte"):
                mock.generate.return_value = valeur
                assert isinstance(get_rag_response("Q ?", contextes), str)

    def test_passe_par_le_llm_local(self, contextes):
        """Souveraineté : la génération doit passer par Ollama (local), jamais
        par `llm_service` (Hugging Face, cloud)."""
        with patch("services.llm_engine.ollama_service") as mock:
            mock.generate.return_value = "ok"
            get_rag_response("Q ?", contextes)
            mock.generate.assert_called_once()
