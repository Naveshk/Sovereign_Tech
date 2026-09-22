from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.engineering_engine import (
    EngineeringInputError,
    barlow_pipe_pressure,
    remaining_life,
    enrich_engineering_result,
)

router = APIRouter(prefix="/engineering", tags=["engineering"])


class BarlowRequest(BaseModel):
    pressure_mpa: float = Field(gt=0)
    diameter_mm: float = Field(gt=0)
    thickness_mm: float = Field(gt=0)
    allowable_stress_mpa: float = Field(gt=0)
    sensitivity_percent: float = Field(default=5.0, gt=0, le=50)
    input_source: str = Field(default="api_payload", min_length=1, max_length=200)
    evidence_refs: list[str] = Field(default_factory=list, max_length=50)


class RemainingLifeRequest(BaseModel):
    current_thickness_mm: float = Field(gt=0)
    minimum_required_thickness_mm: float = Field(gt=0)
    corrosion_rate_mm_per_year: float = Field(gt=0)
    sensitivity_percent: float = Field(default=5.0, gt=0, le=50)
    input_source: str = Field(default="api_payload", min_length=1, max_length=200)
    evidence_refs: list[str] = Field(default_factory=list, max_length=50)


@router.post("/calculate/barlow")
def calculate_barlow(payload: BarlowRequest) -> dict[str, Any]:
    try:
        data = payload.model_dump()
        sensitivity = data.pop("sensitivity_percent")
        source = data.pop("input_source")
        refs = data.pop("evidence_refs")
        return enrich_engineering_result(barlow_pipe_pressure(**data), input_source=source, evidence_refs=refs, sensitivity_percent=sensitivity)
    except EngineeringInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/calculate/remaining-life")
def calculate_remaining_life(payload: RemainingLifeRequest) -> dict[str, Any]:
    try:
        data = payload.model_dump()
        sensitivity = data.pop("sensitivity_percent")
        source = data.pop("input_source")
        refs = data.pop("evidence_refs")
        return enrich_engineering_result(remaining_life(**data), input_source=source, evidence_refs=refs, sensitivity_percent=sensitivity)
    except EngineeringInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
