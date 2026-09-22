"""Batch 17 artifact security and QR verification helpers.

QR payloads are local, deterministic security references. They do not transmit
artifact contents or call an external service.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote, unquote

from reportlab.graphics import renderSVG
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing

from app.services.provenance import sha256_file, verify_provenance_record

QR_SCHEMA = "SWB1"
GENERATED_DIR = Path(__file__).resolve().parents[2] / "data" / "generated"


def build_qr_payload(provenance: dict) -> str:
    artifact = provenance.get("artifact") or {}
    return "|".join([
        QR_SCHEMA,
        str(provenance.get("provenance_id") or ""),
        str(artifact.get("sha256") or ""),
        str(provenance.get("provenance_sha256") or ""),
        str(artifact.get("filename") or ""),
    ])


def parse_qr_payload(payload: str) -> dict:
    parts = (payload or "").strip().split("|", 4)
    if len(parts) != 5 or parts[0] != QR_SCHEMA:
        raise ValueError("Invalid Sovereign Workbench QR payload.")
    schema, provenance_id, sha256, provenance_sha256, filename = parts
    if len(sha256) != 64 or len(provenance_sha256) != 64:
        raise ValueError("QR payload contains an invalid SHA-256 value.")
    if not provenance_id or not filename:
        raise ValueError("QR payload is incomplete.")
    return {
        "schema": schema,
        "provenance_id": provenance_id,
        "sha256": sha256.lower(),
        "provenance_sha256": provenance_sha256.lower(),
        "filename": filename,
    }


def qr_svg(payload: str, size: int = 220) -> str:
    """Render a QR code as an SVG without writing a temporary image file."""
    widget = qr.QrCodeWidget(payload)
    widget.barWidth = size
    widget.barHeight = size
    drawing = Drawing(size, size)
    drawing.add(widget)
    return renderSVG.drawToString(drawing)


def security_view(draft: dict) -> dict:
    metadata = draft.get("metadata") or {}
    artifact = metadata.get("final_artifact") or {}
    provenance = metadata.get("provenance") or {}
    if not artifact or not provenance:
        raise ValueError("Final artifact security metadata is unavailable.")

    payload = build_qr_payload(provenance)
    return {
        "draft_id": draft.get("id"),
        "draft_version": draft.get("version"),
        "artifact": artifact,
        "provenance": provenance,
        "qr": {
            "schema": QR_SCHEMA,
            "payload": payload,
            "svg_url": f"/api/artifacts/{quote(str(draft.get('id')), safe='')}/qr",
        },
        "integrity": {
            "provenance_valid": verify_provenance_record(provenance),
            "artifact_hash_recorded": bool(artifact.get("sha256")),
        },
    }


def verify_qr_payload(payload: str) -> dict:
    """Verify QR claims against the local generated artifact and provenance."""
    claim = parse_qr_payload(payload)

    # Search the local SQLite-backed draft metadata through the existing
    # service rather than introducing a second artifact registry.
    from app.services.auth_db import list_drafts
    matches = []
    for draft in list_drafts(limit=500):
        metadata = draft.get("metadata") or {}
        provenance = metadata.get("provenance") or {}
        artifact = metadata.get("final_artifact") or {}
        if provenance.get("provenance_id") == claim["provenance_id"]:
            matches.append((draft, artifact, provenance))

    if not matches:
        return {
            "valid": False,
            "status": "not_found",
            "message": "Provenance record was not found in the local workbench.",
            "claim": claim,
        }

    draft, artifact, provenance = matches[0]
    provenance_valid = verify_provenance_record(provenance)
    recorded_hash = (provenance.get("artifact") or {}).get("sha256", "").lower()
    filename_matches = artifact.get("filename") == claim["filename"]
    hash_matches = recorded_hash == claim["sha256"] == str(artifact.get("sha256") or "").lower()
    provenance_hash_matches = provenance.get("provenance_sha256", "").lower() == claim["provenance_sha256"]

    path = Path(artifact.get("file_path") or "")
    file_exists = path.is_file()
    current_hash = sha256_file(path) if file_exists else None
    file_hash_matches = bool(file_exists and current_hash == claim["sha256"])

    valid = all([
        provenance_valid,
        filename_matches,
        hash_matches,
        provenance_hash_matches,
        file_hash_matches,
    ])
    return {
        "valid": valid,
        "status": "verified" if valid else "mismatch",
        "message": (
            "Artifact, SHA-256 and provenance verified locally."
            if valid else
            "QR claims do not match the current local artifact/provenance."
        ),
        "claim": claim,
        "draft": {
            "id": draft.get("id"),
            "version": draft.get("version"),
            "revision_group": draft.get("revision_group"),
        },
        "artifact": {
            "filename": artifact.get("filename"),
            "file_exists": file_exists,
            "sha256": current_hash,
            "expected_sha256": claim["sha256"],
            "hash_matches": file_hash_matches,
        },
        "integrity": {
            "provenance_valid": provenance_valid,
            "filename_matches": filename_matches,
            "recorded_hash_matches": hash_matches,
            "provenance_hash_matches": provenance_hash_matches,
        },
    }
