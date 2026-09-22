import json
from pathlib import Path

from app.services.provenance import (
    build_artifact_provenance,
    sha256_file,
    sha256_text,
    verify_file_sha256,
    verify_provenance_record,
)


def test_sha256_file_and_text_are_stable(tmp_path):
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"sovereign-workbench")

    assert sha256_file(path) == sha256_text("sovereign-workbench")
    assert verify_file_sha256(path, sha256_file(path))

    path.write_bytes(b"tampered")
    assert not verify_file_sha256(path, sha256_text("sovereign-workbench"))


def test_provenance_binds_artifact_and_draft(tmp_path):
    path = tmp_path / "final.pdf"
    path.write_bytes(b"final-artifact-bytes")
    artifact = {
        "filename": path.name,
        "file_path": str(path),
        "artifact_type": "pdf",
        "title": "Approval Note",
    }
    draft = {
        "id": "DR-16",
        "version": 2,
        "revision_group": "RG-1",
        "parent_draft_id": "DR-15",
        "content": "Approved content",
        "source_path": "evidence/report.pdf",
    }

    record = build_artifact_provenance(
        artifact=artifact,
        draft=draft,
        review_id=16,
        reviewer_employee_id="E1",
        reviewer_username="alice",
        reviewer_role="Engineer",
    )

    assert record["artifact"]["sha256"] == sha256_file(path)
    assert record["artifact"]["size_bytes"] == path.stat().st_size
    assert record["draft"]["content_sha256"] == sha256_text("Approved content")
    assert record["review"]["decision"] == "approved"
    assert len(record["provenance_sha256"]) == 64
    assert verify_provenance_record(record)

    record["artifact"]["filename"] = "changed.pdf"
    assert not verify_provenance_record(record)


def test_provenance_is_json_serializable(tmp_path):
    path = tmp_path / "final.docx"
    path.write_bytes(b"docx")
    record = build_artifact_provenance(
        artifact={"filename": path.name, "file_path": str(path), "artifact_type": "docx", "title": "Note"},
        draft={"id": "DR-X", "version": 1, "content": "hello"},
        review_id=1,
        reviewer_employee_id="E1",
        reviewer_username="reviewer",
        reviewer_role="Manager",
    )
    json.dumps(record, ensure_ascii=False, sort_keys=True)
