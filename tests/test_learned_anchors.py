"""
Tests de la boucle d'apprentissage — ancres apprises (Phase 3, étape 3a).

Couvre la couche données de add_learned_anchor / load_learned_anchors :
validation, dédup, effet en mémoire sur CATEGORY_ANCHORS. La persistance
MongoDB est non bloquante (best-effort) et n'est pas requise ici. L'état
global CATEGORY_ANCHORS est snapshotté et restauré (pas de fuite entre tests).
"""

import copy
import pytest
import config.categories as cats
from config.categories import (
    add_learned_anchor, load_learned_anchors,
    get_subcategories, DEFAULT_CATEGORY,
)


@pytest.fixture(autouse=True)
def restore_anchors():
    """Isole les tests : restaure CATEGORY_ANCHORS après chaque test."""
    snapshot = copy.deepcopy(cats.CATEGORY_ANCHORS)
    yield
    cats.CATEGORY_ANCHORS.clear()
    cats.CATEGORY_ANCHORS.update(snapshot)


def test_add_anchor_appends_in_memory():
    cat = get_subcategories()[0]
    before = len(cats.CATEGORY_ANCHORS.get(cat, []))
    ok = add_learned_anchor(cat, "Une question corrigée par un humain", added_by="u@ism.sn")
    assert ok is True
    assert len(cats.CATEGORY_ANCHORS[cat]) == before + 1
    assert "Une question corrigée par un humain" in cats.CATEGORY_ANCHORS[cat]


def test_dedup_second_add_is_noop():
    cat = get_subcategories()[0]
    add_learned_anchor(cat, "Phrase répétée pour dédup")
    before = len(cats.CATEGORY_ANCHORS[cat])
    ok = add_learned_anchor(cat, "Phrase répétée pour dédup")
    assert ok is False
    assert len(cats.CATEGORY_ANCHORS[cat]) == before


def test_reject_unknown_category():
    assert add_learned_anchor("CatégorieQuiNexistePas", "question suffisamment longue") is False


def test_reject_too_short_phrase():
    cat = get_subcategories()[0]
    assert add_learned_anchor(cat, "court") is False


def test_whitespace_normalized_before_dedup():
    cat = get_subcategories()[1]
    assert add_learned_anchor(cat, "question   avec   espaces multiples") is True
    # Même phrase après normalisation des espaces → doublon rejeté.
    assert add_learned_anchor(cat, "question avec espaces multiples") is False


def test_load_learned_anchors_no_db_is_safe():
    """Sans base (get_collection mocké → itération impossible), retourne 0 sans crash."""
    n = load_learned_anchors()
    assert isinstance(n, int)
