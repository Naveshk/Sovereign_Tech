from app.models.schemas import WorkbenchState, WorkflowStage


def test_workbench_state_has_five_stages():
    state = WorkbenchState.create("analyze report", "conv-1", False, None, None)
    assert [s.name.value for s in state.stages] == [
        "INGESTION", "ROUTING", "COMPILATION", "SANDBOX", "SYNTHESIS"
    ]


def test_workbench_state_transition_is_typed_and_serializable():
    state = WorkbenchState.create("run python", "conv-1", False, None, None)
    state.transition(WorkflowStage.INGESTION, "completed", "ingested")
    state.transition(WorkflowStage.SANDBOX, "running", "executing")
    payload = state.model_dump(mode="json")
    assert payload["current_stage"] == "SANDBOX"
    assert payload["stages"][0]["status"] == "completed"
    assert payload["stages"][3]["status"] == "running"
