"""Deterministic engineering calculations.

This module intentionally does not use an LLM for arithmetic.  Inputs are validated
before calculation and results include the formula, units, assumptions and warnings
so an agent can present the calculation transparently.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import hashlib
import json


class EngineeringInputError(ValueError):
    """Raised when engineering calculation inputs are invalid."""


def _positive(name: str, value: float) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise EngineeringInputError(f"{name} must be a number.") from exc
    if value <= 0:
        raise EngineeringInputError(f"{name} must be greater than zero.")
    return value


def _nonnegative(name: str, value: float) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise EngineeringInputError(f"{name} must be a number.") from exc
    if value < 0:
        raise EngineeringInputError(f"{name} must be zero or greater.")
    return value



def _canonical_hash(payload: dict[str, Any]) -> str:
    """Create a reproducible SHA-256 fingerprint for calculation evidence."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def attach_provenance(
    result: dict[str, Any],
    *,
    input_source: str = "explicit_input",
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Attach auditable provenance without changing the deterministic result values."""
    evidence = {
        "input_source": input_source,
        "evidence_refs": list(evidence_refs or []),
        "formula": result.get("formula"),
        "inputs": result.get("inputs", {}),
        "results": result.get("results", {}),
    }
    result["provenance"] = {
        "method": "deterministic_engine",
        "input_source": input_source,
        "evidence_refs": list(evidence_refs or []),
        "calculation_fingerprint_sha256": _canonical_hash(evidence),
    }
    return result


def add_uncertainty_and_sensitivity(
    result: dict[str, Any],
    *,
    sensitivity_percent: float = 5.0,
) -> dict[str, Any]:
    """Add transparent scenario sensitivity; no uncertainty is invented by default."""
    if sensitivity_percent <= 0 or sensitivity_percent > 50:
        raise EngineeringInputError("sensitivity_percent must be greater than 0 and at most 50.")

    result["uncertainty"] = {
        "status": "not_provided",
        "statement": "No measurement or material uncertainty was supplied, so no uncertainty interval is claimed.",
    }

    p = result.get("inputs", {})
    r = result.get("results", {})
    pct = sensitivity_percent / 100.0

    if result.get("calculation") == "barlow_pipe_pressure":
        # Local one-at-a-time sensitivity around each input. Other inputs remain fixed.
        base_capacity = r.get("pressure_capacity_mpa")
        base_hoop = r.get("hoop_stress_mpa")
        scenarios = []
        for name in ("pressure_mpa", "diameter_mm", "thickness_mm", "allowable_stress_mpa"):
            value = float(p[name])
            for direction in (-1, 1):
                changed = value * (1 + direction * pct)
                scenario = dict(p)
                scenario[name] = changed
                hoop = changed * scenario["diameter_mm"] / (2 * scenario["thickness_mm"])
                capacity = 2 * scenario["allowable_stress_mpa"] * scenario["thickness_mm"] / scenario["diameter_mm"]
                scenarios.append({
                    "input": name,
                    "change_percent": direction * sensitivity_percent,
                    "hoop_stress_mpa": hoop,
                    "pressure_capacity_mpa": capacity,
                    "pressure_margin_mpa": capacity - scenario["pressure_mpa"],
                })
        result["sensitivity"] = {
            "method": "one_at_a_time",
            "change_percent": sensitivity_percent,
            "baseline": {
                "hoop_stress_mpa": base_hoop,
                "pressure_capacity_mpa": base_capacity,
            },
            "scenarios": scenarios,
        }
    elif result.get("calculation") == "remaining_life":
        base_life = r.get("remaining_life_years")
        scenarios = []
        for name in ("current_thickness_mm", "minimum_required_thickness_mm", "corrosion_rate_mm_per_year"):
            value = float(p[name])
            for direction in (-1, 1):
                changed = value * (1 + direction * pct)
                scenario = dict(p)
                scenario[name] = changed
                if scenario["current_thickness_mm"] < scenario["minimum_required_thickness_mm"]:
                    life = None
                    status = "invalid"
                else:
                    life = (scenario["current_thickness_mm"] - scenario["minimum_required_thickness_mm"]) / scenario["corrosion_rate_mm_per_year"]
                    status = "valid"
                scenarios.append({
                    "input": name,
                    "change_percent": direction * sensitivity_percent,
                    "remaining_life_years": life,
                    "status": status,
                })
        result["sensitivity"] = {
            "method": "one_at_a_time",
            "change_percent": sensitivity_percent,
            "baseline": {"remaining_life_years": base_life},
            "scenarios": scenarios,
        }
    return result


def enrich_engineering_result(
    result: dict[str, Any],
    *,
    input_source: str = "explicit_input",
    evidence_refs: list[str] | None = None,
    sensitivity_percent: float = 5.0,
) -> dict[str, Any]:
    """Apply provenance, explicit assumptions/uncertainty status and sensitivity metadata."""
    attach_provenance(result, input_source=input_source, evidence_refs=evidence_refs)
    return add_uncertainty_and_sensitivity(result, sensitivity_percent=sensitivity_percent)

def barlow_pipe_pressure(
    pressure_mpa: float,
    diameter_mm: float,
    thickness_mm: float,
    allowable_stress_mpa: float,
) -> dict[str, Any]:
    """Calculate hoop stress and pressure margin using Barlow's thin-wall relation.

    Hoop stress: S_h = P*D/(2*t)
    Pressure capacity: P_cap = 2*S*t/D
    All inputs use MPa and mm so no conversion is hidden in the arithmetic.
    """
    p = _positive("pressure_mpa", pressure_mpa)
    d = _positive("diameter_mm", diameter_mm)
    t = _positive("thickness_mm", thickness_mm)
    s = _positive("allowable_stress_mpa", allowable_stress_mpa)

    hoop = p * d / (2.0 * t)
    capacity = 2.0 * s * t / d
    margin = capacity - p
    utilization = hoop / s

    result = {
        "calculation": "barlow_pipe_pressure",
        "formula": "hoop_stress = P*D/(2*t); pressure_capacity = 2*S*t/D",
        "inputs": {
            "pressure_mpa": p, "diameter_mm": d, "thickness_mm": t,
            "allowable_stress_mpa": s,
        },
        "results": {
            "hoop_stress_mpa": hoop,
            "pressure_capacity_mpa": capacity,
            "pressure_margin_mpa": margin,
            "utilization_ratio": utilization,
        },
        "assumptions": [
            "Thin-wall Barlow relation is used.",
            "Pressure, diameter and thickness are supplied in consistent units.",
            "Allowable stress is treated as an engineering input, not inferred by the model.",
        ],
        "warnings": (["Calculated pressure exceeds the supplied pressure capacity."]
                     if margin < 0 else []),
    }
    return enrich_engineering_result(result)


def remaining_life(
    current_thickness_mm: float,
    minimum_required_thickness_mm: float,
    corrosion_rate_mm_per_year: float,
) -> dict[str, Any]:
    """Calculate remaining life from thickness loss rate."""
    current = _positive("current_thickness_mm", current_thickness_mm)
    minimum = _positive("minimum_required_thickness_mm", minimum_required_thickness_mm)
    rate = _positive("corrosion_rate_mm_per_year", corrosion_rate_mm_per_year)

    if current < minimum:
        raise EngineeringInputError(
            "current_thickness_mm cannot be below minimum_required_thickness_mm."
        )

    remaining_thickness = current - minimum
    years = remaining_thickness / rate
    result = {
        "calculation": "remaining_life",
        "formula": "remaining_life_years = (current_thickness - minimum_required_thickness) / corrosion_rate",
        "inputs": {
            "current_thickness_mm": current,
            "minimum_required_thickness_mm": minimum,
            "corrosion_rate_mm_per_year": rate,
        },
        "results": {
            "remaining_thickness_mm": remaining_thickness,
            "remaining_life_years": years,
        },
        "assumptions": [
            "Corrosion rate is constant over the calculation period.",
            "No future inspection data or uncertainty factor is applied.",
        ],
        "warnings": [],
    }
    return enrich_engineering_result(result)


def validate_calculation_inputs(calculation: str, inputs: dict[str, Any]) -> dict[str, float]:
    """Validate and normalize API inputs before invoking a calculator."""
    if calculation == "barlow_pipe_pressure":
        required = ("pressure_mpa", "diameter_mm", "thickness_mm", "allowable_stress_mpa")
        validators = _positive
    elif calculation == "remaining_life":
        required = ("current_thickness_mm", "minimum_required_thickness_mm", "corrosion_rate_mm_per_year")
        validators = _positive
    else:
        raise EngineeringInputError(f"Unsupported engineering calculation: {calculation}")

    missing = [name for name in required if name not in inputs]
    if missing:
        raise EngineeringInputError(f"Missing required inputs: {', '.join(missing)}")

    normalized = {name: validators(name, inputs[name]) for name in required}
    if calculation == "remaining_life" and normalized["current_thickness_mm"] < normalized["minimum_required_thickness_mm"]:
        raise EngineeringInputError(
            "current_thickness_mm cannot be below minimum_required_thickness_mm."
        )
    return normalized
