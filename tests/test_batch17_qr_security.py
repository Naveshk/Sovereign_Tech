from app.services.artifact_security import (
    QR_SCHEMA,
    build_qr_payload,
    parse_qr_payload,
    qr_svg,
    security_view,
    verify_qr_payload,
)
from app.services.provenance import build_artifact_provenance, sha256_file


def _provenance(tmp_path):
    path = tmp_path / "approval.pdf"
    path.write_bytes(b"approved artifact")
    artifact = {
        "filename": path.name,
        "file_path": str(path),
        "artifact_type": "pdf",
        "title": "Approval Note",
        "sha256": sha256_file(path),
    }
    draft = {
        "id": "DR-17",
        "version": 2,
        "revision_group": "RG-17",
        "parent_draft_id": "DR-16",
        "content": "Approved content",
        "source_path": "local/report.pdf",
    }
    provenance = build_artifact_provenance(
        artifact=artifact,
        draft=draft,
        review_id=17,
        reviewer_employee_id="E17",
        reviewer_username="reviewer",
        reviewer_role="Engineer",
    )
    return path, draft, artifact, provenance


def test_qr_payload_round_trip(tmp_path):
    _, _, _, provenance = _provenance(tmp_path)
    payload = build_qr_payload(provenance)
    parsed = parse_qr_payload(payload)

    assert parsed["schema"] == QR_SCHEMA
    assert parsed["provenance_id"] == provenance["provenance_id"]
    assert parsed["sha256"] == provenance["artifact"]["sha256"]
    assert parsed["provenance_sha256"] == provenance["provenance_sha256"]


def test_qr_svg_is_renderable(tmp_path):
    _, _, _, provenance = _provenance(tmp_path)
    svg = qr_svg(build_qr_payload(provenance))
    assert svg.startswith("<?xml")
    assert "<svg" in svg
    assert len(svg) > 1000


def test_security_view_exposes_integrity_metadata(tmp_path):
    path, draft, artifact, provenance = _provenance(tmp_path)
    draft["metadata"] = {
        "final_artifact": {
            **artifact,
            "draft_id": draft["id"],
            "draft_version": draft["version"],
            "provenance_id": provenance["provenance_id"],
            "provenance_sha256": provenance["provenance_sha256"],
            "sha256": provenance["artifact"]["sha256"],
        },
        "provenance": provenance,
    }
    view = security_view(draft)
    assert view["integrity"]["provenance_valid"] is True
    assert view["qr"]["payload"].startswith(QR_SCHEMA + "|")
    assert view["qr"]["svg_url"].endswith("/qr")


def test_qr_verification_detects_tampering(tmp_path, monkeypatch):
    path, draft, artifact, provenance = _provenance(tmp_path)
    final_artifact = {
        **artifact,
        "draft_id": draft["id"],
        "draft_version": draft["version"],
        "provenance_id": provenance["provenance_id"],
        "provenance_sha256": provenance["provenance_sha256"],
        "sha256": provenance["artifact"]["sha256"],
    }
    draft["metadata"] = {"final_artifact": final_artifact, "provenance": provenance}
    payload = build_qr_payload(provenance)

    monkeypatch.setattr(
        "app.services.auth_db.list_drafts",
        lambda limit=500: [draft],
    )
    assert verify_qr_payload(payload)["valid"] is True

    path.write_bytes(b"tampered artifact")
    result = verify_qr_payload(payload)
    assert result["valid"] is False
    assert result["status"] == "mismatch"
    assert result["artifact"]["hash_matches"] is False
