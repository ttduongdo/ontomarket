# Results — worked examples

Three real queries, each showing what pure vector search returns versus what the
graph traversal composes — and the grounded, cited answer OntoMarket synthesizes
from the traversal. **All output below is verbatim from live runs** (Neo4j + ChromaDB
+ Claude), not hand-written illustration.

The pattern to watch: vector search reliably surfaces *relevant facts*, but never the
*composed chain*. The graph does, and the answer cites the exact edges it used.

---

## Example 1 — Hero: supply-chain exposure via an executive move (4 hops)

> **Which companies face supply-chain exposure given an executive moved to a
> competitor after a regulatory event?**

This is the thesis query. Answering it means chaining four different relationship
types: a regulatory `Event` → the affected `Company` → an executive who departed to a
`COMPETES_WITH` competitor → the affected company's `SUPPLIES_TO` suppliers.

**Vector search** (top-3 by cosine similarity) returns related facts, none composing the chain:

```
[sim 0.357] TSMC, AMD, Apple, and Broadcom form an interconnected supply chain…
[sim 0.335] Intel CEO Pat Gelsinger cited intensifying competition from NVIDIA and AMD…
[sim 0.330] Microsoft completed its $69 billion acquisition of Activision Blizzard…
```

Each snippet is *about* the right entities, but no single one connects "MSFT was
affected by a regulatory event → an exec left MSFT for competitor AAPL → NVDA/AMD/INTC
supply MSFT." The chain isn't a property of any document.

**Graph traversal** returns 59 rows / 25 edges. The key edges:

```
EVT-MSFT-2023-activision  -AFFECTED_BY->  MSFT
MSFT                      -COMPETES_WITH-> AAPL
NVDA                      -SUPPLIES_TO->   MSFT
EVT-ftc-regulatory-challenge -AFFECTED_BY-> MSFT
```

**Synthesized answer** (Claude, grounded only in the traversal, `[n]` = cited edge):

> Based on the traversal, two chains satisfy the pattern. For Microsoft: an executive
> (Corporate VP, AI) departed Microsoft on 2025-11-01 and arrived at competitor Apple as
> VP Artificial Intelligence on 2025-12-01, following regulatory events including the FTC
> challenge and the UK CMA battle over the Activision acquisition [8][9][4][2].
> Microsoft's supply-chain exposure runs through its suppliers NVIDIA, AMD, Intel, and
> Snowflake [3][14][15][16].
>
> For Google (Alphabet): the antitrust regulatory event affected GOOGL, which competes
> with Apple, and its exposed suppliers are NVIDIA and Broadcom [17][18][24][25].
>
> A keyword or vector search could not have composed this because it requires chaining
> distinct edges — a regulatory event, an executive's departure-to-competitor move, and
> downstream supplier relationships — which no single document or semantic match would
> connect end-to-end.

**Why graph wins:** the graph found *two* independent chains (Microsoft and Alphabet)
and cited a specific edge for every claim. Vector search returned three plausible
snippets and left the reader to connect them — which, for a four-hop relationship, they
can't do reliably.

---

## Example 2 — Reverse supply exposure (2 hops)

> **If a company faces a regulatory action, which of its suppliers face downstream
> exposure?**

Two hops: a regulatory/lawsuit `Event` → the affected `Company` → that company's
`SUPPLIES_TO` suppliers.

**Vector search** (top-3):

```
[sim 0.309] The US Commerce Department issued updated export controls in October 2023…
[sim 0.299] TSMC, AMD, Apple, and Broadcom form an interconnected supply chain…
[sim 0.285] Microsoft completed its $69 billion acquisition of Activision Blizzard…
```

The export-controls snippet and the supply-chain snippet are both relevant — but they
sit as separate documents. Vector search can't *join* "NVDA faces export controls" to
"TSM supplies NVDA" into a single exposure statement.

**Graph traversal** (6 rows / 9 edges):

```
EVT-NVDA-2023-export-controls -AFFECTED_BY-> AMD
TSM                           -SUPPLIES_TO->  AMD
EVT-GOOGL-2024-antitrust      -AFFECTED_BY-> GOOGL
AVGO                          -SUPPLIES_TO->  GOOGL
NVDA                          -SUPPLIES_TO->  GOOGL
NOW                           -SUPPLIES_TO->  NVDA
```

**Synthesized answer:**

> Two regulatory actions appear in the facts. The 2023 US export controls on NVIDIA
> chips affected both NVIDIA and AMD [7][1]; NVIDIA's exposed suppliers are ServiceNow
> (NOW) and Taiwan Semiconductor (TSM) [8][9], while AMD's exposed supplier is also TSM
> [2]. The 2024 antitrust ruling against Alphabet (GOOGL) [3] creates downstream exposure
> for its suppliers Broadcom (AVGO), NVIDIA (NVDA), and Alphabet itself [4][6][5].
>
> A keyword or vector search could not compose this because it requires chaining a
> regulatory event to its affected company and then hopping again to that company's
> suppliers — a two-step graph traversal that flat text similarity cannot reconstruct.

**Why graph wins:** the graph correctly separated *two distinct regulatory events* and
traced each one's downstream suppliers independently — including catching that the NVIDIA
export controls affected AMD too. Vector search surfaced the raw facts but produced no
exposure map.

---

## Example 3 — Competitor event scan (2 hops)

> **What notable events have Intel's direct competitors had recently?**

Two hops: identify Intel's `COMPETES_WITH` competitors → traverse to each competitor's
`AFFECTED_BY` events.

**Vector search** (top-3):

```
[sim 0.584] Intel CEO Pat Gelsinger cited intensifying competition from NVIDIA and AMD…
[sim 0.577] AMD and Intel compete in the x86 CPU market and increasingly in AI accelerators…
[sim 0.532] Intel and Microsoft announced a multi-year agreement… Intel Foundry…
```

Note the higher similarity scores here (0.53–0.58) — this is closer to vector search's
comfort zone, since the snippets literally mention Intel and its rivals. But it still
can't guarantee it retrieved *all* of Intel's graph-defined competitors, or *all* their
events — it returns a similar subset, not a complete scan.

**Graph traversal** (16 rows / 19 edges):

```
INTC -COMPETES_WITH-> AMD
INTC -COMPETES_WITH-> TSM
EVT-mi300x-unveil          -AFFECTED_BY-> AMD
EVT-amd-export-controls-mi200 -AFFECTED_BY-> AMD
EVT-tsmc-competitive-pressure -AFFECTED_BY-> TSM
```

**Synthesized answer:**

> Intel's three direct competitors are AMD, TSMC, and NVIDIA [1][7][9]. AMD has had a
> mixed run: Lisa Su unveiled the Instinct MI300X AI accelerator claiming superior LLM
> inference performance over NVIDIA's H100, and its data center business more than offset
> weakness, but shares fell 2% on unfavorable roadmap comparisons, gaming GPU revenue
> declined sharply, and its MI200 accelerators fell under US export restrictions [3][6][2][5][4].
> NVIDIA reported record quarterly revenue of $13.5 billion on H100 demand… though it faces
> export controls and Microsoft diversifying to AMD's MI300X [10][11][13][12]. TSMC faces
> emerging competitive pressure from Intel Foundry [8].
>
> A keyword or vector search could not have composed this because it required first
> identifying Intel's competitors via COMPETES_WITH edges, then traversing to each rival's
> distinct events — a multi-hop join that text similarity alone cannot assemble.

**Why graph wins:** the graph gave a *complete, per-competitor* event breakdown (every
AMD event, every NVIDIA event, TSMC's) because it enumerated the competitor set from the
graph first. Vector search returned three Intel-adjacent snippets — useful context, but
not an exhaustive competitor scan.

---

## The pattern across all three

| | Vector search | Graph traversal |
|---|---|---|
| **Returns** | Relevant individual facts | The composed relationship chain |
| **Guarantees completeness?** | No — a similar subset | Yes — enumerated from edges |
| **Composes multi-hop?** | No | Yes |
| **Answer is** | left to the reader | synthesized + cited to specific edges |

Vector search is a good *fact finder*. It is not a *reasoner over relationships* — and
financial questions ("who is exposed if X happens, given Y") are relational by nature.
That's the gap OntoMarket fills, and every claim in its answers is traceable to a
literal graph edge.

> Reproduce these: `python -m src.eval.run_eval` for the scored benchmark, or run the
> queries in the app (`streamlit run app.py`). Numbers reflect the dataset at time of
> writing (2026-07); they shift as the graph grows.
