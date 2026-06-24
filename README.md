# OntoMarket

**Thesis:** Multi-hop graph reasoning over a financial ontology outperforms vector
search on relational questions — questions where the answer depends on traversing a
chain of relationships, not on finding a single matching document.

## What this is

A focused demo built around one sector: big-tech / AI infrastructure (~15–20 companies).
The dataset is small by design. Its purpose is to make the contrast legible, not to
scale.

**Stack:** Neo4j (local Docker) · ChromaDB · sentence-transformers · Streamlit ·
NetworkX / Plotly

## Dataset sourcing

Structural data (founding dates, subsidiaries, sector classification) is pulled from
Wikidata via SPARQL. Executive moves, supply-chain links, and regulatory events are
hand-curated from public filings and verified news sources. The README is upfront about
this: it is a curated dataset, not an automated pipeline at scale.

## Architecture

```
data/raw/          Wikidata SPARQL responses and hand-curated JSON
data/processed/    Cleaned, schema-validated records ready for ingestion

src/data/          Wikidata client, data cleaning, schema validation
src/graph/         Neo4j ingestion and Cypher query templates
src/search/        sentence-transformers embedding, ChromaDB ingestion and retrieval
src/query/         Query router: preset question dropdown → graph or vector backend
```

## Running the demo

_Instructions added in Phase 5._

## Results

_Results table (question asked · vector output · graph output · why graph wins) added
after Phase 4._
