import tempfile
from pathlib import Path

from app.services import auth_db
import app.services.draft_manager as draft_manager


def test_batch14_reject_feedback_creates_v2(monkeypatch):
    original = auth_db.DB_PATH
    with tempfile.TemporaryDirectory() as td:
        auth_db.DB_PATH = Path(td) / "test.db"
        auth_db.init_db()
        auth_db.create_user("E014", "engineer", "pass1234", "Engineer")
        auth_db.create_user("D014", "developer", "pass1234", "Developer")
        first = draft_manager.create_draft(
            requester_employee_id="E014",
            requester_username="engineer",
            requester_role="Engineer",
            action="deliverable_review",
            title="Pump P-101 Note",
            artifact_type="docx",
            content="# Draft v1\nInitial content.",
            metadata={"original_request": "Create a Pump P-101 maintenance approval note."},
        )
        monkeypatch.setattr(
            draft_manager,
            "generate_response",
            lambda model, prompt: "# Draft v2\nUpdated after reviewer feedback."
        )
        result = draft_manager.reject_and_regenerate(
            first["review"]["id"],
            "Add the maintenance scope and clarify the conclusion.",
            "E014",
            "engineer",
            "Engineer",
        )
        assert first["draft"]["version"] == 1
        assert result["draft"]["version"] == 2
        assert result["draft"]["parent_draft_id"] == first["draft"]["id"]
        assert result["draft"]["revision_group"] == first["draft"]["revision_group"]
        assert result["review"]["status"] == "pending"
        assert result["review"]["draft_version"] == 2
        assert result["previous_draft_id"] == first["draft"]["id"]
        assert len(result["version_history"]) == 2
        assert result["version_history"][0]["version"] == 1
        assert result["version_history"][1]["version"] == 2
        old = auth_db.get_human_review(first["review"]["id"])
        assert old["status"] == "rejected"
        assert old["decision_note"] == "Add the maintenance scope and clarify the conclusion."
    auth_db.DB_PATH = original


def test_batch14_reject_requires_feedback():
    original = auth_db.DB_PATH
    with tempfile.TemporaryDirectory() as td:
        auth_db.DB_PATH = Path(td) / "test.db"
        auth_db.init_db()
        first = draft_manager.create_draft(
            requester_employee_id="E015",
            requester_username="engineer",
            requester_role="Engineer",
            action="deliverable_review",
            title="Feedback required",
            artifact_type="pdf",
            content="Draft",
        )
        try:
            draft_manager.reject_and_regenerate(
                first["review"]["id"], "", "E015", "engineer", "Engineer"
            )
            assert False, "empty rejection feedback should fail"
        except ValueError as exc:
            assert "Feedback is required" in str(exc)
        assert auth_db.get_human_review(first["review"]["id"])["status"] == "pending"
    auth_db.DB_PATH = original
