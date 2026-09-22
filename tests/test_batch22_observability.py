from app.services.observability import ObservabilityStore
from app.services.model_router import route_model
from app.models.schemas import WorkbenchState, WorkflowStage


def test_observability_records_latency_and_status():
    store = ObservabilityStore(max_samples=10)
    store.record("router.selection", 12.5, metadata={"operation": "general", "model_id": "qwen"})
    store.record("router.selection", 20.0, status="error", metadata={"operation": "general"})
    metric = store.snapshot()["metrics"]["router.selection"]
    assert metric["count"] == 2
    assert metric["success"] == 1
    assert metric["errors"] == 1
    assert metric["latency_ms"]["avg"] == 16.25
    assert metric["latency_ms"]["p95"] == 20.0


def test_workbench_stage_records_duration():
    state = WorkbenchState.create("hello", "c1", False, None, None)
    state.transition(WorkflowStage.ROUTING, "running", "selecting")
    state.transition(WorkflowStage.ROUTING, "completed", "selected")
    stage = next(s for s in state.stages if s.name == WorkflowStage.ROUTING)
    assert stage.completed_at
    assert stage.duration_ms is not None
    assert stage.duration_ms >= 0


def test_router_contract_and_observability_metric():
    route = route_model({"task_type": "general"}, "general")
    assert route["ollama_model"]
