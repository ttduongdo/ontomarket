"""
Ingests LLM-extracted edges from data/raw/extracted_edges.json into Neo4j.

Reads the output of llm_extractor_batch.py and adds:
  - Event nodes  (deduped by event_id)
  - Person nodes (deduped by person_id slug)
  - AFFECTED_BY edges   (Company → Event,   with confidence + impact)
  - EXECUTIVE_OF edges  (Person  → Company, with confidence + role)
  - FORMERLY_AT edges   (Person  → Company, with confidence)
  - SUPPLIES_TO edges   (Company → Company, with confidence + product)

Company nodes are NOT created here — they must already exist from ingest.py.
Edges referencing unknown tickers are silently skipped (MATCH returns nothing).

Idempotent — safe to re-run after new extraction runs.

Usage:
  python -m src.data.ingest_extracted
"""

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(Path(__file__).parents[2] / ".env")

EXTRACTED_FILE = Path(__file__).parents[2] / "data" / "raw" / "extracted_edges.json"

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def clean_date(value) -> str | None:
    if value and isinstance(value, str) and DATE_RE.match(value):
        return value
    return None


# ---------------------------------------------------------------------------
# Deduplication — collapse 25 articles into unique entity/edge sets
# ---------------------------------------------------------------------------

def deduplicate(articles: list[dict]) -> dict:
    events:          dict[str, dict] = {}
    persons:         dict[str, dict] = {}
    affected_by:     dict[str, dict] = {}   # (ticker, event_id) → row
    executive_of:    dict[str, dict] = {}   # (person_id, ticker) → row
    formerly_at:     dict[str, dict] = {}   # (person_id, ticker) → row
    supplies_to:     dict[str, dict] = {}   # (supplier, customer) → row

    for article in articles:
        ext    = article.get("extracted", {})
        source = article.get("source", "llm-extracted")

        # ── Events ──────────────────────────────────────────────────────────
        for e in ext.get("events", []):
            eid = e.get("id", "").strip()
            if not eid:
                continue
            if eid not in events or e.get("confidence", 0) > events[eid].get("confidence", 0):
                events[eid] = {
                    "event_id":    eid,
                    "event_date":  clean_date(e.get("date")),
                    "event_type":  e.get("event_type", "other"),
                    "description": e.get("description", ""),
                    "confidence":  e.get("confidence", 0.8),
                    "source":      source,
                }
            # AFFECTED_BY: company → event
            ticker = e.get("affected_company", "").strip()
            impact = e.get("impact", "unknown")
            if ticker and eid:
                key = (ticker, eid)
                if key not in affected_by:
                    affected_by[key] = {
                        "company_ticker": ticker,
                        "event_id":       eid,
                        "impact":         impact,
                        "confidence":     e.get("confidence", 0.8),
                    }

        # ── Executive moves ─────────────────────────────────────────────────
        for m in ext.get("executive_moves", []):
            person_name  = m.get("person", "").strip()
            to_ticker    = m.get("to_company", "").strip()
            from_ticker  = (m.get("from_company") or "").strip() or None
            role         = m.get("role", "")
            date         = clean_date(m.get("date"))
            conf         = m.get("confidence", 0.8)

            if not person_name or not to_ticker:
                continue

            pid = slugify(person_name)
            if pid not in persons:
                persons[pid] = {"person_id": pid, "name": person_name}

            eo_key = (pid, to_ticker)
            if eo_key not in executive_of:
                executive_of[eo_key] = {
                    "person_id":      pid,
                    "company_ticker": to_ticker,
                    "title":          role,
                    "start_date":     date,
                    "confidence":     conf,
                    "source":         source,
                }

            if from_ticker:
                fa_key = (pid, from_ticker)
                if fa_key not in formerly_at:
                    formerly_at[fa_key] = {
                        "person_id":      pid,
                        "company_ticker": from_ticker,
                        "confidence":     conf,
                        "source":         source,
                    }

        # ── Supply relationships ─────────────────────────────────────────────
        for s in ext.get("supply_relationships", []):
            supplier = s.get("supplier", "").strip()
            customer = s.get("customer", "").strip()
            product  = s.get("product", "")
            conf     = s.get("confidence", 0.8)

            if not supplier or not customer:
                continue

            key = (supplier, customer)
            if key not in supplies_to or conf > supplies_to[key].get("confidence", 0):
                supplies_to[key] = {
                    "supplier":   supplier,
                    "customer":   customer,
                    "category":   product,
                    "confidence": conf,
                    "source":     source,
                }

    return {
        "events":       list(events.values()),
        "persons":      list(persons.values()),
        "affected_by":  list(affected_by.values()),
        "executive_of": list(executive_of.values()),
        "formerly_at":  list(formerly_at.values()),
        "supplies_to":  list(supplies_to.values()),
    }


# ---------------------------------------------------------------------------
# Neo4j loaders
# ---------------------------------------------------------------------------

def load_events(tx, rows: list[dict]) -> int:
    r = tx.run(
        """
        UNWIND $rows AS row
        MERGE (e:Event {event_id: row.event_id})
        SET e.event_date  = row.event_date,
            e.event_type  = row.event_type,
            e.description = row.description,
            e.confidence  = row.confidence,
            e.source      = row.source
        RETURN count(*) AS n
        """,
        rows=rows,
    )
    return r.single()["n"]


def load_persons(tx, rows: list[dict]) -> int:
    r = tx.run(
        """
        UNWIND $rows AS row
        MERGE (p:Person {person_id: row.person_id})
        ON CREATE SET p.name = row.name
        RETURN count(*) AS n
        """,
        rows=rows,
    )
    return r.single()["n"]


def load_affected_by(tx, rows: list[dict]) -> int:
    r = tx.run(
        """
        UNWIND $rows AS row
        MATCH (c:Company {ticker:   row.company_ticker})
        MATCH (e:Event   {event_id: row.event_id})
        MERGE (c)-[r:AFFECTED_BY]->(e)
        SET r.impact     = row.impact,
            r.confidence = row.confidence
        RETURN count(*) AS n
        """,
        rows=rows,
    )
    return r.single()["n"]


def load_executive_of(tx, rows: list[dict]) -> int:
    r = tx.run(
        """
        UNWIND $rows AS row
        MATCH (p:Person  {person_id: row.person_id})
        MATCH (c:Company {ticker:    row.company_ticker})
        MERGE (p)-[r:EXECUTIVE_OF]->(c)
        SET r.title      = row.title,
            r.start_date = row.start_date,
            r.confidence = row.confidence,
            r.source     = row.source
        RETURN count(*) AS n
        """,
        rows=rows,
    )
    return r.single()["n"]


def load_formerly_at(tx, rows: list[dict]) -> int:
    r = tx.run(
        """
        UNWIND $rows AS row
        MATCH (p:Person  {person_id: row.person_id})
        MATCH (c:Company {ticker:    row.company_ticker})
        MERGE (p)-[r:FORMERLY_AT]->(c)
        SET r.confidence = row.confidence,
            r.source     = row.source
        RETURN count(*) AS n
        """,
        rows=rows,
    )
    return r.single()["n"]


def load_supplies_to(tx, rows: list[dict]) -> int:
    r = tx.run(
        """
        UNWIND $rows AS row
        MATCH (s:Company {ticker: row.supplier})
        MATCH (c:Company {ticker: row.customer})
        MERGE (s)-[r:SUPPLIES_TO]->(c)
        SET r.category   = row.category,
            r.confidence = row.confidence,
            r.source     = row.source
        RETURN count(*) AS n
        """,
        rows=rows,
    )
    return r.single()["n"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not NEO4J_PASSWORD:
        raise EnvironmentError("NEO4J_PASSWORD is not set in .env")

    if not EXTRACTED_FILE.exists():
        raise FileNotFoundError(
            f"{EXTRACTED_FILE} not found. Run llm_extractor_batch.py first."
        )

    articles = json.loads(EXTRACTED_FILE.read_text())
    print(f"Read {len(articles)} extracted articles from {EXTRACTED_FILE.name}")

    print("Deduplicating …")
    data = deduplicate(articles)
    print(f"  {len(data['events'])} unique events")
    print(f"  {len(data['persons'])} unique persons")
    print(f"  {len(data['affected_by'])} AFFECTED_BY edges")
    print(f"  {len(data['executive_of'])} EXECUTIVE_OF edges")
    print(f"  {len(data['formerly_at'])} FORMERLY_AT edges")
    print(f"  {len(data['supplies_to'])} SUPPLIES_TO edges")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            print("\nIngesting into Neo4j …")

            n = session.execute_write(load_events, data["events"])
            print(f"  Event nodes:      {n} merged")

            n = session.execute_write(load_persons, data["persons"])
            print(f"  Person nodes:     {n} merged")

            n = session.execute_write(load_affected_by, data["affected_by"])
            print(f"  AFFECTED_BY:      {n} merged")

            n = session.execute_write(load_executive_of, data["executive_of"])
            print(f"  EXECUTIVE_OF:     {n} merged")

            n = session.execute_write(load_formerly_at, data["formerly_at"])
            print(f"  FORMERLY_AT:      {n} merged")

            n = session.execute_write(load_supplies_to, data["supplies_to"])
            print(f"  SUPPLIES_TO:      {n} merged")

    finally:
        driver.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
