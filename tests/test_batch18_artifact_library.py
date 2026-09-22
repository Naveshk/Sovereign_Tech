from pathlib import Path

from app.services import auth_db
from app.services.artifact_library import list_artifacts, verify_library_artifact
from app.services.provenance import build_artifact_provenance, sha256_file


def _draft(tmp_path):
    path = tmp_path / "final.pdf"
    path.write_bytes(b"final approved artifact")
    artifact = {
        "filename": path.name,
        "file_path": str(path),
        "download_url": f"/api/files/{path.name}",
        "artifact_type": "pdf",
        "title": "Final Approval",
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }
    draft = {
        "id": "LIB-18",
        "version": 2,
        "revision_group": "RG-18",
        "parent_draft_id": "LIB-17",
        "title": "Final Approval",
        "artifact_type": "pdf",
        "content": "Approved content",
        "source_path": "source.pdf",
        "metadata": {},
    }
    provenance = build_artifact_provenance(
        artifact=artifact, draft=draft, review_id=18,
        reviewer_employee_id="E18", reviewer_username="reviewer", reviewer_role="Engineer"
    )
    draft["metadata"] = {"final_artifact": artifact, "provenance": provenance}
    return path, draft


def test_library_lists_only_finalized_artifacts(tmp_path, monkeypatch):
    _, draft = _draft(tmp_path)
    monkeypatch.setattr("app.services.artifact_library.list_drafts", lambda limit=500: [draft])
    items = list_artifacts()
    assert len(items) == 1
    assert items[0]["filename"] == "final.pdf"
    assert items[0]["provenance_valid"] is True


def test_local_verification_detects_tampering(tmp_path, monkeypatch):
    path, draft = _draft(tmp_path)
    monkeypatch.setattr("app.services.artifact_library.list_drafts", lambda limit=500: [draft])
    assert verify_library_artifact("LIB-18")["valid"] is True
    path.write_bytes(b"tampered")
    result = verify_library_artifact("LIB-18")
    assert result["valid"] is False
    assert result["status"] == "mismatch"
    assert result["artifact"]["hash_matches"] is False


def test_library_ignores_missing_files(tmp_path, monkeypatch):
    _, draft = _draft(tmp_path)
    Path(draft["metadata"]["final_artifact"]["file_path"]).unlink()
    monkeypatch.setattr("app.services.artifact_library.list_drafts", lambda limit=500: [draft])
    assert list_artifacts() == []
