import os
from ollama import embeddings

EMBEDDING_MODEL = os.getenv('OLLAMA_EMBEDDING_MODEL', 'qwen3-embedding:0.6b')


def embed_text(text: str) -> list[float]:
    if not text.strip():
        return []
    result = embeddings(model=EMBEDDING_MODEL, prompt=text)
    return result['embedding']


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [embed_text(t) for t in texts]
