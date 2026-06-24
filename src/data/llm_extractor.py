"""
LLM extraction pipeline — converts unstructured news text into structured
graph edges using the Claude API.

Outputs:
  - Return value: dict with companies, events, executive_moves, supply_relationships
  - data/raw/extracted_edges.json: appended on each run

Usage:
  python -m src.data.llm_extractor            # runs built-in sample text
  python -m src.data.llm_extractor path.txt   # reads text from file
"""

import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

from src.data.resolver import resolve_or_keep  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"
OUTPUT_FILE = Path(__file__).parents[2] / "data" / "raw" / "extracted_edges.json"

# ---------------------------------------------------------------------------
# System prompt — ontology schema + output contract
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a financial knowledge graph extraction engine.
Extract structured information from news text using the OntoMarket ontology.

## Entity types
- Company  — identified by stock ticker (e.g. NVDA, AMD, INTC, MSFT, GOOGL, AMZN, META, AAPL)
- Person   — named executive or individual
- Event    — a notable occurrence affecting a company

## Relationship types
- COMPETES_WITH      : Company ↔ Company
- SUPPLIES_TO        : Company → Company  (supplier to customer)
- AFFECTED_BY        : Company → Event
- EXECUTIVE_OF       : Person → Company  (current role)
- FORMERLY_AT        : Person → Company  (past role)

## Confidence guidelines
- 0.9–1.0  : directly and unambiguously stated in the text
- 0.7–0.89 : implied or contextually inferred
- < 0.7    : omit the item entirely

## Output format
Return ONLY a JSON object — no markdown fences, no explanation.

{
  "companies": [
    {
      "name": "<company name as mentioned>",
      "ticker": "<canonical ticker or null>",
      "role": "<brief role in the article>",
      "confidence": 0.95
    }
  ],
  "events": [
    {
      "id": "EVT-<short-slug>",
      "event_type": "<regulatory|financial|leadership|product|legal|merger_acquisition|other>",
      "description": "<one-sentence description>",
      "affected_company": "<ticker or company name>",
      "impact": "<positive|negative|neutral|unknown>",
      "date": "<YYYY-MM-DD or null>",
      "confidence": 0.85
    }
  ],
  "executive_moves": [
    {
      "person": "<full name>",
      "from_company": "<ticker or name or null>",
      "to_company": "<ticker or name>",
      "role": "<job title at destination>",
      "date": "<YYYY-MM-DD or null>",
      "confidence": 0.9
    }
  ],
  "supply_relationships": [
    {
      "supplier": "<ticker or company name>",
      "customer": "<ticker or company name>",
      "product": "<brief description of what is supplied>",
      "confidence": 0.85
    }
  ]
}

All four arrays must be present even if empty."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set in .env")
    return anthropic.Anthropic(api_key=api_key)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that some models add despite instructions."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (```json or ```) and last line (```) if present
        end = -1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])
    return text.strip()


def _resolve_companies(result: dict) -> dict:
    """Normalise all company names/tickers to canonical tickers via resolver."""
    for item in result.get("companies", []):
        if item.get("ticker"):
            item["ticker"] = resolve_or_keep(item["ticker"])

    for item in result.get("events", []):
        if item.get("affected_company"):
            item["affected_company"] = resolve_or_keep(item["affected_company"])

    for item in result.get("executive_moves", []):
        for field in ("from_company", "to_company"):
            if item.get(field):
                item[field] = resolve_or_keep(item[field])

    for item in result.get("supply_relationships", []):
        for field in ("supplier", "customer"):
            if item.get(field):
                item[field] = resolve_or_keep(item[field])

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract(text: str, *, threshold: float = 0.7) -> dict:
    """
    Extract structured graph entities and relationships from news text.

    Args:
        text:      News headline or short article.
        threshold: Minimum confidence to keep an extracted item (default 0.7).

    Returns:
        dict with keys: companies, events, executive_moves, supply_relationships
    """
    client = _make_client()

    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )

    raw = _strip_fences(message.content[0].text)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model returned non-JSON output:\n{raw}") from exc

    # Ensure all expected keys exist
    for key in ("companies", "events", "executive_moves", "supply_relationships"):
        result.setdefault(key, [])

    # Drop low-confidence items
    for key in ("companies", "events", "executive_moves", "supply_relationships"):
        result[key] = [
            item for item in result[key]
            if item.get("confidence", 0) >= threshold
        ]

    # Canonicalise company names
    result = _resolve_companies(result)

    return result


def save(result: dict, source_text: str = "") -> Path:
    """Append an extraction result to data/raw/extracted_edges.json."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing: list = []
    if OUTPUT_FILE.exists():
        try:
            existing = json.loads(OUTPUT_FILE.read_text())
        except json.JSONDecodeError:
            existing = []

    preview = source_text[:200] + ("…" if len(source_text) > 200 else "")
    existing.append({"source_text": preview, "extracted": result})

    OUTPUT_FILE.write_text(json.dumps(existing, indent=2))
    print(f"Saved → {OUTPUT_FILE}  ({len(existing)} total entries)")
    return OUTPUT_FILE


# ---------------------------------------------------------------------------
# Sample text for quick smoke-test
# ---------------------------------------------------------------------------

_SAMPLE = """
Intel announced today that its former Chief Technology Officer, Dr. Greg Bae,
has joined NVIDIA as VP of AI Infrastructure. The move comes weeks after Intel
faced a regulatory investigation by the FTC into alleged anti-competitive chip
pricing practices. Analysts noted that NVIDIA, which supplies AI accelerators to
Microsoft Azure and Amazon AWS, could benefit from Intel's talent exodus as it
continues to dominate the AI training chip market. AMD shares rose 2.3% on the
news as investors bet on further Intel data-centre market-share losses.
"""


if __name__ == "__main__":
    text = Path(sys.argv[1]).read_text() if len(sys.argv) > 1 else _SAMPLE

    print("Extracting …\n")
    result = extract(text)

    print(json.dumps(result, indent=2))
    print()
    save(result, source_text=text)
