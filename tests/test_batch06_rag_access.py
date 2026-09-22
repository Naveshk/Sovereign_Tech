import sys, types, importlib

# Keep this unit test independent of the optional local Ollama/Chroma runtime.
ollama = types.ModuleType("ollama")
ollama.embeddings = lambda *a, **k: {}
sys.modules.setdefault("ollama", ollama)

chroma = types.ModuleType("chromadb")
class _Collection: 
    def count(self): return 0
class _Client:
    def get_or_create_collection(self, **kwargs): return _Collection()
chroma.PersistentClient = lambda **kwargs: _Client()
sys.modules.setdefault("chromadb", chroma)

retriever = importlib.import_module("app.services.rag.retriever")
pipeline = importlib.import_module("app.services.rag.pipeline")


def test_retriever_filters_by_role_and_department(monkeypatch):
    monkeypatch.setattr(retriever, "embed_text", lambda q: [0.1])
    monkeypatch.setattr(retriever, "search", lambda emb, n_results: [
        {"text": "secret", "metadata": {"source": "a.pdf", "allowed_roles": "Manager", "department": "Refinery"}, "distance": 0.1},
        {"text": "engineering", "metadata": {"source": "b.pdf", "allowed_roles": "Engineer,Manager", "department": "Refinery"}, "distance": 0.2},
        {"text": "dev", "metadata": {"source": "c.pdf", "allowed_roles": "Developer", "department": "IT"}, "distance": 0.3},
    ])
    out = retriever.retrieve("query", top_k=5, role="Engineer", department="Refinery")
    assert [x["metadata"]["source"] for x in out] == ["b.pdf"]


def test_pipeline_exposes_evidence_and_rejects_missing_role(monkeypatch):
    monkeypatch.setattr(pipeline, "retrieve", lambda *args, **kwargs: [
        {"text": "x", "metadata": {"source": "manual.pdf", "page": "4", "chunk_index": "2", "classification": "confidential"}, "distance": 0.12}
    ])
    monkeypatch.setattr(pipeline, "build_context", lambda results: "manual evidence")
    out = pipeline.run_rag("pressure", role="Engineer")
    assert out["found"] is True
    assert out["evidence"][0]["source"] == "manual.pdf"
    assert out["access"]["enforced"] is True
    assert pipeline.run_rag("pressure", role=None)["found"] is False
