
from fastapi import APIRouter,HTTPException, Response
from pydantic import BaseModel
from app.services.auth_db import authenticate,create_user,list_files,list_audit,list_audit_provenance,verify_audit_ledger,get_audit_receipt, list_human_reviews,verify_receipt_payload,ROLES, get_human_review, list_drafts, resolve_human_review, require_reviewer_identity
router=APIRouter()
class SignupRequest(BaseModel):
    employee_id:str; username:str; password:str; role:str
class LoginRequest(BaseModel):
    identifier:str; password:str; role:str|None=None
@router.post("/auth/signup")
def signup(b:SignupRequest):
    try:return create_user(b.employee_id,b.username,b.password,b.role)
    except ValueError as e:raise HTTPException(400,str(e))
@router.post("/auth/login")
def login(b:LoginRequest):
    try:return authenticate(b.identifier,b.password,b.role)
    except ValueError as e:raise HTTPException(401,str(e))
@router.get("/auth/roles")
def roles():return {"roles":sorted(ROLES)}


@router.get("/security/encryption")
def encryption_status(employee_id: str = "", username: str = "", role: str = ""):
    identity = require_reviewer_identity(employee_id, username, role)
    info = key_info()
    return {
        "identity": {"employee_id": identity["employee_id"], "role": identity["role"]},
        "encryption": info,
        "protected_storage": [
            "drafts.content", "drafts.metadata_json",
            "conversation_messages.content",
            "conversation_messages.metadata_json",
        ],
    }

@router.get("/admin/files")
def admin_files(role:str):
    if role!="Manager":raise HTTPException(403,"Manager role required.")
    return {"files":list_files()}
@router.get("/admin/audit")
def admin_audit(role:str,limit:int=200):
    if role!="Manager":raise HTTPException(403,"Manager role required.")
    return {"logs":list_audit(limit)}


@router.get("/admin/audit/verify")
def admin_audit_verify(role: str):
    if role != "Manager":
        raise HTTPException(403, "Manager role required.")
    return verify_audit_ledger()


@router.get("/admin/audit/provenance")
def admin_audit_provenance(role: str, draft_id: str | None = None, review_id: int | None = None,
                           provenance_id: str | None = None, artifact_sha256: str | None = None, limit: int = 200):
    """Return the immutable local audit timeline for an artifact/review/draft."""
    if role != "Manager":
        raise HTTPException(403, "Manager role required.")
    try:
        return {"events": list_audit_provenance(
            draft_id=draft_id, review_id=review_id, provenance_id=provenance_id,
            artifact_sha256=artifact_sha256, limit=limit
        )}
    except ValueError as e:
        raise HTTPException(400, str(e))


class ReceiptVerifyRequest(BaseModel):
    payload: dict

@router.get("/admin/audit/{audit_id}/receipt")
def audit_receipt(audit_id: int, role: str):
    if role != "Manager":
        raise HTTPException(403, "Manager role required.")
    receipt = get_audit_receipt(audit_id)
    if not receipt:
        raise HTTPException(404, "Audit entry not found.")
    return {"receipt": receipt, "verification_endpoint": "/api/admin/audit/receipt/verify"}

@router.post("/admin/audit/receipt/verify")
def audit_receipt_verify(b: ReceiptVerifyRequest):
    return verify_receipt_payload(b.payload)

from app.services.draft_manager import reject_and_regenerate
from app.services.artifact_generation import approve_and_generate

from app.services.receipt_service import build_receipt_pdf
from app.services.encryption import key_info

@router.get("/admin/audit/{audit_id}/receipt.pdf")
def audit_receipt_pdf(audit_id: int, role: str):
    if role != "Manager":
        raise HTTPException(403, "Manager role required.")
    receipt = get_audit_receipt(audit_id)
    if not receipt:
        raise HTTPException(404, "Audit entry not found.")
    return Response(content=build_receipt_pdf(receipt), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="audit_receipt_{audit_id}.pdf"'})


class ReviewDecisionRequest(BaseModel):
    decision: str
    note: str = ""


class ReviewRejectRequest(BaseModel):
    feedback: str


# Batch 33: explicit human-approval API names used by the inline chat gate.
@router.get("/human-review/pending")
def human_review_pending(role: str, employee_id: str = "", username: str = "", limit: int = 200):
    identity = require_reviewer_identity(employee_id, username, role)
    items = list_human_reviews(status="pending", limit=limit)
    items = [
        item for item in items
        if (item.get("requester_employee_id") or "").lower() == identity["employee_id"].lower()
    ]
    return {"reviews": items, "count": len(items)}


@router.post("/human-review/{review_id}/approve")
def human_review_approve(review_id: int, role: str, employee_id: str = "", username: str = ""):
    if role not in ROLES:
        raise HTTPException(403, "Authorized role required.")
    try:
        return approve_and_generate(review_id, employee_id, username, role)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise HTTPException(500, f"Final artifact generation failed: {e}")


@router.post("/human-review/{review_id}/reject")
def human_review_reject(review_id: int, body: ReviewRejectRequest, role: str, employee_id: str = "", username: str = ""):
    if role not in ROLES:
        raise HTTPException(403, "Authorized role required.")
    try:
        return reject_and_regenerate(review_id, body.feedback, employee_id, username, role)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Draft regeneration failed: {e}")

# Batch 13: universal human-review API. These routes are intentionally role-agnostic;
# authorization is limited to the application's locally registered roles.
@router.get("/reviews")
def reviews(role: str, employee_id: str = "", username: str = "",
            status: str | None = "pending", limit: int = 200):
    identity = require_reviewer_identity(employee_id, username, role)
    items = list_human_reviews(status=status, limit=limit)
    # Review access is account-owned. Only the authenticated account that
    # created the draft can act on its pending review.
    items = [
        item for item in items
        if (item.get("requester_employee_id") or "").lower() == identity["employee_id"].lower()
    ]
    return {"reviews": items}


@router.get("/reviews/{review_id}")
def review_detail(review_id: int, role: str, employee_id: str = "", username: str = ""):
    review = get_human_review(review_id)
    if not review:
        raise HTTPException(404, "Review request not found.")
    require_reviewer_identity(employee_id, username, role, review)
    return {"review": review}


@router.post("/reviews/{review_id}/decision")
def review_decision(review_id: int, b: ReviewDecisionRequest,
                    role: str, employee_id: str = "", username: str = ""):
    if role not in ROLES:
        raise HTTPException(403, "Authorized role required.")
    try:
        if b.decision.strip().lower() == "approved":
            return approve_and_generate(review_id, employee_id, username, role)
        return {"review": resolve_human_review(review_id, employee_id, username, role, b.decision, b.note)}
    except LookupError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Final artifact generation failed: {e}")


@router.get("/drafts")
def drafts(role: str, limit: int = 200):
    if role not in ROLES:
        raise HTTPException(403, "Authorized role required.")
    return {"drafts": list_drafts(limit=limit)}


class DraftRejectRequest(BaseModel):
    feedback: str

@router.post("/drafts/{review_id}/reject")
def reject_draft(review_id: int, b: DraftRejectRequest,
                 role: str, employee_id: str = "", username: str = ""):
    """Reject a pending draft and create the next revision for review."""
    if role not in ROLES:
        raise HTTPException(403, "Authorized role required.")
    try:
        return reject_and_regenerate(
            review_id, b.feedback, employee_id, username, role
        )
    except LookupError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Draft regeneration failed: {e}")

@router.get("/drafts/{draft_id}/versions")
def draft_versions(draft_id: str, role: str):
    if role not in ROLES:
        raise HTTPException(403, "Authorized role required.")
    draft = __import__("app.services.auth_db", fromlist=["get_draft"]).get_draft(draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found.")
    group = draft.get("revision_group")
    if not group:
        return {"versions": [draft]}
    return {"versions": __import__("app.services.auth_db", fromlist=["list_draft_versions"]).list_draft_versions(group)}
