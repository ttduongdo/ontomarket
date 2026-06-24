"""
Hard-coded Cypher query templates for OntoMarket Phase 3.

Five preset queries, each returning structured result dicts and a list of
(source, target, relationship) triples for the NetworkX/Plotly subgraph.

Usage:
  from src.graph.queries import run_query, QUERIES
  results, triples = run_query(driver, "hero")
"""

from neo4j import Driver

# ---------------------------------------------------------------------------
# Query registry — keys are used in the Streamlit dropdown
# ---------------------------------------------------------------------------

QUERIES: dict[str, dict] = {

    "hero": {
        "label": "Hero query — full 4-hop chain",
        "description": (
            "Which companies face supply-chain exposure when Company X has a "
            "regulatory event, given that an executive moved from X to a "
            "competitor within the last two years?"
        ),
        "cypher": """
            MATCH (evt:Event)<-[:AFFECTED_BY]-(x:Company)
            MATCH (x)-[:COMPETES_WITH]-(y:Company)
            MATCH (p:Person)-[e1:EXECUTIVE_OF]->(x)
            MATCH (p)-[e2:EXECUTIVE_OF]->(y)
            WHERE e1.end_date IS NOT NULL
              AND e2.start_date >= $since
              AND e2.end_date IS NULL
            MATCH (z:Company)-[:SUPPLIES_TO]->(x)
            RETURN
              x.ticker        AS affected_company,
              x.name          AS affected_company_name,
              evt.event_id    AS event_id,
              evt.event_type  AS event_type,
              evt.description AS event_description,
              y.ticker        AS competitor,
              y.name          AS competitor_name,
              p.name          AS executive,
              e1.title        AS former_title,
              e1.end_date     AS departure_date,
              e2.title        AS current_title,
              e2.start_date   AS arrival_date,
              z.ticker        AS exposed_supplier,
              z.name          AS exposed_supplier_name
            ORDER BY e2.start_date DESC
        """,
        "params": {"since": "2024-01-01"},
    },

    "exec_move_then_event": {
        "label": "3-hop — exec moved to competitor, competitor had an event",
        "description": (
            "An executive left Company A for a direct competitor. "
            "Has that competitor had a notable event since the move?"
        ),
        "cypher": """
            MATCH (p:Person)-[e1:EXECUTIVE_OF]->(a:Company)
            MATCH (p)-[e2:EXECUTIVE_OF]->(b:Company)
            MATCH (a)-[:COMPETES_WITH]-(b)
            WHERE e1.end_date IS NOT NULL
              AND e2.start_date >= $since
              AND e2.end_date IS NULL
            MATCH (b)-[:AFFECTED_BY]->(evt:Event)
            WHERE evt.event_date >= e2.start_date
            RETURN
              p.name         AS executive,
              a.ticker       AS former_company,
              a.name         AS former_company_name,
              e1.title       AS former_title,
              e1.end_date    AS departure_date,
              b.ticker       AS current_company,
              b.name         AS current_company_name,
              e2.title       AS current_title,
              e2.start_date  AS arrival_date,
              evt.event_id   AS event_id,
              evt.event_type AS event_type,
              evt.event_date AS event_date,
              evt.description AS event_description
            ORDER BY evt.event_date DESC
        """,
        "params": {"since": "2024-01-01"},
    },

    "reverse_supply_exposure": {
        "label": "Reverse supply — who supplies the affected company?",
        "description": (
            "If Company A faces a regulatory action, which of its suppliers "
            "face downstream exposure?"
        ),
        "cypher": """
            MATCH (a:Company)-[:AFFECTED_BY]->(evt:Event)
            WHERE evt.event_type IN ['regulatory_filing', 'lawsuit']
            MATCH (supplier:Company)-[:SUPPLIES_TO]->(a)
            RETURN
              a.ticker         AS affected_company,
              a.name           AS affected_company_name,
              evt.event_id     AS event_id,
              evt.event_type   AS event_type,
              evt.description  AS event_description,
              supplier.ticker  AS supplier,
              supplier.name    AS supplier_name
            ORDER BY a.ticker, supplier.ticker
        """,
        "params": {},
    },

    "competitor_events": {
        "label": "Competitor scan — notable events among rivals",
        "description": (
            "For a given company, what notable events have its direct "
            "competitors had?"
        ),
        "cypher": """
            MATCH (focus:Company {ticker: $ticker})
            MATCH (focus)-[:COMPETES_WITH]-(rival:Company)
            MATCH (rival)-[ab:AFFECTED_BY]->(evt:Event)
            RETURN
              rival.ticker     AS rival,
              rival.name       AS rival_name,
              evt.event_id     AS event_id,
              evt.event_type   AS event_type,
              evt.event_date   AS event_date,
              evt.description  AS event_description,
              ab.impact        AS impact
            ORDER BY evt.event_date DESC
        """,
        "params": {"ticker": "INTC"},
    },

    "supply_chain_map": {
        "label": "Supply chain map — who supplies whom?",
        "description": (
            "Show all SUPPLIES_TO relationships in the graph, with categories."
        ),
        "cypher": """
            MATCH (s:Company)-[r:SUPPLIES_TO]->(c:Company)
            RETURN
              s.ticker    AS supplier,
              s.name      AS supplier_name,
              c.ticker    AS customer,
              c.name      AS customer_name,
              r.category  AS category
            ORDER BY s.ticker, c.ticker
        """,
        "params": {},
    },
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_query(driver: Driver, query_key: str) -> tuple[list[dict], list[tuple]]:
    """
    Execute a named query and return:
      results — list of record dicts (for the Streamlit result panel)
      triples — list of (source_label, target_label, rel_type) for the graph viz
    """
    if query_key not in QUERIES:
        raise ValueError(f"Unknown query key '{query_key}'. Options: {list(QUERIES)}")

    q = QUERIES[query_key]

    with driver.session() as session:
        records = session.run(q["cypher"], **q["params"]).data()

    triples = _extract_triples(query_key, records)
    return records, triples


def _extract_triples(key: str, records: list[dict]) -> list[tuple]:
    """Build (source, target, rel_type) triples for NetworkX from query results."""
    seen = set()
    triples = []

    def add(src, tgt, rel):
        edge = (src, tgt, rel)
        if edge not in seen:
            seen.add(edge)
            triples.append(edge)

    if key == "hero":
        for r in records:
            add(r["event_id"],        r["affected_company"], "AFFECTED_BY")
            add(r["affected_company"], r["competitor"],       "COMPETES_WITH")
            add(r["executive"],        r["affected_company"], "EXECUTIVE_OF (former)")
            add(r["executive"],        r["competitor"],       "EXECUTIVE_OF (current)")
            add(r["exposed_supplier"], r["affected_company"], "SUPPLIES_TO")

    elif key == "exec_move_then_event":
        for r in records:
            add(r["executive"],      r["former_company"],   "EXECUTIVE_OF (former)")
            add(r["executive"],      r["current_company"],  "EXECUTIVE_OF (current)")
            add(r["former_company"], r["current_company"],  "COMPETES_WITH")
            add(r["event_id"],       r["current_company"],  "AFFECTED_BY")

    elif key == "reverse_supply_exposure":
        for r in records:
            add(r["event_id"],   r["affected_company"], "AFFECTED_BY")
            add(r["supplier"],   r["affected_company"], "SUPPLIES_TO")

    elif key == "competitor_events":
        for r in records:
            add("focus",         r["rival"],    "COMPETES_WITH")
            add(r["event_id"],   r["rival"],    "AFFECTED_BY")

    elif key == "supply_chain_map":
        for r in records:
            add(r["supplier"], r["customer"], "SUPPLIES_TO")

    return triples
