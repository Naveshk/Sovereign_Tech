import json
from pathlib import Path

import pytest

from app.services import artifact_generation


def test_final_artifact_requires_approved_draft_metadata(monkeypatch, tmp_path):
    calls = {"updated": None, "audits": []}

    class DB:
        @staticmethod
        def update_draft_metadata(draft_id, updates):
            calls["updated"] = (draft_id, updates)
            return {"id": draft_id, "metadata": updates}

        @staticmethod
        def audit(*args):
            calls["audits"].append(args)

    monkeypatch.setattr(artifact_generation, "auth_db", DB)
    monkeypatch.setattr(
        artifact_generation,
        "generate_docx",
        lambda content, title: {"file_path": str(tmp_path / "final.docx"), "filename": "final.docx"},
    )
    (tmp_path / "final.docx").write_bytes(b"not-a-real-docx")

    monkeypatch.setattr(
        artifact_generation,
        "validate_generated_file",
        lambda path, kind: None,
    )

    draft = {
        "id": "DR-1",
        "title": "Approval Note",
        "artifact_type": "docx",
        "content": "# Approved\n\nFinal content.",
        "version": 1,
        "requester_role": "Engineer",
        "requester_employee_id": "E1",
        "requester_username": "alice",
    }
    result = artifact_generation.generate_final_artifact(draft)

    assert result["filename"] == "final.docx"
    assert result["download_url"] == "/api/files/final.docx"
    assert calls["updated"][0] == "DR-1"
    assert calls["updated"][1]["final_artifact_status"] == "generated"


def test_xlsx_final_artifact_uses_structured_draft(monkeypatch, tmp_path):
    calls = {}

    class DB:
        @staticmethod
        def update_draft_metadata(draft_id, updates):
            calls["metadata"] = updates

        @staticmethod
        def audit(*args):
            calls["audit"] = args

    monkeypatch.setattr(artifact_generation, "auth_db", DB)
    out = tmp_path / "final.xlsx"
    out.write_bytes(b"xlsx")
    monkeypatch.setattr(
        artifact_generation,
        "generate_excel_from_records",
        lambda **kwargs: {"file_path": str(out), "filename": out.name},
    )
    monkeypatch.setattr(artifact_generation, "validate_generated_file", lambda *args: None)

    draft = {
        "id": "DR-X",
        "title": "Equipment Register",
        "artifact_type": "xlsx",
        "content": json.dumps([{"Tag": "P-101", "Status": "OK"}]),
        "version": 2,
        "requester_role": "Developer",
        "requester_employee_id": "E2",
        "requester_username": "dev",
    }

    result = artifact_generation.generate_final_artifact(draft)
    assert result["artifact_type"] == "xlsx"
    assert result["draft_version"] == 2
    assert calls["metadata"]["final_artifact_status"] == "generated"


def test_approve_and_generate_rejects_missing_review(monkeypatch):
    monkeypatch.setattr(artifact_generation.auth_db, "get_human_review", lambda review_id: None)
    with pytest.raises(LookupError):
        artifact_generation.approve_and_generate(999, "E1", "alice", "Engineer")
