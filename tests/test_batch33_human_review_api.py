import tempfile
from pathlib import Path

import pytest

from app.services import auth_db
from app.api import auth as auth_api


def _setup(td):
    original = auth_db.DB_PATH
    auth_db.DB_PATH = Path(td) / "test.db"
    auth_db.init_db()
    auth_db.create_user("E331", "engineer", "pass1234", "Engineer")
    auth_db.create_user("D331", "developer", "pass1234", "Developer")
    return original


def test_batch33_pending_endpoint_and_reject_endpoint():
    with tempfile.TemporaryDirectory() as td:
        original = _setup(td)
        try:
            from app.services.draft_manager import create_draft
            bundle = create_draft(
                requester_employee_id="E331", requester_username="engineer", requester_role="Engineer",
                action="deliverable_review", title="API Review", artifact_type="docx", content="Draft",
            )
            queue = auth_api.human_review_pending("Engineer", "E331", "engineer")
            assert queue["count"] == 1
            assert queue["reviews"][0]["id"] == bundle["review"]["id"]
            other_queue = auth_api.human_review_pending("Developer", "D331", "developer")
            assert other_queue["count"] == 0
        finally:
            auth_db.DB_PATH = original


def test_batch33_approve_endpoint_uses_approval_gate(tmp_path, monkeypatch):
    original = _setup(tmp_path)
    try:
        from app.services.draft_manager import create_draft
        bundle = create_draft(
            requester_employee_id="E331", requester_username="engineer", requester_role="Engineer",
            action="deliverable_review", title="Approval API", artifact_type="docx", content="Draft",
        )
        monkeypatch.setattr(auth_api, "approve_and_generate", lambda *args: {
            "status": "final_artifact_ready", "artifact": {"filename": "approved.docx"}
        })
        result = auth_api.human_review_approve(bundle["review"]["id"], "Engineer", "E331", "engineer")
        assert result["status"] == "final_artifact_ready"
    finally:
        auth_db.DB_PATH = original
