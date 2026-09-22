from app.services.rag.embeddings import embed_text
from app.services.rag.vector_store import search

VALID_ROLES = {"Engineer", "Developer", "Manager"}


def _allowed(metadata: dict, role: str | None) -> bool:
    if role not in VALID_ROLES:
        return False
    raw = metadata.get("allowed_roles")
    if raw is None:
        return True  # legacy chunks remain readable until re-ingested
    roles = {r.strip() for r in str(raw).split(",") if r.strip()}
    return role in roles


def retrieve(query: str, top_k: int = 5, role: str | None = None,
             department: str | None = None, classification: str | None = None) -> list[dict]:
    """Retrieve local chunks and enforce access metadata before returning evidence."""
    if role not in VALID_ROLES:
        return []
    candidates = search(embed_text(query), n_results=max(top_k * 4, top_k))
    filtered = []
    for item in candidates:
        metadata = item.get("metadata") or {}
        if not _allowed(metadata, role):
            continue
        if department and metadata.get("department") not in {None, "", department}:
            continue
        if classification and metadata.get("classification") not in {None, "", classification}:
            continue
        filtered.append(item)
        if len(filtered) >= top_k:
            break
    return filtered
