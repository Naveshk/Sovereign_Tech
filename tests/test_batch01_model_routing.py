from app.services.model_registry import MODEL_REGISTRY, LOCAL_OPERATIONS
from app.services.model_router import route_model, planned_routes


def test_registry_contains_core_models():
    assert {"qwen3", "qwen2.5-vl", "qwen2.5-coder"}.issubset(MODEL_REGISTRY)


def test_route_model_uses_registry():
    route = route_model({"task_type": "coding"}, "coding")
    assert route["model_id"] == "qwen2.5-coder"
    assert route["ollama_model"] == MODEL_REGISTRY["qwen2.5-coder"]["ollama_model"]


def test_route_model_vision():
    route = route_model({"task_type": "multimodal"}, "vision")
    assert "vision" in route["capabilities"]


def test_planned_routes_preserve_local_operations():
    routes = planned_routes({
        "task_type": "multimodal_coding",
        "requires_vision": True,
        "requires_coding": True,
        "requires_rag": False,
        "requires_file_generation": False,
        "analyze_pdf": False,
        "analyze_excel": False,
        "analyze_docx": False,
        "analyze_pptx": False,
    })
    assert [r["operation"] for r in routes] == ["vision", "coding"]
    assert "pdf_analysis" in LOCAL_OPERATIONS
