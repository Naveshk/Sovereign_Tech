import pytest
from app.services import auth_db

@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "conversation_test.db"
    monkeypatch.setattr(auth_db, "DB_PATH", db_path)
    auth_db.init_db()
    return db_path

def test_conversation_and_messages_are_persisted(isolated_db):
    conv = auth_db.ensure_conversation("SV-TEST-1", "EMP001", "First request")
    assert conv["id"] == "SV-TEST-1"
    assert conv["employee_id"] == "EMP001"
    user = auth_db.append_conversation_message("SV-TEST-1", "EMP001", "user", "Prepare the approval note.", {"task_type": "document_generation", "file_name": "input.pdf"})
    assistant = auth_db.append_conversation_message("SV-TEST-1", "EMP001", "assistant", "Draft prepared.", {"model": "local-model"})
    assert user["role"] == "user" and assistant["role"] == "assistant"
    messages = auth_db.get_conversation_messages("SV-TEST-1", "EMP001")
    assert [m["content"] for m in messages] == ["Prepare the approval note.", "Draft prepared."]
    assert messages[0]["metadata"]["file_name"] == "input.pdf"
    rows = auth_db.list_conversations("EMP001")
    assert rows[0]["message_count"] == 2
    assert rows[0]["title"] == "First request"

def test_context_history_is_limited_to_recent_turns(isolated_db):
    auth_db.ensure_conversation("SV-TEST-2", "EMP001", "History")
    for i in range(10):
        role = "user" if i % 2 == 0 else "assistant"
        auth_db.append_conversation_message("SV-TEST-2", "EMP001", role, f"message {i}")
    history = auth_db.conversation_context_history("SV-TEST-2", "EMP001", limit=8)
    assert len(history) == 8
    assert history[0]["content"] == "message 2"
    assert history[-1]["content"] == "message 9"

def test_conversation_isolation_prevents_cross_user_access(isolated_db):
    auth_db.ensure_conversation("SV-PRIVATE", "EMP001", "Private")
    with pytest.raises(PermissionError):
        auth_db.get_conversation("SV-PRIVATE", "EMP002")
    with pytest.raises(PermissionError):
        auth_db.append_conversation_message("SV-PRIVATE", "EMP002", "user", "No access")

def test_archive_hides_conversation_from_default_history(isolated_db):
    auth_db.ensure_conversation("SV-ARCHIVE", "EMP001", "Archive me")
    assert auth_db.list_conversations("EMP001")[0]["id"] == "SV-ARCHIVE"
    archived = auth_db.archive_conversation("SV-ARCHIVE", "EMP001")
    assert archived["archived"] == 1
    assert auth_db.list_conversations("EMP001") == []
    assert auth_db.list_conversations("EMP001", include_archived=True)[0]["id"] == "SV-ARCHIVE"
