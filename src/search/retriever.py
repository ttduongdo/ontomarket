"""
Vector search retriever — queries ChromaDB using sentence-transformers embeddings.

Returns top-k matching snippets with cosine similarity scores.
Used by the Streamlit app as the vector search baseline.
"""

from pathlib import Path
from dataclasses import dataclass

import chromadb
from sentence_transformers import SentenceTransformer

CHROMA_PATH     = Path(__file__).parents[2] / "chroma_db"
COLLECTION_NAME = "ontomarket_snippets"
MODEL_NAME      = "all-MiniLM-L6-v2"

# Module-level singletons — loaded once, reused across calls
_model:      SentenceTransformer | None = None
_collection: chromadb.Collection | None = None


@dataclass
class SearchResult:
    id:         str
    text:       str
    tags:       str
    similarity: float   # 1 - cosine distance (higher = more similar)


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _get_collection() -> chromadb.Collection:
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        try:
            _collection = client.get_collection(COLLECTION_NAME)
        except Exception:
            # Collection missing (e.g. fresh Streamlit Cloud deploy) — rebuild from snippets file
            from src.search.embed import main as _build_index
            _build_index()
            _collection = client.get_collection(COLLECTION_NAME)
    return _collection


def search(query: str, top_k: int = 5) -> list[SearchResult]:
    """
    Embed `query` and return the top_k most similar snippets.
    Raises RuntimeError if the ChromaDB collection doesn't exist yet
    (run embed.py first).
    """
    try:
        collection = _get_collection()
    except Exception as exc:
        raise RuntimeError(
            "ChromaDB collection not found. Run 'python src/search/embed.py' first."
        ) from exc

    model     = _get_model()
    embedding = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append(SearchResult(
            id=results["ids"][0][len(hits)],
            text=doc,
            tags=meta.get("tags", ""),
            similarity=round(1 - dist, 4),
        ))
    return hits
