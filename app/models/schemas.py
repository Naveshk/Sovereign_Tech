from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class WorkflowStage(str, Enum):
    INGESTION = "INGESTION"
    ROUTING = "ROUTING"
    COMPILATION = "COMPILATION"
    SANDBOX = "SANDBOX"
    SYNTHESIS = "SYNTHESIS"


class StageState(BaseModel):
    name: WorkflowStage
    status: str = "pending"
    label: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    detail: str | None = None
    duration_ms: float | None = None


class WorkbenchState(BaseModel):
    """Typed, serializable state shared by the chat workflow.

    This is deliberately additive: existing task_analysis/results payloads remain
    unchanged, while the state gives the UI and future agent nodes one stable contract.
    """
    request_id: str
    workflow_version: str = "1.0"
    conversation_id: str | None = None
    message: str = ""
    file_attached: bool = False
    file_name: str | None = None
    file_type: str | None = None
    task_analysis: dict[str, Any] = Field(default_factory=dict)
    routes: list[dict[str, Any]] = Field(default_factory=list)
    stages: list[StageState] = Field(default_factory=list)
    current_stage: WorkflowStage | None = None
    results: list[dict[str, Any]] = Field(default_factory=list)
    generated_files: list[dict[str, Any]] = Field(default_factory=list)
    final_response: str | None = None
    status: str = "running"
    error: str | None = None
    observability: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    completed_at: str | None = None
    duration_ms: float | None = None

    @classmethod
    def create(cls, message: str, conversation_id: str | None, file_attached: bool,
               file_name: str | None, file_type: str | None) -> "WorkbenchState":
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            request_id=f"wb-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            workflow_version="1.0",
            conversation_id=conversation_id,
            message=message,
            file_attached=file_attached,
            file_name=file_name,
            file_type=file_type,
            created_at=now,
            stages=[StageState(name=s, label=s.value.title()) for s in WorkflowStage],
        )

    def sync_results(self, result: dict[str, Any]) -> None:
        """Merge agent output into the typed workflow state without changing legacy result keys."""
        self.results = list(result.get("results") or [])
        self.generated_files = list(result.get("generated_files") or [])
        self.final_response = result.get("final_response") or result.get("final_context")

    def finalize(self, status: str = "completed", error: str | None = None) -> None:
        """Close the workflow and calculate total wall-clock duration."""
        now = datetime.now(timezone.utc)
        self.completed_at = now.isoformat()
        self.status = status
        self.error = error
        if self.created_at:
            try:
                started = datetime.fromisoformat(self.created_at)
                self.duration_ms = round((now - started).total_seconds() * 1000, 3)
            except ValueError:
                self.duration_ms = None
        self.current_stage = None

    def transition(self, stage: WorkflowStage, status: str, detail: str | None = None) -> StageState:
        target = next(s for s in self.stages if s.name == stage)
        now = datetime.now(timezone.utc).isoformat()
        target.status = status
        target.detail = detail
        if status == "running" and not target.started_at:
            target.started_at = now
        if status in {"completed", "skipped", "error"}:
            target.completed_at = now
            if target.started_at:
                try:
                    started = datetime.fromisoformat(target.started_at)
                    finished = datetime.fromisoformat(now)
                    target.duration_ms = round((finished - started).total_seconds() * 1000, 3)
                except ValueError:
                    target.duration_ms = None
        if status == "running":
            self.current_stage = stage
        elif self.current_stage == stage and status != "running":
            self.current_stage = None
        return target
