# MarketGraph — Financial Ontology Engine for Multi-Hop Reasoning
> Demonstrates ontology-augmented reasoning beating pure vector search on relational financial questions. Built to demo for companies working on knowledge graphs, ontologies, and agentic data infrastructure (Prometheux, Tacnode, Glean, Neo4j).

---

## The Core Thesis (what this project proves)

Vector search finds documents that *mention* related entities. Ontology reasoning *traverses relationships* between entities. Financial questions are inherently multi-hop ("which companies are exposed if X happens, given Y's executive history") — exactly where vector search breaks down and ontology reasoning shines.

**Target demo query:** *"Which companies are exposed to supply chain risk if Company X has a regulatory event, given executives who moved from X to its competitors in the last 2 years?"*

---

## Phase 1: Ontology Schema Design

- [ ] Define entity types
  - [ ] `Company` (ticker, name, sector, industry, founded_date)
  - [ ] `Person` (name, role history)
  - [ ] `Sector` / `Industry` (hierarchical: Industry → Sector → Sub-sector)
  - [ ] `Instrument` (stock, bond, derivative — type, underlying)
  - [ ] `Event` (earnings call, merger, lawsuit, regulatory filing, leadership change — date, type, description)
  - [ ] `Metric` (revenue, P/E ratio, debt-to-equity — time-series values)
- [ ] Define relationship types
  - [ ] `BELONGS_TO` (Company → Sector)
  - [ ] `COMPETES_WITH` (Company → Company, bidirectional)
  - [ ] `SUPPLIES_TO` / `CUSTOMER_OF` (Company → Company, directional)
  - [ ] `SUBSIDIARY_OF` (Company → Company)
  - [ ] `EXECUTIVE_OF` (Person → Company, with `start_date`, `end_date` properties)
  - [ ] `AFFECTED_BY` (Company → Event)
  - [ ] `REPORTS` (Company → Metric, time-series edge)
  - [ ] `CORRELATES_WITH` (Instrument → Instrument, with correlation coefficient property)
- [ ] Write ontology schema doc (`docs/ontology_schema.md`) with entity-relationship diagram
- [ ] Validate schema against 5-10 sample real-world scenarios before building extraction pipeline

---

## Phase 2: Data Collection

- [ ] **SEC EDGAR**
  - [ ] Pull 10-K and 8-K filings for ~50-100 companies (start with one sector, e.g. tech or consumer goods)
  - [ ] Extract executive disclosures (Form 4 filings) for leadership movement tracking
  - [ ] Extract subsidiary structures from filing exhibits
- [ ] **Wikidata**
  - [ ] Query Wikidata SPARQL endpoint for company relationships (subsidiaries, founders, mergers, sector classification)
  - [ ] This gives you clean, structured ground-truth relationships to bootstrap the graph
- [ ] **Financial APIs**
  - [ ] Alpha Vantage or Yahoo Finance for sector/industry classification, fundamentals, pricing history
  - [ ] Build a simple Python client (`src/data/market_api.py`)
- [ ] **News/Events**
  - [ ] NewsAPI or GDELT for company-related news (earnings, lawsuits, regulatory events)
  - [ ] Scope to last 2-3 years for the companies in your dataset
- [ ] Save all raw data to `data/raw/` with clear source attribution
- [ ] Write `data/README.md` documenting all sources and collection dates

---

## Phase 3: Entity & Relationship Extraction

- [ ] **Structured extraction** (from SEC/Wikidata — already structured, just need parsing)
  - [ ] Parse Wikidata SPARQL results into entity/relationship tuples
  - [ ] Parse SEC Form 4 filings for executive movement (regex + structured XML parsing)
  - [ ] Parse subsidiary structures from 10-K exhibits
- [ ] **Unstructured extraction** (from news — needs LLM)
  - [ ] Build an LLM-based extraction pipeline using prompt engineering to extract:
    - [ ] Companies mentioned and their role in the event (subject, affected party, competitor mentioned)
    - [ ] Event type classification (merger, lawsuit, regulatory, leadership change, earnings)
    - [ ] Sentiment/impact direction (positive, negative, neutral)
  - [ ] Validate extraction quality on a 50-document sample (manual spot check)
  - [ ] Build a confidence scoring system for extracted relationships (LLM self-reported confidence + rule-based validation)
- [ ] **Entity resolution / deduplication**
  - [ ] Match company name variants (e.g. "Apple Inc." vs "Apple" vs "AAPL") to canonical entities
  - [ ] Build a simple fuzzy-matching + ticker-lookup resolution function
- [ ] Save extracted entities/relationships to `data/processed/entities.json` and `relationships.json`

---

## Phase 4: Graph Construction

- [ ] Set up Neo4j (local Docker instance or Neo4j Aura free tier)
- [ ] Write Cypher schema constraints (unique constraints on Company ticker, Person name+company, etc.)
- [ ] Build ingestion pipeline (`src/graph/ingest.py`) loading entities and relationships into Neo4j
- [ ] Add time-bound properties on relationships where relevant (executive tenure dates, event dates)
- [ ] Build graph validation queries — check for orphaned nodes, duplicate relationships, schema violations
- [ ] Visualize the graph (Neo4j Bloom or simple NetworkX/Plotly visualization) for a sanity check

---

## Phase 5: Vector Search Baseline

- [ ] Embed all news articles and filing excerpts using OpenAI embeddings or a local model (sentence-transformers)
- [ ] Store embeddings in a vector store (pgvector, FAISS, or Chroma — pick lightweight option)
- [ ] Build a simple semantic search function (`src/search/vector_search.py`)
- [ ] This is your "control group" — what a pure RAG system would return for relational questions

---

## Phase 6: Ontology-Augmented Query Layer

- [ ] Build a natural language → Cypher query translator
  - [ ] Use an LLM with the ontology schema in context to translate questions into Cypher graph traversal queries
  - [ ] Start with a few hand-written Cypher templates for common multi-hop patterns, then generalize
- [ ] Build the **target demo query** end-to-end:
  - [ ] "Which companies are exposed to supply chain risk if Company X has a regulatory event, given executives who moved from X to its competitors in the last 2 years?"
  - [ ] Decompose into graph traversal: `Event(regulatory) → AFFECTED_BY → Company X → COMPETES_WITH → Company Y` AND `Person → EXECUTIVE_OF(X, past) → EXECUTIVE_OF(Y, current)` AND `Company X → SUPPLIES_TO → Company Z`
- [ ] Build 4-5 additional multi-hop demo queries covering different relationship chains
- [ ] Build a simple comparison harness running the same question through both vector search and ontology traversal, side by side

---

## Phase 7: The Demo Interface

- [ ] Build a simple Streamlit or FastAPI + minimal frontend interface
  - [ ] Input: natural language question
  - [ ] Output: side-by-side comparison — "Vector Search Result" vs "Ontology Reasoning Result"
  - [ ] Show the actual graph traversal path visually for the ontology answer (this is the "wow" moment)
- [ ] Pre-load 5 strong demo questions as one-click examples
- [ ] Add a graph visualization panel showing the relevant subgraph for the current query
- [ ] Make sure this runs reliably live — test the full demo flow 10+ times before any actual meeting

---

## Phase 8: Documentation & Company-Specific Framing

- [ ] **README.md** — project overview, architecture diagram, quickstart, the core thesis, key results
- [ ] **Architecture diagram** — data flow from raw sources → extraction → graph → query layer → demo
- [ ] **Results doc** (`docs/results.md`) — concrete examples of questions vector search got wrong/incomplete vs. ontology got right
- [ ] Write 3-4 short company-specific framing blurbs (don't put all in repo, use when reaching out):
  - [ ] **For Prometheux:** frame around "ontology beats vector search for multi-hop financial reasoning" — direct parallel to their own retail case study, applied to finance where they already have a customer (Sella)
  - [ ] **For Tacnode:** frame around real-time freshness — stock prices and company events change constantly; multiple agents querying the same graph need Decision Coherence
  - [ ] **For Glean:** frame as "personal/enterprise knowledge graph for financial research teams," same Personal Knowledge Graph narrative applied to a finance vertical
  - [ ] **For Neo4j:** lead with the raw graph modeling — show you understand Cypher and graph data modeling deeply, this is literally built on their product
- [ ] Deploy demo publicly if possible (Streamlit Cloud free tier, or a simple Render/Railway deployment)
- [ ] Record a 90-second demo video as backup in case live demo has issues during a real conversation

---

## Resume Bullet Draft (update after building)

**MarketGraph** | Python, Neo4j, Cypher, LLM Extraction, FAISS/pgvector, FastAPI/Streamlit

- Built a financial ontology engine modeling companies, executives, instruments, and market events as a knowledge graph in Neo4j; designed a schema with 6 entity types and 8 relationship types supporting time-bound, multi-hop relational queries
- Built an LLM-based entity and relationship extraction pipeline processing SEC filings, Wikidata, and financial news, with confidence scoring and entity resolution for deduplication across data sources
- Built a comparison harness demonstrating ontology-augmented graph traversal answering multi-hop relational questions (e.g., supply chain exposure given executive movement and competitor relationships) that pure vector search could not resolve correctly

---

## ATS Keywords Cleared by This Project

| Keyword | Where |
|---|---|
| Knowledge graphs | Core of the project |
| Ontology / ontology engineering | Phase 1 schema design |
| Neo4j / graph databases | Phase 4 |
| Entity extraction / NER | Phase 3 |
| Relationship extraction | Phase 3 |
| Information extraction | Phase 3 |
| LLM APIs / prompt engineering | Phase 3 extraction pipeline |
| Vector databases / semantic search | Phase 5 baseline |
| RAG | Phase 5/6 comparison |
| Entity resolution | Phase 3 |
| Multi-hop reasoning | Phase 6 |
| Graph traversal / Cypher | Phase 6 |
| Data pipelines / ETL | Phase 2/3 |
| Confidence scoring | Phase 3 |

---

## Notes on Domain Choice

This project intentionally uses public financial market data (SEC filings, Wikidata, financial news) rather than government/policy data, keeping the technical work in a globally portable, non-sensitive domain. Good for long-term portfolio use regardless of where you end up working.
