
"""Batch 30 critical-path API integration tests.

These tests intentionally mock the local model/tool boundary so the full FastAPI
request lifecycle is exercised without requiring Ollama, Docker, tcpdump, or a
live external service.
"""
import json
import sys
import types

# Keep the API integration tests runnable in a clean test environment where the
# optional local Ollama Python package is not installed. The actual Ollama client
# is still exercised by the application's normal runtime when installed.
if "ollama" not in sys.modules:
    try:
        import ollama  # noqa: F401
    except ImportError:
        ollama_stub = types.ModuleType("ollama")
        ollama_stub.chat = lambda **kwargs: {"message": {"content": ""}}
        ollama_stub.embeddings = lambda **kwargs: {"embedding": []}
        sys.modules["ollama"] = ollama_stub

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import chat as chat_api


@pytest.fixture()
def client(monkeypatch):
    analysis = {
        "task_type": "general",
        "requires_coding": False,
        "requires_vision": False,
        "requires_rag": False,
        "requires_engineering_calculation": False,
    }
    routes = [{"operation": "general", "model_name": "Qwen Local", "ollama_model": "qwen2.5:7b"}]
    result = {
        "message": "hello",
        "task_analysis": analysis,
        "results": [{
            "step": 1, "operation": "general", "model": "Qwen Local",
            "response": "Local integration response"
        }],
        "generated_files": [],
        "final_context": "",
        "final_response": "Local integration response",
        "status": "completed",
        "conversation_context": {"used": False, "is_follow_up": False},
    }

    monkeypatch.setattr(chat_api, "analyze_task", lambda **kwargs: dict(analysis))
    monkeypatch.setattr(chat_api, "planned_routes", lambda a: list(routes))
    monkeypatch.setattr(chat_api, "_run_agent_thread", lambda *args, **kwargs: _async_value(result))
    monkeypatch.setattr(chat_api, "audit", lambda *args, **kwargs: None)
    return TestClient(app)


async def _async_value(value):
    return value


def _events(text):
    events = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event = "message"
        data_lines = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
        if data_lines:
            events.append((event, json.loads("\n".join(data_lines))))
    return events


def test_chat_sync_critical_path(client):
    response = client.post("/api/chat", data={"message": "hello"})
    assert response.status_code == 200
    body = response.json()

    assert body["agent_result"]["status"] == "completed"
    assert body["agent_result"]["final_response"] == "Local integration response"
    state = body["workbench_state"]
    assert state["status"] == "completed"
    assert state["completed_at"]
    assert state["results"]
    assert state["stages"]


def test_chat_stream_critical_path(client):
    response = client.post("/api/chat/stream", data={"message": "hello"})
    assert response.status_code == 200
    events = _events(response.text)
    names = [name for name, _ in events]

    assert "task" in names
    assert "complete" in names
    assert names[-1] == "complete"

    complete = next(data for name, data in events if name == "complete")
    assert complete["agent_result"]["status"] == "completed"
    assert complete["workbench_state"]["status"] == "completed"

    synthesis = [
        data for name, data in events
        if name == "stage" and data.get("stage") == "SYNTHESIS"
    ]
    assert synthesis[-1]["status"] == "completed"


def test_chat_stream_failure_never_emits_completed_synthesis(monkeypatch):
    analysis = {
        "task_type": "general",
        "requires_coding": False,
        "requires_vision": False,
        "requires_rag": False,
        "requires_engineering_calculation": False,
    }
    monkeypatch.setattr(chat_api, "analyze_task", lambda **kwargs: dict(analysis))
    monkeypatch.setattr(
        chat_api, "planned_routes",
        lambda a: [{"operation": "general", "model_name": "Qwen Local", "ollama_model": "qwen2.5:7b"}],
    )
    failed = {
        "status": "error",
        "results": [{
            "step": 1, "operation": "error_recovery", "status": "error",
            "error_type": "LOCAL_MODEL_TIMEOUT",
            "response": "The local model exceeded the configured time limit.",
        }],
        "generated_files": [],
        "final_response": "The local model exceeded the configured time limit. No final artifact was generated.",
    }
    monkeypatch.setattr(chat_api, "_run_agent_thread", lambda *args, **kwargs: _async_value(failed))
    monkeypatch.setattr(chat_api, "audit", lambda *args, **kwargs: None)

    response = TestClient(app).post("/api/chat/stream", data={"message": "timeout"})
    assert response.status_code == 200
    events = _events(response.text)

    synthesis = [
        data for name, data in events
        if name == "stage" and data.get("stage") == "SYNTHESIS"
    ]
    assert synthesis
    assert synthesis[-1]["status"] == "error"
    assert not any(item.get("status") == "completed" for item in synthesis)

    complete = next(data for name, data in events if name == "complete")
    assert complete["agent_result"]["status"] == "error"
    assert complete["workbench_state"]["status"] == "error"
    assert complete["agent_result"]["generated_files"] == []


def test_health_endpoint_smoke():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
