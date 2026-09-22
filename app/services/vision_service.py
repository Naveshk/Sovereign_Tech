"""Local vision/OCR pipeline for industrial images.

OCR is attempted first when available. Vision is used as a fallback and, for
visual engineering documents (P&IDs/drawings/diagrams), as a second pass because
OCR alone cannot capture symbols, topology, arrows, or visual relationships.

All extracted engineering values are represented explicitly; missing values are
``None`` rather than guessed.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.services.model_registry import get_model
from app.services.ocr_service import local_ocr


ENGINEERING_FIELDS = {
    "equipment_tag": "Equipment/tag identifier",
    "line_number": "Line number",
    "pipe_size": "Nominal pipe size",
    "material": "Material/specification",
    "pressure_mpa": "Pressure in MPa",
    "temperature_c": "Temperature in °C",
    "thickness_mm": "Measured/current thickness in mm",
    "minimum_required_thickness_mm": "Minimum required thickness in mm",
    "corrosion_rate_mm_per_year": "Corrosion rate in mm/year",
    "diameter_mm": "Diameter in mm",
    "allowable_stress_mpa": "Allowable stress in MPa",
    "flow_rate": "Flow rate, including stated unit",
    "valve_tags": "Valve identifiers",
    "instrument_tags": "Instrument identifiers",
}


def _first(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _number(pattern: str, text: str) -> float | None:
    value = _first(pattern, text)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_engineering_fields(text: str) -> dict[str, Any]:
    """Conservative field extraction from OCR/vision text.

    This parser only returns values that are explicitly present in the source
    text. It intentionally does not convert units or infer missing values.
    """
    source = text or ""
    equipment = _first(
        r"\b(?:equipment|equip|tag)\s*(?:tag|id|number)?\s*[:=#-]\s*([A-Z0-9][A-Z0-9._/-]*)",
        source,
    )
    line = _first(
        r"\bline(?:\s*(?:no|number))?\s*[:=#-]\s*([A-Z0-9][A-Z0-9._/-]*)",
        source,
    )
    pipe_size = _first(
        r"\b(?:pipe\s*size|nominal\s*(?:pipe\s*)?size|nps)\s*[:=#-]\s*([0-9A-Z./-]+)",
        source,
    )
    material = _first(r"\bmaterial\s*[:=#-]\s*([A-Z0-9._ /-]+?)(?=\n|,|;|$)", source)

    return {
        "equipment_tag": equipment,
        "line_number": line,
        "pipe_size": pipe_size,
        "material": material,
        "pressure_mpa": _number(r"\bpressure(?:\s*\(?(?:mpa)\)?)?\s*[:=#-]\s*(-?\d+(?:\.\d+)?)\s*(?:mpa)?", source),
        "temperature_c": _number(r"\btemperature\s*[:=#-]\s*(-?\d+(?:\.\d+)?)\s*(?:°?\s*c|c)?", source),
        "thickness_mm": _number(r"\b(?:current|measured|wall)\s*thickness\s*[:=#-]\s*(-?\d+(?:\.\d+)?)\s*mm", source),
        "minimum_required_thickness_mm": _number(r"\b(?:minimum|required|min)\s*(?:required\s*)?thickness\s*[:=#-]\s*(-?\d+(?:\.\d+)?)\s*mm", source),
        "corrosion_rate_mm_per_year": _number(r"\bcorrosion\s*rate\s*[:=#-]\s*(-?\d+(?:\.\d+)?)\s*mm\s*(?:/|per)\s*year", source),
        "diameter_mm": _number(r"\b(?:diameter|od|outside\s*diameter)\s*[:=#-]\s*(-?\d+(?:\.\d+)?)\s*mm", source),
        "allowable_stress_mpa": _number(r"\ballowable\s*stress\s*[:=#-]\s*(-?\d+(?:\.\d+)?)\s*(?:mpa)?", source),
        "flow_rate": _first(r"\bflow\s*rate\s*[:=#-]\s*([^\n,;]+)", source),
        "valve_tags": re.findall(r"\b(?:valve|v)\s*(?:tag)?\s*[:=#-]\s*([A-Z0-9][A-Z0-9._/-]*)", source, flags=re.IGNORECASE) or [],
        "instrument_tags": re.findall(r"\b(?:instrument|instr|i)\s*(?:tag)?\s*[:=#-]\s*([A-Z0-9][A-Z0-9._/-]*)", source, flags=re.IGNORECASE) or [],
    }


def build_extraction_schema(
    *,
    image_path: str,
    ocr_text: str = "",
    vision_text: str = "",
    vision_used: bool = False,
) -> dict[str, Any]:
    combined = "\n".join(x for x in (ocr_text, vision_text) if x).strip()
    fields = extract_engineering_fields(combined)
    present = [key for key, value in fields.items() if value not in (None, "", [])]

    if not combined:
        confidence = "none"
    elif vision_used and ocr_text:
        confidence = "review_required"
    elif vision_used:
        confidence = "vision_review_required"
    else:
        confidence = "ocr"

    return {
        "schema_version": "1.0",
        "source": {
            "filename": Path(image_path).name,
            "ocr_used": bool(ocr_text.strip()),
            "vision_used": bool(vision_used),
        },
        "confidence": confidence,
        "fields": fields,
        "present_fields": present,
        "missing_fields": [key for key in ENGINEERING_FIELDS if key not in present],
        "raw_ocr_text": ocr_text,
        "raw_vision_text": vision_text,
        "warnings": [
            "Extracted values must be verified against the source image before engineering calculations.",
            "Missing values are represented as null; no values are inferred or unit-converted.",
        ],
    }


def analyze_industrial_image(
    image_path: str,
    user_prompt: str,
    *,
    force_vision: bool = False,
) -> dict[str, Any]:
    ocr = local_ocr.extract(image_path)
    ocr_text = (ocr.get("text") or "").strip()

    # P&IDs/drawings/diagrams need visual context even if OCR succeeded.
    prompt_lower = (user_prompt or "").lower()
    visual_structure = any(
        word in prompt_lower
        for word in ("p&id", "diagram", "drawing", "handwritten", "photo", "image")
    )
    use_vision = force_vision or visual_structure or not ocr_text

    vision_text = ""
    if use_vision:
        # Lazy import keeps OCR/schema utilities usable in environments where
        # the optional Ollama Python client is not installed yet.
        from app.services.ollama_client import analyze_image
        model = get_model("qwen2.5-vl")["ollama_model"]
        vision_text = analyze_image(
            model,
            (
                "Analyze this industrial image locally. Extract only information "
                "actually visible. Preserve exact tags, labels, numbers and units. "
                "For P&IDs/drawings, describe visible equipment, line numbers, "
                "valves, instruments and connections. For handwriting, preserve "
                "uncertain characters rather than guessing. Do not invent missing values."
            ),
            image_path,
        )

    schema = build_extraction_schema(
        image_path=image_path,
        ocr_text=ocr_text,
        vision_text=vision_text,
        vision_used=bool(vision_text),
    )
    return {
        "ocr": {
            "available": bool(ocr.get("available")),
            "text": ocr_text,
            "error": ocr.get("error"),
        },
        "vision": {
            "used": bool(vision_text),
            "text": vision_text,
        },
        "engineering_extraction": schema,
    }
