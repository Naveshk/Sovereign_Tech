"""Central registry for all local models used by the workbench.

Keep model identifiers here so routing logic does not need to know concrete
Ollama tags. New local models can be added by extending MODEL_REGISTRY.
"""

MODEL_REGISTRY = {
    "qwen3": {
        "name": "Qwen3",
        "ollama_model": "qwen3:8b",
        "provider": "ollama",
        "enabled": True,
        "priority": 100,
        "capabilities": ["general", "reasoning", "writing", "synthesis"],
        "operations": ["general", "file_generation", "synthesis"],
    },
    "qwen2.5-vl": {
        "name": "Qwen2.5VL",
        "ollama_model": "qwen2.5vl:7b",
        "provider": "ollama",
        "enabled": True,
        "priority": 100,
        "capabilities": ["vision", "image", "ocr", "document_understanding"],
        "operations": ["vision"],
    },
    "qwen2.5-coder": {
        "name": "Qwen2.5-Coder",
        "ollama_model": "qwen2.5-coder:7b",
        "provider": "ollama",
        "enabled": True,
        "priority": 100,
        "capabilities": ["coding", "debugging", "programming"],
        "operations": ["coding"],
    },
    "qwen3-embedding": {
        "name": "Qwen3 Embedding",
        "ollama_model": "qwen3-embedding:0.6b",
        "provider": "ollama",
        "enabled": True,
        "priority": 100,
        "capabilities": ["embeddings", "retrieval"],
        "operations": ["embedding"],
    },
}

# Operations that are deterministic/local tools rather than LLM calls.
LOCAL_OPERATIONS = {
    "pdf_analysis": {"name": "PyMuPDF / local OCR / vision fallback", "provider": "local"},
    "excel_analysis": {"name": "pandas / openpyxl", "provider": "local"},
    "docx_analysis": {"name": "python-docx", "provider": "local"},
    "pptx_analysis": {"name": "python-pptx", "provider": "local"},
    "rag": {"name": "Qwen3-Embedding-0.6B + ChromaDB", "provider": "local"},
}


def get_model(model_id: str) -> dict:
    """Return a defensive copy of a registered model."""
    if model_id not in MODEL_REGISTRY:
        raise KeyError(f"Unknown model id: {model_id}")
    return dict(MODEL_REGISTRY[model_id])


def iter_enabled_models():
    """Yield enabled models in deterministic priority order."""
    return (
        (model_id, model)
        for model_id, model in sorted(
            MODEL_REGISTRY.items(),
            key=lambda item: (-item[1].get("priority", 0), item[0]),
        )
        if model.get("enabled", True)
    )


def models_for_operation(operation: str):
    """Return enabled models capable of an operation."""
    return [
        (model_id, model)
        for model_id, model in iter_enabled_models()
        if operation in model.get("operations", [])
    ]
