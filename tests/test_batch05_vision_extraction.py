import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.vision_service import extract_engineering_fields, build_extraction_schema


def test_engineering_extraction_is_conservative():
    text = """Equipment Tag: P-101
Line No: L-20
Pressure: 10.5 MPa
Temperature: 120 C
Current Thickness: 8.2 mm
Corrosion Rate: 0.12 mm/year
"""
    fields = extract_engineering_fields(text)
    assert fields["equipment_tag"] == "P-101"
    assert fields["line_number"] == "L-20"
    assert fields["pressure_mpa"] == 10.5
    assert fields["temperature_c"] == 120.0
    assert fields["thickness_mm"] == 8.2
    assert fields["corrosion_rate_mm_per_year"] == 0.12
    assert fields["diameter_mm"] is None


def test_schema_marks_missing_without_guessing():
    schema = build_extraction_schema(
        image_path="/tmp/pid.png",
        ocr_text="Pressure: 4.0 MPa",
        vision_text="",
        vision_used=False,
    )
    assert schema["fields"]["pressure_mpa"] == 4.0
    assert schema["fields"]["diameter_mm"] is None
    assert "diameter_mm" in schema["missing_fields"]
    assert schema["source"]["ocr_used"] is True
