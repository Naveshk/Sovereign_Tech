import importlib, tempfile
from pathlib import Path

def _fresh_db(monkeypatch, tmp_path):
    mod=importlib.import_module("app.services.auth_db")
    monkeypatch.setattr(mod, "DB_PATH", Path(tmp_path) / "audit.db")
    mod.init_db()
    return mod

def test_audit_ledger_chain_and_verification(monkeypatch, tmp_path):
    mod=_fresh_db(monkeypatch,tmp_path)
    mod.audit("E1","alice","Engineer","chat_request","c1")
    mod.audit("E1","alice","Engineer","file_upload","f1")
    result=mod.verify_audit_ledger()
    assert result["valid"] is True
    assert result["checked_entries"] == 2

def test_audit_tamper_is_detected(monkeypatch, tmp_path):
    mod=_fresh_db(monkeypatch,tmp_path)
    mod.audit("E1","alice","Engineer","chat_request","c1")
    with mod._conn() as c:
        c.execute("UPDATE audit_logs SET resource='tampered' WHERE id=1")
    result=mod.verify_audit_ledger()
    assert result["valid"] is False
    assert "hash mismatch" in result["reason"].lower()
