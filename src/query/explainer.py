"""
Result explainer — generates a 2-3 sentence plain-English explanation of a
graph query result, emphasising why graph reasoning found something vector
search could not.

Usage:
  from src.query.explainer import explain
  text = explain("Who supplies chips to Microsoft?", results, query_type="supply_chain_map")
"""

import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

MODEL = "claude-opus-4-8"

_SYSTEM = """You are a financial analyst answering a question using ONLY a knowledge-graph traversal.

You are given:
  - the user's question
  - a numbered list of FACTS, each a graph edge: [n] SOURCE —RELATION→ TARGET
  - the raw result rows (dates, titles, event descriptions) backing those edges

Rules:
  - Answer the question directly, in 2-4 sentences.
  - Support every claim with a bracket citation to the fact(s) that establish it, e.g. "NVDA supplies Microsoft [3]".
  - Use ONLY the given facts and rows. Do not add companies, executives, events, or relationships that are not present.
  - If the facts are insufficient to answer, say so plainly — do not fill the gap with outside knowledge.
  - End with one sentence on why a keyword/vector search could not have composed this multi-hop chain.
Be concise and direct. No bullet points, no preamble."""



def explain(question: str, results: list[dict], query_type: str = "", triples=None) -> str:
    """
    Generate a plain-English explanation of graph query results.

    Args:
        question:   The original question (NL or preset description).
        results:    List of result row dicts from the Cypher query.
        query_type: Optional query key or label for context.

    Returns:
        2-3 sentence explanation string.
    """
    triples = triples or []

    if not results:
        return "The query returned no results. This may mean the relevant nodes or edges are not yet in the graph, or the date filters do not match the ingested data."
    if not triples:
        return "The query returned rows but no connected relationship chain to cite, so a grounded multi-hop answer cannot be composed from this result."
    
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set in .env or Streamlit secrets")

    client = anthropic.Anthropic(api_key=api_key)

    # Numbered fact list — the [n] anchors the citations map back to.
    facts_text = "\n".join(
        f"[{i}] {src} —{rel}→ {tgt}"
        for i, (src, tgt, rel) in enumerate(triples, start=1)
    )

    # Summarise results — cap at 10 rows to keep prompt short
    sample = results[:10]
    results_text = "\n".join(
        ", ".join(f"{k}: {v}" for k, v in row.items() if v is not None)
        for row in sample
    )
    
    if len(results) > 10:
        results_text += f"\n… and {len(results) - 10} more rows."

    user_content = (
        f"Question: {question}\n\n"
        f"Query type: {query_type}\n\n"
        f"Facts (graph edges — cite these by number):\n{facts_text}\n\n"
        f"Results rows ({len(results)} total):\n{results_text}"
    )

    message = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    # First text block — content[0] may be a ThinkingBlock on models with
    # adaptive thinking on by default, so don't assume index 0.
    return next(b.text for b in message.content if b.type == "text").strip()
