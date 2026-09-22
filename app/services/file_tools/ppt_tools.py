from __future__ import annotations

from pathlib import Path
import re
from pptx import Presentation


def analyze_pptx(path: str) -> dict:
    p = Path(path)
    prs = Presentation(p)
    slides = []
    for number, slide in enumerate(prs.slides, start=1):
        texts = []
        tables = []
        notes = ""
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False):
                text = shape.text.strip()
                if text:
                    texts.append(text)
            if getattr(shape, "has_table", False):
                rows = []
                for row in shape.table.rows:
                    rows.append([cell.text.strip() for cell in row.cells])
                tables.append(rows)
        try:
            if slide.has_notes_slide:
                notes = "\n".join(
                    shape.text.strip()
                    for shape in slide.notes_slide.notes_text_frame.paragraphs
                    if shape.text.strip()
                )
        except Exception:
            notes = ""
        slides.append({
            "slide": number,
            "title": texts[0] if texts else "",
            "texts": texts,
            "tables": tables,
            "notes": notes,
            "shape_count": len(slide.shapes),
        })
    return {
        "file": p.name,
        "slide_count": len(slides),
        "slides": slides,
        "text": "\n\n".join(
            f"Slide {s['slide']}: {s['title']}\n" + "\n".join(s["texts"][1:] if s["texts"] else [])
            for s in slides
        )
    }


def generate_pptx(output_path: str, title: str, content: str, source_name: str | None = None) -> dict:
    """Create a validated, presentation-ready deck from Markdown-like model output.

    The interface is intentionally unchanged for backward compatibility.
    Markdown tables become real PowerPoint tables; headings become slide titles;
    bullets and prose become readable text. No external assets or network calls
    are required.
    """
    from pptx.util import Inches, Pt

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    prs = Presentation()
    prs.core_properties.title = title or "Sovereign AI Workbench"
    prs.core_properties.author = "Sovereign AI Workbench"

    # Title slide.
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = title or "Generated Presentation"
    subtitle = slide.placeholders[1]
    subtitle.text = "Sovereign AI Workbench"
    if source_name:
        subtitle.text += f"\nSource: {source_name}"

    def add_content_slide(heading: str, items: list[str], table: list[list[str]] | None = None):
        if not heading and not items and not table:
            return
        s = prs.slides.add_slide(prs.slide_layouts[5])  # title-only layout
        s.shapes.title.text = heading or "Details"

        if table:
            cols = max(len(row) for row in table)
            rows = len(table)
            if cols:
                shape = s.shapes.add_table(
                    rows, cols, Inches(0.55), Inches(1.45), Inches(12.2), Inches(5.1)
                )
                tbl = shape.table
                # Keep column widths usable for both short and long source tables.
                width = Inches(12.2 / cols)
                for col in tbl.columns:
                    col.width = width
                for r, row in enumerate(table):
                    for c in range(cols):
                        cell = tbl.cell(r, c)
                        cell.text = row[c] if c < len(row) else ""
                        for para in cell.text_frame.paragraphs:
                            para.font.size = Pt(12 if r else 13)
                            if r == 0:
                                para.font.bold = True
            return

        box = s.shapes.add_textbox(Inches(0.75), Inches(1.45), Inches(11.8), Inches(5.2))
        tf = box.text_frame
        tf.word_wrap = True
        tf.clear()
        for i, item in enumerate(items or ["No additional details provided."]):
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            para.text = item
            para.level = 0
            para.font.size = Pt(20)

    current_title = None
    bullets: list[str] = []
    current_table: list[list[str]] | None = None

    def flush():
        nonlocal current_title, bullets, current_table
        if current_title is not None or bullets or current_table:
            add_content_slide(current_title, bullets, current_table)
        current_title, bullets, current_table = None, [], None

    lines = (content or "").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("#"):
            flush()
            current_title = line.lstrip("# ").strip()
            i += 1
            continue
        if line.startswith("|") and line.endswith("|"):
            table_rows = []
            while i < len(lines):
                candidate = lines[i].strip()
                if not (candidate.startswith("|") and candidate.endswith("|")):
                    break
                cells = [c.strip() for c in candidate.strip("|").split("|")]
                if not all(set(c) <= set("-: ") for c in cells):
                    table_rows.append(cells)
                i += 1
            if table_rows:
                if bullets:
                    flush()
                    current_title = current_title or "Details"
                current_table = table_rows
                flush()
            continue
        if line.startswith("- "):
            bullets.append(line[2:].strip())
        elif re.match(r"^\d+\.\s+", line):
            bullets.append(re.sub(r"^\d+\.\s+", "", line))
        else:
            bullets.append(line)
        i += 1

    flush()

    # Guarantee a usable deck even when model output is empty.
    if len(prs.slides) == 1:
        add_content_slide("Summary", ["No structured content was returned."])

    prs.save(path)

    # Re-open for structural validation.
    check = Presentation(path)
    if len(check.slides) < 1:
        raise ValueError("Generated PPTX contains no slides.")
    for slide in check.slides:
        if slide.shapes.title is None or not slide.shapes.title.text.strip():
            raise ValueError("Generated PPTX contains a slide without a title.")

    return {
        "filename": path.name,
        "file_path": str(path),
        "file_type": "pptx",
        "title": title,
        "slides": len(check.slides),
    }

