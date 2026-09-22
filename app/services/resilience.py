"""Local model resilience primitives for Batch 21.

Provides:
- bounded retries for transient local-model failures
- an in-memory circuit breaker per model
- blind resampling: independent candidates generated without exposing one
  candidate to another, followed by deterministic local selection

No network service, cloud model, or persistent state is introduced.
"""
from __future__ import annotations

import os
import time
import threading
from queue import Queue
from dataclasses import dataclass
from threading import Lock
from typing import Callable, Any

from app.services.ollama_client import generate_response as _ollama_generate_response


class ModelCircuitOpenError(RuntimeError):
    """Raised when a local model is temporarily blocked after repeated failures."""


@dataclass
class _CircuitState:
    failures: int = 0
    opened_until: float = 0.0


class ModelCircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_seconds: float = 30.0):
        self.failure_threshold = max(1, int(failure_threshold))
        self.recovery_seconds = max(1.0, float(recovery_seconds))
        self._states: dict[str, _CircuitState] = {}
        self._lock = Lock()

    def before_call(self, model: str) -> None:
        now = time.monotonic()
        with self._lock:
            state = self._states.get(model)
            if state and state.opened_until > now:
                remaining = max(0, int(state.opened_until - now))
                raise ModelCircuitOpenError(
                    f"Local model '{model}' circuit is open; retry after about {remaining}s."
                )
            if state and state.opened_until and state.opened_until <= now:
                state.opened_until = 0.0
                state.failures = 0

    def record_success(self, model: str) -> None:
        with self._lock:
            self._states.pop(model, None)

    def record_failure(self, model: str) -> None:
        with self._lock:
            state = self._states.setdefault(model, _CircuitState())
            state.failures += 1
            if state.failures >= self.failure_threshold:
                state.opened_until = time.monotonic() + self.recovery_seconds

    def status(self, model: str) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            state = self._states.get(model)
            if not state:
                return {"model": model, "state": "closed", "failures": 0, "retry_after_seconds": 0}
            if state.opened_until > now:
                return {
                    "model": model,
                    "state": "open",
                    "failures": state.failures,
                    "retry_after_seconds": max(0, int(state.opened_until - now)),
                }
            return {"model": model, "state": "closed", "failures": state.failures, "retry_after_seconds": 0}


DEFAULT_CIRCUIT_BREAKER = ModelCircuitBreaker(
    failure_threshold=int(os.getenv("SWB_MODEL_FAILURE_THRESHOLD", "3")),
    recovery_seconds=float(os.getenv("SWB_MODEL_RECOVERY_SECONDS", "30")),
)


def _default_validator(value: str) -> bool:
    return bool(str(value or "").strip())


def _call_with_timeout(model: str, prompt: str, timeout_seconds: float | None):
    """Run the local Ollama call with a bounded wait.

    The worker is daemonized so a stuck local client cannot block process
    shutdown. A timeout is treated as a model failure and is retried by the
    existing bounded resilience policy.
    """
    if timeout_seconds is None or timeout_seconds <= 0:
        return _ollama_generate_response(model, prompt)

    result_queue: Queue = Queue(maxsize=1)

    def worker():
        try:
            result_queue.put(("ok", _ollama_generate_response(model, prompt)))
        except Exception as exc:
            result_queue.put(("error", exc))

    thread = threading.Thread(target=worker, name="swb-ollama-call", daemon=True)
    thread.start()
    thread.join(float(timeout_seconds))
    if thread.is_alive():
        raise TimeoutError(
            f"Local model '{model}' exceeded the {float(timeout_seconds):g}s timeout."
        )
    status, value = result_queue.get_nowait()
    if status == "error":
        raise value
    return value


def resilient_generate_response(
    model: str,
    prompt: str,
    *,
    max_attempts: int = 3,
    validator: Callable[[str], bool] | None = None,
    circuit_breaker: ModelCircuitBreaker = DEFAULT_CIRCUIT_BREAKER,
    timeout_seconds: float | None = None,
) -> str:
    """Generate with bounded retries and circuit protection.

    Retries are intentionally bounded. A failed attempt is never passed to the
    next attempt as model context, preserving blind retry semantics.
    """
    attempts = max(1, min(int(max_attempts), 3))
    validate = validator or _default_validator
    last_error: Exception | None = None

    for _ in range(attempts):
        circuit_breaker.before_call(model)
        try:
            result = _call_with_timeout(model, prompt, timeout_seconds)
            if not validate(result):
                raise ValueError("Local model returned empty or invalid content.")
            circuit_breaker.record_success(model)
            return str(result)
        except ModelCircuitOpenError:
            raise
        except Exception as exc:
            last_error = exc
            circuit_breaker.record_failure(model)
            # Do not sleep here: the local workflow must remain responsive.
            if circuit_breaker.status(model)["state"] == "open":
                break

    raise RuntimeError(
        f"Local model '{model}' failed after bounded retries: "
        f"{type(last_error).__name__ if last_error else 'unknown error'}"
    ) from last_error


def _candidate_score(text: str) -> tuple[int, int, int]:
    """Small deterministic quality signal; never uses another model."""
    value = str(text or "").strip()
    if not value:
        return (0, 0, 0)
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    headings = sum(line.startswith("#") for line in lines)
    structured = sum(line.startswith(("-", "*", "1.", "2.", "3.")) for line in lines)
    return (1, min(len(value), 12000), headings + structured)


def blind_resample(
    model: str,
    prompt: str,
    *,
    samples: int = 2,
    validator: Callable[[str], bool] | None = None,
    generate_fn: Callable[[str, str], str] | None = None,
) -> dict[str, Any]:
    """Generate independent candidates and select one locally.

    Candidate N never receives candidate N-1. This is deliberately blind
    resampling rather than iterative self-revision.
    """
    count = max(1, min(int(samples), 3))
    validate = validator or _default_validator
    candidates: list[str] = []
    failures: list[dict[str, str]] = []

    for index in range(count):
        try:
            if generate_fn is not None:
                candidate = generate_fn(model, prompt)
                if not validate(candidate):
                    raise ValueError("Generator returned empty or invalid content.")
            else:
                candidate = resilient_generate_response(
                    model,
                    prompt,
                    max_attempts=2,
                    validator=validate,
                )
            if validate(candidate):
                candidates.append(str(candidate))
            else:
                failures.append({"attempt": str(index + 1), "reason": "validator rejected candidate"})
        except Exception as exc:
            failures.append({"attempt": str(index + 1), "reason": str(exc)})

    if not candidates:
        detail = failures[-1]["reason"] if failures else "no valid candidate"
        raise RuntimeError(f"Blind resampling produced no valid candidate: {detail}")

    # Deterministic local selection only; no candidate is shown to an LLM.
    selected = max(enumerate(candidates), key=lambda item: _candidate_score(item[1]))[0]
    return {
        "content": candidates[selected],
        "candidate_count": len(candidates),
        "selected_candidate": selected + 1,
        "failed_candidates": failures,
    }


def circuit_status(model: str) -> dict[str, Any]:
    return DEFAULT_CIRCUIT_BREAKER.status(model)
