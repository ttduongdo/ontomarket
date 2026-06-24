"""
Natural-language → Cypher translator for OntoMarket.

Given a freeform question, Claude either:
  (a) routes to the closest preset query key, or
  (b) generates a new Cypher string validated against the schema.

Returns a TranslationResult dataclass. The caller should try executing the
Cypher and fall back to closest_preset if it raises a ClientError.

Usage:
  from src.query.nl_to_cypher import translate
  result = translate("Who supplies chips to Microsoft?")
  # result.type == "preset" → use result.preset_key
  # result.type == "freeform" → use result.cypher
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# System prompt — ontology + all 5 templates
# ---------------------------------------------------------------------------

_SYSTEM = """You are a Cypher query generator for a Neo4j financial knowledge graph called OntoMarket.

## Schema

Node labels and key properties:
  Company  — ticker (unique), name, founded_date
  Person   — person_id (unique, slug), name
  Event    — event_id (unique), event_type, event_date, description

Relationship types:
  (Company)-[:COMPETES_WITH]-(Company)          — undirected
  (Company)-[:SUPPLIES_TO]->(Company)           — r.category, r.confidence
  (Company)-[:AFFECTED_BY]->(Event)             — r.impact, r.confidence
  (Person)-[:EXECUTIVE_OF]->(Company)           — r.title, r.start_date, r.end_date, r.confidence
  (Person)-[:FORMERLY_AT]->(Company)            — r.confidence

Known tickers: NVDA AMD INTC MSFT GOOGL AMZN META AAPL PLTR SNOW CRM NOW ORCL NET MDB ESTC AVGO

## Preset queries (prefer these over generating new Cypher)

KEY: hero
DESCRIPTION: Which companies face supply-chain exposure when a company has a regulatory event, given that an executive moved from it to a competitor?
CYPHER:
MATCH (evt:Event)<-[:AFFECTED_BY]-(x:Company)
MATCH (x)-[:COMPETES_WITH]-(y:Company)
MATCH (p:Person)-[e1:EXECUTIVE_OF]->(x)
MATCH (p)-[e2:EXECUTIVE_OF]->(y)
WHERE e1.end_date IS NOT NULL AND e2.start_date >= '2024-01-01' AND e2.end_date IS NULL
MATCH (z:Company)-[:SUPPLIES_TO]->(x)
RETURN x.ticker AS affected_company, evt.description AS event_description, y.ticker AS competitor, p.name AS executive, z.ticker AS exposed_supplier

KEY: exec_move_then_event
DESCRIPTION: An executive moved from Company A to a competitor — has that competitor had a notable event since?
CYPHER:
MATCH (p:Person)-[e1:EXECUTIVE_OF]->(a:Company)
MATCH (p)-[e2:EXECUTIVE_OF]->(b:Company)
MATCH (a)-[:COMPETES_WITH]-(b)
WHERE e1.end_date IS NOT NULL AND e2.start_date >= '2024-01-01' AND e2.end_date IS NULL
MATCH (b)-[:AFFECTED_BY]->(evt:Event)
WHERE evt.event_date >= e2.start_date
RETURN p.name AS executive, a.ticker AS former_company, b.ticker AS current_company, evt.description AS event_description

KEY: reverse_supply_exposure
DESCRIPTION: If a company faces a regulatory action or lawsuit, which of its suppliers face downstream exposure?
CYPHER:
MATCH (a:Company)-[:AFFECTED_BY]->(evt:Event)
WHERE evt.event_type IN ['regulatory_filing', 'lawsuit']
MATCH (supplier:Company)-[:SUPPLIES_TO]->(a)
RETURN a.ticker AS affected_company, evt.description AS event_description, supplier.ticker AS supplier

KEY: competitor_events
DESCRIPTION: What notable events have a specific company's direct competitors had?
CYPHER:
MATCH (focus:Company {ticker: 'INTC'})
MATCH (focus)-[:COMPETES_WITH]-(rival:Company)
MATCH (rival)-[:AFFECTED_BY]->(evt:Event)
RETURN rival.ticker AS rival, evt.event_type AS event_type, evt.description AS event_description

KEY: supply_chain_map
DESCRIPTION: Show all supply relationships in the graph — who supplies what to whom.
CYPHER:
MATCH (s:Company)-[r:SUPPLIES_TO]->(c:Company)
RETURN s.ticker AS supplier, c.ticker AS customer, r.category AS category

## Instructions

Given the user's question, respond with JSON only (no markdown, no explanation):

{
  "type": "preset" | "freeform",
  "preset_key": "<key from above> or null",
  "cypher": "<valid Cypher query> or null",
  "rationale": "<one sentence: why this mapping or query>",
  "closest_preset": "<key of the most relevant preset, always set>"
}

Rules:
- Prefer "preset" when the question clearly maps to one of the 5 templates above.
- Use "freeform" only when the question genuinely cannot be answered by any preset.
- For freeform: write minimal, correct Cypher using only the schema above.
- Always set closest_preset (used as fallback if the generated Cypher fails).
- Never use labels, properties, or relationship types not listed in the schema.
- Return ONLY the JSON object."""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class TranslationResult:
    type:            str          # "preset" | "freeform"
    preset_key:      str | None   # set when type == "preset"
    cypher:          str | None   # set when type == "freeform"
    rationale:       str
    closest_preset:  str          # always set — fallback key


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def translate(question: str) -> TranslationResult:
    """
    Translate a natural-language question into a Cypher query or preset key.

    Args:
        question: Freeform financial question about the graph.

    Returns:
        TranslationResult with type, preset_key or cypher, rationale, closest_preset.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set in .env")

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": question}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        end = -1 if lines[-1].strip() == "```" else len(lines)
        raw = "\n".join(lines[1:end]).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model returned non-JSON:\n{raw}") from exc

    return TranslationResult(
        type=data.get("type", "preset"),
        preset_key=data.get("preset_key"),
        cypher=data.get("cypher"),
        rationale=data.get("rationale", ""),
        closest_preset=data.get("closest_preset", "hero"),
    )
