"""
Tests du référentiel structurel (services / instituts) — config/structures.

Vérifie la source unique : socle par défaut, ajout dynamique, dédup, protection
du socle à la suppression. La persistance MongoDB est best-effort et non testée
ici. L'état module (_EXTRA) est restauré après chaque test.
"""

import pytest
import config.structures as struct
from config.structures import (
    get_services, get_instituts, get_structures,
    add_structure, remove_structure,
    DEFAULT_SERVICES, DEFAULT_INSTITUTS,
)


@pytest.fixture(autouse=True)
def restore_extra():
    snap = {k: list(v) for k, v in struct._EXTRA.items()}
    yield
    struct._EXTRA.clear()
    struct._EXTRA.update({k: list(v) for k, v in snap.items()})


def test_defaults_present():
    assert set(DEFAULT_SERVICES).issubset(set(get_services()))
    assert set(DEFAULT_INSTITUTS).issubset(set(get_instituts()))


def test_get_structures_by_type():
    assert get_structures("SERVICE") == get_services()
    assert get_structures("INSTITUT") == get_instituts()
    assert get_structures("autre") == get_services()   # défaut = SERVICE


def test_add_service_dynamic():
    ok, _ = add_structure("SERVICE", "Bibliothèque")
    assert ok is True
    assert "Bibliothèque" in get_services()


def test_add_duplicate_rejected():
    ok, _ = add_structure("SERVICE", "Scolarité")   # déjà dans le socle
    assert ok is False


def test_add_empty_rejected():
    ok, _ = add_structure("INSTITUT", "   ")
    assert ok is False


def test_remove_default_protected():
    ok, msg = remove_structure("SERVICE", "Scolarité")
    assert ok is False
    assert "défaut" in msg.lower()


def test_remove_dynamic_ok():
    add_structure("INSTITUT", "Institut Test")
    assert "Institut Test" in get_instituts()
    ok, _ = remove_structure("INSTITUT", "Institut Test")
    assert ok is True
    assert "Institut Test" not in get_instituts()
