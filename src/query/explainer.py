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

MODEL = "claude-sonnet-4-6"

_SYSTEM = """You are a financial analyst assistant explaining knowledge graph query results.
Write exactly 2-3 sentences. Be specific — name companies, executives, and events from the data.
Always end with one sentence on why a keyword/vector search could NOT have produced this answer
(it cannot compose multi-hop relational chains). Be concise and direct. No bullet points."""


def explain(question: str, results: list[dict], query_type: str = "") -> str:
    """
    Generate a plain-English explanation of graph query results.

    Args:
        question:   The original question (NL or preset description).
        results:    List of result row dicts from the Cypher query.
        query_type: Optional query key or label for context.

    Returns:
        2-3 sentence explanation string.
    """
    if not results:
        return "The query returned no results. This may mean the relevant nodes or edges are not yet in the graph, or the date filters do not match the ingested data."

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
        f"Results ({len(results)} rows):\n{results_text}"
    )

    message = client.messages.create(
        model=MODEL,
        max_tokens=256,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    return message.content[0].text.strip()
