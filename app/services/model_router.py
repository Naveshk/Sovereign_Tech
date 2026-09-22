"""Dynamic task-to-model routing backed by the central model registry."""

from app.services.observability import timed
from app.services.model_registry import (
    LOCAL_OPERATIONS,
    get_model,
    models_for_operation,
)


# Compatibility aliases: existing callers can keep using these operation names.
OPERATION_CAPABILITIES = {
    "vision": "vision",
    "coding": "coding",
    "general": "general",
    "file_generation": "file_generation",
    "synthesis": "synthesis",
}


def _model_route(model_id: str, model: dict) -> dict:
    return {
        "model_id": model_id,
        "model_name": model["name"],
        "ollama_model": model["ollama_model"],
        "provider": model["provider"],
        "capabilities": model.get("capabilities", []),
    }


def _route_model_impl(task_analysis: dict, operation: str | None = None) -> dict:
    """Select a model from the registry based on the requested operation.

    The task analyzer describes *what* the task needs; this function decides
    *which registered model* can perform it. This keeps model names/tags out of
    the agent workflow and makes adding another local model configuration safe.
    """
    operation = operation or "general"
    capability = OPERATION_CAPABILITIES.get(operation, operation)

    candidates = models_for_operation(capability)
    if not candidates:
        # Safe compatibility fallback for an unknown operation.
        candidates = models_for_operation("general")

    if not candidates:
        raise RuntimeError(f"No enabled local model is registered for '{operation}'.")

    model_id, model = candidates[0]
    route = _model_route(model_id, model)
    return route


def route_model(task_analysis: dict, operation: str | None = None) -> dict:
    """Select and time one local model route without changing the route contract."""
    with timed("router.selection", metadata={"operation": operation or "general"}):
        return _route_model_impl(task_analysis, operation)


def _local_route(operation: str) -> dict:
    config = LOCAL_OPERATIONS[operation]
    return {
        "operation": operation,
        "model_name": config["name"],
        "provider": config["provider"],
    }


def planned_routes(task_analysis: dict) -> list[dict]:
    """Build an ordered execution plan from task requirements.

    Ordering is intentionally deterministic: file/local extraction first,
    knowledge retrieval next, LLM work after that, and file generation last.
    Existing operation names and response fields are preserved for the UI.
    """
    routes: list[dict] = []

    if task_analysis.get("analyze_pdf"):
        routes.append(_local_route("pdf_analysis"))
    elif task_analysis.get("requires_vision"):
        routes.append({"operation": "vision", **route_model(task_analysis, "vision")})

    if task_analysis.get("analyze_excel"):
        routes.append(_local_route("excel_analysis"))
    if task_analysis.get("analyze_docx"):
        routes.append(_local_route("docx_analysis"))
    if task_analysis.get("analyze_pptx"):
        routes.append(_local_route("pptx_analysis"))
    if task_analysis.get("requires_rag"):
        routes.append(_local_route("rag"))
    if task_analysis.get("requires_engineering_calculation"):
        routes.append({"operation": "engineering_calculation", "model_name": "deterministic engineering engine", "provider": "local"})

    if task_analysis.get("requires_coding"):
        routes.append({"operation": "coding", **route_model(task_analysis, "coding")})
    if task_analysis.get("requires_file_generation"):
        routes.append({"operation": "file_generation", **route_model(task_analysis, "file_generation")})

    if not routes:
        routes.append({"operation": "general", **route_model(task_analysis, "general")})

    return routes


def describe_task_route(task_analysis: dict) -> dict:
    """Return a compact routing summary for API/UI consumers."""
    routes = planned_routes(task_analysis)
    return {
        "task_type": task_analysis.get("task_type", "general"),
        "routes": routes,
        "models": [
            route["model_id"]
            for route in routes
            if route.get("model_id")
        ],
    }
