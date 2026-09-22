import json
from app.services.receipt_service import receipt_payload, build_receipt_pdf
from app.services.auth_db import init_db, audit, get_audit_receipt, verify_receipt_payload

def test_receipt_payload_is_self_contained():
    r={"version":"1","audit_id":7,"entry_hash":"abc123","created_at":"2026-01-01T00:00:00Z","action":"chat","resource":"x","status":"success"}
    p=receipt_payload(r)
    assert p["type"]=="sovereign-ai-audit-receipt"
    assert p["audit_id"]==7 and p["entry_hash"]=="abc123"

def test_receipt_pdf_contains_pdf_signature():
    r={"version":"1","audit_id":7,"entry_hash":"abc123","created_at":"2026-01-01T00:00:00Z","action":"chat","resource":"x","status":"success"}
    assert build_receipt_pdf(r).startswith(b"%PDF")

def test_local_receipt_verification(tmp_path, monkeypatch):
    import app.services.auth_db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path/"test.db")
    init_db()
    h=audit("E1","u","Manager","test","resource")
    row=get_audit_receipt(1)
    result=verify_receipt_payload({"audit_id":1,"entry_hash":h})
    assert result["valid"] is True
    bad=verify_receipt_payload({"audit_id":1,"entry_hash":"0"*64})
    assert bad["valid"] is False
