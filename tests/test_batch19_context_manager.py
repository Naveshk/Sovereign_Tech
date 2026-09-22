import sys
import types

if "ollama" not in sys.modules:
    try:
        import ollama  # noqa: F401
    except ImportError:
        ollama_stub = types.ModuleType("ollama")
        ollama_stub.chat = lambda **kwargs: {"message": {"content": ""}}
        ollama_stub.embeddings = lambda **kwargs: {"embedding": []}
        sys.modules["ollama"] = ollama_stub

import json

from app.services.context_manager import build_context, detect_follow_up, normalize_history, prepare_context


def test_context_is_bounded_and_normalized():
    history = [
        {"role": "user", "content": " First   request ", "fileName": "a.pdf"},
        {"role": "assistant", "content": "Answer", "model": "local"},
    ]
    result = build_context(history)
    assert result["message_count"] == 2
    assert "USER [file: a.pdf]:" in result["text"]
    assert "First request" in result["text"]


def test_follow_up_detected_with_recent_history():
    history = [{"role": "user", "content": "Prepare the approval note."},
               {"role": "assistant", "content": "Draft prepared."}]
    assert detect_follow_up("Can you revise it?", history) is True
    assert prepare_context("Can you revise it?", history)["is_follow_up"] is True


def test_standalone_request_is_not_forced_into_follow_up():
    history = [{"role": "user", "content": "Hello"}]
    assert detect_follow_up("Generate a new Excel report for unit A.", history) is False


def test_invalid_history_is_ignored():
    assert normalize_history({"role": "user", "content": "x"}) == []
    assert build_context("not-json")["message_count"] == 0


def test_simple_rewrite_follow_up_is_detected():
    history = [
        {"role": "user", "content": "What is an agent?"},
        {"role": "assistant", "content": "An agent is an AI system that can observe, decide and act."},
    ]
    result = prepare_context("Give in simple words.", history)
    assert result["is_follow_up"] is True
    assert "What is an agent?" in result["text"]


