# OntoMarket

**Ask a financial question about big tech. Get an answer with receipts.**

OntoMarket is a GraphRAG assistant that answers questions like *"which companies
face supply-chain exposure when an executive jumps to a competitor after a
regulatory hit?"* — the kind of question that depends on chaining several
relationships together, not just finding one matching document. It answers by
walking a live knowledge graph and writing a plain-English response where
**every claim links back to the exact fact that supports it.**

**[→ Try it live: ontomarket.vercel.app](https://ontomarket.vercel.app)**

<!-- TODO: drop a screenshot or short GIF of the graph UI here, e.g.:
![OntoMarket graph UI](docs/screenshot.png) -->

### Why this is harder than it looks

Ask a normal search engine or a vector-search chatbot the same question, and it
can usually find the *individual facts* — "Company X had a regulatory event,"
"Executive Y joined Company Z" — as separate, disconnected hits. What it can't
do is reliably **compose** them into the actual answer, because the answer only
exists as a *chain* of relationships, and that chain isn't written down anywhere
as a single sentence.

Across every question in this project's benchmark, a pure vector-search
baseline never once found a single source that contained the full answer chain
— **0% "chain recall,"** even on the simplest one-hop question. It finds the
puzzle pieces. It doesn't assemble the puzzle. OntoMarket does, and it shows its
work: click any citation and see the exact fact it came from.

### How it works, in three steps

1. **Retrieve** — a short natural-language question is matched against the
   graph's entities (companies, people, events).
2. **Traverse** — those entities seed a query that walks the actual
   relationship graph, following the real chain of connections.
3. **Answer, with citations** — the model writes a grounded answer from *only*
   the traversal results, marking exactly which fact backs each sentence.

The app also runs the same question through plain vector search side-by-side,
so you can see the difference for yourself, live.

---

Built with a Neo4j graph, Claude, and a small hand-curated dataset covering ~20
AI-infrastructure companies. Architecture, local setup, and deployment notes
are in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for anyone who wants to dig
into the source.
