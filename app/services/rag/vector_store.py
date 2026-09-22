import os
from pathlib import Path
import chromadb

BASE_DIR = Path(__file__).resolve().parents[3]
CHROMA_DIR = Path(os.getenv('CHROMA_DIR', str(BASE_DIR / 'data' / 'knowledge_base' / 'chroma')))
COLLECTION_NAME = os.getenv('CHROMA_COLLECTION', 'sovereign_knowledge')

CHROMA_DIR.mkdir(parents=True, exist_ok=True)
_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
_collection = _client.get_or_create_collection(
    name=COLLECTION_NAME,
    metadata={'hnsw:space': 'cosine'},
)


def upsert_chunks(ids, documents, embeddings, metadatas):
    if not documents:
        return 0
    _collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
    return len(documents)


def search(query_embedding: list[float], n_results: int = 5):
    if not query_embedding or _collection.count() == 0:
        return []
    # Cosine distance is lower for more similar chunks. Keep the threshold
    # configurable so deployments can tune recall/precision without code changes.
    try:
        min_similarity_distance = float(os.getenv("RAG_MAX_COSINE_DISTANCE", "0.65"))
    except ValueError:
        min_similarity_distance = 0.65
    result = _collection.query(query_embeddings=[query_embedding], n_results=max(1, n_results))
    docs = (result.get('documents') or [[]])[0]
    metas = (result.get('metadatas') or [[]])[0]
    distances = (result.get('distances') or [[]])[0]
    matches = []
    for i, d in enumerate(docs):
        distance = distances[i] if i < len(distances) else None
        if not d or (distance is not None and distance > min_similarity_distance):
            continue
        matches.append({'text': d, 'metadata': metas[i] or {}, 'distance': distance})
    return matches


def count() -> int:
    return _collection.count()
