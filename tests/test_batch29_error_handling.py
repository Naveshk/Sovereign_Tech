
import os

import app.services.resilience as resilience
import app.services.agent as agent


def test_resilient_generation_timeout_is_bounded(monkeypatch):
    def slow_call(model, prompt):
        import time
        time.sleep(0.2)
        return "late"

    monkeypatch.setattr(resilience, "_ollama_generate_response", slow_call)
    breaker = resilience.ModelCircuitBreaker(failure_threshold=3, recovery_seconds=1)

    try:
        resilience.resilient_generate_response(
            "test-model", "hello",
            max_attempts=1,
            timeout_seconds=0.03,
            circuit_breaker=breaker,
        )
        assert False, "expected timeout"
    except RuntimeError as exc:
        assert "failed after bounded retries" in str(exc)

    assert breaker.status("test-model")["failures"] == 1


def test_run_agent_returns_safe_fallback(monkeypatch):
    def fail(*args, **kwargs):
        raise TimeoutError("model timeout")

    monkeypatch.setattr(agent, "_run_agent_impl", fail)
    result = agent.run_agent("test", {"task_type": "general"})

    assert result["status"] == "error"
    assert result["fallback"]["used"] is True
    assert result["fallback"]["error_code"] == "LOCAL_MODEL_TIMEOUT"
    assert result["generated_files"] == []
    assert "No final artifact was generated" in result["final_response"]


def test_model_timeout_configuration_is_bounded(monkeypatch):
    monkeypatch.setenv("SWB_MODEL_TIMEOUT_SECONDS", "9999")
    monkeypatch.setattr(
        agent,
        "resilient_generate_response",
        lambda model, prompt, **kwargs: (
            "ok" if kwargs["timeout_seconds"] == 300.0 else (_ for _ in ()).throw(AssertionError())
        ),
    )
    assert agent.generate_response("model", "prompt") == "ok"


def test_stream_error_state_is_not_marked_completed():
    import inspect
    from app.api import chat

    source = inspect.getsource(chat.chat_stream)
    assert 'agent_failed = result.get("status") == "error"' in source
    assert '"status": "error"' in source
    assert "Workflow failed safely; no final artifact generated" in source
