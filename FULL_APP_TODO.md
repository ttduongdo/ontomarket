# OntoMarket — Full App Roadmap
> From working MVP to a production-quality portfolio piece ready to demo live at Prometheux, Tacnode, Glean, and Neo4j.
>
> **Last audited against the repo: 2026-07-08.** Tracks A, B, and D are substantially further along than this doc previously showed — it hadn't been kept in sync with the working tree. Checkboxes below now reflect what's actually in the codebase.

---

## What's already built (don't redo)

- Ontology schema (6 entity types, 8 relationship types, schema doc, `Sector`/`Instrument`/`Metric` documented as "future" entities so the shape doesn't change when Track C ships)
- Wikidata pull for Company and Person nodes — **20 companies, 47 persons**
- Edges: **18 COMPETES_WITH, 14 SUPPLIES_TO, 23 EXECUTIVE_OF, 19 AFFECTED_BY**, **16 events**
- Neo4j graph with constraints, ingestion, and Cypher query templates (`src/graph/queries.py`, `src/graph/ingest.py`)
- ChromaDB vector baseline — **91 hand-written/generated snippets** + sentence-transformers (`src/search/embed.py`, `src/search/retriever.py`)
- Streamlit app (`app.py`, 600+ lines): preset dropdown **and freeform NL question box**, side-by-side vector/graph panels, animated Cytoscape.js traversal graph (bundled locally, no CDN), expandable "Cypher used" block, LLM-generated result explanation
- Schema validation and merge pipeline (`src/data/validate_schema.py`, `validate_schema_real.py`, `src/data/merge.py`)
- SEC Form 4 pipeline (`src/data/sec_form4.py`) — pulls executive filings from EDGAR
- LLM extraction pipeline (`src/data/llm_extractor.py` + batch variant) using Claude, with **confidence scoring already wired** (0.0–1.0 field, 0.7 threshold filter, source-based defaults)
- Entity resolution (`src/data/resolver.py`) — alias table mapping name variants to canonical tickers
- NL → Cypher translator (`src/query/nl_to_cypher.py`) — routes to closest preset or generates new Cypher, with fallback-to-preset on invalid query
- Result explainer (`src/query/explainer.py`) — 2–3 sentence plain-English explanation shown under results
- Eval harness (`src/eval/run_eval.py`, `scorer.py`, `data/eval/eval_set.json`) — benchmark runner comparing graph vs. vector on 5 scored questions, not in the original plan at all

---

## Eval infrastructure audit (2026-07-08)

Full read-only audit of everything eval-related in the repo. Details below feed Track G.

**What exists:**
- `src/eval/run_eval.py` — CLI runner. Loads `data/eval/eval_set.json`, runs each question against both Neo4j (`src/query/router.run`) and ChromaDB (`src/search/retriever.search`), times both, scores via `scorer.py`, prints a comparison table or JSON (`--json`). Isolates errors per backend instead of crashing the whole run.
- `src/eval/scorer.py` — pure functions, no I/O: `graph_entity_recall`, `graph_precision`, `vector_entity_recall`, `vector_chain_recall`, combined in `score_question()`. All string/substring matching (case-insensitive), not semantic.
- `data/eval/eval_set.json` — 5 hand-written questions (one per Cypher template in `queries.py`: `hero`, `exec_move_then_event`, `reverse_supply_exposure`, `competitor_events`, `supply_chain_map`), each with hop count, hop-chain description, `must_include_entities`, `expected_min_rows`, and a `vector_can_compose` flag with written rationale for why vector search should fail or succeed.
- No eval logic exists outside `src/eval/` (grepped for precision/recall/accuracy/ground_truth across `src/` and `app.py` — no hits elsewhere).
- No test files exist anywhere in the repo (no `pytest`/`unittest`).

**`curated_edges.json` cross-check** (the ground truth `eval_set.json` scores against): 16 events (all sourced), 17 `competes_with` pairs (4 marked `TODO: add analyst report`), 14 `supplies_to` edges (all sourced), 23 `executive_of` entries (several static CEO records marked `TODO: add source` — Pichai, Jassy, Zuckerberg, Cook — though the "verified cross-competitor moves" block that powers the hero query is fully sourced), 19 `affected_by` edges. **No `confidence` field anywhere in this file** — confidence only exists on the LLM-extractor output path, not on curated edges.

**Gaps identified:**
1. Only 5 questions, 1:1 with the 5 Cypher templates — no adversarial/negative cases, no held-out set.
2. `scorer.py`'s own metric functions are untested — no unit tests confirm they handle `None` values, duplicates, or empty inputs correctly. A bug here silently invalidates every benchmark number.
3. Pure string/substring matching risks false negatives (e.g. a snippet saying "Microsoft" instead of "MSFT" fails `vector_entity_recall`) — could be artificially inflating the graph's apparent advantage.
4. No persisted historical results — nothing writes benchmark runs to disk, so there's no way to track regression as Track A grows the dataset.
5. Confidence scoring isn't in the eval loop at all — if LLM-extracted edges get ingested later, eval can't distinguish a 1.0-confidence hand-curated hit from a shaky 0.7-confidence LLM guess.
6. Some `executive_of`/`competes_with` records backing the eval questions are unsourced (`TODO: add source`), which weakens the ground truth the eval is scored against.

---

## Track A — Data & Coverage (makes the demo richer)

### A1. Expand the company dataset
- [x] Company count now at 20 (started at ~17 target)
- [ ] Cross-reference tickers against a financial API (Alpha Vantage free tier or yfinance) to fill in any null `founded_date` values from Wikidata
- [ ] Pull additional COMPETES_WITH and SUPPLIES_TO edges from 10-K "Competition" and "Customers" sections (manual, SEC EDGAR full-text search)

### A2. SEC Form 4 pipeline (executive moves at scale)
- [x] `src/data/sec_form4.py` written — pulls Form 4 filings from SEC EDGAR
- [x] Parses officer name, transaction date, company → EXECUTIVE_OF edges
- [ ] Confirm hand-curated `executive_of` entries have been fully reconciled against Form 4 output (dedupe pass)

### A3. Add more events
- [x] 16 events now in the dataset (started at 4)
- [ ] Verify at least 2 events per major company cluster (Intel/AMD, MSFT/GOOGL/AAPL) — spot check, not yet confirmed
- [ ] Fill in remaining TODO source URLs in `curated_edges.json`

### A4. Expand vector snippets
- [x] Grown from 44 → 91 snippets (target 80–100 met)
- [ ] Confirm `src/search/embed.py` has been re-run against the current snippet set so the ChromaDB index isn't stale

---

## Track B — Extraction pipeline (makes the project technically deeper)

### B1. LLM-based extraction from news
- [x] `src/data/llm_extractor.py` written — takes text, outputs structured entities/relationships as JSON via Claude
- [x] Extracts companies, event type, impact, executive names
- [ ] Confirm a 20–30 article sample has actually been run and manually verified (batch variant exists — check it's been exercised, not just written)

### B2. Confidence scoring
- [x] `confidence` field present on extracted relationship records (0.0–1.0)
- [x] Threshold filter implemented (default 0.7) in `llm_extractor.py`
- [ ] Confirm rule-based defaults for SEC Form 4 (1.0) / Wikidata (0.95) sources are applied, not just the LLM self-reported path
- [ ] Surface confidence in the Streamlit result panel (not yet seen in `app.py`)

### B3. Entity resolution
- [x] `src/data/resolver.py` written with alias table (e.g. "Alphabet" → GOOGL)
- [ ] Confirm resolution is actually invoked in the ingestion path before writes, not just available as a utility

---

## Track C — Schema expansion (unlocks future queries)

### C1. Sector / Industry nodes
- [ ] Add `Sector` nodes and `BELONGS_TO` edges for all 17 companies
- [ ] Source from Wikidata P452 (industry) already pulled — just needs ingestion
- [ ] Unlocks benchmark query: "which other companies in the same sector as X?"

### C2. Instrument nodes
- [ ] Add stock `Instrument` nodes for the publicly traded companies (ticker → Instrument)
- [ ] Add `CORRELATES_WITH` edges using 90-day price correlation from yfinance
- [ ] Unlocks: "how did competitors' stock prices move after X's regulatory event?"

### C3. Metric edges
- [ ] Add `REPORTS` edges (Company → Metric) for revenue and P/E ratio from last 4 quarters
- [ ] Pull from Alpha Vantage or yfinance free tier
- [ ] Unlocks: "did revenue shift after the leadership change?"

---

## Track D — Query layer (makes the demo smarter)

### D1. NL → Cypher translator
- [x] `src/query/nl_to_cypher.py` written — routes freeform questions to Claude with the ontology schema as context
- [x] Routes to closest of the existing preset queries or generates new Cypher
- [x] Freeform input box added to the Streamlit app alongside the preset dropdown (`app.py` mode radio: Preset / Freeform)
- [x] Graceful fallback implemented: invalid Cypher falls back to closest preset with a warning shown in the UI

### D2. Query results explanation
- [x] `src/query/explainer.py` written — calls Claude for a 2–3 sentence plain-English explanation
- [x] Explanation shown below the results dataframe in the Streamlit app
- [ ] Confirm the explanation text explicitly frames "why graph wins" rather than just summarizing the result (worth a prompt check)

### D3. Add 3 more Cypher templates
- [ ] Sector benchmark: "which companies in the same sector as X should be benchmarked against it?" (requires C1)
- [ ] Metric shift: "did revenue change after the leadership event?" (requires C3)
- [ ] Correlation chain: "how did X's competitors' stock prices respond after X's event?" (requires C2)
- [ ] Blocked on Track C — none of C1/C2/C3 have shipped yet

---

## Track E — App quality (makes it demo-safe)

### E1. Reliability hardening
- [ ] Run the full demo flow (all 5 presets, both panels) 10+ times — log any crashes or empty results
- [ ] Add a connection health check on app startup: if Neo4j or ChromaDB is unreachable, show a clear error banner rather than crashing
- [ ] Cache Neo4j query results in `st.session_state` so re-runs don't re-query the graph

### E2. UI polish
- [ ] Add a "Why graph wins" callout box below each query result explaining the specific reasoning gap vector search hit
- [x] Show the Cypher query used (expandable code block) — `app.py` has "Cypher used" expander for both preset and generated queries
- [ ] Add company logos or ticker badges to the result table (simple dict lookup → emoji or colored badge)
- [ ] Dark/light mode compatibility check — app currently ships a fixed dark "obsidian" theme; verify it degrades acceptably or is forced regardless of system theme

### E3. Performance
- [ ] Profile `embed.py` — if sentence-transformers model load is slow on first run, move to a cached singleton loaded at app startup
- [ ] Add `@st.cache_data(ttl=300)` to graph query results so repeat questions are instant

---

## Track G — Eval hardening (makes the core claim trustworthy)

Findings from the 2026-07-08 audit above. This is the thesis-proving infrastructure — bugs here undermine the entire "graph beats vector" pitch, so it comes before more eval questions are added.

### G1. Unit test `scorer.py`
- [x] Wrote `tests/test_scorer.py` covering all four metric functions with synthetic inputs (no DB required)
- [x] Covered edge cases: empty `results`/`snippets`, empty `must_include`, `None` values in result cells, duplicate entities across rows, plus a `score_question` orchestrator test (deltas, `rows_ok`)
- [x] `pytest==9.1.1` already pinned in `requirements.txt`; 13/13 tests passing (`python -m pytest tests/test_scorer.py -v`)
- [ ] Re-confirm the run inside the project's own venv/pinned `pytest` version, not just system Python — first run used Anaconda's `pytest 7.4.0`

### G2. Matching quality
- [x] Decided substring-only matching was insufficient — confirmed real snippets use company names ("Nvidia", "Intel") while `must_include_entities` are tickers ("NVDA", "INTC"), so `vector_entity_recall`/`vector_chain_recall` were undercounting vector search's real performance
- [x] Added `TICKER_TO_ALIASES` reverse index + `aliases_for()` to `src/data/resolver.py`; added `_mentioned()` helper in `src/eval/scorer.py` used by both vector metrics (graph metrics untouched — Neo4j values are already canonical tickers, no aliasing gap there)
- [x] Updated/added `tests/test_scorer.py` cases for the new alias-aware behavior (16/16 passing)
- [x] Re-ran the live benchmark (`venv/bin/python -m src.eval.run_eval`)

**Result (post-alias-fix):**

| ID | Hops | G-recall | V-recall | V-chain | Δ recall |
|---|---|---|---|---|---|
| q-hero | 4 | 100% | 100% | 0% | +0% |
| q-exec-then-event | 3 | 33.3% | 66.7% | 0% | -33.4% |
| q-reverse-supply | 2 | 66.7% | 100% | 0% | -33.3% |
| q-competitor-events | 2 | 100% | 50% | 0% | +50% |
| q-supply-chain-map | 1 | 100% | 66.7% | 0% | +33.3% |
| **AVERAGE** | | **80.0%** | **76.7%** | **0.0%** | **+3.3%** |

Before the alias fix, `V-recall` was pinned at 0% everywhere (snippets say "Nvidia," must_include says "NVDA" — pure substring miss), making `recall_delta` look artificially huge (+100% on 3/5 questions) and the graph look unbeatable across the board. After the fix, entity-level recall is much closer between graph and vector (average delta only +3.3%, and vector actually *wins* on 2 of 5 questions on raw entity recall) — **but `vector_chain_recall` is 0% on every single question, including the 1-hop `supply_chain_map` case.** That's the real finding: individual entities are often scattered across separate snippets even for simple questions, and no snippet ever composes the full answer in one place. This is a *much better* demo narrative than the old inflated recall_delta — "vector can find the pieces but never assembles them" is true and falsifiable, whereas the old numbers were an artifact of a matching bug.

### G3. Historical tracking
- [x] Added `--save` flag to `run_eval.py` — writes a timestamped snapshot (per-question results + averages) to `data/eval/history/<UTC-timestamp>.json`
- [x] Added `src/eval/diff_history.py` — diffs two snapshots (`--latest-two` or explicit paths), prints per-question and average deltas for all 5 metrics
- [x] Verified end-to-end: ran twice with different `--top-k` values, diffed them — confirmed `top_k` materially affects `vector_entity_recall`/`recall_delta` (fewer snippets retrieved = lower vector recall), which is itself a useful thing to know before quoting any single benchmark number publicly. Test snapshots were deleted after verification; `data/eval/history/` starts empty and is created on first real `--save` run.

### G4. Ground truth cleanup
- [x] Filled in all 7 remaining `TODO: add source` entries in `curated_edges.json` (web-verified, real URLs, not fabricated):
  - `executive_of`: Pichai (GOOGL, blog.google), Jassy (AMZN, press.aboutamazon.com), Zuckerberg (META, meta.com/about/leadership), Cook (AAPL, apple.com/newsroom)
  - `competes_with`: NVDA-INTC (industry AI-accelerator market-share analysis), CRM-NOW (Gartner compare page), MDB-SNOW (Gartner compare page)
- [x] Bumped `_meta.last_updated` to 2026-07-09
- [x] **Found and fixed a stale-data bug while sourcing Tim Cook:** Apple's own newsroom shows Cook stepped down as CEO on 2026-04-20, succeeded by John Ternus — `curated_edges.json` still had Cook's `end_date: null` (i.e. claiming he's still CEO, months after he wasn't). Added `end_date: "2026-04-20"` to the Cook record and a new `john-ternus` CEO record. This matters because `AAPL` is a `must_include_entity` in the eval's `hero` question.
- [x] Re-ran `src/data/merge.py` then `src/graph/ingest.py` (idempotent, MERGE-based — safe to re-run) to propagate the fix into Neo4j. Persons went 47→48, EXECUTIVE_OF edges 23→24. Verified directly against live Neo4j: AAPL now correctly shows Tim Cook (end_date 2026-04-20) and John Ternus (start_date 2026-04-20, current CEO).
- [x] Confirms the eval's ground truth is now fully verifiable and current in the live graph

### G5. Expand eval coverage (only after G1–G2 land)
- [ ] Add negative/adversarial questions (expect low recall from both backends, or expect the graph to correctly return zero rows)
- [ ] Consider a held-out question not mapped 1:1 to an existing Cypher template, to test the NL→Cypher generation path specifically

---

## Track H — Actual GraphRAG (closes the retrieval → generation loop)

**Why this track exists:** as of 2026-07-09, this project is not actually GraphRAG — it's two parallel, non-interacting systems shown side by side. The graph path runs Cypher and returns rows; the vector path runs cosine similarity and returns snippets; `explainer.py` narrates the graph result in prose. Nothing retrieves from the graph *and* feeds it back into an LLM as grounding context for a synthesized answer, and nothing lets vector search seed a graph traversal. That's the core mechanic GraphRAG requires and it's currently missing. Discussed in full 2026-07-09 (design only, no code written yet).

### H1. Graph-grounded answer synthesis (the core piece)
- [x] Serialize the `triples` list into a numbered fact list (`[n] SRC —REL→ TGT`) inside `explain()` — this is the retrieval context
- [x] Extended `src/query/explainer.py` in place (not a separate synthesizer) — takes `triples` + rows, answers the question grounded in them; model updated stale `claude-sonnet-4-6` → `claude-opus-4-8`, `max_tokens` 256 → 600
- [x] System prompt instructs Claude to cite the supporting fact(s) per claim with `[n]` markers, use only the given facts, and end with the "why vector can't compose this" line
- [x] Render citations in the Streamlit UI: `[n]` markers in the answer + a "Citations" expander legend mapping each `[n]` to its edge ([app.py]), and the Cytoscape edge labels now carry the same `[n]` numbering so graph/answer/legend share one index. (True click-to-highlight across the iframe boundary deferred — see note below; the shared numbering gets ~90% of the value without a component rewrite.)
- [x] Explicit "insufficient evidence" path: empty `results` and empty `triples` both short-circuit `explain()` with honest messages rather than letting the LLM pad
- [x] **Verified end-to-end live** (Neo4j + Claude API, 2026-07-09). Hero query → 59 rows / 25 edges → answer with 8 distinct `[n]` citations, every one mapping to a real triple; "why vector can't compose" line present; both insufficient-evidence paths (empty results, rows-but-no-edges) fire correctly with no wasted LLM call. Open nuance: citations are *structurally* valid (all map to real edges) but per-clause *semantic* correctness of each `[n]` is only spot-checkable by hand — fine for the demo, worth a manual audit if rigor is needed later.
- [ ] *(deferred, optional)* True interactive click-`[n]`-→-highlight-edge requires rebuilding the Cytoscape graph as a bidirectional Streamlit custom component (JS↔Python events); it's currently an isolated `components.html` iframe with no message bridge. Out of scope for H1; shared numbering covers the demo need.

### H2. Vector-seeded graph traversal (the hybrid piece)
- [x] Picked **Pattern B (vector-as-entity-seeder)** — the more legitimately "GraphRAG" story, chosen over Pattern A despite smaller near-term accuracy gain at 20 companies (the LLM already extracts entities well from a hardcoded ticker list; B's win is architectural + demonstrable, not accuracy)
- [x] New `src/query/entity_seeder.py` — `seed_entities(question)` runs `retriever.search()`, pools snippet text + question, substring-matches the G2 alias table, resolves to canonical tickers. Deterministic, no LLM call, testable.
- [x] `tests/test_entity_seeder.py` — 2 tests (named company, alias resolution), passing under `venv/bin/python -m pytest`
- [x] `nl_to_cypher.translate()` takes optional `anchors=` and injects them into the user turn ("prefer these tickers when they fit" — a hint, not a constraint); stale model `claude-sonnet-4-6` → `claude-sonnet-5`
- [x] Wired into `app.py` freeform path: seed → show seeded entities as a caption (makes the retrieve step visible in the demo) → `translate(anchors=...)`
- [x] **Verified live end-to-end.** "Microsoft" question → anchors `[MSFT,GOOGL,INTC,AAPL]` → generated Cypher targets `{ticker:'MSFT'}` combining SUPPLIES_TO + COMPETES_WITH; alias "Google" correctly seeds GOOGL. Verification caught a real bug: `content[0].text` crashed under Sonnet 5's default-on adaptive thinking (`content[0]` is a ThinkingBlock) — fixed in `nl_to_cypher.py` AND preemptively in `explainer.py` (same latent pattern, currently safe only because it's on Opus 4.8 with thinking off).
- [x] Env note resolved: `pytest` installed into `venv/` (was missing); tests that import `retriever`/`sentence_transformers` MUST run under `venv/bin/python`, not system Anaconda (broken `protobuf`/`transformers`).
- [ ] *(known tuning nuance, not a bug)* Seeder over-seeds — pools competitor snippets so "Google" also anchors AMZN/MSFT/INTC/AAPL. Harmless for hint-based seeding; tighten by pooling fewer snippets or weighting question-text matches if it ever causes bad Cypher.

### H3. Lower priority / probably out of scope given dataset size
- [ ] Community/entity summarization layer (Microsoft GraphRAG sense) — precomputed cluster summaries retrieved for broad questions; likely not worth it at 20 companies, more relevant at scale
- [ ] Iterative multi-hop retrieval (retrieve → realize another hop is needed → retrieve again)
- [ ] Reranking retrieved context before synthesis

**Sequencing note:** H1 alone (no H2) already changes the demo narrative materially — from "graph finds things vector can't" to "graph doesn't just find things, it answers your question and shows exactly which facts it used, verifiably." That's a stronger pitch for Prometheux/Glean/Neo4j specifically, whose audiences care about groundedness as much as recall. Consider landing H1 before F2/F3 (results doc, company framing) so those docs describe the system this track produces, not the pre-synthesis version.

---

## Track F — Docs & positioning (makes it shareable)

### F1. Complete README.md
- [x] Running instructions filled in (venv, secrets, merge → ingest → embed → streamlit, benchmark, tests) — includes the venv-vs-Anaconda protobuf gotcha
- [x] Mermaid data-flow diagram added (raw → processed → Neo4j/ChromaDB → retrieve → traverse → synthesize → UI)
- [x] Results table written from **real** benchmark numbers (the run_eval output captured during G/H work), 5 rows, with the "V-chain 0% everywhere" headline finding called out
- [x] Thesis + stack updated to reflect GraphRAG synthesis: added Claude API + Cytoscape, "local Docker" → "Aura", dropped stale NetworkX/Plotly; dataset table shows real counts (20/48/16/75 edges/91 snippets)
- [ ] Results table is a **snapshot** — re-running the benchmark with a different `top_k` will shift the numbers; update the table if that happens

### F2. Results doc
- [x] Wrote `docs/results.md` with 3 worked examples (hero 4-hop, reverse-supply 2-hop, competitor-scan 2-hop)
- [x] Each: question → real vector snippets (with sim scores) → real graph triples → the actual synthesized cited answer → "why graph wins". **All output verbatim from live runs** (Neo4j + ChromaDB + Claude), not illustrative — generated via a scratchpad script that ran the real pipeline.
- [x] Linked from README (Results section)
- [ ] Snapshot caveat (same as F1): the quoted rows/answers reflect the 2026-07 dataset; regenerate if the graph changes materially.

### F3. Company-specific framing
- [ ] Write 4 short positioning blurbs (not in the repo — use when reaching out):
  - [ ] **Prometheux:** ontology beats vector for multi-hop financial reasoning; direct parallel to their Sella retail case, applied to finance
  - [ ] **Tacnode:** real-time graph freshness — stock prices and executive moves change constantly; multi-agent Decision Coherence applied to financial data
  - [ ] **Glean:** personal/enterprise knowledge graph for financial research teams; same Personal Knowledge Graph narrative in a finance vertical
  - [ ] **Neo4j:** raw graph modeling depth — Cypher traversals, schema design, constraint enforcement; built on their product for a real use case

### F4. Deployment
- [x] Secrets template ready for Streamlit Cloud (`.streamlit/secrets.toml.example` — 4 keys, matches what code reads)
- [x] **Fixed a real deploy blocker:** `requirements.txt` (a 359-line freeze) was MISSING `neo4j`, `chromadb`, and `sentence-transformers` — the app ran locally (venv had them) but a fresh Streamlit Cloud deploy would crash on `import neo4j`. Added `neo4j==6.2.0`, `chromadb==1.5.9`, `sentence-transformers==5.6.0`.
- [x] Confirmed ChromaDB is deploy-safe: `chroma_db/` gitignored but `retriever.py` auto-rebuilds from the committed `vector_snippets.json` on first run. Vector search needs no external infra.
- [x] Wrote a "Deploying" section in README (provision Neo4j → seed via ingest → set secrets → deploy, + the asleep-graph and manual-seed gotchas)
- [x] **Backend decision:** Neo4j Aura Free is expiring — chose to KEEP Neo4j and self-host free (Fly.io always-on preferred over sleep-prone Render/Railway) rather than swap to Kuzu/NetworkX. Zero code changes; preserves the "real Cypher over Neo4j" thesis + resume bullet.
- [ ] **Yours (can't automate):** provision the replacement Neo4j Community instance, run `src/graph/ingest.py` against it to seed the 20/48/75 graph, set `NEO4J_URI`+creds in Streamlit Cloud Secrets, wake/redeploy the app, verify a live query end-to-end before sharing the link.

### F5. Demo video
- [ ] Record a 90-second walkthrough: thesis → hero query → graph result vs. vector result → traversal subgraph
- [ ] Upload to YouTube (unlisted) or Loom
- [ ] Embed link in README as a fallback in case live demo has issues

---

## Track I — Migration off Streamlit (decided 2026-07-14)

**Why:** Streamlit Cloud deploys were chronically fragile (macOS freeze poisoning, Python-version roulette, torch/torchvision breakage, sleep + cold-start re-downloads), and the approved graph-first redesign (full-bleed canvas globe, ⌘K spotlight, dim-to-traversal, scroll-emerge answer sheet) outgrows what Streamlit can render at all. Interactive mockup of the target design: https://claude.ai/code/artifact/a1b72823-8bd2-4e82-bca2-5a1acc70b077 (built with the real 84-node/75-edge graph; elastic node drag, click-to-focus neighborhood, clickable relationship legend, all 5 presets wired with verified answers).

**Decided stack:** FastAPI backend + React front-end (Vite recommended over Next — SPA, no SSR need, static build). `src/` stays UNTOUCHED — all verified H1/H2 logic (router, nl_to_cypher, explainer, entity_seeder, retriever) wraps behind ~4 endpoints.

### I1. FastAPI layer — DONE 2026-07-14, live-verified
- [x] `api/main.py`: `GET /graph` (84 nodes/75 edges from data/processed — renders even if Neo4j is down), `GET /presets`, `POST /query`, `POST /vector`. src/ untouched; fastapi==0.139.2 + uvicorn==0.49.0 pinned.
- [x] CORS for Vite dev (:5173) only, with a comment to tighten at deploy — /query spends Anthropic credits
- [x] Warm-up in FastAPI lifespan (model + Chroma at boot). **Note:** uvicorn doesn't accept connections until lifespan completes (~20s+) — Docker healthcheck must allow for this.
- [x] Live-verified: preset hero → 59 rows / 25 triples / cited answer, all citations valid. Freeform → anchors seeded (7 tickers), valid targeted Cypher generated, 4 rows returned, insufficient-evidence guard fired correctly.
### I1b. Freeform triples gap (deferred — building I2 first)
- [ ] Freeform-generated Cypher returns rows but often **0 triples**: `router._infer_triples()` only recognizes the 5 preset queries' column names, so novel column aliases → no triples → no cited answer + nothing to highlight on the globe. (The insufficient-evidence guard fires correctly, but a freeform query that "works" still lights up nothing.)
- [ ] Fix options: (a) teach `translate()` to emit a column→triple mapping alongside the generated Cypher, or (b) generalize `_infer_triples` to detect (source, target) node columns heuristically. (a) is more reliable.
- [ ] **Sequencing:** front-end (I2) is being built first against **preset** queries, which return triples fine. This gap only bites the freeform path — so the globe's dim-to-traversal is fully demoable on presets while this is open. Resolve before freeform is promoted as a headline feature.

### I2. React front-end (Vite) — DONE 2026-07-14 (globe checkpoint passed, full stack live-verified)
- [x] `web/` = Vite + React + TS. Files: `api.ts` (typed client, `/api/*` via dev proxy), `Graph.tsx` (canvas force-sim in a rAF loop against refs — never React state), `Spotlight.tsx`, `AnswerSheet.tsx`, `App.tsx` (lifecycle + highlight state), `index.css`.
- [x] Globe ported: force sim, pan/zoom/pinch, elastic node drag+snapback, click-to-focus neighborhood, clickable relationship legend. **User confirmed globe feel passes.**
- [x] Spotlight (⌘K): preset list + freeform (a no-match query becomes an "Ask freeform" NL→Cypher option); ↑↓/⏎/esc keyboard nav.
- [x] Dim-to-traversal wired to real `triples`: App maps triple rel-names (incl. suffixed `EXECUTIVE_OF (former)`) back to edge codes to light the exact path. Highlight precedence: query result > node focus > legend filter.
- [x] Scroll-emerge answer sheet: serif cited answer (coral `[n]` superscripts), retrieved-entities line, vector column (parallel `/vector` call fills as it returns) + cited-triples column. Scroll-to-top dismisses back to graph.
- [x] Loading choreography: staged copy (retrieving → traversing → synthesizing) on a spinner toast while the single `/query` request runs; error state clickable to dismiss. Vector search fires in parallel.
- [x] Live-verified through the Vite proxy: hero preset → 59 rows / 25 triples / cited answer, all citations map to triples, rel-types match the highlight matcher. Build (`npm run build`) passes clean. `.gitignore` covers `web/node_modules` + `web/dist`.
- [ ] Not browser-tested by me (no browser in the loop) — user should click through: run a preset, watch dim-to-traversal, scroll the answer sheet, try freeform (highlighting limited per I1b).

### I3. Deploy
- [ ] One Docker container (FastAPI serves the built static front-end) on HF Spaces (16GB free, local HF model cache kills the cold-start download) — or split: front-end on Vercel, API on Spaces/Fly
- [ ] Neo4j backend still required (Track F4 decision: self-hosted Community, Fly.io preferred)
- [ ] Retire `app.py` + Streamlit Cloud app once the new deploy passes the same live checks (hero query end-to-end with citations)

---

## Priority order (what to do next)

Tracks A, B, and D are functionally done. What's left is documentation, hardening, and the schema-expansion track that unlocks new query types. Revised order:

Track G (G1–G4: unit tests, matching-quality fix, historical tracking, ground-truth cleanup) is complete as of 2026-07-09.

1. **H1 Graph-grounded answer synthesis** — this is the single highest-leverage change left: it's the difference between "a graph demo" and an actual GraphRAG project, which is the stated goal. Worth doing before F1/F2/F3 so the docs describe the system this produces, not the pre-synthesis version.
2. **F1 README** — still has two placeholder sections; async reviewers see this first. Write/update after H1 so it accurately describes the synthesis + citation flow.
3. **E1 Reliability hardening** — no evidence of a startup health check or repeated demo-flow soak test; must be stable before any live demo
4. **F4 Deployment verification** — secrets template exists but actual live deployment is unconfirmed; commit says "deploy updates" — check if there's a working URL
5. **H2 Vector-seeded graph traversal** — bigger lift than H1, decide on the fallback-context vs. entity-seeder pattern before starting
6. **C1 Sector nodes** — unlocks a new query type with minimal effort (Wikidata P452 industry data already pulled per the schema doc)
7. **E2/E3 UI polish + perf** — confidence surfacing in the result panel, cache decorators, badges
8. **F2 Results doc + F3 Company framing** — write after H1 lands so worked examples show synthesized, cited answers, not just side-by-side rows/snippets
9. **F5 Demo video** — record last, after everything else is stable
10. **C2/C3 + D3, H3** — Instrument/Metric nodes, dependent Cypher templates, community summarization/reranking; lowest priority, biggest lift

---

## Resume bullet (update as tracks complete)

**OntoMarket — GraphRAG for multi-hop financial reasoning** | Python · Neo4j · Cypher · Claude API · ChromaDB · Streamlit

- Built a **GraphRAG system** that answers relational financial questions by retrieving entities via vector search, traversing a Neo4j knowledge graph, and synthesizing grounded natural-language answers where **every claim cites the specific graph edge** that supports it — verifiable reasoning, not plausible-sounding prose
- Designed a financial ontology (6 entity types, 8 relationship types) over 20 AI-infrastructure companies with verified executive moves, supply-chain links, and regulatory events sourced from SEC filings and Wikidata; ingestion, constraints, and Cypher traversals in Neo4j
- Implemented a natural-language→Cypher layer seeded by vector-retrieved entities (retrieve-then-traverse), with graceful fallback to preset queries on invalid generation
- Built an eval harness benchmarking graph vs. vector retrieval; showed vector search **never composes the multi-hop chain** (0% chain recall across every benchmark question) even when it surfaces the individual facts — quantifying why graph reasoning wins on relational questions
- *(supporting)* LLM extraction pipeline (Claude) converting unstructured news into structured edges with confidence scoring and entity resolution

<!-- Notes: lead with GraphRAG + citations (strongest, most current framing; the buzzword Prometheux/Glean screen for). "0% chain recall" is the real benchmark number — true for the 5-question eval set, so say "every benchmark question" not "thousands". If cutting to 4 bullets, drop the (supporting) extraction line first. -->oloo

**Blurb (one-liner):** GraphRAG over a financial ontology — vector search retrieves the entities, Neo4j Cypher traversals compose the multi-hop chain, and Claude writes a grounded answer citing the exact edges. Pure vector search never composes the chain (0% chain recall); the graph does.

## Pipeline
question
  → retriever.search(question)          # you have this
  → extract entity mentions from snippet text + tags
  → resolver.resolve() each mention     # you have this (+ aliases_for from G2)
  → set of anchor tickers
  → pass anchors into nl_to_cypher.translate(question, anchors=...)
  → LLM generates Cypher seeded with confirmed entities
