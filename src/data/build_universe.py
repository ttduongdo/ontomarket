"""
Company universe builder (scaling workstream 1.1).

Replaces the hardcoded company lists in `wikidata_client.py` (17 ticker/QID
tuples) and `sec_form4.py` (TICKER_TO_CIK map) with a single committed,
version-controlled data file. Adding/removing companies becomes a data change,
not a code change.

Source: the S&P 500 constituents CSV (maintained, public, reliable) — carries
ticker, company name, GICS sector, GICS sub-industry, CIK, and founding year
in one file. We keep the tech + finance + communication-services slice
(~170 companies), which the GICS sector labels classify for us — no per-company
industry lookup needed.

Why not Wikidata SPARQL: WDQS is flaky and this repo deliberately avoids it
(see docs/logs.md). Why not brute-force-classify all 10k SEC filers: the SEC
company list has no industry field, so classifying it would mean ~10k Wikidata
calls. The index seed sidesteps both — its GICS sector IS the filter.

Output: data/raw/company_universe.json

Usage:
  python -m src.data.build_universe            # rebuild from the live CSV
  python -m src.data.build_universe --sectors "Information Technology,Financials"
"""

import argparse
import csv
import io
import json
import sys
from pathlib import Path

import requests

RAW = Path(__file__).parents[2] / "data" / "raw"
OUT = RAW / "company_universe.json"

# Maintained public S&P 500 constituents dataset (ticker, name, GICS sector,
# sub-industry, HQ, date added, CIK, founded).
SP500_CSV_URL = (
    "https://raw.githubusercontent.com/datasets/"
    "s-and-p-500-companies/main/data/constituents.csv"
)
USER_AGENT = "OntoMarket/0.2 (financial ontology research; contact via github.com/ontomarket)"

# GICS sectors we keep — tech + finance, plus Communication Services, which is
# where several relevant names live post-2018 GICS reshuffle (GOOGL, META,
# NFLX, telecoms). Communication Services straddles tech; include it so the
# tech story isn't missing its biggest players.
DEFAULT_SECTORS = {
    "Information Technology",
    "Financials",
    "Communication Services",
}


def fetch_sp500() -> list[dict]:
    """Download the S&P 500 constituents CSV and parse it into row dicts."""
    resp = requests.get(SP500_CSV_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return list(csv.DictReader(io.StringIO(resp.text)))


def build(sectors: set[str]) -> list[dict]:
    """Filter the S&P 500 to the target sectors and normalize into universe records."""
    rows = fetch_sp500()
    universe = []
    for r in rows:
        if r["GICS Sector"] not in sectors:
            continue
        cik_raw = (r.get("CIK") or "").strip()
        founded = (r.get("Founded") or "").strip()
        universe.append({
            "ticker": r["Symbol"].strip(),
            "name": r["Security"].strip(),
            # CIK zero-padding to the 10-digit form SEC APIs expect; None if absent.
            "cik": int(cik_raw) if cik_raw.isdigit() else None,
            "sector": r["GICS Sector"].strip(),
            "sub_industry": r["GICS Sub-Industry"].strip(),
            # Founded is sometimes a year, sometimes "1888 (1978)" style — keep raw.
            "founded": founded or None,
            "hq": (r.get("Headquarters Location") or "").strip() or None,
        })
    # Deterministic order (by ticker) so the committed file diffs cleanly.
    universe.sort(key=lambda c: c["ticker"])
    return universe


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the company universe file")
    parser.add_argument(
        "--sectors",
        default=",".join(sorted(DEFAULT_SECTORS)),
        help="Comma-separated GICS sectors to keep",
    )
    args = parser.parse_args()
    sectors = {s.strip() for s in args.sectors.split(",") if s.strip()}

    print(f"Fetching S&P 500 constituents; keeping sectors: {sorted(sectors)}")
    universe = build(sectors)

    RAW.mkdir(parents=True, exist_ok=True)
    payload = {
        "_meta": {
            "source": SP500_CSV_URL,
            "sectors": sorted(sectors),
            "count": len(universe),
            "note": "Committed company universe — regenerate with build_universe.py. "
                    "GICS sector is the classification of record; CIK feeds sec_form4.",
        },
        "companies": universe,
    }
    OUT.write_text(json.dumps(payload, indent=2))

    # Report distribution so a bad run is obvious.
    from collections import Counter
    by_sector = Counter(c["sector"] for c in universe)
    missing_cik = sum(1 for c in universe if c["cik"] is None)
    print(f"\nWrote {len(universe)} companies to {OUT.relative_to(Path(__file__).parents[2])}")
    for s, n in by_sector.most_common():
        print(f"  {n:3d}  {s}")
    if missing_cik:
        print(f"  ⚠  {missing_cik} companies missing a CIK (SEC pipeline will skip them)")


if __name__ == "__main__":
    main()
