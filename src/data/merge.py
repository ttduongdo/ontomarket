"""
Merges raw Wikidata pulls and curated_edges.json into schema-valid processed
files ready for Neo4j ingestion.

Inputs:
  data/raw/wikidata_companies.json
  data/raw/wikidata_persons.json   (optional — supplements Person nodes)
  data/raw/curated_edges.json

Outputs:
  data/processed/companies.json   Company nodes
  data/processed/persons.json     Person nodes
  data/processed/events.json      Event nodes
  data/processed/edges.json       All four relationship types
"""

import json
import re
import sys
from pathlib import Path

RAW  = Path(__file__).parents[2] / "data" / "raw"
PROC = Path(__file__).parents[2] / "data" / "processed"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load(path: Path) -> dict:
    if not path.exists():
        print(f"  [MISSING] {path}")
        sys.exit(1)
    return json.loads(path.read_text())


def is_todo(value) -> bool:
    return isinstance(value, str) and value.strip().upper().startswith("TODO")


def slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace(".", "")


def name_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def warn(msg: str) -> None:
    print(f"  ⚠  {msg}")


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

def build_companies(raw: dict) -> tuple[list[dict], set[str]]:
    records = []
    tickers = set()
    issues = 0

    for r in raw.get("companies", []):
        ticker = r.get("ticker", "")
        name   = r.get("name", "")
        fd     = r.get("founded_date")

        if not ticker or not name:
            warn(f"Company record missing ticker or name — skipped: {r}")
            issues += 1
            continue

        if fd is None:
            warn(f"{ticker}: founded_date is null — keeping record, flag for manual fill")
        elif not DATE_RE.match(fd):
            warn(f"{ticker}: founded_date '{fd}' bad format — setting null")
            fd = None

        records.append({"ticker": ticker, "name": name, "founded_date": fd})
        tickers.add(ticker)

    print(f"  Companies: {len(records)} records ({issues} skipped)")
    return records, tickers


# ---------------------------------------------------------------------------
# Persons
# ---------------------------------------------------------------------------

def build_persons(
    wikidata_raw: dict | None,
    exec_edges: list[dict],
    known_tickers: set[str],
) -> tuple[list[dict], set[str]]:
    persons: dict[str, str] = {}  # person_id → name

    # 1. Seed from curated executive_of entries (authoritative IDs)
    for edge in exec_edges:
        pid = edge.get("person_id", "")
        if not pid or is_todo(pid) or "_comment" in edge:
            continue
        if pid not in persons:
            persons[pid] = name_from_slug(pid)

    # 2. Supplement with Wikidata persons not already covered
    if wikidata_raw:
        for p in wikidata_raw.get("persons", []):
            name = p.get("name", "")
            if not name:
                continue
            pid = slugify(name)
            if pid not in persons:
                # Only include if they have a role at a known company
                roles = p.get("roles", [])
                if any(r.get("company_ticker") in known_tickers for r in roles):
                    persons[pid] = name

    records = [{"person_id": pid, "name": name} for pid, name in sorted(persons.items())]
    person_ids = set(persons.keys())
    print(f"  Persons: {len(records)} records")
    return records, person_ids


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def build_events(curated: dict) -> tuple[list[dict], set[str]]:
    records = []
    event_ids = set()
    skipped = 0

    for e in curated.get("events", []):
        if any(is_todo(v) for v in e.values()):
            warn(f"Event {e.get('event_id', '?')} has TODO fields — skipped")
            skipped += 1
            continue

        eid   = e["event_id"]
        edate = e["event_date"]
        etype = e["event_type"]
        edesc = e["description"]

        if not DATE_RE.match(edate):
            warn(f"Event {eid}: bad date '{edate}' — skipped")
            skipped += 1
            continue

        records.append({
            "event_id":   eid,
            "event_date": edate,
            "event_type": etype,
            "description": edesc,
        })
        event_ids.add(eid)

    print(f"  Events: {len(records)} records ({skipped} skipped)")
    return records, event_ids


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------

def build_edges(
    curated: dict,
    known_tickers: set[str],
    known_persons: set[str],
    known_events: set[str],
) -> dict:

    competes_with = []
    for e in curated.get("competes_with", []):
        a, b = e.get("company_a"), e.get("company_b")
        if is_todo(a) or is_todo(b):
            continue
        if a not in known_tickers:
            warn(f"COMPETES_WITH: unknown ticker '{a}' — skipped")
            continue
        if b not in known_tickers:
            warn(f"COMPETES_WITH: unknown ticker '{b}' — skipped")
            continue
        competes_with.append({"company_a": a, "company_b": b})

    supplies_to = []
    for e in curated.get("supplies_to", []):
        sup, cust = e.get("supplier"), e.get("customer")
        if is_todo(sup) or is_todo(cust):
            continue
        if sup not in known_tickers:
            warn(f"SUPPLIES_TO: unknown ticker '{sup}' — skipped")
            continue
        if cust not in known_tickers:
            warn(f"SUPPLIES_TO: unknown ticker '{cust}' — skipped")
            continue
        supplies_to.append({
            "supplier": sup,
            "customer": cust,
            "category": e.get("category", ""),
        })

    executive_of = []
    for e in curated.get("executive_of", []):
        if "_comment" in e:
            continue
        pid    = e.get("person_id")
        ticker = e.get("company_ticker")
        title  = e.get("title")
        sd     = e.get("start_date")
        ed     = e.get("end_date")

        if any(is_todo(v) for v in [pid, ticker, title, sd]):
            warn(f"EXECUTIVE_OF entry has TODO fields — skipped: {pid}")
            continue
        if pid not in known_persons:
            warn(f"EXECUTIVE_OF: unknown person_id '{pid}' — skipped")
            continue
        if ticker not in known_tickers:
            warn(f"EXECUTIVE_OF: unknown ticker '{ticker}' — skipped")
            continue
        if sd and not DATE_RE.match(sd):
            warn(f"EXECUTIVE_OF {pid}@{ticker}: bad start_date '{sd}' — skipped")
            continue
        if ed and not DATE_RE.match(ed):
            warn(f"EXECUTIVE_OF {pid}@{ticker}: bad end_date '{ed}' — setting null")
            ed = None

        executive_of.append({
            "person_id":      pid,
            "company_ticker": ticker,
            "title":          title,
            "start_date":     sd,
            "end_date":       ed,
        })

    affected_by = []
    for e in curated.get("affected_by", []):
        ticker = e.get("company_ticker")
        eid    = e.get("event_id")
        impact = e.get("impact")

        if is_todo(ticker) or is_todo(eid):
            continue
        if ticker not in known_tickers:
            warn(f"AFFECTED_BY: unknown ticker '{ticker}' — skipped")
            continue
        if eid not in known_events:
            warn(f"AFFECTED_BY: unknown event_id '{eid}' — skipped")
            continue

        affected_by.append({
            "company_ticker": ticker,
            "event_id":       eid,
            "impact":         impact,
        })

    print(f"  COMPETES_WITH: {len(competes_with)} edges")
    print(f"  SUPPLIES_TO:   {len(supplies_to)} edges")
    print(f"  EXECUTIVE_OF:  {len(executive_of)} edges")
    print(f"  AFFECTED_BY:   {len(affected_by)} edges")

    return {
        "competes_with": competes_with,
        "supplies_to":   supplies_to,
        "executive_of":  executive_of,
        "affected_by":   affected_by,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Loading raw data …")
    companies_raw = load(RAW / "wikidata_companies.json")
    curated       = load(RAW / "curated_edges.json")

    persons_raw_path = RAW / "wikidata_persons.json"
    persons_raw = json.loads(persons_raw_path.read_text()) if persons_raw_path.exists() else None
    if not persons_raw:
        print("  wikidata_persons.json not found — Person nodes from curated data only")

    PROC.mkdir(parents=True, exist_ok=True)

    print("\nBuilding Company nodes …")
    companies, known_tickers = build_companies(companies_raw)

    print("\nBuilding Event nodes …")
    events, known_events = build_events(curated)

    print("\nBuilding Person nodes …")
    exec_edges = curated.get("executive_of", [])
    persons, known_persons = build_persons(persons_raw, exec_edges, known_tickers)

    print("\nBuilding edges …")
    edges = build_edges(curated, known_tickers, known_persons, known_events)

    print("\nWriting processed files …")
    (PROC / "companies.json").write_text(json.dumps({"companies": companies}, indent=2))
    (PROC / "persons.json").write_text(json.dumps({"persons": persons}, indent=2))
    (PROC / "events.json").write_text(json.dumps({"events": events}, indent=2))
    (PROC / "edges.json").write_text(json.dumps(edges, indent=2))

    print(f"\nDone. Processed files written to {PROC}/")
    print(f"  companies.json  — {len(companies)} nodes")
    print(f"  persons.json    — {len(persons)} nodes")
    print(f"  events.json     — {len(events)} nodes")
    print(f"  edges.json      — "
          f"{sum(len(v) for v in edges.values())} edges across 4 relationship types")


if __name__ == "__main__":
    main()
