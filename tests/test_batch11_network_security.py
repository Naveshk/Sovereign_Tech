from app.services.network.security import is_local_target, validate_outbound_url, security_controls
def test_sovereignty_controls_are_explicit():
 c=security_controls(); assert c["external_outbound"]["status"]=="BLOCKED"; assert c["cloud_calls"]["status"]=="BLOCKED"; assert c["sandbox_network"]["mode"]=="disabled"; assert c["host_firewall"]["status"]=="DEPLOYMENT_REQUIRED"
def test_local_targets_allowed_and_external_blocked():
 assert is_local_target("127.0.0.1"); assert is_local_target("192.168.1.10"); assert validate_outbound_url("http://127.0.0.1:11434")[0]; ok,reason=validate_outbound_url("https://example.com"); assert not ok and "blocked" in reason.lower()
def test_network_status_contract(monkeypatch):
 import app.api.network as api
 monkeypatch.setattr(api,"connection_snapshot",lambda:{"external_connections":0,"cloud_calls":0,"local_connections":2,"note":"test snapshot"}); monkeypatch.setattr(api,"tcpdump_available",lambda:True)
 r=api.network_status(); assert r["air_gapped"] is True; assert r["controls"]["external_outbound"]["status"]=="BLOCKED"; assert r["tcpdump_available"] is True
