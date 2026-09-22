"""Local workflow observability for Batch 22.

Tracks bounded, in-memory latency/counter metrics only. No prompts, document
contents, secrets, or external telemetry are recorded.
"""
from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import perf_counter
from typing import Any
import time


class ObservabilityStore:
    def __init__(self, max_samples: int = 100):
        self.max_samples = max(10, int(max_samples))
        self._lock = Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._latencies: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.max_samples)
        )
        self._last: dict[str, dict[str, Any]] = {}

    def record(
        self,
        metric: str,
        duration_ms: float | None = None,
        *,
        status: str = "ok",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._counters[f"{metric}.total"] += 1
            self._counters[f"{metric}.{status}"] += 1
            if duration_ms is not None:
                self._latencies[metric].append(round(float(duration_ms), 3))
            safe_meta = {
                k: v for k, v in (metadata or {}).items()
                if k in {"operation", "model_id", "model_name", "stage", "request_id"}
            }
            self._last[metric] = {
                "status": status,
                "duration_ms": round(float(duration_ms), 3) if duration_ms is not None else None,
                "at": time.time(),
                **safe_meta,
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            metrics: dict[str, Any] = {}
            for metric, samples in self._latencies.items():
                values = list(samples)
                metrics[metric] = {
                    "count": self._counters.get(f"{metric}.total", 0),
                    "success": self._counters.get(f"{metric}.ok", 0),
                    "errors": self._counters.get(f"{metric}.error", 0),
                    "latency_ms": _latency_summary(values),
                    "last": dict(self._last.get(metric, {})),
                }
            for key, count in self._counters.items():
                metric, suffix = key.rsplit(".", 1)
                if metric not in metrics:
                    metrics[metric] = {
                        "count": self._counters.get(f"{metric}.total", 0),
                        "success": self._counters.get(f"{metric}.ok", 0),
                        "errors": self._counters.get(f"{metric}.error", 0),
                        "latency_ms": _latency_summary(list(self._latencies.get(metric, []))),
                        "last": dict(self._last.get(metric, {})),
                    }
            return {"metrics": metrics, "generated_at": time.time()}

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._latencies.clear()
            self._last.clear()


def _latency_summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"count": 0, "avg": None, "min": None, "max": None, "p95": None}
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(0.95 * len(ordered))) - 1))
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 3),
        "min": round(ordered[0], 3),
        "max": round(ordered[-1], 3),
        "p95": round(ordered[index], 3),
    }


OBSERVABILITY = ObservabilityStore()


class timed:
    """Small context manager for timing one synchronous workflow operation."""

    def __init__(self, metric: str, *, metadata: dict[str, Any] | None = None):
        self.metric = metric
        self.metadata = metadata or {}
        self.started = 0.0

    def __enter__(self):
        self.started = perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        duration = (perf_counter() - self.started) * 1000
        OBSERVABILITY.record(
            self.metric,
            duration,
            status="error" if exc_type else "ok",
            metadata=self.metadata,
        )
        return False
