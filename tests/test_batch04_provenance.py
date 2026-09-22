from app.services.engineering_engine import (
    EngineeringInputError,
    barlow_pipe_pressure,
    remaining_life,
    enrich_engineering_result,
)


def test_barlow_has_reproducible_provenance():
    a = barlow_pipe_pressure(5, 500, 10, 120)
    b = barlow_pipe_pressure(5, 500, 10, 120)
    assert a["provenance"]["method"] == "deterministic_engine"
    assert a["provenance"]["calculation_fingerprint_sha256"] == b["provenance"]["calculation_fingerprint_sha256"]
    assert len(a["provenance"]["calculation_fingerprint_sha256"]) == 64


def test_uncertainty_is_not_invented():
    result = remaining_life(12, 8, 0.5)
    assert result["uncertainty"]["status"] == "not_provided"
    assert "No measurement" in result["uncertainty"]["statement"]


def test_sensitivity_is_explicit_scenario_analysis():
    result = remaining_life(12, 8, 0.5)
    sensitivity = result["sensitivity"]
    assert sensitivity["method"] == "one_at_a_time"
    assert sensitivity["change_percent"] == 5.0
    assert len(sensitivity["scenarios"]) == 6


def test_invalid_sensitivity():
    result = remaining_life(12, 8, 0.5)
    try:
        enrich_engineering_result(result, sensitivity_percent=0)
    except EngineeringInputError:
        return
    raise AssertionError("Expected invalid sensitivity error")


def test_custom_evidence_refs_and_source():
    result = barlow_pipe_pressure(5, 500, 10, 120)
    enrich_engineering_result(
        result,
        input_source="uploaded_inspection_report",
        evidence_refs=["inspection-report.pdf#page=3"],
        sensitivity_percent=10,
    )
    assert result["provenance"]["input_source"] == "uploaded_inspection_report"
    assert result["provenance"]["evidence_refs"] == ["inspection-report.pdf#page=3"]
    assert result["sensitivity"]["change_percent"] == 10.0
