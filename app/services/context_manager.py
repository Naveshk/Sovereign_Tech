"""Lightweight local conversation context and follow-up detection.

Batch 19 keeps context additive: the existing chat contract remains unchanged.
The frontend may provide recent conversation messages; this service turns them
into a bounded context block and detects whether the current request is likely
a follow-up. No external memory service is used.
"""
from __future__ import annotations

import json
import re
from typing import Any

MAX_MESSAGES = 8
MAX_MESSAGE_CHARS = 4000
MAX_CONTEXT_CHARS = 12000

_FOLLOW_UP_PATTERNS = [
    r"\b(continue|proceed|do that|do it|go ahead|as above|same as above)\b",
    r"\b(what about|how about|and|also|then|next|now)\b",
    r"\b(this|that|these|those|it|they|them|same|previous|above|below)\b",
    r"^\s*(yes|no|okay|ok|sure|correct|right|fine)\s*[.!?]*$",
    r"^\s*(why|how|what|which|where|when)\s+(about|with|for)\s+(it|that|this|them)\b",
]

def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()

def normalize_history(history: Any) -> list[dict[str, Any]]:
    """Return only safe, bounded conversation message fields."""
    if isinstance(history, str):
        try:
            history = json.loads(history)
        except json.JSONDecodeError:
            return []
    if not isinstance(history, list):
        return []
    result = []
    for item in history[-MAX_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role = _clean(item.get("role")).lower()
        content = _clean(item.get("content"))
        if role not in {"user", "assistant"} or not content:
            continue
        result.append({
            "role": role,
            "content": content[:MAX_MESSAGE_CHARS],
            "file_name": _clean(item.get("fileName"))[:256] or None,
            "task_type": _clean(item.get("taskType"))[:128] or None,
            "model": _clean(item.get("model"))[:128] or None,
        })
    return result

def detect_follow_up(message: str, history: Any = None) -> bool:
    text = _clean(message).lower()
    messages = normalize_history(history)
    if not messages:
        return False
    if len(text) <= 120 and any(re.search(pattern, text, re.I) for pattern in _FOLLOW_UP_PATTERNS):
        return True
    # Very short replies/question fragments after an assistant answer are likely
    # follow-ups, but never classify a substantial standalone request this way.
    return len(text.split()) <= 8 and bool(messages) and not text.startswith(("generate ", "create ", "analyze "))

def build_context(history: Any = None) -> dict[str, Any]:
    messages = normalize_history(history)
    lines = []
    for item in messages:
        label = "USER" if item["role"] == "user" else "ASSISTANT"
        suffix = f" [file: {item['file_name']}]" if item.get("file_name") else ""
        lines.append(f"{label}{suffix}:\n{item['content']}")
    text = "\n\n".join(lines)
    if len(text) > MAX_CONTEXT_CHARS:
        text = text[-MAX_CONTEXT_CHARS:]
    return {"messages": messages, "text": text, "message_count": len(messages)}

def prepare_context(message: str, history: Any = None) -> dict[str, Any]:
    context = build_context(history)
    follow_up = detect_follow_up(message, context["messages"])
    # The current message is always authoritative; history is supporting context.
    return {
        **context,
        "is_follow_up": follow_up,
        "current_message": _clean(message),
    }
