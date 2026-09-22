from pathlib import Path
import tempfile

import fitz

from app.services.ocr_service import local_ocr
from app.services.ollama_client import analyze_image
from app.services.model_registry import get_model


def analyze_pdf(path: str, vision_model: str | None = None) -> dict:
    if vision_model is None:
        vision_model = get_model("qwen2.5-vl")["ollama_model"]
    doc = fitz.open(path)
    try:
        pages = []
        total_chars = 0
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            total_chars += len(text)
            pages.append({"page": i + 1, "text": text})

        if total_chars >= 80:
            return {
                "mode": "text",
                "pages": pages,
                "text": "\n\n".join(
                    f"Page {p['page']}:\n{p['text']}" for p in pages if p["text"]
                ),
            }

        # Scanned/image-only PDF: local OCR first, then the existing local vision model.
        results = []
        ocr_used = False
        vision_used = False
        with tempfile.TemporaryDirectory(prefix="sovereign_pdf_") as temp_dir:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
                image_path = Path(temp_dir) / f"page_{i + 1}.png"
                pix.save(str(image_path))
                ocr = local_ocr.extract(image_path)

                if ocr.get("text", "").strip():
                    ocr_used = True
                    results.append({
                        "page": i + 1,
                        "text": ocr["text"],
                        "source": "PaddleOCR",
                    })
                    continue

                vision_used = True
                answer = analyze_image(
                    vision_model,
                    "Extract and summarize all visible text, tables, labels and important visual details from this PDF page. Preserve exact values where readable. Do not invent missing information.",
                    str(image_path),
                )
                results.append({
                    "page": i + 1,
                    "text": answer,
                    "source": "Qwen2.5-VL",
                })

        mode = (
            "ocr" if ocr_used and not vision_used
            else "ocr+vision" if ocr_used
            else "vision"
        )
        return {
            "mode": mode,
            "pages": results,
            "text": "\n\n".join(
                f"Page {p['page']}:\n{p['text']}" for p in results
            ),
        }
    finally:
        doc.close()
