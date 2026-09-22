import tempfile
from pathlib import Path

from app.services import auth_db
from app.services import artifact_generation
from app.services.draft_manager import create_draft, reject_and_regenerate


def _setup(tmp_path):
    original = auth_db.DB_PATH
    auth_db.DB_PATH = Path(tmp_path) / "test.db"
    auth_db.init_db()
    auth_db.create_user("E330", "engineer", "pass1234", "Engineer")
    auth_db.create_user("D330", "developer", "pass1234", "Developer")
    return original


def test_batch33_pending_review_persists_and_exposes_draft(tmp_path):
    original = _setup(tmp_path)
    try:
        bundle = create_draft(
            requester_employee_id="E330", requester_username="engineer", requester_role="Engineer",
            action="deliverable_review", title="MRPL Pump Analysis", artifact_type="docx",
            content="# Draft\nVerified technical summary.",
        )
        review = auth_db.get_human_review(bundle["review"]["id"])
        assert review["status"] == "pending"
        assert review["draft"]["id"] == bundle["draft"]["id"]
        assert review["draft"]["content"].startswith("# Draft")
    finally:
        auth_db.DB_PATH = original


def test_batch33_reject_creates_next_pending_revision(tmp_path, monkeypatch):
    original = _setup(tmp_path)
    try:
        first = create_draft(
            requester_employee_id="E330", requester_username="engineer", requester_role="Engineer",
            action="deliverable_review", title="MRPL Pump Analysis", artifact_type="docx",
            content="# Draft v1\nInitial.",
            metadata={"original_request": "Prepare an approval-ready technical summary."},
        )
        monkeypatch.setattr(
            "app.services.draft_manager.generate_response",
            lambda model, prompt: "# Draft v2\nDetailed revision after reviewer feedback.",
        )
        result = reject_and_regenerate(
            first["review"]["id"], "Add detailed calculation verification.",
            "E330", "engineer", "Engineer",
        )
        assert result["review"]["status"] == "pending"
        assert result["draft"]["version"] == 2
        assert result["draft"]["parent_draft_id"] == first["draft"]["id"]
        assert len(result["version_history"]) == 2
    finally:
        auth_db.DB_PATH = original


def test_batch33_final_artifact_not_generated_before_approval(tmp_path):
    original = _setup(tmp_path)
    try:
        bundle = create_draft(
            requester_employee_id="E330", requester_username="engineer", requester_role="Engineer",
            action="deliverable_review", title="Approval Gate", artifact_type="docx",
            content="# Draft content",
        )
        draft = auth_db.get_draft(bundle["draft"]["id"])
        review = auth_db.get_human_review(bundle["review"]["id"])
        assert review["status"] == "pending"
        assert draft["metadata"].get("final_artifact_status") != "generated"
        assert "final_artifact" not in draft["metadata"]
    finally:
        auth_db.DB_PATH = original
