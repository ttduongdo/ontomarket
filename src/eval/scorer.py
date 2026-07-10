"""
Scoring functions for graph vs. vector search comparison.

Metrics
-------
graph_entity_recall
    Fraction of must_include_entities that appear as a value in any column
    of any result row.  1.0 = all expected entities found.

vector_entity_recall
    Fraction of must_include_entities whose string value — or a known name
    alias, via src.data.resolver — appears (case-insensitive substring) in
    the combined text of the top-K snippets.

vector_chain_recall
    1.0 if a single snippet's text contains ALL must_include_entities
    (literal or aliased). Always 0 for multi-hop questions by construction.

graph_precision
    Fraction of (col, val) pairs in results that mention at least one
    must_include_entity.  Measures noise — rows that contain none of the
    expected entities.
"""

from __future__ import annotations

from src.data.resolver import aliases_for


def _mentioned(entity: str, text_lower: str) -> bool:
    """
    True if `entity` (a ticker, or any plain string) is present in
    `text_lower`, either literally or via any known name alias
    (e.g. entity="NVDA" also matches "nvidia", "nvidia corp", ...).
    """
    if entity.lower() in text_lower:
        return True
    return any(alias in text_lower for alias in aliases_for(entity))


def graph_entity_recall(results: list[dict], must_include: list[str]) -> float:
    """Fraction of expected entities that appear in any result cell."""
    if not must_include:
        return 1.0
    all_values = {
        str(v).strip()
        for row in results
        for v in row.values()
        if v is not None
    }
    found = sum(1 for e in must_include if e in all_values)
    return round(found / len(must_include), 3)


def graph_precision(results: list[dict], must_include: list[str]) -> float:
    """
    Fraction of result rows where at least one cell value matches a
    must_include entity.  Low precision = graph returned irrelevant rows.
    """
    if not results or not must_include:
        return 1.0
    entity_set = set(must_include)
    relevant = sum(
        1 for row in results
        if any(str(v).strip() in entity_set for v in row.values() if v is not None)
    )
    return round(relevant / len(results), 3)


def vector_entity_recall(snippets: list, must_include: list[str]) -> float:
    """
    Fraction of expected entities mentioned (case-insensitive) across all
    retrieved snippets. An entity counts as mentioned if its literal string
    or any known name alias (e.g. "NVDA" / "nvidia") appears in the text.
    """
    if not must_include:
        return 1.0
    combined = " ".join(s.text for s in snippets).lower()
    found = sum(1 for e in must_include if _mentioned(e, combined))
    return round(found / len(must_include), 3)


def vector_chain_recall(snippets: list, must_include: list[str]) -> float:
    """
    1.0 if any single snippet text contains ALL must_include entities
    (literal string or known name alias). For multi-hop questions
    (hops >= 2) this is almost always 0.
    """
    if not must_include:
        return 1.0
    for snippet in snippets:
        text = snippet.text.lower()
        if all(_mentioned(e, text) for e in must_include):
            return 1.0
    return 0.0


def score_question(
    question: dict,
    graph_results: list[dict],
    vector_hits: list,
) -> dict:
    """
    Run all four metrics for one eval question.  Returns a result dict
    ready for tabular display or JSON output.
    """
    must_include = question.get("must_include_entities", [])
    hops         = question.get("hops", 1)

    g_recall   = graph_entity_recall(graph_results, must_include)
    g_prec     = graph_precision(graph_results, must_include)
    v_recall   = vector_entity_recall(vector_hits, must_include)
    v_chain    = vector_chain_recall(vector_hits, must_include)
    v_expected = question.get("vector_can_compose", False)

    return {
        "id":                  question["id"],
        "query_key":           question["query_key"],
        "hops":                hops,
        "graph_rows":          len(graph_results),
        "expected_min_rows":   question.get("expected_min_rows", 0),
        "rows_ok":             len(graph_results) >= question.get("expected_min_rows", 0),
        "graph_entity_recall": g_recall,
        "graph_precision":     g_prec,
        "vector_entity_recall": v_recall,
        "vector_chain_recall": v_chain,
        "vector_can_compose":  v_expected,
        "recall_delta":        round(g_recall - v_recall, 3),
        "chain_gap":           round(g_recall - v_chain, 3),
    }
