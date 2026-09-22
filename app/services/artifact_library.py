"""Local artifact library and offline-verification manifest helpers for Batch 18."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.auth_db import list_drafts
from app.services.artifact_security import build_qr_payload
from app.services.provenance import sha256_file, verify_provenance_record


def _artifact_entry(draft: dict[str, Any]) -> dict[str, Any] | None:
    metadata = draft.get("metadata") or {}
    artifact = metadata.get("final_artifact") or {}
    provenance = metadata.get("provenance") or {}
    path = Path(artifact.get("file_path") or "")
    if not artifact or not provenance or not artifact.get("filename"):
        return None
    if not path.is_file():
        return None
    expected = str(artifact.get("sha256") or provenance.get("artifact", {}).get("sha256") or "").lower()
    if len(expected) != 64:
        return None
    return {
        "draft_id": draft.get("id"),
        "draft_version": draft.get("version"),
        "revision_group": draft.get("revision_group"),
        "title": artifact.get("title") or draft.get("title") or artifact.get("filename"),
        "artifact_type": artifact.get("artifact_type") or draft.get("artifact_type"),
        "filename": artifact.get("filename"),
        "download_url": artifact.get("download_url"),
        "size_bytes": artifact.get("size_bytes") or path.stat().st_size,
        "sha256": expected,
        "provenance_id": provenance.get("provenance_id"),
        "provenance_sha256": provenance.get("provenance_sha256"),
        "generated_at": provenance.get("generation", {}).get("generated_at"),
        "review_id": provenance.get("review", {}).get("review_id"),
        "reviewer_role": provenance.get("review", {}).get("reviewer_role"),
        "provenance_valid": verify_provenance_record(provenance),
        "qr_payload": build_qr_payload(provenance),
    }


def list_artifacts(limit: int = 100) -> list[dict[str, Any]]:
    """Return only finalized artifacts currently present in the local library."""
    limit = max(1, min(int(limit), 500))
    results: list[dict[str, Any]] = []
    for draft in list_drafts(limit=500):
        entry = _artifact_entry(draft)
        if entry:
            results.append(entry)
            if len(results) >= limit:
                break
    return results


def get_artifact_entry(draft_id: str) -> dict[str, Any] | None:
    for draft in list_drafts(limit=500):
        if str(draft.get("id")) == str(draft_id):
            return _artifact_entry(draft)
    return None


def verify_library_artifact(draft_id: str) -> dict[str, Any]:
    """Re-hash the stored local file and compare it to its provenance record."""
    entry = get_artifact_entry(draft_id)
    if not entry:
        return {"valid": False, "status": "not_found", "message": "Artifact was not found in the local library."}
    path = Path(next(
        (d.get("metadata", {}).get("final_artifact", {}).get("file_path")
         for d in list_drafts(limit=500) if str(d.get("id")) == str(draft_id)), ""
    ))
    exists = path.is_file()
    current = sha256_file(path) if exists else None
    hash_matches = bool(exists and current == entry["sha256"])
    valid = bool(entry["provenance_valid"] and hash_matches)
    return {
        "valid": valid,
        "status": "verified" if valid else "mismatch",
        "message": "Artifact hash and provenance verified locally." if valid else "Artifact hash or provenance verification failed.",
        "artifact": {**entry, "file_exists": exists, "current_sha256": current, "hash_matches": hash_matches},
    }
