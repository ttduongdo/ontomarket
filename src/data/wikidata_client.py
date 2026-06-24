"""
Wikidata company pull for OntoMarket Phase 2.

Uses the MediaWiki wbgetentities API (not SPARQL) — more resilient during
WDQS outages. One HTTP request for all 17 company entities.

Pulls per company:
  - founding date      (P571)
  - direct subsidiaries (P355)
  - industry classification (P452)

Output: data/raw/wikidata_companies.json
"""

import json
from datetime import date
from pathlib import Path

import requests

API_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "OntoMarket/0.1 (financial ontology research; contact: github.com/ontomarket)"

# ---------------------------------------------------------------------------
# Target companies: (ticker, Wikidata QID, display name)
# QIDs verified manually against Wikidata entity pages.
# ---------------------------------------------------------------------------
COMPANIES = [
    ("NVDA",  "Q182477",   "NVIDIA"),
    ("AMD",   "Q182059",   "Advanced Micro Devices"),
    ("INTC",  "Q248",      "Intel"),
    ("MSFT",  "Q2283",     "Microsoft"),
    ("GOOGL", "Q20800404", "Alphabet Inc."),
    ("AMZN",  "Q3884",     "Amazon"),
    ("META",  "Q380",      "Meta Platforms"),
    ("AAPL",  "Q312",      "Apple Inc."),
    ("PLTR",  "Q30259440", "Palantir Technologies"),
    ("SNOW",  "Q56027867", "Snowflake Inc."),
    ("CRM",   "Q607790",   "Salesforce"),
    ("NOW",   "Q7457432",  "ServiceNow"),
    ("ORCL",  "Q40147",    "Oracle Corporation"),
    ("NET",   "Q56001469", "Cloudflare"),
    ("MDB",   "Q17577905", "MongoDB"),
    ("ESTC",  "Q47009605", "Elastic NV"),
    ("AVGO",  "Q584301",   "Broadcom Inc."),
]

QID_MAP = {qid: (ticker, name) for ticker, qid, name in COMPANIES}

OUTPUT_PATH = Path(__file__).parents[2] / "data" / "raw" / "wikidata_companies.json"

P_FOUNDING_DATE = "P571"
P_SUBSIDIARY    = "P355"
P_INDUSTRY      = "P452"


def wbgetentities(qids: list[str]) -> dict:
    resp = requests.get(
        API_URL,
        params={
            "action": "wbgetentities",
            "ids": "|".join(qids),
            "props": "claims|labels",
            "languages": "en",
            "format": "json",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["entities"]


def _label(entity: dict) -> str:
    return entity.get("labels", {}).get("en", {}).get("value", "")


def _time_value(claim: dict) -> str | None:
    try:
        raw = claim["mainsnak"]["datavalue"]["value"]["time"]
        return raw.lstrip("+").split("T")[0]
    except (KeyError, TypeError):
        return None


def _item_qid(claim: dict) -> str | None:
    try:
        return claim["mainsnak"]["datavalue"]["value"]["id"]
    except (KeyError, TypeError):
        return None


def resolve_labels(qids: list[str]) -> dict[str, str]:
    if not qids:
        return {}
    entities = wbgetentities(qids)
    return {qid: _label(e) for qid, e in entities.items()}


def assemble_records(entities: dict) -> list[dict]:
    # Collect subsidiary QIDs so we can resolve their labels in one shot
    subsidiary_qids: set[str] = set()
    industry_qids: set[str] = set()

    raw: dict[str, dict] = {}
    for _, qid, _ in COMPANIES:
        entity = entities.get(qid, {})
        claims = entity.get("claims", {})

        founding_dates = set()
        for c in claims.get(P_FOUNDING_DATE, []):
            v = _time_value(c)
            if v:
                founding_dates.add(v)

        sub_qids = []
        for c in claims.get(P_SUBSIDIARY, []):
            q = _item_qid(c)
            if q:
                sub_qids.append(q)
                subsidiary_qids.add(q)

        ind_qids = []
        for c in claims.get(P_INDUSTRY, []):
            q = _item_qid(c)
            if q:
                ind_qids.append(q)
                industry_qids.add(q)

        raw[qid] = {
            "founding_dates": founding_dates,
            "subsidiary_qids": sub_qids,
            "industry_qids": ind_qids,
        }

    print(f"  Resolving labels for {len(subsidiary_qids)} subsidiaries and {len(industry_qids)} industries …")
    sub_labels = resolve_labels(list(subsidiary_qids))
    ind_labels = resolve_labels(list(industry_qids))

    records = []
    for _, qid, _ in COMPANIES:
        ticker, name = QID_MAP[qid]
        r = raw[qid]
        fd_list = sorted(r["founding_dates"])
        records.append({
            "ticker": ticker,
            "wikidata_qid": qid,
            "name": name,
            "founded_date": fd_list[0] if fd_list else None,
            "subsidiaries": sorted(sub_labels.get(q, q) for q in r["subsidiary_qids"]),
            "industry_classifications": sorted(ind_labels.get(q, q) for q in r["industry_qids"]),
        })
    return records


def main() -> None:
    company_qids = [qid for _, qid, _ in COMPANIES]

    print(f"Request 1 — fetching {len(company_qids)} company entities …")
    entities = wbgetentities(company_qids)

    print("Assembling records …")
    records = assemble_records(entities)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "_meta": {
            "source": "Wikidata wbgetentities API (https://www.wikidata.org/w/api.php)",
            "query_date": date.today().isoformat(),
            "generated_by": "src/data/wikidata_client.py",
            "note": (
                "Structural ground-truth only. Founding dates, subsidiaries, and "
                "industry classification pulled directly from Wikidata entity records. "
                "Executive moves, supply-chain links, and events are hand-curated separately."
            ),
        },
        "companies": records,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Wrote {len(records)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
