import importlib
from pathlib import Path


def _fresh_db(monkeypatch, tmp_path):
    mod = importlib.import_module("app.services.auth_db")
    monkeypatch.setattr(mod, "DB_PATH", Path(tmp_path) / "audit.db")
    mod.init_db()
    return mod


def test_context_linked_audit_is_ledger_protected(monkeypatch, tmp_path):
    mod = _fresh_db(monkeypatch, tmp_path)
    mod.audit(
        "E1", "alice", "Engineer", "artifact_generated", "DR-1", "success",
        entity_type="artifact", entity_id="report.pdf", correlation_id="C-1",
        provenance_id="PV-ABC", artifact_sha256="a" * 64, review_id=7,
        draft_id="DR-1", draft_version=2,
        metadata={"artifact_type": "pdf", "content_sha256": "b" * 64},
    )
    result = mod.verify_audit_ledger()
    assert result["valid"] is True
    rows = mod.list_audit()
    assert rows[0]["provenance_id"] == "PV-ABC"
    assert rows[0]["review_id"] == 7
    assert rows[0]["metadata"]["artifact_type"] == "pdf"


def test_audit_context_tamper_is_detected(monkeypatch, tmp_path):
    mod = _fresh_db(monkeypatch, tmp_path)
    mod.audit("E1", "alice", "Engineer", "artifact_generated", "DR-1", "success",
              entity_type="artifact", entity_id="report.pdf", provenance_id="PV-1")
    with mod._conn() as c:
        c.execute("UPDATE audit_logs SET provenance_id='PV-TAMPERED' WHERE id=1")
    result = mod.verify_audit_ledger()
    assert result["valid"] is False
    assert "hash mismatch" in result["reason"].lower()


def test_legacy_audit_hashes_remain_verifiable(monkeypatch, tmp_path):
    mod = _fresh_db(monkeypatch, tmp_path)
    mod.audit("E1", "alice", "Engineer", "chat_request", "c1")
    # Batch 26 columns exist, but an old-style event has no meaningful context.
    assert mod.verify_audit_ledger()["valid"] is True


def test_provenance_timeline_selectors(monkeypatch, tmp_path):
    mod = _fresh_db(monkeypatch, tmp_path)
    mod.audit("E1", "alice", "Engineer", "draft_created", "DR-1", "success",
              entity_type="draft", entity_id="DR-1", draft_id="DR-1", draft_version=1)
    mod.audit("E2", "bob", "Manager", "human_review_approved", "DR-1", "approved",
              entity_type="human_review", entity_id="9", review_id=9, draft_id="DR-1", draft_version=1)
    mod.audit("E2", "bob", "Manager", "final_artifact_generated", "DR-1", "success",
              entity_type="artifact", entity_id="report.pdf", provenance_id="PV-9",
              artifact_sha256="c" * 64, review_id=9, draft_id="DR-1", draft_version=1)

    by_draft = mod.list_audit_provenance(draft_id="DR-1")
    by_review = mod.list_audit_provenance(review_id=9)
    by_prov = mod.list_audit_provenance(provenance_id="PV-9")
    assert [x["action"] for x in by_draft] == ["draft_created", "human_review_approved", "final_artifact_generated"]
    assert len(by_review) == 2
    assert by_prov[0]["artifact_sha256"] == "c" * 64
