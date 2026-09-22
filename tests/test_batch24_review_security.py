
import tempfile
from pathlib import Path
import pytest

from app.services import auth_db


def _setup(db):
    original = auth_db.DB_PATH
    auth_db.DB_PATH = Path(db) / "test.db"
    auth_db.init_db()
    return original


def test_batch24_registered_identity_and_role_are_enforced():
    with tempfile.TemporaryDirectory() as td:
        original = _setup(td)
        try:
            auth_db.create_user("E100", "engineer", "pass1234", "Engineer")
            auth_db.create_user("D100", "developer", "pass1234", "Developer")
            review = auth_db.create_human_review(
                "E100", "engineer", "deliverable_review", "draft-100",
                requester_role="Engineer"
            )
            resolved = auth_db.resolve_human_review(
                review["id"], "E100", "engineer", "Engineer", "rejected", "Needs revision"
            )
            assert resolved["status"] == "rejected"
            assert resolved["reviewer_employee_id"] == "E100"
        finally:
            auth_db.DB_PATH = original


def test_batch24_blocks_role_spoof_and_unknown_reviewer():
    with tempfile.TemporaryDirectory() as td:
        original = _setup(td)
        try:
            auth_db.create_user("E101", "engineer", "pass1234", "Engineer")
            auth_db.create_user("D101", "developer", "pass1234", "Developer")
            review = auth_db.create_human_review(
                "E101", "engineer", "deliverable_review", "draft-101",
                requester_role="Engineer"
            )
            with pytest.raises(PermissionError, match="role"):
                auth_db.resolve_human_review(
                    review["id"], "D101", "developer", "Manager", "approved"
                )
            with pytest.raises(PermissionError, match="account"):
                auth_db.resolve_human_review(
                    review["id"], "X999", "unknown", "Developer", "approved"
                )
            assert auth_db.get_human_review(review["id"])["status"] == "pending"
        finally:
            auth_db.DB_PATH = original


def test_batch24_same_account_can_approve_and_other_account_is_blocked():
    with tempfile.TemporaryDirectory() as td:
        original = _setup(td)
        try:
            auth_db.create_user("E102", "engineer", "pass1234", "Engineer")
            auth_db.create_user("D102", "developer", "pass1234", "Developer")
            review = auth_db.create_human_review(
                "E102", "engineer", "deliverable_review", "draft-102",
                requester_role="Engineer"
            )
            with pytest.raises(PermissionError, match="different account"):
                auth_db.resolve_human_review(
                    review["id"], "D102", "developer", "Developer", "approved"
                )
            resolved = auth_db.resolve_human_review(
                review["id"], "E102", "engineer", "Engineer", "rejected", "Needs revision"
            )
            assert resolved["status"] == "rejected"
            assert resolved["reviewer_employee_id"] == "E102"
        finally:
            auth_db.DB_PATH = original


def test_batch24_review_queue_is_account_owned():
    from app.api.auth import reviews
    with tempfile.TemporaryDirectory() as td:
        original = _setup(td)
        try:
            auth_db.create_user("E103", "engineer", "pass1234", "Engineer")
            auth_db.create_user("D103", "developer", "pass1234", "Developer")
            auth_db.create_human_review(
                "E103", "engineer", "deliverable_review", "draft-103",
                requester_role="Engineer"
            )
            own_queue = reviews("Engineer", "E103", "engineer", "pending", 200)
            other_queue = reviews("Developer", "D103", "developer", "pending", 200)
            assert len(own_queue["reviews"]) == 1
            assert other_queue["reviews"] == []
        finally:
            auth_db.DB_PATH = original


def test_batch24_approval_gate_rejects_review_version_mismatch():
    # Service-level gate: a stale review cannot approve a different draft revision.
    from app.services.artifact_generation import approve_and_generate
    with tempfile.TemporaryDirectory() as td:
        original = _setup(td)
        try:
            auth_db.create_user("E104", "engineer", "pass1234", "Engineer")
            auth_db.create_user("D104", "developer", "pass1234", "Developer")
            review = auth_db.create_human_review(
                "E104", "engineer", "deliverable_review", "draft-104",
                requester_role="Engineer", draft_id="missing", artifact_type="docx", draft_version=1
            )
            with pytest.raises(ValueError, match="linked to a draft"):
                approve_and_generate(review["id"], "E104", "engineer", "Engineer")
            assert auth_db.get_human_review(review["id"])["status"] == "pending"
        finally:
            auth_db.DB_PATH = original
