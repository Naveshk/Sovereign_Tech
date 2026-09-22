
import hashlib, hmac, json, os, sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
from app.services.encryption import encrypt_text, decrypt_text
BASE_DIR=Path(__file__).resolve().parents[2]
DB_PATH=BASE_DIR/"data"/"sovereign.db"
DB_PATH.parent.mkdir(parents=True,exist_ok=True)
ROLES={"Engineer","Developer","Manager"}
@contextmanager
def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
def _now(): return datetime.now(timezone.utc).isoformat()
def init_db():
    with _conn() as c:
        c.executescript("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT UNIQUE NOT NULL,
        username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('Engineer','Developer','Manager')), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS uploaded_files(
        id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL, filename TEXT NOT NULL,
        file_type TEXT, path TEXT, uploaded_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS rag_documents(
        id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT UNIQUE NOT NULL, chunks INTEGER DEFAULT 0,
        uploaded_by TEXT, uploaded_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT, username TEXT, role TEXT,
        action TEXT NOT NULL, resource TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL,
        entity_type TEXT, entity_id TEXT, correlation_id TEXT, metadata_json TEXT NOT NULL DEFAULT '{}',
        provenance_id TEXT, artifact_sha256 TEXT, review_id INTEGER, draft_id TEXT, draft_version INTEGER);
        CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id, id);
        CREATE INDEX IF NOT EXISTS idx_audit_draft ON audit_logs(draft_id, id);
        CREATE INDEX IF NOT EXISTS idx_audit_review ON audit_logs(review_id, id);
        CREATE TABLE IF NOT EXISTS audit_ledger(
        id INTEGER PRIMARY KEY AUTOINCREMENT, audit_id INTEGER UNIQUE NOT NULL,
        previous_hash TEXT NOT NULL, entry_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(audit_id) REFERENCES audit_logs(id));
        CREATE TABLE IF NOT EXISTS drafts(
        id TEXT PRIMARY KEY, requester_employee_id TEXT, requester_username TEXT, requester_role TEXT,
        action TEXT NOT NULL, title TEXT NOT NULL, artifact_type TEXT NOT NULL, content TEXT NOT NULL,
        source_path TEXT, metadata_json TEXT NOT NULL DEFAULT '{}', version INTEGER NOT NULL DEFAULT 1,
        revision_group TEXT, parent_draft_id TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS human_reviews(
        id INTEGER PRIMARY KEY AUTOINCREMENT, requester_employee_id TEXT, requester_username TEXT,
        requester_role TEXT, action TEXT NOT NULL, resource TEXT, status TEXT NOT NULL DEFAULT 'pending',
        reviewer_employee_id TEXT, reviewer_username TEXT, reviewer_role TEXT,
        decision_note TEXT, draft_id TEXT, artifact_type TEXT, draft_version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL, reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS conversations(
        id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, title TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS idx_conversations_employee_updated
            ON conversations(employee_id, updated_at DESC);
        CREATE TABLE IF NOT EXISTS conversation_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,
        employee_id TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
        content TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE);
        CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation
            ON conversation_messages(conversation_id, id);""")
def _ensure_batch26_audit_schema():
    """Add Batch 26 audit/provenance linkage columns to existing local DBs."""
    with _conn() as c:
        cols = {row[1] for row in c.execute("PRAGMA table_info(audit_logs)").fetchall()}
        additions = {
            "entity_type": "TEXT",
            "entity_id": "TEXT",
            "correlation_id": "TEXT",
            "metadata_json": "TEXT NOT NULL DEFAULT '{}'",
            "provenance_id": "TEXT",
            "artifact_sha256": "TEXT",
            "review_id": "INTEGER",
            "draft_id": "TEXT",
            "draft_version": "INTEGER",
        }
        for name, definition in additions.items():
            if name not in cols:
                c.execute(f"ALTER TABLE audit_logs ADD COLUMN {name} {definition}")
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id, id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit_draft ON audit_logs(draft_id, id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit_review ON audit_logs(review_id, id)")


def _ensure_batch13_schema():
    """Add Batch 13 columns/tables without disturbing existing local databases."""
    with _conn() as c:
        cols = {row[1] for row in c.execute("PRAGMA table_info(human_reviews)").fetchall()}
        additions = {
            "requester_role": "TEXT",
            "draft_id": "TEXT",
            "artifact_type": "TEXT",
            "draft_version": "INTEGER NOT NULL DEFAULT 1",
        }
        for name, definition in additions.items():
            if name not in cols:
                c.execute(f"ALTER TABLE human_reviews ADD COLUMN {name} {definition}")
        c.execute("""CREATE TABLE IF NOT EXISTS drafts(
            id TEXT PRIMARY KEY, requester_employee_id TEXT, requester_username TEXT, requester_role TEXT,
            action TEXT NOT NULL, title TEXT NOT NULL, artifact_type TEXT NOT NULL, content TEXT NOT NULL,
            source_path TEXT, metadata_json TEXT NOT NULL DEFAULT '{}', version INTEGER NOT NULL DEFAULT 1,
            revision_group TEXT, parent_draft_id TEXT, created_at TEXT NOT NULL)""")
        draft_cols = {row[1] for row in c.execute("PRAGMA table_info(drafts)").fetchall()}
        for name in ("revision_group", "parent_draft_id"):
            if name not in draft_cols:
                c.execute(f"ALTER TABLE drafts ADD COLUMN {name} TEXT")


    _ensure_batch13_schema()
    _ensure_batch26_audit_schema()

def _hash(p):
    salt=os.urandom(16); d=hashlib.pbkdf2_hmac("sha256",p.encode(),salt,210000)
    return f"pbkdf2_sha256$210000${salt.hex()}${d.hex()}"
def _verify(p,e):
    try:
        _,rounds,salt,digest=e.split("$")
        d=hashlib.pbkdf2_hmac("sha256",p.encode(),bytes.fromhex(salt),int(rounds))
        return hmac.compare_digest(d.hex(),digest)
    except Exception: return False
def _audit_context_hash(audit_row):
    """Hash only the optional Batch 26 context so legacy ledger hashes stay valid."""
    values = [
        str(audit_row["entity_type"] or ""),
        str(audit_row["entity_id"] or ""),
        str(audit_row["correlation_id"] or ""),
        str(audit_row["metadata_json"] or "{}"),
        str(audit_row["provenance_id"] or ""),
        str(audit_row["artifact_sha256"] or ""),
        str(audit_row["review_id"] or ""),
        str(audit_row["draft_id"] or ""),
        str(audit_row["draft_version"] or ""),
    ]
    meaningful = [v for v in values if v not in {"", "{}"}]
    if not meaningful:
        return ""
    return hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()

def _ledger_hash(previous_hash, audit_row):
    payload = "|".join([
        previous_hash,
        str(audit_row["id"]),
        str(audit_row["employee_id"] or ""),
        str(audit_row["username"] or ""),
        str(audit_row["role"] or ""),
        str(audit_row["action"] or ""),
        str(audit_row["resource"] or ""),
        str(audit_row["status"] or ""),
        str(audit_row["created_at"] or ""),
    ])
    context_hash = _audit_context_hash(audit_row)
    if context_hash:
        payload += "|" + context_hash
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def audit(employee_id,username,role,action,resource,status="success", *,
          entity_type=None, entity_id=None, correlation_id=None, metadata=None,
          provenance_id=None, artifact_sha256=None, review_id=None, draft_id=None,
          draft_version=None):
    """Append an immutable local audit event with optional Batch 26 provenance linkage.

    Metadata is intentionally structured operational metadata only; callers should never
    place document contents, prompts, passwords, keys, or secrets here.
    """
    init_db()
    safe_metadata = metadata if isinstance(metadata, dict) else {}
    # Prevent accidental leakage of sensitive content into the audit trail.
    blocked = {"content", "prompt", "password", "password_hash", "secret", "key", "token", "document_text"}
    safe_metadata = {str(k): v for k, v in safe_metadata.items() if str(k).lower() not in blocked}
    metadata_json = json.dumps(safe_metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with _conn() as c:
        created_at = _now()
        cur = c.execute(
            """INSERT INTO audit_logs(
                employee_id,username,role,action,resource,status,created_at,
                entity_type,entity_id,correlation_id,metadata_json,provenance_id,
                artifact_sha256,review_id,draft_id,draft_version)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (employee_id,username,role,action,resource,status,created_at,
             entity_type,entity_id,correlation_id,metadata_json,provenance_id,
             artifact_sha256,review_id,draft_id,draft_version),
        )
        audit_id = cur.lastrowid
        prev = c.execute("SELECT entry_hash FROM audit_ledger ORDER BY id DESC LIMIT 1").fetchone()
        previous_hash = prev["entry_hash"] if prev else "GENESIS"
        row = c.execute("SELECT * FROM audit_logs WHERE id=?", (audit_id,)).fetchone()
        entry_hash = _ledger_hash(previous_hash, row)
        c.execute(
            "INSERT INTO audit_ledger(audit_id,previous_hash,entry_hash,created_at) VALUES(?,?,?,?)",
            (audit_id, previous_hash, entry_hash, created_at),
        )
        return entry_hash

def verify_audit_ledger():
    init_db()
    with _conn() as c:
        audits = c.execute("SELECT * FROM audit_logs ORDER BY id ASC").fetchall()
        ledger = c.execute("SELECT * FROM audit_ledger ORDER BY id ASC").fetchall()
        if len(audits) != len(ledger):
            return {"valid": False, "reason": "Audit and ledger row counts differ.", "checked_entries": min(len(audits), len(ledger))}
        previous_hash = "GENESIS"
        for audit_row, ledger_row in zip(audits, ledger):
            if ledger_row["audit_id"] != audit_row["id"]:
                return {"valid": False, "reason": f"Ledger linkage mismatch at ledger id {ledger_row['id']}.", "checked_entries": ledger_row["id"] - 1}
            if ledger_row["previous_hash"] != previous_hash:
                return {"valid": False, "reason": f"Previous-hash mismatch at ledger id {ledger_row['id']}.", "checked_entries": ledger_row["id"] - 1}
            expected = _ledger_hash(previous_hash, audit_row)
            if not hmac.compare_digest(expected, ledger_row["entry_hash"]):
                return {"valid": False, "reason": f"Entry hash mismatch for audit id {audit_row['id']}.", "checked_entries": ledger_row["id"] - 1}
            previous_hash = ledger_row["entry_hash"]
        return {"valid": True, "reason": "Audit ledger verified.", "checked_entries": len(ledger), "head_hash": previous_hash}

def list_audit(limit=200):
    init_db()
    limit=max(1,min(int(limit),500))
    with _conn() as c:
        rows = c.execute(
            """SELECT id,employee_id,username,role,action,resource,status,created_at,
                      entity_type,entity_id,correlation_id,metadata_json,provenance_id,
                      artifact_sha256,review_id,draft_id,draft_version
               FROM audit_logs ORDER BY id DESC LIMIT ?""", (limit,)
        ).fetchall()
    result=[]
    for row in rows:
        item=dict(row)
        try: item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        except (TypeError,json.JSONDecodeError): item["metadata"] = {}; item.pop("metadata_json",None)
        result.append(item)
    return result

def list_audit_provenance(*, draft_id=None, review_id=None, provenance_id=None, artifact_sha256=None, limit=200):
    """Return the local audit trail linked to a draft/review/artifact provenance record."""
    init_db(); limit=max(1,min(int(limit),500))
    clauses=[]; params=[]
    if draft_id:
        clauses.append("(draft_id=? OR entity_id=?)"); params.extend([draft_id,draft_id])
    if review_id is not None:
        clauses.append("review_id=?"); params.append(int(review_id))
    if provenance_id:
        clauses.append("provenance_id=?"); params.append(provenance_id)
    if artifact_sha256:
        clauses.append("artifact_sha256=?"); params.append(artifact_sha256.lower())
    if not clauses:
        raise ValueError("At least one provenance selector is required.")
    where=" OR ".join(clauses)
    with _conn() as c:
        rows=c.execute(f"SELECT * FROM audit_logs WHERE {where} ORDER BY id ASC LIMIT ?", (*params,limit)).fetchall()
    out=[]
    for row in rows:
        item=dict(row)
        try: item["metadata"]=json.loads(item.pop("metadata_json") or "{}")
        except (TypeError,json.JSONDecodeError): item["metadata"]={}; item.pop("metadata_json",None)
        out.append(item)
    return out

def create_user(employee_id,username,password,role):
    init_db(); employee_id=employee_id.strip(); username=username.strip(); role=role.strip()
    if role not in ROLES: raise ValueError("Role must be Engineer, Developer, or Manager.")
    if min(len(employee_id),len(username),len(password))<4: raise ValueError("Please provide valid account details.")
    try:
        with _conn() as c:
            c.execute("INSERT INTO users(employee_id,username,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                      (employee_id,username,_hash(password),role,_now()))
    except sqlite3.IntegrityError: raise ValueError("Employee ID or username already exists.")
    audit(employee_id,username,role,"account_created","users")
    return {"employee_id":employee_id,"username":username,"role":role}
def authenticate(identifier,password,role=None):
    init_db()
    with _conn() as c:
        row=c.execute("SELECT * FROM users WHERE lower(employee_id)=lower(?) OR lower(username)=lower(?)",
                      (identifier.strip(),identifier.strip())).fetchone()
    if not row or not _verify(password,row["password_hash"]):
        raise ValueError("Invalid Employee ID / username or password.")
    if role and row["role"]!=role:
        raise ValueError("Role does not match the registered account.")
    audit(row["employee_id"],row["username"],row["role"],"login","users")
    return {"employee_id":row["employee_id"],"username":row["username"],"role":row["role"]}
def record_file(employee_id,filename,file_type,path):
    init_db()
    with _conn() as c: c.execute("INSERT INTO uploaded_files(employee_id,filename,file_type,path,uploaded_at) VALUES(?,?,?,?,?)",
                                  (employee_id,filename,file_type,path,_now()))
def record_rag(source,chunks,uploaded_by):
    init_db()
    with _conn() as c: c.execute("""INSERT INTO rag_documents(source,chunks,uploaded_by,uploaded_at) VALUES(?,?,?,?)
        ON CONFLICT(source) DO UPDATE SET chunks=excluded.chunks,uploaded_by=excluded.uploaded_by,uploaded_at=excluded.uploaded_at""",
                                  (source,chunks,uploaded_by,_now()))
def list_files():
    init_db()
    with _conn() as c: return [dict(r) for r in c.execute("SELECT employee_id,filename,file_type,uploaded_at FROM uploaded_files ORDER BY id DESC")]
def _conversation_title(message: str, fallback="New Chat"):
    title = " ".join(str(message or "").split()).strip()
    if len(title) > 80:
        title = title[:80].rstrip() + "…"
    return title or fallback


def _encrypted_or_plain(value, aad):
    return decrypt_text(value or "", aad=aad)


def _encrypt_if_needed(value, aad):
    value = str(value or "")
    return value if value.startswith("SWBENC1:") else encrypt_text(value, aad=aad)


def _migrate_sensitive_rows():
    """Encrypt legacy plaintext draft/conversation fields once, in place."""
    with _conn() as c:
        drafts = c.execute("SELECT id, content, metadata_json FROM drafts").fetchall()
        for row in drafts:
            content = row["content"] or ""
            metadata = row["metadata_json"] or "{}"
            new_content = _encrypt_if_needed(content, f"draft:{row['id']}:content")
            new_metadata = _encrypt_if_needed(metadata, f"draft:{row['id']}:metadata")
            if new_content != content or new_metadata != metadata:
                c.execute("UPDATE drafts SET content=?, metadata_json=? WHERE id=?",
                          (new_content, new_metadata, row["id"]))
        messages = c.execute("SELECT id, content, metadata_json FROM conversation_messages").fetchall()
        for row in messages:
            content = row["content"] or ""
            metadata = row["metadata_json"] or "{}"
            new_content = _encrypt_if_needed(content, f"conversation_message:{row['id']}:content")
            new_metadata = _encrypt_if_needed(metadata, f"conversation_message:{row['id']}:metadata")
            if new_content != content or new_metadata != metadata:
                c.execute("UPDATE conversation_messages SET content=?, metadata_json=? WHERE id=?",
                          (new_content, new_metadata, row["id"]))


def _conversation_message_row(row):
    if not row:
        return None
    item = dict(row)
    message_id = item.get("id")
    item["content"] = _encrypted_or_plain(item.get("content"), f"conversation_message:{message_id}:content")
    try:
        metadata_raw = _encrypted_or_plain(item.pop("metadata_json"), f"conversation_message:{message_id}:metadata")
        item["metadata"] = json.loads(metadata_raw or "{}")
    except (TypeError, json.JSONDecodeError, ValueError):
        item["metadata"] = {}
        item.pop("metadata_json", None)
    return item


def _conversation_row(row):
    return dict(row) if row else None


def ensure_conversation(conversation_id, employee_id, title=None):
    """Create or validate an employee-owned local conversation."""
    if not employee_id:
        raise PermissionError("Employee identity required for conversation history.")
    conversation_id = (conversation_id or "").strip()
    if not conversation_id:
        conversation_id = f"SV-{os.urandom(8).hex().upper()}"
    init_db()
    with _conn() as c:
        row = c.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        if row:
            if row["employee_id"] != employee_id:
                raise PermissionError("Conversation belongs to another local user.")
            return _conversation_row(row)
        now = _now()
        c.execute(
            "INSERT INTO conversations(id,employee_id,title,created_at,updated_at,archived) VALUES(?,?,?,?,?,0)",
            (conversation_id, employee_id, _conversation_title(title), now, now),
        )
        row = c.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
    return _conversation_row(row)


def append_conversation_message(conversation_id, employee_id, role, content, metadata=None):
    if not employee_id:
        raise PermissionError("Employee identity required for conversation history.")
    role = (role or "").strip().lower()
    if role not in {"user", "assistant", "system"}:
        raise ValueError("Conversation message role is invalid.")
    content = str(content or "").strip()
    if not content:
        raise ValueError("Conversation message content cannot be empty.")
    init_db()
    with _conn() as c:
        conv = c.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        if not conv:
            raise LookupError("Conversation not found.")
        if conv["employee_id"] != employee_id:
            raise PermissionError("Conversation belongs to another local user.")
        created_at = _now()
        cur = c.execute(
            """INSERT INTO conversation_messages
               (conversation_id,employee_id,role,content,metadata_json,created_at)
               VALUES(?,?,?,?,?,?)""",
            (conversation_id, employee_id, role, "", "", created_at),
        )
        message_id = cur.lastrowid
        c.execute(
            "UPDATE conversation_messages SET content=?, metadata_json=? WHERE id=?",
            (encrypt_text(content, aad=f"conversation_message:{message_id}:content"),
             encrypt_text(json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                          aad=f"conversation_message:{message_id}:metadata"), message_id),
        )
        c.execute("UPDATE conversations SET updated_at=? WHERE id=?", (created_at, conversation_id))
        row = c.execute("SELECT * FROM conversation_messages WHERE id=?", (message_id,)).fetchone()
    return _conversation_message_row(row)


def list_conversations(employee_id, include_archived=False, limit=100):
    if not employee_id:
        raise PermissionError("Employee identity required for conversation history.")
    init_db()
    limit = max(1, min(int(limit), 200))
    with _conn() as c:
        where = "c.employee_id=?" + ("" if include_archived else " AND c.archived=0")
        rows = c.execute(
            f"""SELECT c.*, COUNT(m.id) AS message_count,
                       MAX(m.created_at) AS last_message_at
                FROM conversations c
                LEFT JOIN conversation_messages m ON m.conversation_id=c.id
                WHERE {where}
                GROUP BY c.id
                ORDER BY c.updated_at DESC LIMIT ?""",
            (employee_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_conversation(conversation_id, employee_id):
    if not employee_id:
        raise PermissionError("Employee identity required for conversation history.")
    init_db()
    with _conn() as c:
        row = c.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        if not row:
            return None
        if row["employee_id"] != employee_id:
            raise PermissionError("Conversation belongs to another local user.")
        return _conversation_row(row)


def get_conversation_messages(conversation_id, employee_id, limit=200):
    conv = get_conversation(conversation_id, employee_id)
    if not conv:
        return None
    init_db()
    limit = max(1, min(int(limit), 500))
    with _conn() as c:
        rows = c.execute(
            """SELECT * FROM (
                   SELECT * FROM conversation_messages
                   WHERE conversation_id=? AND employee_id=?
                   ORDER BY id DESC LIMIT ?
               ) recent
               ORDER BY id ASC""",
            (conversation_id, employee_id, limit),
        ).fetchall()
    return [_conversation_message_row(row) for row in rows]


def archive_conversation(conversation_id, employee_id):
    conv = get_conversation(conversation_id, employee_id)
    if not conv:
        return None
    init_db()
    with _conn() as c:
        c.execute("UPDATE conversations SET archived=1, updated_at=? WHERE id=?", (_now(), conversation_id))
    return get_conversation(conversation_id, employee_id)


def conversation_context_history(conversation_id, employee_id, limit=8):
    messages = get_conversation_messages(conversation_id, employee_id, limit=max(1, min(int(limit), 50)))
    if messages is None:
        return []
    return [
        {
            "role": item["role"],
            "content": item["content"],
            "fileName": item.get("metadata", {}).get("file_name"),
            "taskType": item.get("metadata", {}).get("task_type"),
            "model": item.get("metadata", {}).get("model"),
        }
        for item in messages
        if item["role"] in {"user", "assistant"}
    ]

init_db()
try:
    _migrate_sensitive_rows()
except Exception:
    # Startup should fail closed if encrypted data cannot be migrated/read.
    raise


def get_audit_receipt(audit_id: int):
    init_db()
    with _conn() as c:
        row = c.execute(
            """SELECT a.*, l.previous_hash, l.entry_hash, l.created_at AS ledger_created_at
               FROM audit_logs a JOIN audit_ledger l ON l.audit_id=a.id
               WHERE a.id=?""", (audit_id,)
        ).fetchone()
    if not row:
        return None
    return {
        "version": "1",
        "audit_id": row["id"],
        "employee_id": row["employee_id"],
        "role": row["role"],
        "action": row["action"],
        "resource": row["resource"],
        "status": row["status"],
        "created_at": row["created_at"],
        "previous_hash": row["previous_hash"],
        "entry_hash": row["entry_hash"],
    }

def verify_receipt_payload(payload: dict):
    if not isinstance(payload, dict):
        return {"valid": False, "reason": "Receipt payload must be an object."}
    try:
        audit_id = int(payload["audit_id"])
    except (KeyError, TypeError, ValueError):
        return {"valid": False, "reason": "Receipt is missing a valid audit_id."}
    receipt = get_audit_receipt(audit_id)
    if not receipt:
        return {"valid": False, "reason": "Audit entry not found locally."}
    if not hmac.compare_digest(str(payload.get("entry_hash", "")), receipt["entry_hash"]):
        return {"valid": False, "reason": "Receipt hash does not match the local audit ledger.", "audit_id": audit_id}
    chain = verify_audit_ledger()
    if not chain.get("valid"):
        return {"valid": False, "reason": "Local audit ledger is invalid.", "audit_id": audit_id, "ledger": chain}
    return {"valid": True, "reason": "Receipt verified against the local audit ledger.", "audit_id": audit_id, "entry_hash": receipt["entry_hash"]}


def create_draft(*, draft_id, requester_employee_id, requester_username, requester_role,
                 action, title, artifact_type, content, source_path=None, metadata=None,
                 version=1, revision_group=None, parent_draft_id=None):
    """Persist a reviewable draft. No final artifact is generated here."""
    if requester_role not in ROLES:
        raise PermissionError("Authorized role required for human review.")
    init_db()
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
    with _conn() as c:
        c.execute("""INSERT INTO drafts
            (id,requester_employee_id,requester_username,requester_role,action,title,artifact_type,content,
             source_path,metadata_json,version,revision_group,parent_draft_id,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (draft_id, requester_employee_id, requester_username, requester_role, action, title,
             artifact_type, encrypt_text(content or "", aad=f"draft:{draft_id}:content"), source_path,
             encrypt_text(metadata_json, aad=f"draft:{draft_id}:metadata"), int(version), revision_group, parent_draft_id, _now()))
        row = c.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
    return _draft_row(row)


def _draft_row(row):
    if not row:
        return None
    item = dict(row)
    draft_id = item.get("id")
    try:
        item["content"] = _encrypted_or_plain(item.get("content"), f"draft:{draft_id}:content")
        metadata_raw = _encrypted_or_plain(item.pop("metadata_json"), f"draft:{draft_id}:metadata")
        item["metadata"] = json.loads(metadata_raw or "{}")
    except (TypeError, json.JSONDecodeError, ValueError):
        item["metadata"] = {}
        item.pop("metadata_json", None)
    return item


def get_draft(draft_id):
    init_db()
    with _conn() as c:
        row = c.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
    return _draft_row(row)



def update_draft_metadata(draft_id, updates: dict):
    """Merge metadata into an existing draft without changing its immutable content."""
    init_db()
    with _conn() as c:
        row = c.execute("SELECT metadata_json FROM drafts WHERE id=?", (draft_id,)).fetchone()
        if not row:
            raise LookupError("Draft not found.")
        try:
            metadata_raw = _encrypted_or_plain(row["metadata_json"], f"draft:{draft_id}:metadata")
            metadata = json.loads(metadata_raw or "{}")
        except (TypeError, json.JSONDecodeError, ValueError):
            metadata = {}
        metadata.update(updates or {})
        c.execute(
            "UPDATE drafts SET metadata_json=? WHERE id=?",
            (encrypt_text(json.dumps(metadata, ensure_ascii=False, sort_keys=True), aad=f"draft:{draft_id}:metadata"), draft_id),
        )
    return get_draft(draft_id)

def list_drafts(limit=200):
    init_db()
    limit=max(1,min(int(limit),500))
    with _conn() as c:
        rows=c.execute("SELECT * FROM drafts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [_draft_row(row) for row in rows]


def list_draft_versions(revision_group):
    init_db()
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM drafts WHERE revision_group=? ORDER BY version ASC",
            (revision_group,),
        ).fetchall()
    return [_draft_row(row) for row in rows]




def get_user_identity(employee_id: str = "", username: str = ""):
    """Return the canonical local account for a reviewer/requester identity."""
    employee_id = (employee_id or "").strip()
    username = (username or "").strip()
    if not employee_id and not username:
        return None
    init_db()
    with _conn() as c:
        row = c.execute(
            """SELECT employee_id, username, role FROM users
               WHERE (? <> '' AND lower(employee_id)=lower(?))
                  OR (? <> '' AND lower(username)=lower(?))
               LIMIT 1""",
            (employee_id, employee_id, username, username),
        ).fetchone()
    return dict(row) if row else None


def require_reviewer_identity(employee_id: str, username: str, role: str,
                              review: dict | None = None):
    """Enforce that the local authenticated identity matches the review action."""
    if role not in ROLES:
        raise PermissionError("Authorized role required.")
    identity = get_user_identity(employee_id, username)
    if not identity:
        raise PermissionError("Reviewer account was not found.")
    if identity["role"] != role:
        raise PermissionError("Reviewer role does not match the registered account.")
    if employee_id and identity["employee_id"].lower() != employee_id.strip().lower():
        raise PermissionError("Reviewer Employee ID does not match the registered account.")
    if username and identity["username"].lower() != username.strip().lower():
        raise PermissionError("Reviewer username does not match the registered account.")
    if review:
        # Human review is an account-owned verification gate. The authenticated
        # account that created the draft is the account allowed to accept or
        # reject that draft. Role is validated above, but role does not grant
        # or deny review access.
        requester = (review.get("requester_employee_id") or "").strip()
        if requester and requester.lower() != identity["employee_id"].lower():
            raise PermissionError("This review belongs to a different account.")
    return identity
def create_human_review(requester_employee_id, requester_username, action, resource,
                        requester_role=None, draft_id=None, artifact_type=None, draft_version=1):
    """Create a universal human-review item for any authorized local role."""
    if requester_role not in ROLES:
        raise PermissionError("Authorized role required for human review.")
    init_db()
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO human_reviews
            (requester_employee_id,requester_username,requester_role,action,resource,status,
             draft_id,artifact_type,draft_version,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (requester_employee_id, requester_username, requester_role, action, resource, "pending",
             draft_id, artifact_type, int(draft_version), _now()),
        )
        review_id = cur.lastrowid
    audit(requester_employee_id, requester_username, requester_role, "human_review_requested", resource, "pending",
          entity_type="human_review", entity_id=str(review_id), review_id=review_id,
          draft_id=draft_id, draft_version=int(draft_version),
          metadata={"action": action, "artifact_type": artifact_type})
    return get_human_review(review_id)


def get_human_review(review_id):
    init_db()
    with _conn() as c:
        row=c.execute("SELECT * FROM human_reviews WHERE id=?", (review_id,)).fetchone()
    item = dict(row) if row else None
    if item and item.get("draft_id"):
        item["draft"] = get_draft(item["draft_id"])
    return item


def list_human_reviews(status=None, limit=200):
    init_db()
    limit=max(1,min(int(limit),500))
    with _conn() as c:
        if status:
            rows=c.execute("SELECT * FROM human_reviews WHERE status=? ORDER BY id DESC LIMIT ?",(status,limit)).fetchall()
        else:
            rows=c.execute("SELECT * FROM human_reviews ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    reviews=[]
    for row in rows:
        item=dict(row)
        if item.get("draft_id"):
            item["draft"] = get_draft(item["draft_id"])
        reviews.append(item)
    return reviews


def resolve_human_review(review_id, reviewer_employee_id, reviewer_username, reviewer_role, decision, note=""):
    decision=(decision or "").strip().lower()
    if decision not in {"approved","rejected"}:
        raise ValueError("Decision must be approved or rejected.")
    init_db()
    reviewed_at=_now()
    with _conn() as c:
        row=c.execute("SELECT * FROM human_reviews WHERE id=?", (review_id,)).fetchone()
        if not row:
            raise LookupError("Review request not found.")
        require_reviewer_identity(reviewer_employee_id, reviewer_username, reviewer_role, dict(row))
        if row["status"] != "pending":
            raise ValueError("Review request is already resolved.")
        c.execute("""UPDATE human_reviews SET status=?,reviewer_employee_id=?,reviewer_username=?,
                     reviewer_role=?,decision_note=?,reviewed_at=? WHERE id=?""",
                  (decision,reviewer_employee_id,reviewer_username,reviewer_role,note.strip(),reviewed_at,review_id))
    audit(reviewer_employee_id, reviewer_username, reviewer_role,
          f"human_review_{decision}", row["resource"], decision,
          entity_type="human_review", entity_id=str(review_id), review_id=review_id,
          draft_id=row["draft_id"], draft_version=row["draft_version"],
          metadata={"decision_note_present": bool(note.strip()), "artifact_type": row["artifact_type"]})
    return get_human_review(review_id)

