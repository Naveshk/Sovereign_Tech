from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.services.auth_db import audit
from app.services.sandbox.manager import sandbox_manager
from app.services.sandbox.security import sandbox_security_profile

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


class SandboxRequest(BaseModel):
    code: str = Field(min_length=1, max_length=262144)
    language: str = "python"
    timeout: int = Field(default=10, ge=1, le=30)


@router.post("/execute")
def execute_sandbox(payload: SandboxRequest, x_employee_id: str | None = Header(None), x_role: str | None = Header(None)):
    result = sandbox_manager.execute(payload.code, payload.language, payload.timeout)
    if x_employee_id:
        audit(x_employee_id, None, x_role, "sandbox_execution", result.get("status", "unknown"))
    return result


@router.get("/security")
def sandbox_security():
    """Expose the non-secret sandbox hardening contract for local UI/demo use."""
    return sandbox_security_profile()
