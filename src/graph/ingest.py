"""
Neo4j ingestion for OntoMarket Phase 3.

Reads data/processed/*.json and loads all nodes and edges into a local Neo4j
instance. Idempotent — safe to re-run after a data fix (MERGE, not CREATE).

Usage:
  python src/graph/ingest.py

Environment variables (or .env file):
  NEO4J_URI      default: bolt://localhost:7687
  NEO4J_USER     default: neo4j
  NEO4J_PASSWORD required
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

PROC = Path(__file__).parents[2] / "data" / "processed"

NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")


# ---------------------------------------------------------------------------
# Schema constraints and indexes
# ---------------------------------------------------------------------------

CONSTRAINTS = [
    "CREATE CONSTRAINT company_ticker IF NOT EXISTS FOR (c:Company) REQUIRE c.ticker IS UNIQUE",
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.person_id IS UNIQUE",
    "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.event_id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)",
    "CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name)",
]


def apply_schema(tx) -> None:
    for stmt in CONSTRAINTS + INDEXES:
        tx.run(stmt)


# ---------------------------------------------------------------------------
# Node loaders
# ---------------------------------------------------------------------------

def load_companies(tx, companies: list[dict]) -> int:
    result = tx.run(
        """
        UNWIND $rows AS row
        MERGE (c:Company {ticker: row.ticker})
        SET c.name         = row.name,
            c.founded_date = row.founded_date
        RETURN count(*) AS n
        """,
        rows=companies,
    )
    return result.single()["n"]


def load_persons(tx, persons: list[dict]) -> int:
    result = tx.run(
        """
        UNWIND $rows AS row
        MERGE (p:Person {person_id: row.person_id})
        SET p.name = row.name
        RETURN count(*) AS n
        """,
        rows=persons,
    )
    return result.single()["n"]


def load_events(tx, events: list[dict]) -> int:
    result = tx.run(
        """
        UNWIND $rows AS row
        MERGE (e:Event {event_id: row.event_id})
        SET e.event_date  = row.event_date,
            e.event_type  = row.event_type,
            e.description = row.description
        RETURN count(*) AS n
        """,
        rows=events,
    )
    return result.single()["n"]


# ---------------------------------------------------------------------------
# Edge loaders
# ---------------------------------------------------------------------------

def load_competes_with(tx, edges: list[dict]) -> int:
    result = tx.run(
        """
        UNWIND $rows AS row
        MATCH (a:Company {ticker: row.company_a})
        MATCH (b:Company {ticker: row.company_b})
        MERGE (a)-[:COMPETES_WITH]-(b)
        RETURN count(*) AS n
        """,
        rows=edges,
    )
    return result.single()["n"]


def load_supplies_to(tx, edges: list[dict]) -> int:
    result = tx.run(
        """
        UNWIND $rows AS row
        MATCH (s:Company {ticker: row.supplier})
        MATCH (c:Company {ticker: row.customer})
        MERGE (s)-[r:SUPPLIES_TO]->(c)
        SET r.category = row.category
        RETURN count(*) AS n
        """,
        rows=edges,
    )
    return result.single()["n"]


def load_executive_of(tx, edges: list[dict]) -> int:
    result = tx.run(
        """
        UNWIND $rows AS row
        MATCH (p:Person  {person_id: row.person_id})
        MATCH (c:Company {ticker:    row.company_ticker})
        MERGE (p)-[r:EXECUTIVE_OF {
            company_ticker: row.company_ticker,
            start_date:     row.start_date
        }]->(c)
        SET r.title      = row.title,
            r.end_date   = row.end_date
        RETURN count(*) AS n
        """,
        rows=edges,
    )
    return result.single()["n"]


def load_affected_by(tx, edges: list[dict]) -> int:
    result = tx.run(
        """
        UNWIND $rows AS row
        MATCH (c:Company {ticker:   row.company_ticker})
        MATCH (e:Event   {event_id: row.event_id})
        MERGE (c)-[r:AFFECTED_BY]->(e)
        SET r.impact = row.impact
        RETURN count(*) AS n
        """,
        rows=edges,
    )
    return result.single()["n"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_json(name: str) -> dict:
    path = PROC / name
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run src/data/merge.py first."
        )
    return json.loads(path.read_text())


def main() -> None:
    if not NEO4J_PASSWORD:
        raise EnvironmentError(
            "NEO4J_PASSWORD is not set. Add it to .env or export it."
        )

    companies_data = load_json("companies.json")
    persons_data   = load_json("persons.json")
    events_data    = load_json("events.json")
    edges_data     = load_json("edges.json")

    companies = companies_data["companies"]
    persons   = persons_data["persons"]
    events    = events_data["events"]

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        print("Applying schema constraints and indexes …")
        session.execute_write(apply_schema)

        print(f"Loading {len(companies)} Company nodes …")
        n = session.execute_write(load_companies, companies)
        print(f"  Merged {n} companies")

        print(f"Loading {len(persons)} Person nodes …")
        n = session.execute_write(load_persons, persons)
        print(f"  Merged {n} persons")

        print(f"Loading {len(events)} Event nodes …")
        n = session.execute_write(load_events, events)
        print(f"  Merged {n} events")

        cw = edges_data.get("competes_with", [])
        print(f"Loading {len(cw)} COMPETES_WITH edges …")
        n = session.execute_write(load_competes_with, cw)
        print(f"  Merged {n} edges")

        st = edges_data.get("supplies_to", [])
        print(f"Loading {len(st)} SUPPLIES_TO edges …")
        n = session.execute_write(load_supplies_to, st)
        print(f"  Merged {n} edges")

        eo = edges_data.get("executive_of", [])
        print(f"Loading {len(eo)} EXECUTIVE_OF edges …")
        n = session.execute_write(load_executive_of, eo)
        print(f"  Merged {n} edges")

        ab = edges_data.get("affected_by", [])
        print(f"Loading {len(ab)} AFFECTED_BY edges …")
        n = session.execute_write(load_affected_by, ab)
        print(f"  Merged {n} edges")

    driver.close()
    print("\nIngestion complete.")


if __name__ == "__main__":
    main()
