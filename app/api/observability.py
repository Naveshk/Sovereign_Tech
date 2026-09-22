from fastapi import APIRouter, Header, HTTPException
from app.services.observability import OBSERVABILITY
from app.services.resilience import circuit_status

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("")
def get_observability(
    x_employee_id: str | None = Header(None),
    x_role: str | None = Header(None),
):
    if not x_employee_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    # Observability contains only operational metrics, not user content.
    snapshot = OBSERVABILITY.snapshot()
    models = {}
    for metric in snapshot.get("metrics", {}):
        last = snapshot["metrics"][metric].get("last", {})
        model = last.get("model_id") or last.get("model_name")
        if model:
            models[str(model)] = circuit_status(str(model))
    return {"metrics": snapshot["metrics"], "models": models, "scope": "local-process"}


@router.post("/reset")
def reset_observability(
    x_employee_id: str | None = Header(None),
    x_role: str | None = Header(None),
):
    if not x_employee_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    if str(x_role or "").lower() != "manager":
        raise HTTPException(status_code=403, detail="Manager role required")
    OBSERVABILITY.reset()
    return {"reset": True}
