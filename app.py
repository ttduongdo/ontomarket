"""
OntoMarket — Streamlit demo app.

Layout:
  Sidebar   — mode toggle (Preset / Ask a question) + Run button
  Main top  — two columns: Vector Search result (left) | Graph Reasoning result (right)
  Main mid  — plain-English explanation of the graph result (D2)
  Main bot  — NetworkX/Plotly traversal subgraph

Run:
  streamlit run app.py
"""

import sys
from pathlib import Path

import networkx as nx
import pandas as pd
from plotly import graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from src.query.router import run, run_raw, query_labels, query_description
from src.search.retriever import search

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="OntoMarket",
    page_icon="🕸️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Graph visualisation helpers
# ---------------------------------------------------------------------------

NODE_COLORS = {
    "Company": "#4C9BE8",
    "Person":  "#52C98F",
    "Event":   "#F0814A",
    "default": "#AAAAAA",
}

def _node_type(label: str) -> str:
    if label.startswith("EVT-"):
        return "Event"
    if "-" in label and not label.isupper():
        return "Person"
    return "Company"


def build_figure(triples: list[tuple]) -> go.Figure:
    if not triples:
        return go.Figure().update_layout(
            title="No traversal path to display",
            height=300,
        )

    G = nx.DiGraph()
    for src, tgt, rel in triples:
        G.add_edge(src, tgt, label=rel)

    pos = nx.spring_layout(G, seed=42, k=2.5)

    edge_traces = []
    for src, tgt, data in G.edges(data=True):
        x0, y0 = pos[src]
        x1, y1 = pos[tgt]
        mid_x  = (x0 + x1) / 2
        mid_y  = (y0 + y1) / 2
        edge_traces.append(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode="lines",
            line=dict(width=1.5, color="#888"),
            hoverinfo="none",
            showlegend=False,
        ))
        edge_traces.append(go.Scatter(
            x=[mid_x], y=[mid_y],
            mode="text",
            text=[data["label"]],
            textfont=dict(size=9, color="#555"),
            hoverinfo="none",
            showlegend=False,
        ))

    node_x, node_y, node_text, node_color, node_hover = [], [], [], [], []
    for node in G.nodes():
        x, y = pos[node]
        ntype = _node_type(node)
        node_x.append(x)
        node_y.append(y)
        node_text.append(node)
        node_color.append(NODE_COLORS.get(ntype, NODE_COLORS["default"]))
        node_hover.append(f"{ntype}: {node}")

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="top center",
        textfont=dict(size=10),
        marker=dict(size=18, color=node_color, line=dict(width=1.5, color="#333")),
        hovertext=node_hover,
        hoverinfo="text",
        showlegend=False,
    )

    legend_traces = [
        go.Scatter(x=[None], y=[None], mode="markers",
                   marker=dict(size=10, color=color),
                   name=ntype, showlegend=True)
        for ntype, color in NODE_COLORS.items() if ntype != "default"
    ]

    fig = go.Figure(
        data=edge_traces + [node_trace] + legend_traces,
        layout=go.Layout(
            height=420,
            margin=dict(l=20, r=20, t=30, b=20),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor="#0e1117",
            paper_bgcolor="#0e1117",
            font=dict(color="#fafafa"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        ),
    )
    return fig


# ---------------------------------------------------------------------------
# Preset question config
# Maps query_key → natural-language question sent to vector search
# ---------------------------------------------------------------------------

VECTOR_QUERIES = {
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

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🕸️ OntoMarket")
    st.caption("Multi-hop graph reasoning vs. vector search")
    st.divider()

    mode = st.radio("Query mode", ["Preset queries", "Ask a question"], horizontal=True)
    st.divider()

    if mode == "Preset queries":
        labels     = query_labels()
        query_keys = list(labels.keys())
        query_key  = st.selectbox(
            "Preset question",
            options=query_keys,
            format_func=lambda k: labels[k],
        )
        st.caption(query_description(query_key))
        nl_question = VECTOR_QUERIES[query_key]
        freeform    = False
    else:
        nl_question = st.text_area(
            "Your question",
            placeholder="e.g. Who supplies chips to Microsoft Azure?",
            height=100,
        )
        query_key = None
        freeform  = True

    st.divider()
    top_k   = st.slider("Vector search — top K results", 1, 10, 5)
    run_btn = st.button("Run", type="primary", width='stretch')

# ---------------------------------------------------------------------------
# Main header
# ---------------------------------------------------------------------------

st.header("OntoMarket: Graph Reasoning vs. Vector Search")
if nl_question:
    st.markdown(f"**Question:** _{nl_question}_")

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if run_btn and nl_question:
    col_vec, col_graph = st.columns(2, gap="large")

    results       = []
    triples       = []
    cypher_used   = None
    graph_label   = "Preset"
    fallback_used = False
    translation   = None

    # ── Vector search ────────────────────────────────────────────────────────
    with col_vec:
        st.subheader("🔍 Vector Search")
        st.caption(
            "Top matching snippets by cosine similarity — "
            "finds relevant facts but cannot compose the relational chain."
        )
        with st.spinner("Searching ChromaDB …"):
            try:
                hits = search(nl_question, top_k=top_k)
                for i, hit in enumerate(hits, 1):
                    with st.container(border=True):
                        st.markdown(f"**#{i} · similarity {hit.similarity:.3f}**")
                        st.write(hit.text)
                        st.caption(f"tags: {hit.tags}")
            except RuntimeError as e:
                st.error(str(e))

    # ── Graph reasoning ──────────────────────────────────────────────────────
    with col_graph:
        st.subheader("🕸️ Ontology Reasoning")
        st.caption("Cypher traversal over Neo4j — composes the full multi-hop relational chain.")

        if freeform:
            with st.spinner("Translating question to Cypher …"):
                try:
                    from src.query.nl_to_cypher import translate
                    translation = translate(nl_question)
                    st.caption(f"_Routing: {translation.rationale}_")

                    if translation.type == "preset" and translation.preset_key:
                        query_key   = translation.preset_key
                        graph_label = f"Preset ({query_key})"
                    elif translation.cypher:
                        cypher_used = translation.cypher
                        graph_label = "Freeform Cypher"
                    else:
                        query_key   = translation.closest_preset
                        graph_label = f"Fallback ({query_key})"

                except Exception as e:
                    st.error(f"Translation error: {e}")
                    query_key   = "hero"
                    graph_label = "Fallback (hero)"

        with st.spinner("Querying Neo4j …"):
            try:
                if cypher_used:
                    try:
                        results, triples = run_raw(cypher_used)
                    except Exception as cypher_err:
                        fallback_key = translation.closest_preset if translation else "hero"
                        st.warning(
                            f"Generated Cypher failed. "
                            f"Falling back to preset: **{fallback_key}**"
                        )
                        query_key     = fallback_key
                        graph_label   = f"Fallback ({query_key})"
                        fallback_used = True
                        results, triples = run(query_key)
                else:
                    results, triples = run(query_key)

                if results:
                    st.dataframe(
                        pd.DataFrame(results),
                        width='stretch',
                        hide_index=True,
                    )
                    st.caption(
                        f"{len(results)} result row(s) — "
                        f"{len(triples)} graph edges traversed · {graph_label}"
                    )
                else:
                    st.info(
                        "Query returned no results. "
                        "Check that the graph is loaded and date filters match your data."
                    )

            except Exception as e:
                st.error(f"Neo4j error: {e}")

    # ── Cypher display ───────────────────────────────────────────────────────
    from src.graph.queries import QUERIES
    if cypher_used and not fallback_used:
        with st.expander("Cypher query used", expanded=False):
            st.code(cypher_used, language="cypher")
    elif query_key and query_key in QUERIES:
        with st.expander("Cypher query used", expanded=False):
            st.code(QUERIES[query_key]["cypher"].strip(), language="cypher")

    # ── Plain-English explanation ─────────────────────────────────────────────
    st.divider()
    if results:
        with st.spinner("Generating explanation …"):
            try:
                from src.query.explainer import explain
                explanation = explain(
                    question=nl_question,
                    results=results,
                    query_type=query_key or "freeform",
                )
                st.info(explanation)
            except Exception as e:
                st.caption(f"Explanation unavailable: {e}")

    # ── Traversal subgraph ───────────────────────────────────────────────────
    st.subheader("Traversal Path")
    if triples:
        st.plotly_chart(build_figure(triples), width='stretch')
    else:
        st.caption("No traversal path to display for this query.")

elif run_btn and not nl_question:
    st.warning("Please enter a question first.")
else:
    st.info("Select a preset question or type your own, then click **Run**.")
