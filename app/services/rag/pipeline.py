from app.services.rag.retriever import retrieve
from app.services.rag.context_builder import build_context


def run_rag(query: str, top_k: int = 5, role: str | None = None,
            department: str | None = None, classification: str | None = None) -> dict:
    if role not in {"Engineer", "Developer", "Manager"}:
        return {"query": query, "results": [], "context": "", "found": False,
                "evidence": [], "access": {"role": role, "department": department,
                                             "classification": classification, "enforced": False}}
    results = retrieve(query, top_k=top_k, role=role,
                       department=department, classification=classification)
    evidence = []
    for item in results:
        metadata = item.get("metadata") or {}
        evidence.append({
            "source": metadata.get("source"),
            "page": metadata.get("page"),
            "chunk_index": metadata.get("chunk_index"),
            "distance": item.get("distance"),
            "classification": metadata.get("classification"),
        })
    return {
        "query": query, "results": results, "context": build_context(results),
        "found": bool(results), "evidence": evidence,
        "access": {"role": role, "department": department,
                   "classification": classification, "enforced": role is not None},
    }
