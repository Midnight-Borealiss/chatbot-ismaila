"""
Tests de nlp_engine.assess_confidence (Phase 3 — classification à la source).

Le modèle sémantique n'est PAS chargé : on force son indisponibilité
(`_model_failed = True`) pour tester de façon déterministe les branches
mots-clés et défaut (abstention). Les branches sémantiques dépendent du
modèle et sont couvertes en intégration, pas ici.
"""

import pytest
from services.nlp_engine import NLPEngine
from config.categories import DEFAULT_CATEGORY, get_parent_category


@pytest.fixture
def engine_no_model():
    """Moteur avec la voie sémantique désactivée (aucun modèle chargé)."""
    eng = NLPEngine()
    eng._model_failed = True   # get_model() renverra None → sémantique = (None, 0.0)
    return eng


def test_keyword_hit_is_confident_no_review(engine_no_model):
    """Un mot-clé du domaine → voie mots-clés, pas de révision."""
    res = engine_no_model.assess_confidence("Comment obtenir une bourse d'excellence ?")
    assert res["source"] == "mots-clés"
    assert res["needs_review"] is False
    assert res["confidence"] == 0.70
    assert res["category"] == "Bourses d'excellence"
    assert res["parent_category"] == get_parent_category(res["category"])


def test_abstention_flags_needs_review(engine_no_model):
    """Aucune voie ne tranche → défaut + needs_review=True (plus de défaut silencieux)."""
    res = engine_no_model.assess_confidence("xyzzy plugh qwerty")
    assert res["source"] == "défaut"
    assert res["needs_review"] is True
    assert res["confidence"] == 0.0
    assert res["category"] == DEFAULT_CATEGORY


def test_result_shape(engine_no_model):
    """Contrat de sortie stable pour les appelants (search_controller)."""
    res = engine_no_model.assess_confidence("bonjour")
    assert set(res) == {"category", "parent_category", "confidence", "source", "needs_review"}
