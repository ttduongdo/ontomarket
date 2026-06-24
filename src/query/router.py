"""
Graph query router — thin wrapper around src/graph/queries.py.

Manages the Neo4j driver lifecycle and exposes a single run() call for the
Streamlit app. The driver is created once and reused.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver

from src.graph.queries import run_query, QUERIES

load_dotenv(Path(__file__).parents[2] / ".env")

NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")


def get_driver() -> Driver:
    if not NEO4J_PASSWORD:
        raise EnvironmentError("NEO4J_PASSWORD is not set in .env")
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def run(query_key: str) -> tuple[list[dict], list[tuple]]:
    """
    Execute a named graph query. Returns:
      results — list of record dicts for the result panel
      triples — list of (source, target, rel_type) for the subgraph viz
    """
    driver = get_driver()
    try:
        return run_query(driver, query_key)
    finally:
        driver.close()


def run_raw(cypher: str, params: dict | None = None) -> tuple[list[dict], list[tuple]]:
    """
    Execute a raw Cypher string (from the NL→Cypher translator).
    Returns results + a best-effort triple list extracted from result columns.
    Raises neo4j.exceptions.ClientError on invalid Cypher.
    """
    driver = get_driver()
    try:
        with driver.session() as session:
            records = session.run(cypher, **(params or {})).data()
        triples = _infer_triples(records)
        return records, triples
    finally:
        driver.close()


def _infer_triples(records: list[dict]) -> list[tuple]:
    """Best-effort: scan column names for recognisable (source, target) pairs."""
    if not records:
        return []

    cols = list(records[0].keys())
    pair_hints = [
        ("supplier",         "customer",         "SUPPLIES_TO"),
        ("exposed_supplier", "affected_company",  "SUPPLIES_TO"),
        ("affected_company", "competitor",        "COMPETES_WITH"),
        ("rival",            "focus",             "COMPETES_WITH"),
        ("executive",        "former_company",    "EXECUTIVE_OF (former)"),
        ("executive",        "current_company",   "EXECUTIVE_OF (current)"),
        ("event_id",         "affected_company",  "AFFECTED_BY"),
        ("event_id",         "rival",             "AFFECTED_BY"),
        ("event_id",         "current_company",   "AFFECTED_BY"),
    ]

    seen: set[tuple] = set()
    triples: list[tuple] = []

    for src_col, tgt_col, rel in pair_hints:
        if src_col in cols and tgt_col in cols:
            for r in records:
                src, tgt = r.get(src_col), r.get(tgt_col)
                if src and tgt:
                    edge = (str(src), str(tgt), rel)
                    if edge not in seen:
                        seen.add(edge)
                        triples.append(edge)

    return triples


def query_labels() -> dict[str, str]:
    """Returns {query_key: display_label} for the Streamlit dropdown."""
    return {k: v["label"] for k, v in QUERIES.items()}


def query_description(query_key: str) -> str:
    return QUERIES[query_key]["description"]
