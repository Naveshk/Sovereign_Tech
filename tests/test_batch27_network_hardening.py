import os
import subprocess
from pathlib import Path

from app.services.network.evidence import (
    _tcpdump_command, capture_tcpdump_evidence, tcpdump_capability,
)


def test_tcpdump_command_is_header_only():
    cmd = _tcpdump_command(10, 100)
    assert cmd[:2] == ["tcpdump", "-nn"]
    assert "-l" in cmd and "-c" in cmd
    assert "-w" not in cmd  # no packet-payload pcap is stored


def test_tcpdump_capability_truthful(monkeypatch):
    import app.services.network.evidence as ev
    monkeypatch.setattr(ev.shutil, "which", lambda name: "/usr/bin/tcpdump" if name == "tcpdump" else None)
    c = tcpdump_capability()
    assert c["available"] is True
    assert c["path"].endswith("tcpdump")


def test_capture_permission_denied_is_truthful(tmp_path, monkeypatch):
    import app.services.network.evidence as ev
    monkeypatch.setattr(ev, "EVIDENCE_DIR", tmp_path)
    monkeypatch.setattr(ev.shutil, "which", lambda name: "/usr/bin/tcpdump")
    def denied(*args, **kwargs):
        raise PermissionError("need root")
    monkeypatch.setattr(ev.subprocess, "Popen", denied)
    r = capture_tcpdump_evidence(10, 100)
    assert r["status"] == "permission_denied"
    assert r["path"] is None


def test_capture_writes_metadata_and_packet_headers(tmp_path, monkeypatch):
    import app.services.network.evidence as ev
    monkeypatch.setattr(ev, "EVIDENCE_DIR", tmp_path)
    monkeypatch.setattr(ev.shutil, "which", lambda name: "/usr/bin/tcpdump")

    class FakeProc:
        returncode = 0
        def communicate(self, timeout=None):
            return ("1.0 IP 127.0.0.1.5000 > 127.0.0.1.6000: TCP\n", "")
        def terminate(self): pass
        def kill(self): pass

    monkeypatch.setattr(ev.subprocess, "Popen", lambda *a, **k: FakeProc())
    r = capture_tcpdump_evidence(10, 100)
    assert r["status"] == "captured"
    files = list(tmp_path.glob("tcpdump_*.txt"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "packet_limit=100" in content
    assert "127.0.0.1" in content

def test_network_evidence_status(monkeypatch):
    import app.api.network as api
    monkeypatch.setattr(api, "tcpdump_capability", lambda: {"available": True, "path": "/usr/bin/tcpdump", "platform": "Linux", "reason": "ok"})
    monkeypatch.setattr(api, "read_evidence", lambda: [])
    result = api.network_evidence_status()
    assert result["tcpdump"]["available"] is True


def test_network_evidence_capture_requires_manager(monkeypatch):
    import app.api.network as api
    from fastapi import HTTPException
    monkeypatch.setattr(api, "require_reviewer_identity", lambda *a, **k: {"employee_id": "E1", "role": "Engineer"})
    try:
        api.network_evidence_capture(employee_id="E1", username="u", role="Engineer")
        assert False
    except HTTPException as exc:
        assert exc.status_code == 403


def test_network_evidence_capture_manager(monkeypatch):
    import app.api.network as api
    monkeypatch.setattr(api, "require_reviewer_identity", lambda *a, **k: {"employee_id": "M1", "role": "Manager"})
    monkeypatch.setattr(api, "capture_tcpdump_evidence", lambda *a: {"status": "captured"})
    result = api.network_evidence_capture(employee_id="M1", username="m", role="Manager")
    assert result["evidence"]["status"] == "captured"
