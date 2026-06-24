# OntoMarket — Full App Roadmap
> From working MVP to a production-quality portfolio piece ready to demo live at Prometheux, Tacnode, Glean, and Neo4j.

---

## What the MVP already has (don't redo)

- Ontology schema (6 entity types, 8 relationship types, schema doc)
- Wikidata pull for Company and Person nodes
- Hand-curated edges: 3 verified executive moves, 7 supply edges, 11 competition edges, 4 events
- Neo4j graph with constraints, ingestion, and 5 Cypher query templates
- ChromaDB vector baseline with 44 hand-written snippets + sentence-transformers
- Streamlit app: preset dropdown, side-by-side panels, Plotly subgraph viz
- Schema validation and merge pipeline

---

## Track A — Data & Coverage (makes the demo richer)

### A1. Expand the company dataset
- [ ] Add 5–10 more companies in adjacent sectors (semiconductors, enterprise SaaS) to deepen the graph
- [ ] Cross-reference tickers against a financial API (Alpha Vantage free tier or yfinance) to fill in any null `founded_date` values from Wikidata
- [ ] Pull additional COMPETES_WITH and SUPPLIES_TO edges from 10-K "Competition" and "Customers" sections (manual, SEC EDGAR full-text search)

### A2. SEC Form 4 pipeline (executive moves at scale)
- [ ] Write `src/data/sec_form4.py` — pulls Form 4 filings from SEC EDGAR for the 17 target companies
- [ ] Parse officer name, transaction date, and company to extract EXECUTIVE_OF edges automatically
- [ ] Replace or supplement hand-curated `executive_of` entries with verified Form 4 data
- [ ] This replaces the biggest manual bottleneck in the current pipeline

### A3. Add more events
- [ ] Source 5–10 additional events (regulatory filings, mergers, lawsuits) across the dataset
- [ ] Aim for at least 2 events per major company cluster (Intel/AMD, MSFT/GOOGL/AAPL)
- [ ] Fill in remaining TODO source URLs in `curated_edges.json`

### A4. Expand vector snippets
- [ ] Grow from 44 → 80–100 snippets to cover new events and companies
- [ ] Re-run `src/search/embed.py` after additions to rebuild the ChromaDB index

---

## Track B — Extraction pipeline (makes the project technically deeper)

### B1. LLM-based extraction from news
- [ ] Write `src/data/llm_extractor.py` — takes a news headline or short article and outputs structured entities and relationships as JSON
- [ ] Use Claude API (claude-sonnet-4-6) with the ontology schema in the system prompt
- [ ] Extract: company names, event type, impact direction, any executive names mentioned
- [ ] Run on a 20–30 article sample and manually verify extraction quality
- [ ] This covers the "unstructured extraction" gap in Phase 3 of the extended plan

### B2. Confidence scoring
- [ ] Add a `confidence` field to extracted relationship records (0.0–1.0)
- [ ] Rule-based: SEC Form 4 = 1.0, Wikidata = 0.95, LLM-extracted = LLM self-reported confidence
- [ ] Filter edges below a threshold (e.g. 0.7) before ingestion
- [ ] Surface confidence in the Streamlit result panel

### B3. Entity resolution
- [ ] Write `src/data/resolver.py` — maps company name variants to canonical ticker
- [ ] Build a 20-row alias table (e.g. "Alphabet" → GOOGL, "Meta" → META, "Google" → GOOGL)
- [ ] Apply resolution before ingestion so name variants don't create duplicate nodes

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
- [ ] Write `src/query/nl_to_cypher.py` — takes a freeform question, sends it to Claude with the ontology schema as context, returns a Cypher query
- [ ] Start narrow: validate on the 5 existing query templates before allowing freeform
- [ ] Add a freeform input box to the Streamlit app alongside the preset dropdown
- [ ] Graceful fallback: if the LLM returns invalid Cypher, catch the error and suggest the closest preset

### D2. Query results explanation
- [ ] After each graph query, call Claude to generate a 2–3 sentence plain English explanation of the result
- [ ] Show explanation below the results dataframe in the Streamlit app
- [ ] This makes the "why graph wins" obvious without requiring the viewer to read Cypher

### D3. Add 3 more Cypher templates
- [ ] Sector benchmark: "which companies in the same sector as X should be benchmarked against it?" (requires C1)
- [ ] Metric shift: "did revenue change after the leadership event?" (requires C3)
- [ ] Correlation chain: "how did X's competitors' stock prices respond after X's event?" (requires C2)

---

## Track E — App quality (makes it demo-safe)

### E1. Reliability hardening
- [ ] Run the full demo flow (all 5 presets, both panels) 10+ times — log any crashes or empty results
- [ ] Add a connection health check on app startup: if Neo4j or ChromaDB is unreachable, show a clear error banner rather than crashing
- [ ] Cache Neo4j query results in `st.session_state` so re-runs don't re-query the graph

### E2. UI polish
- [ ] Add a "Why graph wins" callout box below each query result explaining the specific reasoning gap vector search hit
- [ ] Show the Cypher query used (expandable code block) so technical viewers can verify it
- [ ] Add company logos or ticker badges to the result table (simple dict lookup → emoji or colored badge)
- [ ] Dark/light mode compatibility check

### E3. Performance
- [ ] Profile `embed.py` — if sentence-transformers model load is slow on first run, move to a cached singleton loaded at app startup
- [ ] Add `@st.cache_data(ttl=300)` to graph query results so repeat questions are instant

---

## Track F — Docs & positioning (makes it shareable)

### F1. Complete README.md
- [ ] Fill in running instructions (Docker, venv, full pipeline steps)
- [ ] Add Mermaid architecture diagram (data flow: raw → processed → Neo4j/ChromaDB → Streamlit)
- [ ] Write results table: 5 rows, one per query — what vector returned, what graph returned, why graph wins
- [ ] This is the most important doc for async reviewers who won't run the demo live

### F2. Results doc
- [ ] Write `docs/results.md` with 3–4 concrete worked examples
- [ ] Each example: question → vector output (screenshot or quote) → graph output → explanation
- [ ] Link from README

### F3. Company-specific framing
- [ ] Write 4 short positioning blurbs (not in the repo — use when reaching out):
  - [ ] **Prometheux:** ontology beats vector for multi-hop financial reasoning; direct parallel to their Sella retail case, applied to finance
  - [ ] **Tacnode:** real-time graph freshness — stock prices and executive moves change constantly; multi-agent Decision Coherence applied to financial data
  - [ ] **Glean:** personal/enterprise knowledge graph for financial research teams; same Personal Knowledge Graph narrative in a finance vertical
  - [ ] **Neo4j:** raw graph modeling depth — Cypher traversals, schema design, constraint enforcement; built on their product for a real use case

### F4. Deployment
- [ ] Deploy to Streamlit Cloud (free tier, GitHub-connected, zero infra)
- [ ] Set Neo4j secrets in Streamlit Cloud environment variables
- [ ] Use Neo4j Aura free tier (500MB) as the cloud graph backend — switch `NEO4J_URI` in `.env`
- [ ] Test the deployed app end-to-end before sharing the link

### F5. Demo video
- [ ] Record a 90-second walkthrough: thesis → hero query → graph result vs. vector result → traversal subgraph
- [ ] Upload to YouTube (unlisted) or Loom
- [ ] Embed link in README as a fallback in case live demo has issues

---

## Priority order (what to do next)

1. **F1 README** — highest leverage per hour; async reviewers see this first
2. **E1 Reliability hardening** — must be stable before any live demo
3. **A3 More events + A4 More snippets** — makes the contrast more convincing
4. **B1 LLM extractor** — the biggest technical gap vs. the extended plan; adds a real extraction pipeline story
5. **D1 NL→Cypher** — turns hard-coded templates into a real query layer
6. **F4 Deployment** — makes it shareable with a link instead of "clone and run"
7. **C1 Sector nodes** — unlocks a new query type with minimal effort (data already pulled)
8. **F3 Company framing** — write before any outreach
9. **F5 Demo video** — record last, after everything else is stable

---

## Resume bullet (update as tracks complete)

**OntoMarket** | Python · Neo4j · Cypher · Claude API · ChromaDB · sentence-transformers · Streamlit

- Designed a financial ontology with 6 entity types and 8 relationship types; built a graph in Neo4j over 17 AI infrastructure companies with verified executive moves, supply-chain edges, and regulatory events sourced from SEC filings and Wikidata
- Built an LLM-based extraction pipeline (Claude API) converting unstructured news into structured graph edges with confidence scoring and entity resolution
- Demonstrated that multi-hop Cypher traversals answer relational financial questions (supply chain exposure given executive movement + competitor relationships) that pure vector search cannot compose correctly
