"""
Embeds vector_snippets.json with sentence-transformers and stores them in a
local ChromaDB collection. Idempotent — clears and re-builds the collection
on each run so snippets stay in sync with the source file.

Usage:
  python src/search/embed.py
"""

import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

SNIPPETS_PATH  = Path(__file__).parents[2] / "data" / "raw" / "vector_snippets.json"
CHROMA_PATH    = Path(__file__).parents[2] / "chroma_db"
COLLECTION_NAME = "ontomarket_snippets"
MODEL_NAME      = "all-MiniLM-L6-v2"   # fast, 384-dim, good enough for demo


def main() -> None:
    print(f"Loading snippets from {SNIPPETS_PATH} …")
    data     = json.loads(SNIPPETS_PATH.read_text())
    snippets = data["snippets"]
    print(f"  {len(snippets)} snippets loaded")

    print(f"Loading embedding model '{MODEL_NAME}' …")
    model = SentenceTransformer(MODEL_NAME)

    texts = [s["text"] for s in snippets]
    ids   = [s["id"]   for s in snippets]
    metas = [{"tags": ", ".join(s.get("tags", []))} for s in snippets]

    print("Embedding …")
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    print(f"Writing to ChromaDB at {CHROMA_PATH} …")
    client     = chromadb.PersistentClient(path=str(CHROMA_PATH))

    # Delete and recreate so re-runs are idempotent
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metas,
    )

    print(f"Done. {collection.count()} documents in '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    main()
