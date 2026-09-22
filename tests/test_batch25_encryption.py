import json
import os
import tempfile
from pathlib import Path

from app.services import auth_db
from app.services import encryption


def _setup(db):
    original = auth_db.DB_PATH
    auth_db.DB_PATH = Path(db) / "test.db"
    auth_db.init_db()
    return original


def test_batch25_aes256_gcm_roundtrip_and_tamper_detection():
    original = encryption.KEY_FILE
    with tempfile.TemporaryDirectory() as td:
        encryption.KEY_FILE = Path(td) / "keys" / "aes256gcm.json"
        try:
            info = encryption.key_info()
            assert info["algorithm"] == "AES-256-GCM"
            assert info["key_source"] == "local_file"
            token = encryption.encrypt_text("confidential refinery draft", aad="demo")
            assert token.startswith("SWBENC1:")
            assert encryption.decrypt_text(token, aad="demo") == "confidential refinery draft"
            try:
                encryption.decrypt_text(token, aad="wrong")
            except ValueError:
                pass
            else:
                raise AssertionError("AES-GCM AAD tampering was not rejected")
        finally:
            encryption.KEY_FILE = original


def test_batch25_drafts_are_encrypted_at_rest_but_transparent_to_application():
    original_db = auth_db.DB_PATH
    original_key = encryption.KEY_FILE
    with tempfile.TemporaryDirectory() as td:
        encryption.KEY_FILE = Path(td) / "keys" / "aes256gcm.json"
        auth_db.DB_PATH = Path(td) / "test.db"
        try:
            auth_db.init_db()
            auth_db.create_draft(
                draft_id="DR-ENC-1",
                requester_employee_id="E100",
                requester_username="eng",
                requester_role="Engineer",
                action="approval_note",
                title="Confidential",
                artifact_type="docx",
                content="Do not expose this draft",
                metadata={"classification": "confidential"},
            )
            draft = auth_db.get_draft("DR-ENC-1")
            assert draft["content"] == "Do not expose this draft"
            with auth_db._conn() as c:
                row = c.execute("SELECT content, metadata_json FROM drafts WHERE id=?", ("DR-ENC-1",)).fetchone()
            assert row["content"].startswith("SWBENC1:")
            assert row["metadata_json"].startswith("SWBENC1:")
            assert "Do not expose this draft" not in row["content"]
            assert "confidential" not in row["metadata_json"]
        finally:
            auth_db.DB_PATH = original_db
            encryption.KEY_FILE = original_key


def test_batch25_conversation_messages_are_encrypted_at_rest():
    original_db = auth_db.DB_PATH
    original_key = encryption.KEY_FILE
    with tempfile.TemporaryDirectory() as td:
        encryption.KEY_FILE = Path(td) / "keys" / "aes256gcm.json"
        auth_db.DB_PATH = Path(td) / "test.db"
        try:
            auth_db.init_db()
            auth_db.ensure_conversation("CV-ENC", "E100", "Secure chat")
            msg = auth_db.append_conversation_message(
                "CV-ENC", "E100", "user", "Internal process data",
                {"task_type": "analysis"},
            )
            assert msg["content"] == "Internal process data"
            with auth_db._conn() as c:
                row = c.execute(
                    "SELECT content, metadata_json FROM conversation_messages WHERE id=?",
                    (msg["id"],),
                ).fetchone()
            assert row["content"].startswith("SWBENC1:")
            assert row["metadata_json"].startswith("SWBENC1:")
            assert "Internal process data" not in row["content"]
        finally:
            auth_db.DB_PATH = original_db
            encryption.KEY_FILE = original_key


def test_batch25_legacy_plaintext_rows_are_migrated():
    original_db = auth_db.DB_PATH
    original_key = encryption.KEY_FILE
    with tempfile.TemporaryDirectory() as td:
        encryption.KEY_FILE = Path(td) / "keys" / "aes256gcm.json"
        auth_db.DB_PATH = Path(td) / "test.db"
        try:
            auth_db.init_db()
            with auth_db._conn() as c:
                c.execute(
                    """INSERT INTO drafts
                       (id, requester_employee_id, requester_username, requester_role,
                        action, title, artifact_type, content, metadata_json, version, created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    ("LEGACY", "E1", "u", "Engineer", "x", "Legacy", "docx",
                     "legacy secret", '{"old":true}', 1, auth_db._now()),
                )
            auth_db._migrate_sensitive_rows()
            with auth_db._conn() as c:
                row = c.execute("SELECT content, metadata_json FROM drafts WHERE id='LEGACY'").fetchone()
            assert row["content"].startswith("SWBENC1:")
            assert row["metadata_json"].startswith("SWBENC1:")
            assert auth_db.get_draft("LEGACY")["content"] == "legacy secret"
        finally:
            auth_db.DB_PATH = original_db
            encryption.KEY_FILE = original_key
