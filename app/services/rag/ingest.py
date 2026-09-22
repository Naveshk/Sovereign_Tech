import hashlib
import shutil
from pathlib import Path
from app.services.rag.document_loader import load_document
from app.services.rag.chunker import chunk_pages
from app.services.rag.embeddings import embed_texts
from app.services.rag.vector_store import upsert_chunks

BASE_DIR = Path(__file__).resolve().parents[3]
DOC_DIR = BASE_DIR / "data" / "knowledge_base" / "documents"
DOC_DIR.mkdir(parents=True, exist_ok=True)
VALID_ROLES = {"Engineer", "Developer", "Manager"}
VALID_CLASSIFICATIONS = {"general", "internal", "confidential", "restricted"}


def ingest_file(path: str, original_name: str | None = None,
                allowed_roles: list[str] | None = None,
                classification: str = "internal",
                department: str | None = None) -> dict:
    source = Path(path)
    pages = load_document(str(source))
    chunks = chunk_pages(pages)
    if not chunks:
        return {"status": "error", "message": "No text could be extracted from the document."}
    roles = set(allowed_roles or VALID_ROLES)
    if not roles or not roles.issubset(VALID_ROLES):
        return {"status": "error", "message": "allowed_roles must contain only Engineer, Developer, or Manager."}
    classification = (classification or "internal").lower().strip()
    if classification not in VALID_CLASSIFICATIONS:
        return {"status": "error", "message": "Invalid classification."}
    texts = [c["text"] for c in chunks]
    vectors = embed_texts(texts)
    base = original_name or source.name
    ids, metas = [], []
    roles_text = ",".join(sorted(roles))
    for c in chunks:
        raw = f'{base}|{c["page"]}|{c["chunk_index"]}|{c["text"]}'.encode("utf-8", errors="ignore")
        ids.append(hashlib.sha1(raw).hexdigest())
        metas.append({
            "source": base, "page": str(c["page"]), "chunk_index": str(c["chunk_index"]),
            "allowed_roles": roles_text, "classification": classification,
            "department": department or "",
        })
    count = upsert_chunks(ids, texts, vectors, metas)
    destination = DOC_DIR / source.name
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)
    return {"status": "completed", "source": base, "chunks": count,
            "metadata": {"allowed_roles": sorted(roles), "classification": classification,
                         "department": department}}
