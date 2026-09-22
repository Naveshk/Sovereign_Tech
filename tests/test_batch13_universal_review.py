from pathlib import Path
import tempfile

from app.services import auth_db
from app.services.draft_manager import create_draft


def test_batch13_draft_v1_and_account_owned_review():
    original = auth_db.DB_PATH
    with tempfile.TemporaryDirectory() as td:
        auth_db.DB_PATH = Path(td) / "test.db"
        auth_db.init_db()
        auth_db.create_user("E013", "engineer", "pass1234", "Engineer")
        bundle = create_draft(
            requester_employee_id="E013",
            requester_username="engineer",
            requester_role="Engineer",
            action="deliverable_review",
            title="Pump P-101 Approval Note",
            artifact_type="docx",
            content="# Draft\nReview maintenance request.",
        )
        assert bundle["draft"]["version"] == 1
        assert bundle["review"]["status"] == "pending"
        assert bundle["review"]["draft_id"] == bundle["draft"]["id"]
        assert bundle["review"]["artifact_type"] == "docx"
        resolved = auth_db.resolve_human_review(
            bundle["review"]["id"], "E013", "engineer", "Engineer", "approved"
        )
        assert resolved["status"] == "approved"
        assert resolved["reviewer_role"] == "Engineer"
    auth_db.DB_PATH = original


def test_batch13_all_registered_roles_can_review_own_draft():
    original = auth_db.DB_PATH
    with tempfile.TemporaryDirectory() as td:
        auth_db.DB_PATH = Path(td) / "test.db"
        auth_db.init_db()
        for role, employee, username in [
            ("Engineer", "E014", "engineer"),
            ("Developer", "D014", "developer"),
            ("Manager", "M014", "manager"),
        ]:
            auth_db.create_user(employee, username, "pass1234", role)
            current = create_draft(
                requester_employee_id=employee,
                requester_username=username,
                requester_role=role,
                action="deliverable_review",
                title=f"Universal Review {role}",
                artifact_type="pdf",
                content="Draft content",
            )
            resolved = auth_db.resolve_human_review(
                current["review"]["id"], employee, username, role, "approved"
            )
            assert resolved["reviewer_role"] == role
            assert resolved["reviewer_employee_id"] == employee
    auth_db.DB_PATH = original
