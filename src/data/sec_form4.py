"""
SEC Form 4 pipeline — extracts EXECUTIVE_OF edges from SEC EDGAR.

Pulls Form 4 (Statement of Changes in Beneficial Ownership) filings for
the 20 target companies and parses officer names, titles, and transaction
dates to supplement the hand-curated executive_of entries.

Output: data/raw/sec_form4_edges.json  (list of EXECUTIVE_OF edge dicts)

Usage:
  python -m src.data.sec_form4               # all tickers
  python -m src.data.sec_form4 NVDA AMD INTC  # specific tickers

SEC EDGAR full-text search API — no auth required, rate limit ~10 req/s.
"""

import json
import sys
import time
from pathlib import Path

import requests

OUTPUT_FILE = Path(__file__).parents[2] / "data" / "raw" / "sec_form4_edges.json"

# SEC EDGAR company search — maps ticker → CIK
EDGAR_COMPANY_URL   = "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt={start}&enddt={end}&forms=4"
EDGAR_TICKER_URL    = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
EDGAR_SEARCH_URL    = "https://efts.sec.gov/LATEST/search-index?q=%22{cik}%22&forms=4&dateRange=custom&startdt={start}&enddt={end}"
EDGAR_SUBMISSIONS   = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
EDGAR_TICKER_LOOKUP = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=4&dateb=&owner=include&count=10&search_text=&ticker={ticker}&output=atom"

# Central Index Keys (CIK) for our 20 tickers — hard-coded to avoid a lookup
# round-trip on every run. Source: https://www.sec.gov/cgi-bin/browse-edgar
TICKER_TO_CIK: dict[str, int] = {
    "NVDA": 1045810,
    "AMD":  2488,
    "INTC": 50863,
    "MSFT": 789019,
    "GOOGL": 1652044,
    "AMZN": 1018724,
    "META": 1326801,
    "AAPL": 320193,
    "PLTR": 1321655,
    "SNOW": 1640147,
    "CRM":  1108524,
    "NOW":  1373715,
    "ORCL": 1341439,
    "NET":  1477333,
    "MDB":  1492298,
    "ESTC": 1707092,
    "AVGO": 1054374,
    "TSM":  1046179,
    "QCOM": 804328,
    "WDAY": 1327811,
}

KNOWN_OFFICER_TYPES = {
    "chief executive officer", "ceo", "president", "cfo",
    "chief financial officer", "cto", "chief technology officer",
    "chief operating officer", "coo", "evp", "svp", "vp",
    "executive vice president", "senior vice president", "vice president",
    "general counsel", "chief marketing officer", "cmo",
    "chief product officer", "chief revenue officer",
}

HEADERS = {
    "User-Agent": "OntoMarket research project dothuyduong@example.com",
    "Accept": "application/json",
}

_RATE_DELAY = 0.15   # ~7 req/s — well under the 10 req/s limit


def _get(url: str) -> dict | list | None:
    time.sleep(_RATE_DELAY)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        print(f"  [WARN] GET failed: {url} — {exc}")
        return None


def _slugify(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def fetch_form4_filings(ticker: str, cik: int, start: str = "2020-01-01") -> list[dict]:
    """
    Fetch recent Form 4 filings for a company from SEC EDGAR submissions API.
    Returns a list of parsed executive edge dicts.
    """
    url = EDGAR_SUBMISSIONS.format(cik=cik)
    data = _get(url)
    if not data:
        return []

    filings = data.get("filings", {}).get("recent", {})
    forms   = filings.get("form", [])
    dates   = filings.get("filingDate", [])
    accessions = filings.get("accessionNumber", [])
    reporters  = filings.get("reportingOwner", []) if "reportingOwner" in filings else []

    edges = []
    for i, form in enumerate(forms):
        if form != "4":
            continue
        filing_date = dates[i] if i < len(dates) else None
        if filing_date and filing_date < start:
            continue

        # The submissions API doesn't include reporter details in the index.
        # For scale we'd parse individual XBRL files; for now we record the
        # filing metadata and return a stub that can be enriched later.
        edges.append({
            "ticker":       ticker,
            "cik":          cik,
            "form":         "4",
            "filing_date":  filing_date,
            "accession":    accessions[i] if i < len(accessions) else None,
            "source":       f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=10",
        })

    return edges


def run(tickers: list[str] | None = None, start: str = "2020-01-01") -> list[dict]:
    """
    Pull Form 4 filing metadata for all (or specified) tickers.

    Args:
        tickers: List of ticker strings, or None for all 20.
        start:   Earliest filing date to include (YYYY-MM-DD).

    Returns:
        List of filing metadata dicts saved to OUTPUT_FILE.
    """
    targets = {t: TICKER_TO_CIK[t] for t in (tickers or TICKER_TO_CIK) if t in TICKER_TO_CIK}
    all_filings = []

    for ticker, cik in targets.items():
        print(f"  {ticker} (CIK {cik}) …", end=" ", flush=True)
        filings = fetch_form4_filings(ticker, cik, start=start)
        all_filings.extend(filings)
        print(f"{len(filings)} filings")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(all_filings, indent=2))
    print(f"\nSaved {len(all_filings)} filing records → {OUTPUT_FILE}")
    return all_filings


if __name__ == "__main__":
    tickers = sys.argv[1:] or None
    print(f"Fetching Form 4 filings from SEC EDGAR (start=2020-01-01) …")
    run(tickers=tickers)
