"""Approval-gated final artifact generation for Batch 15.

This module is intentionally separate from the existing draft-generation path.
It converts an approved draft into the requested file using the existing local
generators, validates the result, and records the artifact metadata on the draft.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.services import auth_db
from app.services.provenance import build_artifact_provenance, verify_file_sha256
from app.services.artifact_security import build_qr_payload
from app.services.file_generator import generate_docx, create_document_title
from app.services.file_tools.document_generators import markdown_to_pdf
from app.services.file_tools.excel_tools import generate_excel_from_records
from app.services.file_tools.ppt_tools import generate_pptx
from app.services.file_tools.validation_tools import validate_generated_file

BASE_DIR = Path(__file__).resolve().parents[2]
GENERATED_DIR = BASE_DIR / "data" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def _download_url(filename: str) -> str:
    return f"/api/files/{filename}"


def _safe_name(title: str, artifact_type: str) -> str:
    import re
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", title or "generated_artifact").strip("._-") or "generated_artifact"
    return f"{stem}_{uuid.uuid4().hex[:10]}.{artifact_type}"


def _records_from_draft(content: str) -> list[dict[str, Any]]:
    data = json.loads(content or "[]")
    if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
        raise ValueError("Approved XLSX draft does not contain structured records.")
    return data


def generate_final_artifact(draft: dict[str, Any]) -> dict[str, Any]:
    """Generate and validate the final artifact from an approved draft only."""
    artifact_type = (draft.get("artifact_type") or "docx").lower()
    title = draft.get("title") or "Generated Document"
    content = draft.get("content") or ""
    if not content.strip():
        raise ValueError("Approved draft has no content to generate.")

    if artifact_type == "docx":
        generated = generate_docx(content=content, title=title)
    elif artifact_type == "pdf":
        generated = markdown_to_pdf(content=content, title=title)
    elif artifact_type == "pptx":
        output_path = GENERATED_DIR / _safe_name(title, "pptx")
        generated = generate_pptx(
            output_path=str(output_path),
            title=title,
            content=content,
            source_name=Path(draft["source_path"]).name if draft.get("source_path") else None,
        )
    elif artifact_type == "xlsx":
        records = _records_from_draft(content)
        output_path = GENERATED_DIR / _safe_name(title, "xlsx")
        generated = generate_excel_from_records(
            output_path=str(output_path),
            records=records,
            sheet_name="Data",
            title=title,
            summary={
                "Source": Path(draft["source_path"]).name if draft.get("source_path") else "Local evidence / knowledge context",
                "Records": len(records),
                "Generated from": f"approved draft v{draft.get('version', 1)}",
            },
        )
    else:
        raise ValueError(f"Unsupported artifact type: {artifact_type}")

    path = generated.get("file_path") or generated.get("path")
    if not path:
        raise ValueError("Artifact generator returned no file path.")
    validate_generated_file(path, artifact_type)
    filename = Path(path).name

    artifact = {
        "filename": filename,
        "file_path": str(path),
        "download_url": _download_url(filename),
        "artifact_type": artifact_type,
        "title": title,
        "draft_id": draft.get("id"),
        "draft_version": int(draft.get("version") or 1),
    }

    # Batch 15 compatibility: keep the initial artifact metadata update.
    # Batch 16 enriches this same metadata with integrity/provenance below.
    auth_db.update_draft_metadata(draft["id"], {
        "final_artifact": artifact,
        "final_artifact_status": "generated",
    })
    return artifact


def approve_and_generate(review_id: int, reviewer_employee_id: str,
                         reviewer_username: str, reviewer_role: str) -> dict[str, Any]:
    """Enforce the approval gate, then generate the final artifact."""
    review = auth_db.get_human_review(review_id)
    if not review:
        raise LookupError("Review request not found.")
    if review.get("status") != "pending":
        raise ValueError("Review request is already resolved.")
    # Batch 24/33 security gate: the caller must be a real local account and
    # match the registered role. Batch 33 uses account ownership for the
    # review gate, so the draft owner may approve or reject their own draft.
    auth_db.require_reviewer_identity(
        reviewer_employee_id, reviewer_username, reviewer_role, review
    )
    draft = review.get("draft")
    if not draft:
        raise ValueError("Review is not linked to a draft.")
    if not draft.get("content"):
        raise ValueError("Draft content is empty.")
    review_version = int(review.get("draft_version") or 1)
    draft_version = int(draft.get("version") or 1)
    if review_version != draft_version:
        raise ValueError("Review version does not match the linked draft version.")
    metadata = draft.get("metadata") or {}
    if metadata.get("final_artifact_status") == "generated":
        raise ValueError("Final artifact has already been generated for this draft.")

    # The endpoint only calls this function for an explicit Accept decision.
    # Generate first so a transient generator failure does not consume the
    # pending review; a successful generation is then committed as approved.
    try:
        artifact = generate_final_artifact(draft)
        provenance = build_artifact_provenance(
            artifact=artifact,
            draft=draft,
            review_id=review_id,
            reviewer_employee_id=reviewer_employee_id,
            reviewer_username=reviewer_username,
            reviewer_role=reviewer_role,
        )
        if not verify_file_sha256(artifact["file_path"], provenance["artifact"]["sha256"]):
            raise ValueError("Generated artifact SHA-256 verification failed.")
        artifact["sha256"] = provenance["artifact"]["sha256"]
        artifact["size_bytes"] = provenance["artifact"]["size_bytes"]
        artifact["provenance_id"] = provenance["provenance_id"]
        artifact["provenance_sha256"] = provenance["provenance_sha256"]
        artifact["qr_payload"] = build_qr_payload(provenance)
        auth_db.update_draft_metadata(draft["id"], {
            "final_artifact": artifact,
            "final_artifact_status": "generated",
            "provenance": provenance,
            "qr_payload": artifact["qr_payload"],
        })
        audit_hash = auth_db.audit(
            reviewer_employee_id,
            reviewer_username,
            reviewer_role,
            "final_artifact_generated",
            draft["id"],
            "success",
            entity_type="artifact", entity_id=artifact["filename"],
            review_id=review_id, draft_id=draft["id"], draft_version=int(draft.get("version") or 1),
            provenance_id=provenance["provenance_id"],
            artifact_sha256=provenance["artifact"]["sha256"],
            metadata={
                "filename": artifact["filename"],
                "artifact_type": artifact["artifact_type"],
                "provenance_sha256": provenance["provenance_sha256"],
                "validation": provenance["generation"]["validation"],
                "generation_mode": provenance["generation"]["mode"],
                "requester_employee_id": draft.get("requester_employee_id"),
            },
        )
    except Exception as exc:
        auth_db.audit(
            reviewer_employee_id, reviewer_username, reviewer_role,
            "final_artifact_generation_failed", draft["id"], type(exc).__name__,
            entity_type="artifact", entity_id=draft["id"], review_id=review_id,
            draft_id=draft["id"], draft_version=int(draft.get("version") or 1),
            metadata={"error_type": type(exc).__name__},
        )
        raise

    approved = auth_db.resolve_human_review(
        review_id, reviewer_employee_id, reviewer_username, reviewer_role, "approved", ""
    )
    return {"review": approved, "artifact": artifact, "provenance": provenance, "status": "final_artifact_ready"}
