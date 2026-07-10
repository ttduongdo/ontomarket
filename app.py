"""
OntoMarket — Streamlit demo app.

Layout:
  Top     — title + query controls (no sidebar)
  Main    — two columns: Ontology Reasoning + traversal graph (left) | Vector Search (right)
"""

import sys
from pathlib import Path
import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ---------------------------------------------------------------------------
# Inline JS bundles — loaded once at startup, embedded in the HTML template
# so st.html() shadow-DOM rendering works without CDN requests.
# ---------------------------------------------------------------------------
_STATIC = Path(__file__).parent / "static"
_JS_CYTOSCAPE  = (_STATIC / "cytoscape.min.js").read_text()
_JS_WEBCOLA    = (_STATIC / "webcola.min.js").read_text()
_JS_CY_COLA    = (_STATIC / "cytoscape-cola.js").read_text()

sys.path.insert(0, str(Path(__file__).parent))

from src.query.router import run, run_raw, query_labels, query_description
from src.search.retriever import search

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="OntoMarket",
    page_icon="⬡",
    layout="wide",
)

st.session_state.setdefault("triples", [])

# ---------------------------------------------------------------------------
# Space / obsidian theme
# ---------------------------------------------------------------------------

st.markdown("""
<style>
/* ── Background ─────────────────────────────────────────────────────────── */
[data-testid="stApp"] {
  background: #050300;
}
[data-testid="stSidebar"] { display: none !important; }
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 100%; }

/* ── Typography ─────────────────────────────────────────────────────────── */
h1 {
  background: linear-gradient(120deg, #f5c518 0%, #ff9500 50%, #f5c518 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: 0.08em;
  font-size: 2.1rem !important;
  margin-bottom: 0 !important;
}
h2, h3 { color: #fde68a !important; letter-spacing: 0.04em; }
p, li, [data-testid="stMarkdown"] { color: #c8b06a; }

/* ── Top query bar ──────────────────────────────────────────────────────── */
.query-bar {
  background: linear-gradient(135deg, #0d0a00 0%, #1a1400 100%);
  border: 1px solid #f5c51822;
  border-radius: 10px;
  padding: 14px 20px;
  margin-bottom: 16px;
  box-shadow: 0 0 30px #f5c51808;
}

/* ── Columns / panels ───────────────────────────────────────────────────── */
[data-testid="column"] { background: transparent; }

/* ── Buttons ────────────────────────────────────────────────────────────── */
[data-testid="stButton"] > button {
  background: linear-gradient(135deg, #1f1600 0%, #100d00 100%);
  border: 1px solid #f5c51844;
  color: #fde68a;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 0.8rem;
  transition: all 0.25s;
  box-shadow: 0 0 12px #f5c51815;
}
[data-testid="stButton"] > button:hover {
  border-color: #f5c518;
  box-shadow: 0 0 24px #f5c51844;
  color: #fff8dc;
}
[data-testid="stButton"] > button[kind="primary"] {
  background: linear-gradient(135deg, #3a2800 0%, #1f1400 100%);
  border-color: #f5c51877;
  color: #ffe066;
  box-shadow: 0 0 20px #f5c51833;
}
[data-testid="stButton"] > button[kind="primary"]:hover {
  box-shadow: 0 0 35px #f5c51866;
  color: #fff;
}

/* ── Form inputs ────────────────────────────────────────────────────────── */
[data-testid="stSelectbox"] > label,
[data-testid="stRadio"] > label,
[data-testid="stSlider"] > label,
[data-testid="stTextInput"] > label,
[data-testid="stTextArea"] > label {
  color: #7a6010 !important;
  font-size: 0.73rem !important;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
  background: #0a0800 !important;
  border: 1px solid #f5c51833 !important;
  color: #fde68a !important;
  border-radius: 6px !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  border-color: #f5c51877 !important;
  box-shadow: 0 0 10px #f5c51822 !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
  background: #0a0800 !important;
  border-color: #f5c51833 !important;
  color: #fde68a !important;
}

/* ── Containers with border ─────────────────────────────────────────────── */
[data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"] {
  border-radius: 8px;
}

/* ── Dataframe ──────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
  border: 1px solid #f5c51818;
  border-radius: 8px;
  background: #0a0800;
}
[data-testid="stDataFrame"] table { background: transparent; }
[data-testid="stDataFrame"] th { background: #1a1200 !important; color: #fde68a !important; }
[data-testid="stDataFrame"] td { color: #c8b06a !important; }

/* ── Info / warning / error ─────────────────────────────────────────────── */
[data-testid="stInfo"] {
  background: #0d0a00 !important;
  border-left: 3px solid #f5c518 !important;
  color: #c8b06a !important;
  border-radius: 0 6px 6px 0 !important;
}
[data-testid="stAlert"] { border-radius: 6px !important; }

/* ── Expander ───────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
  background: #0a0800 !important;
  border: 1px solid #f5c51818 !important;
  border-radius: 8px !important;
}
[data-testid="stExpander"] summary { color: #7a6010 !important; }

/* ── Captions ───────────────────────────────────────────────────────────── */
[data-testid="stCaptionContainer"] { color: #4a3800 !important; }

/* ── Divider ────────────────────────────────────────────────────────────── */
hr { border-color: #f5c51815 !important; }

/* ── Spinner ────────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] { color: #f5c518 !important; }

/* ── Component iframes — strip border, match page bg ───────────────────── */
iframe { border: none !important; background: #050300; }

/* ── Scrollbars ─────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0a0800; }
::-webkit-scrollbar-thumb { background: #f5c51833; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #f5c51866; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Cytoscape traversal — space-themed iframe
# ---------------------------------------------------------------------------

_TRAVERSAL_HTML = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { background: #050300; margin: 0; }
  #controls {
    padding: 8px 14px; display: flex; gap: 8px; align-items: center;
    background: #050300;
    border-bottom: 1px solid #f5c51828;
  }
  button {
    border: none; padding: 5px 14px; border-radius: 4px;
    cursor: pointer; font-size: 11px; font-weight: 700;
    letter-spacing: 0.06em; text-transform: uppercase; transition: all 0.2s;
  }
  #btn-play  {
    background: linear-gradient(135deg, #3a2800, #1f1400);
    color: #ffe066; border: 1px solid #f5c51855;
    box-shadow: 0 0 10px #f5c51822;
  }
  #btn-play:hover { box-shadow: 0 0 18px #f5c51855; }
  #btn-reset { background: #050300; color: #7a6010; border: 1px solid #3a2800; }
  #speed-label { color: #7a6010; font-size: 11px; margin-left: 6px; text-transform: uppercase; letter-spacing: 0.05em; }
  #speed {
    background: #050300; color: #7a6010; border: 1px solid #3a2800;
    border-radius: 4px; padding: 3px 7px; font-size: 11px; cursor: pointer;
  }
  #status { color: #7a6010; font-size: 11px; margin-left: 4px; letter-spacing: 0.03em; }
  #cy { width: 100%; aspect-ratio: 1 / 1; background: transparent; }
</style>
</head>
<body>
<div id="controls">
  <button id="btn-play"  onclick="startAnimation()">&#9654; Play</button>
  <button id="btn-reset" onclick="resetGraph()">&#8635; Reset</button>
  <label id="speed-label" for="speed">Speed</label>
  <select id="speed">
    <option value="1000">Slow</option>
    <option value="520"  selected>Normal</option>
    <option value="200">Fast</option>
    <option value="60">Instant</option>
  </select>
  <span id="status"></span>
</div>
<div id="cy"></div>

<script>__JS_CYTOSCAPE__</script>
<script>__JS_WEBCOLA__</script>
<script>__JS_CY_COLA__</script>
<script>
var TRIPLES    = __TRIPLES__;
var HOP_COLORS = __COLORS__;
var GAP_MS     = 50;
var DASH       = 200000;

// Scripts are inlined so document.getElementById works directly.
function _find(id) { return document.getElementById(id); }

function nodeType(id) {
  if (!id) return 'Company';
  if (id.indexOf('EVT-') === 0) return 'Event';
  if (id.indexOf('-') !== -1 && id !== id.toUpperCase()) return 'Person';
  return 'Company';
}

var cy, animating = false, revealedNodes = {};

function getDrawMs() { return parseInt(_find('speed').value, 10); }
function setStatus(msg) { _find('status').textContent = msg; }
function sleep(ms) { return new Promise(function(r) { setTimeout(r, ms); }); }

function revealNode(id) {
  if (revealedNodes[id]) return;
  revealedNodes[id] = true;
  cy.getElementById(id).animate({ style: { opacity: 1 } }, { duration: 180, easing: 'ease-out' });
}

function drawEdge(i) {
  return new Promise(function(resolve) {
    var t = TRIPLES[i], color = HOP_COLORS[i % HOP_COLORS.length];
    var edge = cy.add({
      data: { id: 'e' + i, source: t.src, target: t.tgt, label: t.rel },
      style: {
        'line-style': 'dashed', 'line-dash-pattern': [DASH, 0],
        'line-dash-offset': DASH, 'line-color': color,
        'target-arrow-color': color, 'target-arrow-opacity': 0,
      }
    });
    edge.animate(
      { style: { 'line-dash-offset': -DASH } },
      { duration: getDrawMs(), easing: 'ease-in-out',
        complete: function() {
          edge.style({ 'line-style': 'solid', 'line-dash-offset': 0, 'target-arrow-opacity': 1 });
          resolve();
        }
      }
    );
  });
}

async function startAnimation() {
  if (animating) return;
  animating = true;
  cy.edges().remove();
  cy.nodes().style('opacity', 0);
  revealedNodes = {};
  var btn = _find('btn-play');
  btn.disabled = true; btn.style.opacity = '0.5';

  for (var i = 0; i < TRIPLES.length; i++) {
    if (!animating) break;
    var t = TRIPLES[i];
    var srcFresh = !revealedNodes[t.src];
    revealNode(t.src);
    if (srcFresh) await sleep(200);
    revealNode(t.tgt);
    await sleep(120);
    setStatus('hop ' + (i+1) + ' / ' + TRIPLES.length + '  —  ' + t.rel);
    await drawEdge(i);
    await sleep(GAP_MS);
  }
  setStatus('');
  animating = false;
  btn.disabled = false; btn.style.opacity = '1';
  btn.textContent = '▶ Replay';
}

function resetGraph() {
  animating = false;
  cy.edges().remove();
  cy.nodes().style('opacity', 0);
  revealedNodes = {};
  setStatus('');
  var btn = _find('btn-play');
  btn.textContent = '▶ Play'; btn.disabled = false; btn.style.opacity = '1';
}

// Scripts are synchronous so initGraph() can run immediately.
function initGraph() {
  var seenNodes = {}, nodeEls = [];
  TRIPLES.forEach(function(t) {
    [t.src, t.tgt].forEach(function(id) {
      if (!seenNodes[id]) {
        seenNodes[id] = true;
        nodeEls.push({ data: { id: id, label: id }, classes: nodeType(id) });
      }
    });
  });

  var NODE_SIZE  = Math.round(Math.max(30, Math.min(38, 320 / Math.max(nodeEls.length, 5))));
  var EVENT_SIZE = Math.round(NODE_SIZE * 1.25);
  var FONT_SIZE  = Math.max(8, Math.round(NODE_SIZE * 0.42)) + 'px';

  cy = cytoscape({
    container: _find('cy'),
    elements: nodeEls,
    style: [
      { selector: 'node', style: {
          opacity: 0,
          label: 'data(label)', 'font-size': FONT_SIZE,
          color: '#fde68a', 'text-valign': 'bottom', 'text-halign': 'center',
          'text-outline-color': '#050300', 'text-outline-width': 2,
          'background-color': '#1a1000', width: NODE_SIZE, height: NODE_SIZE,
          'border-width': 2, 'border-color': '#f5c518',
      }},
      { selector: '.Company', style: { 'background-color': '#1a1000', 'border-color': '#f5c518', color: '#fde68a' }},
      { selector: '.Person',  style: { 'background-color': '#0a2d20', 'border-color': '#00ffaa', color: '#6ee7b7' }},
      { selector: '.Event',   style: {
          'background-color': '#2a0a00', 'border-color': '#ff6644', color: '#fca47d',
          shape: 'diamond', width: EVENT_SIZE, height: EVENT_SIZE,
      }},
      { selector: 'edge', style: {
          label: 'data(label)', 'font-size': '9px',
          color: '#c8a840',
          'text-background-color': '#050300', 'text-background-opacity': 0.8,
          'text-background-padding': '3px', 'text-rotation': 'autorotate',
          'curve-style': 'bezier', 'target-arrow-shape': 'triangle',
          width: 1.5, 'arrow-scale': 1.1,
      }},
    ],
    userZoomingEnabled: true, userPanningEnabled: true,
    minZoom: 0.5, maxZoom: 4,
  });

  // cola with animate: true so the simulation runs properly.
  // Nodes are invisible so the user doesn't see the layout settling.
  var layout = cy.layout({
    name: 'cola', animate: true, fit: true, padding: 70,
    nodeSpacing: 90, edgeLengthVal: 220, avoidOverlap: true,
    handleDisconnected: true, convergenceThreshold: 0.01,
    maxSimulationTime: 2000, randomize: true,
  });
  layout.on('layoutstop', function() { setTimeout(startAnimation, 200); });
  layout.run();
}

initGraph();
</script>
</body>
</html>
"""


def render_traversal_animated(triples: list[tuple]) -> None:
    triples_data = json.dumps([
        {"src": src, "tgt": tgt, "rel": rel}
        for src, tgt, rel in triples
    ])
    colors = json.dumps(["#f5c518", "#ff9500", "#a78bfa", "#00ffaa", "#ff6644"])
    html = (_TRAVERSAL_HTML
            .replace("__TRIPLES__", triples_data)
            .replace("__COLORS__", colors)
            .replace("__JS_CYTOSCAPE__", _JS_CYTOSCAPE)
            .replace("__JS_WEBCOLA__",   _JS_WEBCOLA)
            .replace("__JS_CY_COLA__",   _JS_CY_COLA))
    # Inline scripts + st.html() = shadow DOM with truly transparent background.
    # Falls back to opaque iframe on Streamlit < 1.36.
    components.html(html, height=760, scrolling=False)


# ---------------------------------------------------------------------------
# Preset → vector question mapping
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
# Header
# ---------------------------------------------------------------------------

st.markdown(
    "<h1>⬡ ONTOMARKET</h1>"
    "<p style='color:#4a3800;font-size:0.8rem;letter-spacing:0.12em;"
    "text-transform:uppercase;margin-top:-6px;margin-bottom:12px;'>"
    "Multi-hop ontology graph reasoning &nbsp;·&nbsp; vector search comparison</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Query bar
# ---------------------------------------------------------------------------

st.markdown("<div class='query-bar'>", unsafe_allow_html=True)

qc1, qc2, qc3, qc4 = st.columns([1.2, 4, 1.2, 0.9])

with qc1:
    mode = st.radio("Mode", ["Preset", "Freeform"], horizontal=True)

with qc2:
    if mode == "Preset":
        labels     = query_labels()
        query_keys = list(labels.keys())
        query_key  = st.selectbox("Preset query", options=query_keys, format_func=lambda k: labels[k])
        nl_question = VECTOR_QUERIES[query_key]
        freeform    = False
    else:
        nl_question = st.text_input("Your question", placeholder="e.g. Who supplies chips to Microsoft Azure?")
        query_key   = None
        freeform    = True

with qc3:
    top_k = st.slider("Vector top-K", 1, 10, 5)

with qc4:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    run_btn = st.button("⬡ Run", type="primary", use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)

if mode == "Preset" and query_key:
    st.caption(query_description(query_key))

# ---------------------------------------------------------------------------
# Two-column results area — left: vector search, right: ontology reasoning
# ---------------------------------------------------------------------------

col_vec, col_graph = st.columns([1, 1], gap="large")

# ── Right: Ontology Reasoning ────────────────────────────────────────────
with col_graph:
    st.subheader("⬡ Ontology Reasoning")
    st.caption("Cypher traversal over Neo4j — composes the full multi-hop relational chain.")

    results       = []
    triples       = []
    cypher_used   = None
    graph_label   = "Preset"
    fallback_used = False
    translation   = None

    if run_btn and nl_question:
        if freeform:
            with st.spinner("Translating to Cypher …"):
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
                    except Exception:
                        fallback_key  = translation.closest_preset if translation else "hero"
                        st.warning(f"Generated Cypher failed — falling back to preset **{fallback_key}**")
                        query_key     = fallback_key
                        graph_label   = f"Fallback ({query_key})"
                        fallback_used = True
                        results, triples = run(query_key)
                else:
                    results, triples = run(query_key)

                st.session_state["triples"] = triples

                if results:
                    st.dataframe(pd.DataFrame(results), hide_index=True, use_container_width=True)
                    st.caption(f"{len(results)} rows · {len(triples)} edges · {graph_label}")
                else:
                    st.info("Query returned no results. Check that the graph is loaded and date filters match.")

            except Exception as e:
                st.error(f"Neo4j error: {e}")

        # Cypher expander
        from src.graph.queries import QUERIES
        if cypher_used and not fallback_used:
            with st.expander("Cypher used", expanded=False):
                st.code(cypher_used, language="cypher")
        elif query_key and query_key in QUERIES:
            with st.expander("Cypher used", expanded=False):
                st.code(QUERIES[query_key]["cypher"].strip(), language="cypher")

        # Plain-English explanation
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

    elif run_btn and not nl_question:
        st.warning("Enter a question first.")
    else:
        st.info("Select a query above and click **Run**.")

# ── Left: Vector Search ───────────────────────────────────────────────────
with col_vec:
    st.subheader("◈ Vector Search")
    st.caption("Top snippets by cosine similarity — finds relevant facts but cannot compose the relational chain.")

    if run_btn and nl_question:
        with st.spinner("Searching ChromaDB …"):
            try:
                hits = search(nl_question, top_k=top_k)
                for i, hit in enumerate(hits, 1):
                    with st.container(border=True):
                        st.markdown(
                            f"<span style='color:#f5c518;font-size:0.75rem;font-weight:700;"
                            f"letter-spacing:0.05em;'>#{i}</span>"
                            f"<span style='color:#4a3800;font-size:0.75rem;'> · sim {hit.similarity:.3f}</span>",
                            unsafe_allow_html=True,
                        )
                        st.write(hit.text)
                        st.caption(f"tags: {hit.tags}")
            except RuntimeError as e:
                st.error(str(e))
    elif run_btn and not nl_question:
        pass
    else:
        st.info("Results will appear here after running a query.")

# ---------------------------------------------------------------------------
# Traversal path — full-width, below both columns
# ---------------------------------------------------------------------------
saved_triples = st.session_state.get("triples", [])
if saved_triples:
    st.subheader("◈ Traversal Path")
    _, g_col, _ = st.columns([1, 3, 1])
    with g_col:
        render_traversal_animated(saved_triples)
