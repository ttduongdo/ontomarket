""" 
Entity seeder - vector-search the question, resolve mentions to canonical tickers. These anchors 
ground the NL→Cypher step so it targets real, in-graph entities instead of guessing from raw question
text (the GraphRAG retrieve-then-traverse pattern)
"""

from src.search.retriever import search
from src.data.resolver import ALIAS_TABLE, resolve

def seed_entities(question: str, top_k: int = 5) -> list[str]:
    """
    Return canonical tickers the question is likely about, found by vector search
    over the snippet corpus + alias resolution. Empty list if nothing resolves
    (caller falls back to un-seeded translation).
    """

    hits = search(question, top_k=top_k)

    corpus = (question + " " + " ".join(h.text for h in hits)).lower()

    found: list[str] = []
    seen: set[str] = set()

    for alias in sorted(ALIAS_TABLE, key=len, reverse=True):
        if alias in corpus:
            ticker = resolve(alias)
            if ticker and ticker not in seen:
                seen.add(ticker)
                found.append(ticker)

    return found

