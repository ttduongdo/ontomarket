"""
Wikidata person pull for OntoMarket Phase 2.

Uses the MediaWiki wbgetentities API (not SPARQL) — more resilient during
WDQS outages. Two HTTP requests total:
  1. Fetch company entities → extract founder (P112) and CEO (P169) QIDs
  2. Fetch those person entities → resolve English labels

Output: data/raw/wikidata_persons.json
"""

import json
from datetime import date
from pathlib import Path

import requests

from wikidata_client import COMPANIES, QID_MAP

API_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "OntoMarket/0.1 (financial ontology research; contact: github.com/ontomarket)"

# Wikidata property IDs
P_FOUNDER = "P112"   # founded by (person)
P_CEO     = "P169"   # chief executive officer

OUTPUT_PATH = Path(__file__).parents[2] / "data" / "raw" / "wikidata_persons.json"

ROLE_LABEL = {P_FOUNDER: "founder", P_CEO: "ceo"}


def wbgetentities(qids: list[str], props: str = "claims") -> dict:
    resp = requests.get(
        API_URL,
        params={
            "action": "wbgetentities",
            "ids": "|".join(qids),
            "props": props,
            "languages": "en",
            "format": "json",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["entities"]


def extract_person_qids(entities: dict) -> dict[str, list[tuple[str, str]]]:
    """Returns {person_qid: [(company_ticker, role_type), ...]}"""
    person_roles: dict[str, list[tuple[str, str]]] = {}

    for company_qid, entity in entities.items():
        ticker, _ = QID_MAP.get(company_qid, ("UNKNOWN", ""))
        claims = entity.get("claims", {})

        for prop in (P_FOUNDER, P_CEO):
            for claim in claims.get(prop, []):
                try:
                    person_qid = claim["mainsnak"]["datavalue"]["value"]["id"]
                except (KeyError, TypeError):
                    continue
                if person_qid not in person_roles:
                    person_roles[person_qid] = []
                role = ROLE_LABEL[prop]
                entry = (ticker, role)
                if entry not in person_roles[person_qid]:
                    person_roles[person_qid].append(entry)

    return person_roles


def resolve_labels(person_qids: list[str]) -> dict[str, str]:
    """Returns {person_qid: english_label}"""
    entities = wbgetentities(person_qids, props="labels")
    labels = {}
    for qid, entity in entities.items():
        en = entity.get("labels", {}).get("en", {})
        labels[qid] = en.get("value", qid)
    return labels


def main() -> None:
    company_qids = [qid for _, qid, _ in COMPANIES]

    print(f"Request 1/2 — fetching claims for {len(company_qids)} company entities …")
    company_entities = wbgetentities(company_qids)
    person_roles = extract_person_qids(company_entities)
    print(f"  Found {len(person_roles)} unique person QIDs.")

    print(f"Request 2/2 — resolving labels for {len(person_roles)} persons …")
    labels = resolve_labels(list(person_roles.keys()))

    records = sorted(
        [
            {
                "person_qid": qid,
                "name": labels.get(qid, qid),
                "roles": [
                    {"company_ticker": ticker, "role_type": role}
                    for ticker, role in roles
                ],
            }
            for qid, roles in person_roles.items()
        ],
        key=lambda p: p["name"],
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "_meta": {
            "source": "Wikidata wbgetentities API (https://www.wikidata.org/w/api.php)",
            "query_date": date.today().isoformat(),
            "generated_by": "src/data/wikidata_persons.py",
            "note": (
                "Founders (P112) and current CEOs (P169) only. "
                "EXECUTIVE_OF edges with start/end dates are hand-curated in "
                "data/raw/curated_edges.json — Wikidata position history is too "
                "patchy to rely on for recent moves."
            ),
        },
        "persons": records,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Wrote {len(records)} person records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
