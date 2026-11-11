"""
Tests du cycle de vie des contributions : verrou des statuts figés et historique.

Le verrou est porté par le filtre MongoDB de chaque écriture : on vérifie le
filtre envoyé, et que la méthode renvoie False quand rien n'a été modifié.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from bson import ObjectId
import pytest


@pytest.fixture
def ctrl():
    from controllers.kb_controller import KBController
    c = KBController()
    c.col = MagicMock()
    c.col.find_one.return_value = {"question": "Q ?", "response": "R", "user_email": "anonyme"}
    return c


def _filter(ctrl):
    return ctrl.col.update_one.call_args[0][0]


def _update(ctrl):
    return ctrl.col.update_one.call_args[0][1]


def test_certify_excludes_locked_statuses_and_logs(ctrl):
    ctrl.col.update_one.return_value.matched_count = 1
    with patch.object(ctrl, "_ensure_question_embedding"):
        assert ctrl.update_contribution(str(ObjectId()), "R", "expert@ism.sn") is True
    assert _filter(ctrl)["status"] == {"$nin": ["valide", "archive", "test"]}
    u = _update(ctrl)
    assert u["$set"]["validated_by"] == "expert@ism.sn"
    assert "validated_at" in u["$set"]
    assert u["$push"]["history"]["action"] == "validation"


def test_certify_refused_when_locked(ctrl):
    ctrl.col.update_one.return_value.matched_count = 0
    with patch.object(ctrl, "_ensure_question_embedding") as emb, \
         patch("controllers.kb_controller.send_answer_to_student") as mail:
        assert ctrl.update_contribution(str(ObjectId()), "R", "e@ism.sn") is False
    emb.assert_not_called()
    mail.assert_not_called()


def test_certify_flags_edits_of_a_proposal(ctrl):
    ctrl.col.find_one.return_value = {"question": "Q", "response": "Proposition",
                                      "author_email": "contrib@ism.sn"}
    ctrl.col.update_one.return_value.matched_count = 1
    with patch.object(ctrl, "_ensure_question_embedding"):
        ctrl.update_contribution(str(ObjectId()), "Proposition corrigée", "e@ism.sn")
    assert _update(ctrl)["$set"]["validated_with_edits"] is True


@pytest.mark.parametrize("method", ["archive", "move_to_test", "submit_proposal"])
def test_editing_actions_refused_when_locked(ctrl, method):
    ctrl.col.update_one.return_value.matched_count = 0
    args = (str(ObjectId()), "R", "u@ism.sn") if method == "submit_proposal" else (str(ObjectId()), "u@ism.sn")
    assert getattr(ctrl, method)(*args) is False


def test_invalidate_only_targets_validated(ctrl):
    ctrl.col.update_one.return_value.matched_count = 1
    assert ctrl.invalidate(str(ObjectId()), "e@ism.sn") is True
    assert _filter(ctrl)["status"] == "valide"
    assert "validated_by" in _update(ctrl)["$unset"]
    assert _update(ctrl)["$push"]["history"]["by"] == "e@ism.sn"


def test_restore_only_targets_archive_or_test(ctrl):
    ctrl.col.update_one.return_value.matched_count = 1
    ctrl.restore(str(ObjectId()), "e@ism.sn")
    assert _filter(ctrl)["status"] == {"$in": ["archive", "test"]}


def test_delete_never_targets_validated(ctrl):
    ctrl.col.delete_one.return_value.deleted_count = 0
    assert ctrl.delete(str(ObjectId())) is False
    assert ctrl.col.delete_one.call_args[0][0]["status"] == {"$ne": "valide"}


# ── Provenance & historique (vue) ──────────────────────────────────────────

def test_provenance_proposer_and_validator():
    from views.shared_components import provenance_caption
    doc = {"status": "valide", "author_email": "a@ism.sn", "validated_by": "v@ism.sn",
           "validated_at": datetime(2026, 5, 4, 10, 0), "validated_with_edits": True}
    cap = provenance_caption(doc)
    assert "Proposée par **a@ism.sn**" in cap
    assert "Validée par **v@ism.sn**" in cap and "réponse modifiée" in cap


def test_provenance_expert_wrote_and_validated():
    from views.shared_components import provenance_caption
    cap = provenance_caption({"status": "valide", "validated_by": "v@ism.sn"})
    assert cap.startswith("Rédigée et validée par **v@ism.sn**")


def test_history_keeps_legacy_only_before_tracking():
    from views.shared_components import build_history
    t0 = datetime(2026, 5, 1)
    doc = {
        "created_at": t0, "user_email": "etu@ism.sn", "status": "en_attente",
        "recategorized_by": "old@ism.sn", "recategorized_at": t0 + timedelta(days=1),
        "history": [
            {"action": "validation", "by": "v@ism.sn", "at": t0 + timedelta(days=2)},
            {"action": "invalidation", "by": "v@ism.sn", "at": t0 + timedelta(days=3)},
        ],
    }
    actions = [e["action"] for e in build_history(doc)]
    assert actions == ["question", "recategorisation", "validation", "invalidation"]
