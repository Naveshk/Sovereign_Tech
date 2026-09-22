import pytest

from app.services.resilience import (
    ModelCircuitBreaker,
    ModelCircuitOpenError,
    blind_resample,
    resilient_generate_response,
)


def test_batch21_bounded_retry_then_success(monkeypatch):
    calls = {"n": 0}

    def fake(model, prompt):
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("temporary local model timeout")
        return "valid local response"

    monkeypatch.setattr("app.services.resilience._ollama_generate_response", fake)
    breaker = ModelCircuitBreaker(failure_threshold=5, recovery_seconds=1)

    result = resilient_generate_response("test-model", "hello", max_attempts=3, circuit_breaker=breaker)

    assert result == "valid local response"
    assert calls["n"] == 3
    assert breaker.status("test-model")["state"] == "closed"


def test_batch21_circuit_opens_after_repeated_failures(monkeypatch):
    calls = {"n": 0}

    def fake(model, prompt):
        calls["n"] += 1
        raise ConnectionError("ollama unavailable")

    monkeypatch.setattr("app.services.resilience._ollama_generate_response", fake)
    breaker = ModelCircuitBreaker(failure_threshold=2, recovery_seconds=60)

    with pytest.raises(RuntimeError):
        resilient_generate_response("test-model", "hello", max_attempts=3, circuit_breaker=breaker)

    assert breaker.status("test-model")["state"] == "open"

    with pytest.raises(ModelCircuitOpenError):
        resilient_generate_response("test-model", "hello", max_attempts=3, circuit_breaker=breaker)

    assert calls["n"] == 2


def test_batch21_blind_resampling_keeps_candidates_independent():
    prompts = []
    responses = iter([
        "short candidate",
        "# Better candidate\n- structured content",
    ])

    def fake(model, prompt):
        prompts.append(prompt)
        return next(responses)

    result = blind_resample("test-model", "original prompt", samples=2, generate_fn=fake)

    assert result["candidate_count"] == 2
    assert result["selected_candidate"] == 2
    assert prompts == ["original prompt", "original prompt"]
    assert "candidate" not in prompts[0].lower() or prompts[0] == prompts[1]


def test_batch21_blind_resampling_rejects_empty_candidates():
    calls = {"n": 0}

    def fake(model, prompt):
        calls["n"] += 1
        return "" if calls["n"] == 1 else "usable"

    result = blind_resample("test-model", "prompt", samples=2, generate_fn=fake)

    assert result["content"] == "usable"
    assert result["candidate_count"] == 1
    assert result["failed_candidates"]


def test_batch21_draft_regeneration_preserves_existing_monkeypatch_seam(monkeypatch):
    from app.services import draft_manager

    calls = {"n": 0}

    def fake(model, prompt):
        calls["n"] += 1
        return "# Revised draft"

    monkeypatch.setattr(draft_manager, "generate_response", fake)
    result = draft_manager.generate_response("qwen3:8b", "revise this")

    assert result == "# Revised draft"
    assert calls["n"] == 1
