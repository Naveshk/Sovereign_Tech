import asyncio
import json
import os
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.services.task_analyzer import analyze_task
from app.services.agent import run_agent
from app.services.model_router import planned_routes
from app.services.auth_db import (
    audit, record_file, ensure_conversation, append_conversation_message,
    conversation_context_history,
)
from app.services.context_manager import prepare_context
from app.models.schemas import WorkbenchState, WorkflowStage
from app.services.observability import OBSERVABILITY

router = APIRouter()
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".pdf", ".docx", ".pptx",
    ".xlsx", ".xls", ".zip", ".txt", ".md", ".csv"
}
FILE_TYPES = {
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image",
    ".pdf": "pdf", ".docx": "docx", ".pptx": "pptx", ".xlsx": "xlsx",
    ".xls": "xls", ".zip": "zip", ".txt": "text", ".md": "text", ".csv": "csv"
}


def _save_upload(file):
    if file is None:
        return None, None, None
    original = os.path.basename(file.filename or "uploaded_file")
    ext = os.path.splitext(original)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext or 'unknown'}")
    return original, FILE_TYPES.get(ext, "file"), os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")


async def _persist_file(file):
    original, file_type, file_path = _save_upload(file)
    if not file_path:
        return None, None, None

    size = 0
    try:
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Uploaded file exceeds the 50 MB limit.")
                f.write(chunk)
    except Exception:
        try:
            os.remove(file_path)
        except OSError:
            pass
        raise

    return file_path, file_type, original


def _event(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _run_agent_thread(message, analysis, file_path, employee_id=None, role=None, department=None, conversation_context=None, is_follow_up=False):
    return await asyncio.to_thread(
        run_agent, message, analysis, file_path, employee_id, role, department,
        conversation_context, is_follow_up
    )



def _prepare_conversation(conversation_id, employee_id, role, message, file_name=None, task_type=None):
    """Return the authoritative server-side context before recording the new user turn."""
    if not employee_id:
        return conversation_id, []
    if not role:
        raise HTTPException(status_code=403, detail="Authorized local user required.")
    conversation = ensure_conversation(conversation_id, employee_id, message or file_name or "New Chat")
    prior_history = conversation_context_history(conversation["id"], employee_id, limit=8)
    append_conversation_message(
        conversation["id"], employee_id, "user", message or f"Please analyze {file_name}",
        {"file_name": file_name, "task_type": task_type},
    )
    return conversation["id"], prior_history


def _save_assistant_turn(conversation_id, employee_id, result, analysis):
    if not employee_id or not conversation_id:
        return
    final = result.get("final_response") or result.get("final_context")
    if not final:
        results = result.get("results") or []
        if results:
            final = results[-1].get("response") or results[-1].get("content")
    if not final:
        final = result.get("response") or "No response returned."
    model = next((item.get("model") for item in (result.get("results") or []) if item.get("model")), None)
    append_conversation_message(
        conversation_id, employee_id, "assistant", str(final),
        {"task_type": analysis.get("task_type"), "model": model},
    )



@router.post("/chat")
async def chat(
    message: str = Form(""),
    conversation_id: str | None = Form(None),
    conversation_history: str | None = Form(None),
    file: UploadFile | None = File(None),
    x_employee_id: str | None = Header(None),
    x_role: str | None = Header(None),
    x_department: str | None = Header(None),
):
    file_path = file_type = original = None
    try:
        file_path, file_type, original = await _persist_file(file)
        if file_path and x_employee_id:
            record_file(x_employee_id, original or "uploaded_file", file_type, file_path)
        if x_employee_id:
            audit(x_employee_id, None, x_role, "chat_request", conversation_id or "new")
        conversation_id, server_history = _prepare_conversation(
            conversation_id, x_employee_id, x_role, message, original
        )
        context_source = server_history if x_employee_id else conversation_history
        context_info = prepare_context(message, context_source)
        analysis = analyze_task(message=message, file_path=file_path, file_type=file_type)
        routes = planned_routes(analysis)
        state = WorkbenchState.create(message, conversation_id, bool(file_path), original, file_type)
        state.task_analysis = analysis
        state.routes = routes
        state.transition(WorkflowStage.INGESTION, "completed", "Request and attachment ingested")
        state.transition(WorkflowStage.ROUTING, "completed", "Local model routes selected")
        state.transition(WorkflowStage.COMPILATION, "completed", "Execution plan compiled")
        state.transition(WorkflowStage.SANDBOX, "running" if analysis.get("requires_coding") else "skipped",
                         "Code execution requested" if analysis.get("requires_coding") else "No code execution required")
        result = await _run_agent_thread(message, analysis, file_path, x_employee_id, x_role, x_department, context_info["text"], context_info["is_follow_up"])
        state.sync_results(result)
        if analysis.get("requires_coding"):
            state.transition(WorkflowStage.SANDBOX, "completed", "Sandbox execution completed")
        state.transition(WorkflowStage.SYNTHESIS, "completed", "Final response assembled")
        state.observability = OBSERVABILITY.snapshot()["metrics"]
        state.finalize(result.get("status", "completed"), result.get("error"))
        result["workbench_state"] = state.model_dump(mode="json")
        _save_assistant_turn(conversation_id, x_employee_id, result, analysis)
        return {
            "conversation_id": conversation_id,
            "message": message,
            "task_analysis": analysis,
            "agent_result": result,
            "workbench_state": state.model_dump(mode="json"),
                "observability": OBSERVABILITY.snapshot()["metrics"],
            "file_attached": bool(file_path),
            "file_name": original,
            "conversation_context": {
                "used": bool(context_info["text"]),
                "is_follow_up": context_info["is_follow_up"],
                "message_count": context_info["message_count"],
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[chat_error] {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail="Request processing failed. Check the backend log for details.")


@router.post("/chat/stream")
async def chat_stream(
    message: str = Form(""),
    conversation_id: str | None = Form(None),
    conversation_history: str | None = Form(None),
    file: UploadFile | None = File(None),
    x_employee_id: str | None = Header(None),
    x_role: str | None = Header(None),
    x_department: str | None = Header(None),
):
    request_conversation_id = conversation_id

    async def generator() -> AsyncGenerator[str, None]:
        file_path = file_type = original = None
        active_conversation_id = request_conversation_id
        try:
            file_path, file_type, original = await _persist_file(file)
            if file_path and x_employee_id:
                record_file(x_employee_id, original or "uploaded_file", file_type, file_path)
            if x_employee_id:
                audit(x_employee_id, None, x_role, "chat_request", active_conversation_id or "new")
            active_conversation_id, server_history = _prepare_conversation(
                active_conversation_id, x_employee_id, x_role, message, original
            )
            context_source = server_history if x_employee_id else conversation_history
            context_info = prepare_context(message, context_source)

            analysis = analyze_task(message=message, file_path=file_path, file_type=file_type)
            routes = planned_routes(analysis)
            state = WorkbenchState.create(message, active_conversation_id, bool(file_path), original, file_type)
            state.task_analysis = analysis
            state.routes = routes
            state.transition(WorkflowStage.INGESTION, "running", "Receiving request and attachment")
            yield _event("stage", {"stage": WorkflowStage.INGESTION.value, "status": "running",
                                   "label": "Ingesting request and attachment"})
            state.transition(WorkflowStage.INGESTION, "completed", "Request and attachment ingested")
            yield _event("stage", {"stage": WorkflowStage.INGESTION.value, "status": "completed",
                                   "label": "Request and attachment ingested"})
            state.transition(WorkflowStage.ROUTING, "running", "Selecting local models")
            yield _event("stage", {"stage": WorkflowStage.ROUTING.value, "status": "running",
                                   "label": "Selecting local models"})
            yield _event("task", {
                "conversation_id": active_conversation_id,
                "task_analysis": analysis,
                "file_attached": bool(file_path),
                "file_name": original,
                "routes": routes,
                "conversation_context": {
                    "used": bool(context_info["text"]),
                    "is_follow_up": context_info["is_follow_up"],
                    "message_count": context_info["message_count"],
                },
            })
            state.transition(WorkflowStage.ROUTING, "completed", "Local model routes selected")
            yield _event("stage", {"stage": WorkflowStage.ROUTING.value, "status": "completed",
                                   "label": "Local model routes selected"})
            state.transition(WorkflowStage.COMPILATION, "running", "Compiling execution plan")
            yield _event("stage", {"stage": WorkflowStage.COMPILATION.value, "status": "running",
                                   "label": "Compiling execution plan"})
            yield _event("step", {
                "status": "completed", "step": 1, "operation": "task_analysis",
                "label": "Task analyzed", "task_type": analysis.get("task_type")
            })
            for index, route in enumerate(routes, start=2):
                yield _event("step", {
                    "status": "running", "step": index,
                    "operation": "model_routing",
                    "label": f"Routing {route.get('operation', 'task').replace('_', ' ')}",
                    "model": route.get("model_name"),
                    "ollama_model": route.get("ollama_model"),
                })

            state.transition(WorkflowStage.COMPILATION, "completed", "Execution plan compiled")
            yield _event("stage", {"stage": WorkflowStage.COMPILATION.value, "status": "completed",
                                   "label": "Execution plan compiled"})
            if analysis.get("requires_coding"):
                state.transition(WorkflowStage.SANDBOX, "running", "Executing generated code in isolated sandbox")
                yield _event("stage", {"stage": WorkflowStage.SANDBOX.value, "status": "running",
                                       "label": "Executing code in isolated sandbox"})
            else:
                state.transition(WorkflowStage.SANDBOX, "skipped", "No code execution required")
                yield _event("stage", {"stage": WorkflowStage.SANDBOX.value, "status": "skipped",
                                       "label": "Sandbox not required"})

            # Keep FastAPI's event loop responsive while synchronous local model/tool
            # work runs in a worker thread.
            task = asyncio.create_task(_run_agent_thread(message, analysis, file_path, x_employee_id, x_role, x_department, context_info["text"], context_info["is_follow_up"]))
            heartbeat_count = 0
            while not task.done():
                await asyncio.sleep(5)
                if not task.done():
                    heartbeat_count += 1
                    yield _event("progress", {
                        "status": "running",
                        "label": "Local processing in progress",
                        "elapsed_hint": heartbeat_count * 5,
                    })

            result = task.result()

            agent_failed = result.get("status") == "error"
            if analysis.get("requires_coding"):
                sandbox_status = "error" if agent_failed else "completed"
                sandbox_label = (
                    "Sandbox/workflow execution failed safely"
                    if agent_failed else "Sandbox execution completed"
                )
                state.transition(WorkflowStage.SANDBOX, sandbox_status, sandbox_label)
                yield _event("stage", {"stage": WorkflowStage.SANDBOX.value, "status": sandbox_status,
                                       "label": sandbox_label})
            state.sync_results(result)
            state.transition(
                WorkflowStage.SYNTHESIS,
                "error" if agent_failed else "running",
                "Workflow failed safely; no final artifact generated" if agent_failed
                else "Assembling final response and artifacts"
            )
            yield _event("stage", {"stage": WorkflowStage.SYNTHESIS.value, "status": "running",
                                   "label": "Assembling final response and artifacts"})

            for index, route in enumerate(routes, start=2):
                yield _event("step", {
                    "status": "completed", "step": index,
                    "operation": "model_routing",
                    "label": f"Selected {route.get('model_name', 'local model')}",
                    "model": route.get("model_name"),
                    "ollama_model": route.get("ollama_model"),
                })
            for item in result.get("results", []):
                yield _event("step", {
                    "status": "completed",
                    "step": item.get("step"),
                    "operation": item.get("operation"),
                    "model": item.get("model"),
                    "label": f"{str(item.get('operation', 'task')).replace('_', ' ').title()} completed",
                })
            if agent_failed:
                result["error"] = result.get("error") or "Agent workflow failed safely."
                state.transition(WorkflowStage.SYNTHESIS, "error", "Workflow failed safely; no final artifact generated")
                yield _event("stage", {"stage": WorkflowStage.SYNTHESIS.value, "status": "error",
                                       "label": "Workflow failed safely; no final artifact generated"})
            else:
                state.transition(WorkflowStage.SYNTHESIS, "completed", "Final response assembled")
                yield _event("stage", {"stage": WorkflowStage.SYNTHESIS.value, "status": "completed",
                                       "label": "Final response assembled"})
            state.observability = OBSERVABILITY.snapshot()["metrics"]
            state.finalize(result.get("status", "completed"), result.get("error"))
            result["workbench_state"] = state.model_dump(mode="json")
            _save_assistant_turn(active_conversation_id, x_employee_id, result, analysis)
            yield _event("complete", {
                "conversation_id": active_conversation_id,
                "message": message,
                "task_analysis": analysis,
                "agent_result": result,
                "workbench_state": state.model_dump(mode="json"),
                "observability": OBSERVABILITY.snapshot()["metrics"],
                "file_attached": bool(file_path),
                "file_name": original,
                "conversation_context": {
                    "used": bool(context_info["text"]),
                    "is_follow_up": context_info["is_follow_up"],
                    "message_count": context_info["message_count"],
                },
            })
        except Exception as exc:
            if "state" in locals():
                state.error = "The request could not be completed."
                if state.current_stage:
                    state.transition(state.current_stage, "error", state.error)
                state.finalize("error", state.error)
            print(f"[chat_stream_error] {type(exc).__name__}: {exc}")
            yield _event("error", {
                "error_type": "REQUEST_PROCESSING_ERROR",
                "message": "The request could not be completed. Check the backend log for details.",
            })
        finally:
            # Uploaded source files remain available for the audit/file metadata workflow.
            pass

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
