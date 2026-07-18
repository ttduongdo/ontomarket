"""
OntoMarket API — FastAPI layer for the graph-first front-end.

Wraps the existing (verified) src/ modules unchanged:
  GET  /graph    — all nodes + edges for the landing globe (from data/processed)
  GET  /presets  — the 5 preset queries (key, label, description, question)
  POST /query    — preset key OR freeform question → results, triples, cited answer
  POST /vector   — top-K vector snippets for the side-by-side comparison

Run locally:
  venv/bin/python -m uvicorn api.main:app --reload --port 8000
"""

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from src.query.router import run, run_raw, query_labels  # noqa: E402
from src.graph.queries import QUERIES  # noqa: E402

# Human-readable question per preset (used for vector search + the answer prompt).
PRESET_QUESTIONS = {
    "hero": (
        "Which companies face supply chain exposure given Intel's regulatory "
        "restructuring and executive moves to competitors?"
    ),
    "exec_move_then_event": (
        "An executive left a company and joined a competitor — "
        "has that competitor had a notable event since the move?"
    ),
    "reverse_supply_exposure": (
        "If a company faces a regulatory action, which suppliers "
        "face downstream exposure?"
    ),
    "competitor_events": (
        "What notable events have Intel's direct competitors had recently?"
    ),
    "supply_chain_map": (
        "Which companies supply AI chips and infrastructure to the major cloud providers?"
    ),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pay the vector-search cold start (model load + Chroma index) at boot,
    # not on the first request. Same warm-up the Streamlit app used.
    from src.search.retriever import search
    search("warmup", top_k=1)
    yield


app = FastAPI(title="OntoMarket API", lifespan=lifespan)

# CORS. Split hosting (Vercel front-end → Fly API) means cross-origin browser
# calls, so the front-end origin must be allow-listed. Dev origins are always
# permitted; add the deployed Vercel URL(s) via the CORS_ORIGINS env var
# (comma-separated) on the Fly machine. /query spends Anthropic credits, so
# this is an allowlist, never "*".
_dev_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_env_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_dev_origins + _env_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    preset_key: str | None = None
    question: str | None = None
    top_k: int = 5


class VectorRequest(BaseModel):
    question: str
    top_k: int = 5


# ---------------------------------------------------------------------------
# GET /graph — landing globe data (processed files, no DB dependency)
# ---------------------------------------------------------------------------

@app.get("/graph")
def get_graph():
    proc = ROOT / "data" / "processed"
    companies = json.loads((proc / "companies.json").read_text())["companies"]
    persons = json.loads((proc / "persons.json").read_text())["persons"]
    events = json.loads((proc / "events.json").read_text())["events"]
    edges_raw = json.loads((proc / "edges.json").read_text())

    nodes = (
        [{"id": c["ticker"], "label": c["ticker"], "full": c["name"], "t": "c"} for c in companies]
        + [{"id": p["person_id"], "label": p["name"], "full": p["name"], "t": "p"} for p in persons]
        + [{"id": e["event_id"], "label": e["event_id"].removeprefix("EVT-"),
            "full": e["description"][:120], "t": "e"} for e in events]
    )
    edges = (
        [{"s": e["company_a"], "t": e["company_b"], "r": "cw"} for e in edges_raw["competes_with"]]
        + [{"s": e["supplier"], "t": e["customer"], "r": "st"} for e in edges_raw["supplies_to"]]
        + [{"s": e["person_id"], "t": e["company_ticker"], "r": "eo"} for e in edges_raw["executive_of"]]
        + [{"s": e["event_id"], "t": e["company_ticker"], "r": "ab"} for e in edges_raw["affected_by"]]
    )
    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# GET /presets
# ---------------------------------------------------------------------------

@app.get("/presets")
def get_presets():
    labels = query_labels()
    return [
        {
            "key": key,
            "label": labels[key],
            "description": QUERIES[key]["description"].strip(),
            "question": PRESET_QUESTIONS.get(key, ""),
        }
        for key in labels
    ]


# ---------------------------------------------------------------------------
# POST /query — the full GraphRAG pipeline (same flow app.py ran)
# ---------------------------------------------------------------------------

@app.post("/query")
def post_query(req: QueryRequest):
    if not req.preset_key and not req.question:
        raise HTTPException(422, "Provide preset_key or question")

    question = req.question or PRESET_QUESTIONS.get(req.preset_key, "")
    query_key = req.preset_key
    cypher_used = None
    graph_label = f"Preset ({query_key})" if query_key else None
    fallback_used = False
    anchors: list[str] = []
    rationale = None

    # Freeform → retrieve entities, translate to Cypher
    if not query_key:
        from src.query.entity_seeder import seed_entities
        from src.query.nl_to_cypher import translate
        try:
            anchors = seed_entities(question)
            translation = translate(question, anchors=anchors)
            rationale = translation.rationale
            if translation.type == "preset" and translation.preset_key:
                query_key = translation.preset_key
                graph_label = f"Preset ({query_key})"
            elif translation.cypher:
                cypher_used = translation.cypher
                graph_label = "Freeform Cypher"
            else:
                query_key = translation.closest_preset
                graph_label = f"Fallback ({query_key})"
        except Exception as exc:
            raise HTTPException(502, f"Translation failed: {exc}") from exc

    # Traverse
    try:
        if cypher_used:
            try:
                results, triples = run_raw(cypher_used)
            except Exception:
                query_key = "hero"
                graph_label = "Fallback (hero) — generated Cypher failed"
                fallback_used = True
                results, triples = run(query_key)
        else:
            results, triples = run(query_key)
    except Exception as exc:
        raise HTTPException(503, f"Neo4j unavailable: {exc}") from exc

    # Synthesize the grounded, cited answer
    answer = None
    if results:
        from src.query.explainer import explain
        try:
            answer = explain(
                question=question,
                results=results,
                query_type=query_key or "freeform",
                triples=triples,
            )
        except Exception as exc:
            answer = None
            rationale = (rationale or "") + f" (answer synthesis failed: {exc})"

    if query_key and query_key in QUERIES and not cypher_used:
        cypher_used = QUERIES[query_key]["cypher"].strip()

    return {
        "question": question,
        "query_key": query_key,
        "graph_label": graph_label,
        "fallback_used": fallback_used,
        "anchors": anchors,
        "rationale": rationale,
        "cypher": cypher_used,
        "results": results,
        "triples": [list(t) for t in triples],
        "answer": answer,
    }


# ---------------------------------------------------------------------------
# POST /vector — the comparison baseline
# ---------------------------------------------------------------------------

@app.post("/vector")
def post_vector(req: VectorRequest):
    from src.search.retriever import search
    try:
        hits = search(req.question, top_k=req.top_k)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return [
        {"id": h.id, "text": h.text, "tags": h.tags, "similarity": h.similarity}
        for h in hits
    ]
