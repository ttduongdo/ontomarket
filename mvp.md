Data. 

Skip the 50-100 company SEC scrape. Pick one sector, ~15-20 real companies, sourced two ways: Wikidata SPARQL for structure (subsidiaries, founders, sector classification, which is fast and real), plus a hand-curated layer for what Wikidata won't have cleanly (recent executive moves, supply chain links, a regulatory event or two), pulled from real public filings or news you verify yourself. I'd point this at big tech / AI infra specifically rather than tech-in-general or consumer goods, since Neo4j, Glean, Tacnode, and Prometheux all live in that world, so a chain like "Company X has a regulatory action, competes with Y, an exec moved X to Y in the last two years, X supplies to Z" lands instantly for that audience instead of needing explanation. Be upfront about the sourcing in the README: curated dataset, structurally grounded in Wikidata, manually verified supplementation, not an automated pipeline at scale. Same instinct you already use keeping the Civic bullets accurate, just pointed at data provenance instead of project scope.


Schema. 

Cut 6 entity types and 8 relationships down to exactly what the hero query needs: Company, Person, Event; COMPETES_WITH, SUPPLIES_TO, EXECUTIVE_OF (with start/end dates), AFFECTED_BY. That's the complete chain the target query traverses, nothing decorative.
Vector baseline. Skip the news ETL pipeline. Write 30-50 short snippets yourself, a sentence or two per real event, embed them locally with sentence-transformers, drop them in Chroma. That's enough to show vector search returning documents that mention the right entities while failing to compose the relationship chain. The contrast is the point, not corpus size.


Graph layer. 

Keep Neo4j, real, local Docker rather than Aura. This is the one place not to cut corners, since it's literally their product: real constraints, a real ingestion script, real Cypher traversals.


Query layer. 

Cut the general NL-to-Cypher translator. Hard-code 4-5 Cypher templates, hero query included, triggered from a preset dropdown of questions rather than a freeform box. Freeform parsing is the most likely thing to break live and adds nothing to proving the thesis.


Demo. 

One Streamlit app: preset question dropdown, side-by-side "Vector Search Result" vs "Ontology Reasoning Result" panels, and a NetworkX/Plotly subgraph for the traversal path. No Bloom integration, no public deployment unless you want it later as a stretch.

Docs. README with the thesis, an architecture diagram, and a results table: question asked, what vector search returned and why it's incomplete, what the graph returned and why it's right. That table does more work than the live demo for anyone who reads the repo before they ever run it.


Cut outright, not deferred: confidence scoring, fuzzy entity resolution at scale (a 20-row alias table replaces it), Form 4 parsing, GDELT/NewsAPI ingestion, public deployment, the demo video. None of those prove the thesis; they're hardening for a system that isn't trying to be production yet.
