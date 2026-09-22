from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.services import auth_db
from app.services.artifact_security import security_view, qr_svg, verify_qr_payload
from app.services.artifact_library import list_artifacts, verify_library_artifact

router = APIRouter()


def _authorize(role: str) -> None:
    if role not in auth_db.ROLES:
        raise HTTPException(403, "Authorized role required.")


@router.get("/artifacts/{draft_id}/security")
def artifact_security(draft_id: str, role: str):
    _authorize(role)
    draft = auth_db.get_draft(draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found.")
    try:
        return security_view(draft)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/artifacts/{draft_id}/qr")
def artifact_qr(draft_id: str, role: str | None = None):
    # The QR image itself contains only integrity/provenance references. Keep
    # the optional role query compatible with the frontend while allowing a
    # scanner/browser to request the image without exposing artifact content.
    if role is not None:
        _authorize(role)
    draft = auth_db.get_draft(draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found.")
    try:
        view = security_view(draft)
        return Response(content=qr_svg(view["qr"]["payload"]), media_type="image/svg+xml")
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/artifacts/library")
def artifact_library(role: str, limit: int = 100):
    _authorize(role)
    artifacts = list_artifacts(limit=limit)
    return {"artifacts": artifacts, "count": len(artifacts), "mode": "local-offline"}


@router.get("/artifacts/{draft_id}/manifest")
def artifact_manifest(draft_id: str, role: str):
    _authorize(role)
    from app.services.artifact_library import get_artifact_entry
    entry = get_artifact_entry(draft_id)
    if not entry:
        raise HTTPException(404, "Artifact not found in local library.")
    return {
        "schema": "SWB-ARTIFACT-MANIFEST-1",
        "mode": "offline",
        "artifact": entry,
    }


@router.post("/artifacts/{draft_id}/verify-local")
def verify_local_artifact(draft_id: str, role: str):
    _authorize(role)
    return verify_library_artifact(draft_id)


class QRVerifyRequest(BaseModel):
    payload: str


@router.post("/artifacts/verify")
def artifact_verify(b: QRVerifyRequest, role: str):
    _authorize(role)
    try:
        return verify_qr_payload(b.payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
