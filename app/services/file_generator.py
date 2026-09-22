import os
import re
from typing import Any

from docx import Document


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GENERATED_DIR = os.path.join(BASE_DIR, "data", "generated")

os.makedirs(GENERATED_DIR, exist_ok=True)


def create_document_title(message: str) -> str:
    message = (message or "").strip()
    if not message:
        return "Generated Document"

    prefixes = [
        "generate",
        "create",
        "make",
        "write",
        "prepare"
    ]

    title = message

    # Remove command prefix
    for prefix in prefixes:
        if title.lower().startswith(prefix):
            title = title[len(prefix):].strip()
            break

    # Remove articles
    title = re.sub(
        r"\b(a|an|the)\b",
        "",
        title,
        flags=re.IGNORECASE
    )

    # Remove extra spaces
    title = re.sub(
        r"\s+",
        " ",
        title
    ).strip()

    if not title:
        title = "Generated Document"

    return title.title()



def generate_approval_note_docx(
    content: str,
    title: str = "Approval Note",
    requester: str | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
) -> dict:
    """Create a deterministic, review-ready approval note without changing factual content."""
    document = Document()
    document.add_heading(title or "Approval Note", level=1)

    if requester:
        p = document.add_paragraph()
        p.add_run("Requester: ").bold = True
        p.add_run(str(requester))

    p = document.add_paragraph()
    p.add_run("Status: ").bold = True
    p.add_run("Pending human approval")

    document.add_heading("Approval Request", level=2)
    document.add_paragraph(
        "This note presents the request and supporting information for human review. "
        "Approval is not implied by document generation."
    )

    # Reuse the existing Markdown renderer by building a temporary document body.
    body = (content or "").strip()
    if body:
        document.add_heading("Supporting Details", level=2)
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("### "):
                document.add_heading(line[4:].strip(), level=3)
            elif line.startswith("## "):
                document.add_heading(line[3:].strip(), level=3)
            elif line.startswith("# "):
                document.add_heading(line[2:].strip(), level=3)
            elif line.startswith("- "):
                document.add_paragraph(line[2:].strip(), style="List Bullet")
            elif re.match(r"^\d+\.\s+", line):
                document.add_paragraph(re.sub(r"^\d+\.\s+", "", line), style="List Number")
            else:
                document.add_paragraph(line)

    if evidence_refs:
        document.add_heading("Evidence References", level=2)
        table = document.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        for cell, value in zip(table.rows[0].cells, ["Source", "Page", "Chunk", "Classification"]):
            cell.text = value
        for ref in evidence_refs:
            cells = table.add_row().cells
            cells[0].text = str(ref.get("source") or ref.get("filename") or "—")
            cells[1].text = str(ref.get("page") or "—")
            cells[2].text = str(ref.get("chunk_index") or "—")
            cells[3].text = str(ref.get("classification") or "—")

    document.add_heading("Decision", level=2)
    document.add_paragraph("Decision: ______________________________________________")
    document.add_paragraph("Reviewer / Approver: __________________________________")
    document.add_paragraph("Date: ____________________    Signature: ____________________")

    filename = create_safe_filename(title or "Approval Note")
    file_path = os.path.join(GENERATED_DIR, filename)
    document.save(file_path)
    return {
        "filename": filename,
        "file_path": file_path,
        "file_type": "docx",
        "title": title or "Approval Note",
        "document_kind": "approval_note",
    }


def create_safe_filename(title: str) -> str:
    title = (title or "").strip()
    if not title:
        title = "Generated Document"

    filename = title.lower()

    filename = re.sub(
        r"[^a-z0-9]+",
        "_",
        filename
    )

    filename = filename.strip("_")

    if not filename:
        filename = "generated_document"

    return f"{filename}.docx"


def generate_docx(
    content: str,
    title: str = "Generated Document"
) -> dict:

    document = Document()

    # Add document title
    document.add_heading(
        title,
        level=1
    )

    # Process generated Markdown content, including simple Markdown tables.
    paragraphs = content.splitlines()
    i = 0

    while i < len(paragraphs):
        paragraph = paragraphs[i].strip()
        if not paragraph:
            i += 1
            continue

        if paragraph.startswith("|") and paragraph.endswith("|"):
            table_rows = []
            while i < len(paragraphs):
                line = paragraphs[i].strip()
                if not (line.startswith("|") and line.endswith("|")):
                    break
                cells = [c.strip() for c in line.strip("|").split("|")]
                if not all(set(c) <= set("-: ") for c in cells):
                    table_rows.append(cells)
                i += 1
            if len(table_rows) >= 2:
                table = document.add_table(rows=0, cols=len(table_rows[0]))
                table.style = "Table Grid"
                for row_values in table_rows:
                    cells = table.add_row().cells
                    for idx, value in enumerate(row_values):
                        if idx < len(cells):
                            cells[idx].text = value
                document.add_paragraph()
            continue

        if paragraph.startswith("### "):
            document.add_heading(paragraph[4:].strip(), level=3)
        elif paragraph.startswith("## "):
            document.add_heading(paragraph[3:].strip(), level=2)
        elif paragraph.startswith("# "):
            document.add_heading(paragraph[2:].strip(), level=1)
        elif paragraph == "---":
            document.add_paragraph("────────────────────────")
        elif paragraph.startswith("- "):
            document.add_paragraph(paragraph[2:].strip(), style="List Bullet")
        elif re.match(r"^\d+\.\s+", paragraph):
            document.add_paragraph(re.sub(r"^\d+\.\s+", "", paragraph), style="List Number")
        else:
            document.add_paragraph(paragraph)
        i += 1

    # Create filename
    filename = create_safe_filename(title)

    # Create complete path
    file_path = os.path.join(
        GENERATED_DIR,
        filename
    )

    # Save document
    document.save(file_path)

    print("📄 Filename:", filename)
    print("📁 File path:", file_path)

    return {
        "filename": filename,
        "file_path": file_path,
        "file_type": "docx",
        "title": title,
    }