"""Draft lifecycle primitives for the universal human-review workflow.

Batch 13 deliberately stores draft content and review metadata only.  Final
artifact generation remains a later, approval-gated batch.
"""
from __future__ import annotations

import json
import uuid
from typing import Any


from app.services import auth_db
from app.services.resilience import resilient_generate_response, blind_resample
from app.services.provenance import sha256_text


def create_draft(
    *,
    requester_employee_id: str | None,
    requester_username: str | None,
    requester_role: str | None,
    action: str,
    title: str,
    artifact_type: str,
    content: str,
    source_path: str | None = None,
    metadata: dict[str, Any] | None = None,
    version: int = 1,
    revision_group: str | None = None,
    parent_draft_id: str | None = None,
) -> dict[str, Any]:
    """Persist a draft revision and create its universal human-review request."""
    draft_id = f"DR-{uuid.uuid4().hex[:12].upper()}"
    revision_group = revision_group or f"RG-{uuid.uuid4().hex[:12].upper()}"
    draft = auth_db.create_draft(
        draft_id=draft_id,
        requester_employee_id=requester_employee_id,
        requester_username=requester_username,
        requester_role=requester_role,
        action=action,
        title=title,
        artifact_type=artifact_type,
        content=content,
        source_path=source_path,
        metadata=metadata or {},
        version=version,
        revision_group=revision_group,
        parent_draft_id=parent_draft_id,
    )
    auth_db.audit(
        requester_employee_id, requester_username, requester_role,
        "draft_created", draft_id, "success",
        entity_type="draft", entity_id=draft_id, draft_id=draft_id, draft_version=int(version),
        metadata={
            "action": action, "artifact_type": artifact_type, "title": title,
            "content_sha256": sha256_text(content or ""),
            "revision_group": revision_group, "parent_draft_id": parent_draft_id,
        },
    )
    review = auth_db.create_human_review(
        requester_employee_id=requester_employee_id,
        requester_username=requester_username,
        action=action,
        resource=draft_id,
        requester_role=requester_role,
        draft_id=draft_id,
        artifact_type=artifact_type,
        draft_version=version,
    )
    return {"draft": draft, "review": review}


def draft_preview(draft: dict[str, Any], max_chars: int = 12000) -> str:
    """Create a compact JSON preview for structured draft types such as XLSX."""
    content = draft.get("content") or ""
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n\n[Draft preview truncated]"


def generate_response(model: str, prompt: str) -> str:
    # Kept as a module-level compatibility seam so existing tests/integrations
    # can monkeypatch it. Production uses Batch 21 bounded retry protection.
    return resilient_generate_response(model, prompt, max_attempts=3)


def reject_and_regenerate(review_id: int, feedback: str, reviewer_employee_id: str,
                          reviewer_username: str, reviewer_role: str) -> dict[str, Any]:
    """Reject a pending draft, retain it, and create the next pending draft revision."""
    feedback = (feedback or "").strip()
    if not feedback:
        raise ValueError("Feedback is required when rejecting a draft.")
    review = auth_db.get_human_review(review_id)
    if not review:
        raise LookupError("Review request not found.")
    if review.get("status") != "pending":
        raise ValueError("Review request is already resolved.")
    auth_db.require_reviewer_identity(
        reviewer_employee_id, reviewer_username, reviewer_role, review
    )
    old = review.get("draft") or {}
    revision_group = old.get("revision_group") or f"RG-{uuid.uuid4().hex[:12].upper()}"
    old_version = int(old.get("version") or review.get("draft_version") or 1)
    metadata = old.get("metadata") or {}
    original_request = metadata.get("original_request") or old.get("title") or "Revise the draft"
    prompt = f"""Revise the following deliverable draft based on reviewer feedback.

ORIGINAL REQUEST:
{original_request}

CURRENT DRAFT:
{old.get("content", "")}

REVIEWER FEEDBACK:
{feedback}

Rules:
- Produce a complete replacement draft, not commentary about the changes.
- Preserve correct information from the current draft.
- Apply the feedback explicitly.
- Do not invent missing facts.
- Return only the revised draft content.
"""
    resample = blind_resample("qwen3:8b", prompt, samples=2, generate_fn=generate_response)
    revised_content = resample["content"].strip()
    if not revised_content:
        raise ValueError("Draft regeneration returned empty content.")

    # Resolve the old review first; the rejected version remains immutable.
    auth_db.resolve_human_review(
        review_id, reviewer_employee_id, reviewer_username, reviewer_role, "rejected", feedback
    )
    metadata = dict(metadata)
    metadata.update({
        "revision_group": revision_group,
        "parent_draft_id": old.get("id"),
        "rejection_feedback": feedback,
        "batch21_resampling": resample,
    })
    bundle = create_draft(
        requester_employee_id=old.get("requester_employee_id"),
        requester_username=old.get("requester_username"),
        requester_role=old.get("requester_role"),
        action=old.get("action") or "deliverable_review",
        title=old.get("title") or "Draft",
        artifact_type=old.get("artifact_type") or "docx",
        content=revised_content,
        source_path=old.get("source_path"),
        metadata=metadata,
        version=old_version + 1,
        revision_group=revision_group,
        parent_draft_id=old.get("id"),
    )
    bundle["previous_draft_id"] = old.get("id")
    bundle["feedback"] = feedback
    bundle["version_history"] = auth_db.list_draft_versions(revision_group)
    return bundle
