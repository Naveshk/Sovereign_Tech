"""Local SHA-256 and provenance helpers for final artifacts.

Batch 16 keeps integrity/provenance local and dependency-free.  No external
service, network call, or database schema change is required: provenance is
stored in the existing draft metadata JSON.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes((text or "").encode("utf-8"))


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 digest of a local file without loading it all in RAM."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def provenance_hash(provenance: dict[str, Any]) -> str:
    """Hash the canonical provenance record itself."""
    return sha256_text(canonical_json(provenance))


def build_artifact_provenance(
    *,
    artifact: dict[str, Any],
    draft: dict[str, Any],
    review_id: int,
    reviewer_employee_id: str,
    reviewer_username: str,
    reviewer_role: str,
) -> dict[str, Any]:
    """Build a self-contained local provenance record for a final artifact."""
    path = Path(artifact["file_path"])
    generated_at = datetime.now(timezone.utc).isoformat()
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "provenance_id": "PV-" + hashlib.sha256(f"{review_id}:{artifact['filename']}:{generated_at}".encode()).hexdigest()[:16].upper(),
        "artifact": {
            "filename": artifact["filename"],
            "artifact_type": artifact["artifact_type"],
            "title": artifact.get("title"),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        },
        "draft": {
            "id": draft.get("id"),
            "version": int(draft.get("version") or 1),
            "revision_group": draft.get("revision_group"),
            "parent_draft_id": draft.get("parent_draft_id"),
            "content_sha256": sha256_text(draft.get("content") or ""),
            "source_path": draft.get("source_path"),
        },
        "review": {
            "review_id": review_id,
            "decision": "approved",
            "reviewer_employee_id": reviewer_employee_id,
            "reviewer_username": reviewer_username,
            "reviewer_role": reviewer_role,
        },
        "generation": {
            "mode": "local",
            "generator": "existing-local-generator",
            "validation": "passed",
            "generated_at": generated_at,
        },
    }
    record["provenance_sha256"] = provenance_hash(record)
    return record


def verify_file_sha256(path: str | Path, expected_sha256: str) -> bool:
    """Verify a local file against a recorded SHA-256 digest."""
    expected = (expected_sha256 or "").strip().lower()
    if len(expected) != 64:
        return False
    return sha256_file(path) == expected


def verify_provenance_record(provenance: dict[str, Any]) -> bool:
    """Verify that a provenance record has not been changed since it was hashed."""
    recorded = (provenance or {}).get("provenance_sha256", "")
    if len(recorded) != 64:
        return False
    body = dict(provenance)
    body.pop("provenance_sha256", None)
    return hmac.compare_digest(recorded.lower(), provenance_hash(body))
