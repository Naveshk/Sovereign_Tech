from fastapi import APIRouter
from app.services.network.monitor import connection_snapshot, tcpdump_available
from app.services.network.policy import NETWORK_POLICY
from app.services.network.security import security_controls
from app.services.network.evidence import tcpdump_capability, capture_tcpdump_evidence, read_evidence
from app.services.auth_db import require_reviewer_identity
router=APIRouter(prefix="/network",tags=["network"])

@router.get("/status")
def network_status():
    snapshot=connection_snapshot()
    external=snapshot.get("external_connections",0)
    policy_blocks_external=not NETWORK_POLICY.external_outbound_allowed
    return {"air_gapped":external==0 and policy_blocks_external,"external_connections":external,"cloud_calls":snapshot.get("cloud_calls",0),"local_connections":snapshot.get("local_connections",0),"firewall":"deployment-configured" if policy_blocks_external else "not-enforced","sandbox_network":NETWORK_POLICY.sandbox_network,"tcpdump_available":tcpdump_available(),"evidence_note":snapshot.get("note"),"controls":security_controls()}

@router.get("/controls")
def network_controls():
    return security_controls()


@router.get("/evidence/status")
def network_evidence_status():
    """Report tcpdump capability without claiming that capture is active."""
    return {"tcpdump": tcpdump_capability(), "recent_evidence": read_evidence()}


@router.post("/evidence/capture")
def network_evidence_capture(duration_seconds: int = 10, packet_count: int = 100,
                             employee_id: str = "", username: str = "", role: str = ""):
    """Manager-controlled, short header-only tcpdump capture for offline proof."""
    identity = require_reviewer_identity(employee_id, username, role)
    if identity["role"] != "Manager":
        from fastapi import HTTPException
        raise HTTPException(403, "Manager role required for network evidence capture.")
    return {
        "identity": {"employee_id": identity["employee_id"], "role": identity["role"]},
        "evidence": capture_tcpdump_evidence(duration_seconds, packet_count),
    }
