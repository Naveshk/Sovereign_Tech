"""Local OCR adapter.

PaddleOCR is optional so the existing workbench can still run without a large OCR
runtime. When PaddleOCR is installed, scanned pages use it first; the existing
Qwen2.5-VL local vision fallback remains available for complex/handwritten pages.
"""
from pathlib import Path


class LocalOCR:
    def __init__(self):
        self._engine = None
        self._error = None

    def available(self) -> bool:
        return self._load() is not None

    def _load(self):
        if self._engine is not None:
            return self._engine
        if self._error:
            return None
        try:
            from paddleocr import PaddleOCR
            try:
                self._engine = PaddleOCR(lang="en")
            except TypeError:
                self._engine = PaddleOCR(lang="en", use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False)
            return self._engine
        except Exception as exc:
            self._error = str(exc)
            return None

    @staticmethod
    def _collect_text(value) -> list[str]:
        texts: list[str] = []
        if isinstance(value, str):
            if value.strip():
                texts.append(value.strip())
        elif isinstance(value, dict):
            for key in ("rec_texts", "text", "texts", "transcription"):
                item = value.get(key)
                if isinstance(item, list):
                    texts.extend(str(x).strip() for x in item if str(x).strip())
                elif isinstance(item, str) and item.strip():
                    texts.append(item.strip())
            for item in value.values():
                if isinstance(item, (dict, list)):
                    texts.extend(LocalOCR._collect_text(item))
        elif isinstance(value, (list, tuple)):
            # PaddleOCR v2 commonly returns [[box, (text, score)], ...].
            for item in value:
                if isinstance(item, (list, tuple)) and len(item) >= 2 and isinstance(item[1], (list, tuple)):
                    candidate = item[1][0] if item[1] else ""
                    if isinstance(candidate, str) and candidate.strip():
                        texts.append(candidate.strip())
                texts.extend(LocalOCR._collect_text(item))
        return texts

    def extract(self, image_path: str | Path) -> dict:
        engine = self._load()
        if engine is None:
            return {"available": False, "text": "", "error": self._error or "PaddleOCR is not installed."}
        path = str(image_path)
        try:
            if hasattr(engine, "predict"):
                output = engine.predict(path)
            else:
                output = engine.ocr(path, cls=True)
            texts = self._collect_text(output)
            # Preserve order while removing duplicates produced by recursive parsing.
            unique = list(dict.fromkeys(texts))
            return {"available": True, "text": "\n".join(unique), "error": None}
        except Exception as exc:
            return {"available": True, "text": "", "error": str(exc)}


local_ocr = LocalOCR()
