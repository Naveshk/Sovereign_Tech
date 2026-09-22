from app.models.schemas import WorkbenchState, WorkflowStage


def test_workbench_state_has_workflow_identity_and_lifecycle():
    state = WorkbenchState.create("make a report", "conv-1", False, None, None)
    assert state.request_id.startswith("wb-")
    assert state.workflow_version == "1.0"
    assert state.created_at
    assert state.status == "running"

    state.transition(WorkflowStage.ROUTING, "running", "Selecting local models")
    state.transition(WorkflowStage.ROUTING, "completed", "Local model routes selected")
    state.finalize("completed")

    assert state.completed_at
    assert state.duration_ms is not None
    assert state.duration_ms >= 0
    assert state.current_stage is None


def test_workbench_state_syncs_agent_results_without_changing_contract():
    state = WorkbenchState.create("generate docx", "conv-2", True, "input.pdf", "pdf")
    result = {
        "results": [{"step": 1, "operation": "reasoning", "response": "draft"}],
        "generated_files": [{"filename": "report.docx", "download_url": "/api/files/report.docx"}],
        "final_response": "Draft prepared.",
        "status": "completed",
    }
    state.sync_results(result)

    assert state.results == result["results"]
    assert state.generated_files == result["generated_files"]
    assert state.final_response == "Draft prepared."
    assert state.file_attached is True
    assert state.file_name == "input.pdf"


def test_workbench_state_error_finalization_preserves_error():
    state = WorkbenchState.create("run code", None, False, None, None)
    state.transition(WorkflowStage.SANDBOX, "running", "Executing in sandbox")
    state.transition(WorkflowStage.SANDBOX, "error", "Sandbox failed")
    state.finalize("error", "The request could not be completed.")

    assert state.status == "error"
    assert state.error == "The request could not be completed."
    sandbox = next(s for s in state.stages if s.name == WorkflowStage.SANDBOX)
    assert sandbox.status == "error"
    assert sandbox.duration_ms is not None
