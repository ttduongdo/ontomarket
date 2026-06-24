"""
Schema validation for all OntoMarket raw data files.

Validates against docs/ontology_schema.md before merge/ingestion.

Checks:
  companies   — ticker, name, founded_date (format + null)
  persons     — person_id slug, name
  events      — event_id, date format, event_type enum, no TODOs
  edges       — cross-reference every ticker / person_id / event_id;
                flag TODO fields, bad dates, unknown references
"""

import json
import re
import sys
from pathlib import Path

RAW = Path(__file__).parents[2] / "data" / "raw"

DATE_RE    = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG_RE    = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
EVENT_TYPES = {"earnings_call", "merger", "lawsuit", "regulatory_filing", "leadership_change"}
IMPACTS     = {"positive", "negative", "neutral"}

_warnings = 0
_errors   = 0


def err(msg: str) -> None:
    global _errors
    _errors += 1
    print(f"  ✗  {msg}")


def warn(msg: str) -> None:
    global _warnings
    _warnings += 1
    print(f"  ⚠  {msg}")


def is_todo(v) -> bool:
    return isinstance(v, str) and v.strip().upper().startswith("TODO")


def load(path: Path) -> dict | None:
    if not path.exists():
        warn(f"{path.name} not found — skipping")
        return None
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

def validate_companies(data: dict) -> set[str]:
    print("\n── Companies ──────────────────────────────────────────────")
    records = data.get("companies", [])
    tickers: set[str] = set()
    clean = 0

    for r in records:
        ticker = r.get("ticker", "")
        name   = r.get("name", "")
        fd     = r.get("founded_date")
        ok = True

        if "error" in r:
            err(f"[{ticker or '?'}] fetch error: {r['error']}")
            ok = False
            continue

        if not ticker:
            err("[?] missing ticker")
            ok = False
        if not name:
            err(f"[{ticker}] missing name")
            ok = False

        if fd is None:
            warn(f"[{ticker}] founded_date is null")
            ok = False
        elif not DATE_RE.match(fd):
            err(f"[{ticker}] founded_date bad format: '{fd}'")
            ok = False

        if ok:
            clean += 1
        tickers.add(ticker)

    print(f"  {clean}/{len(records)} clean")
    return tickers


# ---------------------------------------------------------------------------
# Persons
# ---------------------------------------------------------------------------

def validate_persons(data: dict, known_tickers: set[str]) -> set[str]:
    print("\n── Persons (Wikidata) ─────────────────────────────────────")
    records = data.get("persons", [])
    person_ids: set[str] = set()
    clean = 0

    for p in records:
        qid  = p.get("person_qid", "")
        name = p.get("name", "")
        ok = True

        if not qid:
            err("[?] missing person_qid")
            ok = False
        if not name or name.startswith("Q"):
            err(f"[{qid}] name looks like an unresolved QID: '{name}'")
            ok = False

        for role in p.get("roles", []):
            t = role.get("company_ticker", "")
            if t not in known_tickers:
                warn(f"[{name}] role references unknown ticker '{t}'")

        if ok:
            clean += 1
            person_ids.add(qid)

    print(f"  {clean}/{len(records)} clean")
    return person_ids


# ---------------------------------------------------------------------------
# Events (from curated_edges.json)
# ---------------------------------------------------------------------------

def validate_events(curated: dict) -> set[str]:
    print("\n── Events ─────────────────────────────────────────────────")
    records = curated.get("events", [])
    event_ids: set[str] = set()
    clean = 0

    for e in records:
        eid   = e.get("event_id", "?")
        edate = e.get("event_date", "")
        etype = e.get("event_type", "")
        edesc = e.get("description", "")
        ok = True

        if is_todo(eid):
            warn(f"[{eid}] event_id is TODO — skipped")
            continue

        for field, val in [("event_date", edate), ("event_type", etype), ("description", edesc)]:
            if is_todo(val):
                err(f"[{eid}] {field} is TODO")
                ok = False

        if edate and not is_todo(edate) and not DATE_RE.match(edate):
            err(f"[{eid}] event_date bad format: '{edate}'")
            ok = False

        if etype and not is_todo(etype) and etype not in EVENT_TYPES:
            err(f"[{eid}] event_type '{etype}' not in enum {EVENT_TYPES}")
            ok = False

        if not edesc or len(edesc) < 10:
            warn(f"[{eid}] description is very short or missing")

        if ok:
            clean += 1
            event_ids.add(eid)

    print(f"  {clean}/{len(records)} clean")
    return event_ids


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------

def validate_competes_with(curated: dict, known_tickers: set[str]) -> None:
    print("\n── COMPETES_WITH ──────────────────────────────────────────")
    edges = curated.get("competes_with", [])
    clean = 0

    for e in edges:
        a = e.get("company_a", "")
        b = e.get("company_b", "")
        ok = True

        if is_todo(a) or is_todo(b):
            warn(f"Edge has TODO ticker — skipped")
            continue
        if a == b:
            err(f"Self-loop: '{a}' competes with itself")
            ok = False
        if a not in known_tickers:
            err(f"Unknown ticker company_a: '{a}'")
            ok = False
        if b not in known_tickers:
            err(f"Unknown ticker company_b: '{b}'")
            ok = False
        if ok:
            clean += 1

    print(f"  {clean}/{len(edges)} clean")


def validate_supplies_to(curated: dict, known_tickers: set[str]) -> None:
    print("\n── SUPPLIES_TO ────────────────────────────────────────────")
    edges = curated.get("supplies_to", [])
    clean = 0

    for e in edges:
        sup  = e.get("supplier", "")
        cust = e.get("customer", "")
        ok = True

        if is_todo(sup) or is_todo(cust):
            warn(f"Edge has TODO ticker — skipped")
            continue
        if sup == cust:
            err(f"Self-loop: '{sup}' supplies to itself")
            ok = False
        if sup not in known_tickers:
            err(f"Unknown ticker supplier: '{sup}'")
            ok = False
        if cust not in known_tickers:
            err(f"Unknown ticker customer: '{cust}'")
            ok = False
        if ok:
            clean += 1

    print(f"  {clean}/{len(edges)} clean")


def validate_executive_of(curated: dict, known_tickers: set[str]) -> set[str]:
    print("\n── EXECUTIVE_OF ───────────────────────────────────────────")
    edges = curated.get("executive_of", [])
    person_ids: set[str] = set()
    clean = 0

    for e in edges:
        if "_comment" in e:
            continue

        pid    = e.get("person_id", "")
        ticker = e.get("company_ticker", "")
        title  = e.get("title", "")
        sd     = e.get("start_date", "")
        ed     = e.get("end_date")
        ok = True

        if is_todo(pid):
            warn(f"person_id is TODO — skipped")
            continue

        if not SLUG_RE.match(pid):
            err(f"[{pid}] person_id is not a valid slug (lowercase-hyphenated)")
            ok = False

        for field, val in [("company_ticker", ticker), ("title", title), ("start_date", sd)]:
            if is_todo(val):
                err(f"[{pid}] {field} is TODO")
                ok = False

        if ticker and not is_todo(ticker) and ticker not in known_tickers:
            err(f"[{pid}] references unknown ticker '{ticker}'")
            ok = False

        if sd and not is_todo(sd) and not DATE_RE.match(sd):
            err(f"[{pid}@{ticker}] start_date bad format: '{sd}'")
            ok = False

        if ed and not is_todo(ed) and not DATE_RE.match(ed):
            err(f"[{pid}@{ticker}] end_date bad format: '{ed}'")
            ok = False

        if sd and ed and not is_todo(sd) and not is_todo(ed):
            if sd >= ed:
                err(f"[{pid}@{ticker}] start_date '{sd}' >= end_date '{ed}'")
                ok = False

        if ok:
            clean += 1
            person_ids.add(pid)

    print(f"  {clean}/{len([e for e in edges if '_comment' not in e])} clean")
    return person_ids


def validate_affected_by(curated: dict, known_tickers: set[str], known_events: set[str]) -> None:
    print("\n── AFFECTED_BY ────────────────────────────────────────────")
    edges = curated.get("affected_by", [])
    clean = 0

    for e in edges:
        ticker = e.get("company_ticker", "")
        eid    = e.get("event_id", "")
        impact = e.get("impact", "")
        ok = True

        if is_todo(ticker) or is_todo(eid):
            warn(f"Edge has TODO field — skipped")
            continue

        if ticker not in known_tickers:
            err(f"Unknown ticker '{ticker}'")
            ok = False
        if eid not in known_events:
            err(f"Unknown event_id '{eid}'")
            ok = False
        if impact not in IMPACTS:
            err(f"[{ticker}→{eid}] impact '{impact}' not in {IMPACTS}")
            ok = False
        if ok:
            clean += 1

    print(f"  {clean}/{len(edges)} clean")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    global _warnings, _errors
    _warnings = _errors = 0

    companies_data = load(RAW / "wikidata_companies.json")
    persons_data   = load(RAW / "wikidata_persons.json")
    curated        = load(RAW / "curated_edges.json")

    if not companies_data or not curated:
        print("Cannot proceed without companies and curated_edges. Run data pulls first.")
        sys.exit(1)

    known_tickers = validate_companies(companies_data)

    if persons_data:
        validate_persons(persons_data, known_tickers)

    known_events  = validate_events(curated)
    curated_persons = validate_executive_of(curated, known_tickers)

    validate_competes_with(curated, known_tickers)
    validate_supplies_to(curated, known_tickers)
    validate_affected_by(curated, known_tickers, known_events)

    print("\n" + "=" * 60)
    print(f"Errors:   {_errors}")
    print(f"Warnings: {_warnings}")

    if _errors:
        print("\nFix errors before running merge.py.")
        sys.exit(1)
    elif _warnings:
        print("\nWarnings are informational — merge.py can still run.")
    else:
        print("\nAll checks passed. Ready for merge.py.")


if __name__ == "__main__":
    main()
