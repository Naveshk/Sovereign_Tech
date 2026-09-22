"""Local AES-256-GCM encryption and key management for the Sovereign Workbench.

Keys remain on the local machine. No cloud/KMS dependency is introduced.
Sensitive SQLite fields are transparently encrypted at rest and decrypted only
inside the backend process.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

BASE_DIR = Path(__file__).resolve().parents[2]
KEY_DIR = BASE_DIR / "data" / "keys"
KEY_FILE = KEY_DIR / "aes256gcm.json"
SCHEMA = "SWB-AESGCM-1"
ENV_KEY = "SWB_AES256_KEY"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key_id(key: bytes) -> str:
    return "KEY-" + hashlib.sha256(key).hexdigest()[:16].upper()


def _set_restrictive_permissions(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Windows ACLs are inherited from the data directory. Keep this
        # best-effort and never weaken normal application execution.
        pass


def _env_key() -> bytes | None:
    raw = os.getenv(ENV_KEY, "").strip()
    if not raw:
        return None
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise RuntimeError(f"{ENV_KEY} must contain exactly 64 hexadecimal characters.") from exc
    if len(key) != 32:
        raise RuntimeError(f"{ENV_KEY} must decode to exactly 32 bytes (256 bits).")
    return key


def _read_local_key() -> bytes | None:
    if not KEY_FILE.exists():
        return None
    try:
        payload = json.loads(KEY_FILE.read_text(encoding="utf-8"))
        key = base64.b64decode(payload["key_b64"], validate=True)
        if len(key) != 32:
            raise ValueError
        return key
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError("Local AES-256-GCM key file is invalid or unreadable.") from exc


def _write_local_key(key: bytes) -> None:
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA,
        "key_id": _key_id(key),
        "algorithm": "AES-256-GCM",
        "created_at": _now(),
        "key_b64": base64.b64encode(key).decode("ascii"),
    }
    fd, tmp_name = tempfile.mkstemp(prefix=".aes-key-", dir=str(KEY_FILE.parent), text=True)
    tmp_path = Path(tmp_name)
    try:
        os.close(fd)
        _set_restrictive_permissions(tmp_path)
        tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        _set_restrictive_permissions(tmp_path)
        os.replace(tmp_path, KEY_FILE)
        _set_restrictive_permissions(KEY_FILE)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def get_active_key(create: bool = True) -> bytes:
    env = _env_key()
    if env is not None:
        return env
    key = _read_local_key()
    if key is None and create:
        key = AESGCM.generate_key(bit_length=256)
        _write_local_key(key)
    if key is None:
        raise RuntimeError("No local AES-256-GCM key is configured.")
    return key


def key_info() -> dict[str, Any]:
    key = get_active_key(create=True)
    return {
        "schema": SCHEMA,
        "enabled": True,
        "algorithm": "AES-256-GCM",
        "key_id": _key_id(key),
        "key_source": "environment" if _env_key() is not None else "local_file",
        "key_file": (
            str(KEY_FILE.relative_to(BASE_DIR)).replace("\\", "/")
            if _env_key() is None and KEY_FILE.is_relative_to(BASE_DIR)
            else (str(KEY_FILE) if _env_key() is None else None)
        ),
        "offline": True,
    }


def encrypt_bytes(data: bytes, *, aad: str = "") -> str:
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("encrypt_bytes expects bytes.")
    key = get_active_key()
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(key).encrypt(nonce, bytes(data), aad.encode("utf-8") if aad else None)
    envelope = {
        "schema": SCHEMA,
        "key_id": _key_id(key),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
    }
    return base64.urlsafe_b64encode(
        json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).decode("ascii")


def decrypt_bytes(token: str, *, aad: str = "") -> bytes:
    try:
        envelope = json.loads(base64.urlsafe_b64decode(token.encode("ascii")))
        if envelope.get("schema") != SCHEMA:
            raise ValueError("Unsupported encrypted data schema.")
        nonce = base64.b64decode(envelope["nonce_b64"], validate=True)
        ciphertext = base64.b64decode(envelope["ciphertext_b64"], validate=True)
        if len(nonce) != 12:
            raise ValueError("Invalid AES-GCM nonce.")
        return AESGCM(get_active_key()).decrypt(
            nonce, ciphertext, aad.encode("utf-8") if aad else None
        )
    except Exception as exc:
        raise ValueError("Encrypted data failed AES-256-GCM authentication.") from exc


def encrypt_text(text: str, *, aad: str = "") -> str:
    return "SWBENC1:" + encrypt_bytes(str(text).encode("utf-8"), aad=aad)


def decrypt_text(value: str, *, aad: str = "") -> str:
    value = str(value or "")
    if not value.startswith("SWBENC1:"):
        # Backward-compatible read for legacy plaintext rows. Batch 25
        # migration encrypts these rows at startup.
        return value
    return decrypt_bytes(value[len("SWBENC1:"):], aad=aad).decode("utf-8")


def rotate_key() -> dict[str, Any]:
    """Generate a new local key. Data migration is performed by auth_db."""
    if _env_key() is not None:
        raise RuntimeError("Key rotation is disabled while SWB_AES256_KEY is externally managed.")
    old = get_active_key()
    new = AESGCM.generate_key(bit_length=256)
    if secrets.compare_digest(old, new):
        new = AESGCM.generate_key(bit_length=256)
    _write_local_key(new)
    return {"old_key_id": _key_id(old), "new_key_id": _key_id(new)}


def key_id_for(key: bytes) -> str:
    return _key_id(key)
