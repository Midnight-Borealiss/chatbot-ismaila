"""
Tests de l'extension structurelle de KBController.recategorize (routage).

Vérifie que la recatégorisation stocke le RATTACHEMENT (service ⊻ institut) à
côté du THÈME, et reste rétro-compatible quand aucun rattachement n'est fourni.
La collection est mockée ; add_learned_anchor est patché (hors périmètre).
"""

from unittest.mock import MagicMock, patch
from bson import ObjectId
import pytest


@pytest.fixture
def ctrl():
    from controllers.kb_controller import KBController
    c = KBController()
    c.col = MagicMock()
    c.col.find_one.return_value = {"question": "Comment payer ma scolarité ?"}
    return c


def _payload(ctrl):
    return ctrl.col.update_one.call_args[0][1]["$set"]


def test_service_stored(ctrl):
    with patch("controllers.kb_controller.add_learned_anchor"):
        ctrl.recategorize(str(ObjectId()), "Scolarité", "u@ism.sn",
                          structural_type="SERVICE", entity="Scolarité")
    p = _payload(ctrl)
    assert p["structural_type"] == "SERVICE"
    assert p["service"] == "Scolarité"
    assert p["institution"] == ""
    assert p["category"] == "Scolarité"
    assert p["parent_category"] == "Service Administratif"


def test_institut_stored(ctrl):
    with patch("controllers.kb_controller.add_learned_anchor"):
        ctrl.recategorize(str(ObjectId()), "Formations", "u@ism.sn",
                          structural_type="INSTITUT", entity="Institut Ingénieur")
    p = _payload(ctrl)
    assert p["structural_type"] == "INSTITUT"
    assert p["institution"] == "Institut Ingénieur"
    assert p["service"] == ""


def test_backward_compatible_without_structure(ctrl):
    """Sans rattachement, on ne pose aucun champ structurel (ancien appel)."""
    with patch("controllers.kb_controller.add_learned_anchor"):
        ctrl.recategorize(str(ObjectId()), "Scolarité", "u@ism.sn")
    p = _payload(ctrl)
    assert p["category"] == "Scolarité"
    assert "structural_type" not in p
    assert "service" not in p


def test_learning_loop_still_triggered(ctrl):
    """La boucle d'apprentissage (ancre) reste appelée avec la question."""
    with patch("controllers.kb_controller.add_learned_anchor") as anchor:
        ctrl.recategorize(str(ObjectId()), "Scolarité", "u@ism.sn",
                          structural_type="SERVICE", entity="Scolarité")
    anchor.assert_called_once()
