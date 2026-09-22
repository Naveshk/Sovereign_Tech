"""Offline audit receipt generation. QR payload contains no network dependency."""
import json
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode import qr
from reportlab.graphics import renderPDF

def receipt_payload(receipt: dict) -> dict:
    return {
        "type": "sovereign-ai-audit-receipt",
        "version": receipt.get("version", "1"),
        "audit_id": receipt["audit_id"],
        "entry_hash": receipt["entry_hash"],
        "created_at": receipt["created_at"],
    }

def build_receipt_pdf(receipt: dict) -> bytes:
    payload = receipt_payload(receipt)
    qr_value = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Sovereign AI Workbench — Offline Audit Receipt", styles["Title"]),
        Spacer(1, 12),
        Paragraph("This receipt can be verified against the local audit ledger without an external service.", styles["BodyText"]),
        Spacer(1, 14),
    ]
    drawing = Drawing(180, 180)
    code = qr.QrCodeWidget(qr_value)
    code.barWidth = 180
    code.barHeight = 180
    drawing.add(code)
    story += [drawing, Spacer(1, 14)]
    data = [
        ["Audit ID", str(receipt["audit_id"])],
        ["Action", str(receipt["action"])],
        ["Resource", str(receipt["resource"])],
        ["Status", str(receipt["status"])],
        ["Created", str(receipt["created_at"])],
        ["Entry SHA-256", str(receipt["entry_hash"])],
    ]
    table = Table(data, colWidths=[120, 350])
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(table)
    story += [Spacer(1, 12), Paragraph("QR payload is self-contained; verification requires only the local Workbench ledger.", styles["BodyText"])]
    doc.build(story)
    return stream.getvalue()
