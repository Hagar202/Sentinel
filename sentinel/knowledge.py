"""RAG: find the part of the company documents that answers a question.

Documents (knowledge/*.md): security policy, incident runbook, AI cost policy.
1. Cut every document into chunks (one chunk = one "## " section).
2. Embeddings: turn every chunk into a vector with Gemini embeddings, and store the vectors in FAISS.
3. Search: turn the question into a vector and take the closest chunks (cosine similarity).
No API key (offline)? Fall back to a simple keyword search, so the agents still work.
"""
from functools import lru_cache

import numpy as np

from . import config

DOCUMENTS = ["security_policy.md", "incident_runbook.md", "ai_cost_policy.md"]


def load_chunks():
    """[{"source": "security_policy", "text": "## Payments ..."}, ...]"""
    chunks = []
    for name in DOCUMENTS:
        text = (config.KNOWLEDGE_DIR / name).read_text(encoding="utf-8")
        for section in text.split("\n## ")[1:]:                      # skip the document title
            chunks.append({"source": name.removesuffix(".md"), "text": "## " + section.strip()})
    return chunks


def get_embeddings():
    """Gemini embeddings (text -> vector), or None offline."""
    if config.LLM_PROVIDER == "gemini" and config.GOOGLE_API_KEY:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(model=config.GEMINI_EMBEDDING_MODEL, google_api_key=config.GOOGLE_API_KEY)
    return None


class VectorStore:
    """A tiny FAISS index. Vectors are normalized, so inner product = cosine similarity."""

    def __init__(self, chunks, embeddings):
        import faiss
        self.chunks, self.embeddings = chunks, embeddings
        vectors = np.array(embeddings.embed_documents([c["text"] for c in chunks]), dtype="float32")
        faiss.normalize_L2(vectors)
        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)

    def search(self, question, k=2):
        import faiss
        query = np.array([self.embeddings.embed_query(question)], dtype="float32")
        faiss.normalize_L2(query)
        scores, ids = self.index.search(query, k)
        return [{**self.chunks[i], "score": float(s)} for s, i in zip(scores[0], ids[0]) if i >= 0]


@lru_cache   # build the index once (embedding the documents costs API calls)
def vector_store():
    embeddings = get_embeddings()
    if embeddings is None:
        return None
    try:
        return VectorStore(load_chunks(), embeddings)
    except Exception:            # no internet / quota -> keyword search
        return None


def keyword_search(question, k=2):
    """Offline backup: the chunks that share the most words with the question."""
    words = set(question.lower().split())
    scored = [{**c, "score": len(words & set(c["text"].lower().split()))} for c in load_chunks()]
    return [c for c in sorted(scored, key=lambda c: -c["score"])[:k] if c["score"] > 0]


def search_knowledge(question, k=2):
    """The k document chunks closest to the question, with their source."""
    store = vector_store()
    if store is not None:
        try:
            return store.search(question, k)
        except Exception:
            pass
    return keyword_search(question, k)


def find_policy(question):
    """The best matching chunk as text (used in prompts)."""
    found = search_knowledge(question, k=1)
    return found[0]["text"] if found else ""
