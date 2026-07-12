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

from src.query.router import run, run_raw, query_labels
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
  background: #161310;
}
[data-testid="stSidebar"] { display: none !important; }
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 100%; }

/* ── Typography ─────────────────────────────────────────────────────────── */
h1 {
  background: linear-gradient(120deg, #4ec9b0 0%, #e0b877 50%, #4ec9b0 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: 0.08em;
  font-size: 2.1rem !important;
  margin-bottom: 0 !important;
}
h2, h3 { color: #e8e0d0 !important; letter-spacing: 0.04em; }
p, li, [data-testid="stMarkdown"] { color: #c4b8a4; }

/* ── Top query bar ──────────────────────────────────────────────────────── */
.query-bar {
  background: linear-gradient(135deg, #1e1a15 0%, #26211a 100%);
  border: 1px solid #4ec9b022;
  border-radius: 10px;
  padding: 14px 20px;
  margin-bottom: 16px;
  box-shadow: 0 0 30px #4ec9b008;
}

/* ── Columns / panels ───────────────────────────────────────────────────── */
[data-testid="column"] { background: transparent; }

/* ── Buttons ────────────────────────────────────────────────────────────── */
[data-testid="stButton"] > button {
  background: linear-gradient(135deg, #1e1a15 0%, #161310 100%);
  border: 1px solid #4ec9b044;
  color: #e8e0d0;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 0.8rem;
  transition: all 0.25s;
  box-shadow: 0 0 12px #4ec9b015;
}
[data-testid="stButton"] > button:hover {
  border-color: #4ec9b0;
  box-shadow: 0 0 24px #4ec9b044;
  color: #f4efe4;
}
[data-testid="stButton"] > button[kind="primary"] {
  background: linear-gradient(135deg, #2a3f39 0%, #1e1a15 100%);
  border-color: #4ec9b077;
  color: #7fe6d0;
  box-shadow: 0 0 20px #4ec9b033;
}
[data-testid="stButton"] > button[kind="primary"]:hover {
  box-shadow: 0 0 35px #4ec9b066;
  color: #fff;
}

/* ── Form inputs ────────────────────────────────────────────────────────── */
[data-testid="stSelectbox"] > label,
[data-testid="stRadio"] > label,
[data-testid="stSlider"] > label,
[data-testid="stTextInput"] > label,
[data-testid="stTextArea"] > label {
  color: #9a8f7d !important;
  font-size: 0.73rem !important;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
  background: #1e1a15 !important;
  border: 1px solid #4ec9b033 !important;
  color: #e8e0d0 !important;
  border-radius: 6px !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  border-color: #4ec9b077 !important;
  box-shadow: 0 0 10px #4ec9b022 !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
  background: #1e1a15 !important;
  border-color: #4ec9b033 !important;
  color: #e8e0d0 !important;
}

/* ── Containers with border ─────────────────────────────────────────────── */
[data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"] {
  border-radius: 8px;
}

/* ── Dataframe ──────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
  border: 1px solid #4ec9b018;
  border-radius: 8px;
  background: #1e1a15;
}
[data-testid="stDataFrame"] table { background: transparent; }
[data-testid="stDataFrame"] th { background: #26211a !important; color: #e8e0d0 !important; }
[data-testid="stDataFrame"] td {
  color: #c4b8a4 !important;
  font-family: "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, monospace !important;
  font-variant-numeric: tabular-nums;
  font-size: 0.82rem !important;
}

/* ── Info / warning / error ─────────────────────────────────────────────── */
[data-testid="stInfo"] {
  background: #1e1a15 !important;
  border-left: 3px solid #4ec9b0 !important;
  color: #e8e0d0 !important;
  border-radius: 0 6px 6px 0 !important;
}
[data-testid="stAlert"] { border-radius: 6px !important; }

/* ── Grounded answer panel (custom HTML, not st.info) ────────────────────── */
.ans-label {
  font-family: "IBM Plex Mono", ui-monospace, Menlo, monospace;
  font-size: 0.72rem; letter-spacing: 0.18em; text-transform: uppercase;
  color: #4ec9b0; display: flex; align-items: center; gap: 8px; margin: 4px 0 10px;
}
.ans-panel {
  background: linear-gradient(160deg, #1e1a15, #161310);
  border: 1px solid #332c22; border-radius: 12px; padding: 22px 24px; margin-bottom: 6px;
}
/* Question box — sits above the answer, mono with a › marker */
.ans-q-box {
  font-family: "IBM Plex Mono", ui-monospace, Menlo, monospace;
  font-size: 0.9rem; color: #c4b8a4; line-height: 1.5;
  background: linear-gradient(160deg, #1e1a15, #161310);
  border: 1px solid #332c22; border-radius: 12px;
  padding: 14px 18px; margin: 4px 0 18px;
}
.ans-ent {
  font-family: "IBM Plex Mono", ui-monospace, Menlo, monospace;
  font-size: 0.75rem; color: #4ec9b0; margin-bottom: 16px;
}
.ans-body {
  font-family: Georgia, "Times New Roman", "Iowan Old Style", serif;
  font-size: 1.05rem; line-height: 1.68; color: #e8e0d0;
}
.ans-cite {
  font-family: "IBM Plex Mono", ui-monospace, Menlo, monospace;
  font-size: 0.72em; font-weight: 700; color: #e39a86; padding: 0 1px;
}
/* Bordered section containers (vector / graph panels) share the answer box look */
[data-testid="stVerticalBlockBorderWrapper"] {
  background: linear-gradient(160deg, #1e1a15, #161310);
  border: 1px solid #332c22 !important; border-radius: 12px !important;
  padding: 8px 4px;
}
/* Inner snippet cards sit lighter inside the outer panel */
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlockBorderWrapper"] {
  background: #26211a; border: 1px solid #332c22 !important; border-radius: 8px !important;
  padding: 2px 2px;
}

/* ── Expander ───────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
  background: #1e1a15 !important;
  border: 1px solid #4ec9b018 !important;
  border-radius: 8px !important;
}
[data-testid="stExpander"] summary { color: #9a8f7d !important; }

/* ── Captions ───────────────────────────────────────────────────────────── */
[data-testid="stCaptionContainer"] { color: #6b6252 !important; }

/* ── Divider ────────────────────────────────────────────────────────────── */
hr { border-color: #4ec9b015 !important; }

/* ── Spinner ────────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] { color: #4ec9b0 !important; }

/* ── Component iframes — strip border, match page bg ───────────────────── */
iframe { border: none !important; background: #161310; }

/* ── Scrollbars ─────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #1e1a15; }
::-webkit-scrollbar-thumb { background: #4ec9b033; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #4ec9b066; }
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
  html, body { background: #161310; margin: 0; }
  #controls {
    padding: 8px 14px; display: flex; gap: 8px; align-items: center;
    background: #161310;
    border-bottom: 1px solid #4ec9b028;
  }
  button {
    border: none; padding: 5px 14px; border-radius: 4px;
    cursor: pointer; font-size: 11px; font-weight: 700;
    letter-spacing: 0.06em; text-transform: uppercase; transition: all 0.2s;
  }
  #btn-play  {
    background: linear-gradient(135deg, #2a3f39, #1e1a15);
    color: #7fe6d0; border: 1px solid #4ec9b055;
    box-shadow: 0 0 10px #4ec9b022;
  }
  #btn-play:hover { box-shadow: 0 0 18px #4ec9b055; }
  #btn-reset { background: #161310; color: #9a8f7d; border: 1px solid #2a3f39; }
  #speed-label { color: #9a8f7d; font-size: 11px; margin-left: 6px; text-transform: uppercase; letter-spacing: 0.05em; }
  #speed {
    background: #161310; color: #9a8f7d; border: 1px solid #2a3f39;
    border-radius: 4px; padding: 3px 7px; font-size: 11px; cursor: pointer;
  }
  #status { color: #9a8f7d; font-size: 11px; margin-left: 4px; letter-spacing: 0.03em; }
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
    var t = TRIPLES[i];
    // uniform teal edges (matches the styled node/edge theme), no arrows;
    // animate a dash "draw-in" then settle to a solid teal line.
    var edge = cy.add({
      data: { id: 'e' + i, source: t.src, target: t.tgt, label: '[' + (i+1) + '] ' + t.rel },
      style: {
        'line-style': 'dashed', 'line-dash-pattern': [DASH, 0],
        'line-dash-offset': DASH, 'line-color': '#4ec9b0',
      }
    });
    edge.animate(
      { style: { 'line-dash-offset': -DASH } },
      { duration: getDrawMs(), easing: 'ease-in-out',
        complete: function() {
          edge.style({ 'line-style': 'solid', 'line-dash-offset': 0 });
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
          // ticker sits INSIDE the node, bold mono (like the mockup)
          label: 'data(label)', 'font-size': FONT_SIZE,
          'font-family': 'IBM Plex Mono, ui-monospace, Menlo, monospace',
          'font-weight': 700,
          'text-valign': 'center', 'text-halign': 'center',
          color: '#e8dcc4',
          shape: 'round-rectangle', 'corner-radius': 8,
          'background-color': '#26211a', width: NODE_SIZE, height: NODE_SIZE,
          'border-width': 1.5, 'border-color': '#e0b877',
      }},
      { selector: '.Company', style: { 'background-color': '#26211a', 'border-color': '#e0b877', color: '#e8dcc4' }},
      { selector: '.Person',  style: { 'background-color': '#14261f', 'border-color': '#7fcbb0', color: '#a8ddca', shape: 'ellipse' }},
      { selector: '.Event',   style: {
          'background-color': '#2a1a15', 'border-color': '#e39a86', color: '#f0b8a8',
          shape: 'diamond', width: EVENT_SIZE, height: EVENT_SIZE,
      }},
      { selector: 'edge', style: {
          // relationship label above the line, mono uppercase teal, no chip
          label: 'data(label)', 'font-size': '9px',
          'font-family': 'IBM Plex Mono, ui-monospace, Menlo, monospace',
          'letter-spacing': '1px', 'text-transform': 'uppercase',
          color: '#5bbfa8',
          'text-background-opacity': 0, 'text-margin-y': -9,
          'text-rotation': 'autorotate',
          'curve-style': 'straight', 'line-color': '#4ec9b0',
          'target-arrow-shape': 'none',
          width: 1.5,
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
    colors = json.dumps(["#4ec9b0", "#e0b877", "#a78bfa", "#00ffaa", "#ff6644"])
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
    "<h1>ONTOMARKET</h1>"
    "<p style='color:#6b6252;font-size:0.8rem;letter-spacing:0.12em;"
    "text-transform:uppercase;margin-top:-6px;margin-bottom:12px;'>"
    "Grounded GraphRAG answers &nbsp;·&nbsp; multi-hop ontology reasoning vs. vector search</p>",
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
    run_btn = st.button("Run", type="primary", use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)

import html as _html
if nl_question:
    st.markdown(
        f"<div class='ans-q-box'>&#8250; {_html.escape(nl_question)}</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Run the graph pipeline once — retrieve → traverse → synthesize.
# Computed above the columns so the grounded answer can be a full-width hero.
# ---------------------------------------------------------------------------

results       = []
triples       = []
cypher_used   = None
graph_label   = "Preset"
fallback_used = False
translation   = None
anchors       = []
explanation   = None

if run_btn and nl_question:
    # 1. Freeform → seed entities via vector search, then NL→Cypher
    if freeform:
        with st.spinner("Retrieving entities & translating to Cypher …"):
            try:
                from src.query.nl_to_cypher import translate
                from src.query.entity_seeder import seed_entities
                anchors = seed_entities(nl_question)
                translation = translate(nl_question, anchors=anchors)
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

    # 2. Traverse the graph
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
        except Exception as e:
            st.error(f"Neo4j error: {e}")

    # 3. Synthesize the grounded answer
    if results:
        with st.spinner("Generating answer …"):
            try:
                from src.query.explainer import explain
                explanation = explain(
                    question=nl_question,
                    results=results,
                    query_type=query_key or "freeform",
                    triples=triples,
                )
            except Exception as e:
                st.caption(f"Answer unavailable: {e}")

# ── Hero: grounded, cited answer (full width, custom HTML panel) ──────────
import html as _html
import re as _re

def _render_answer(answer_text: str, anchor_list: list[str]) -> None:
    """Render the grounded answer as a styled panel (serif body, coral
    citations) instead of st.info(), which fights Streamlit's alert styling."""
    safe = _html.escape(answer_text)
    # style [n] / [8][9] citation markers → mono coral superscript
    safe = _re.sub(r"(\[\d+\])+", lambda m: f"<sup class='ans-cite'>{m.group(0)}</sup>", safe)
    ent_line = (f"<div class='ans-ent'>retrieved: {' &middot; '.join(anchor_list)}</div>"
                if anchor_list else "")
    st.markdown(
        f"<div class='ans-panel'>{ent_line}"
        f"<div class='ans-body'>{safe}</div></div>",
        unsafe_allow_html=True,
    )

if run_btn and nl_question:
    st.markdown("<div class='ans-label'>&#11041; Answer</div>", unsafe_allow_html=True)
    if explanation:
        _render_answer(explanation, anchors)
        if triples:
            legend = "  \n".join(
                f"**[{i}]** {src} → *{rel}* → {tgt}"
                for i, (src, tgt, rel) in enumerate(triples, start=1)
            )
            with st.expander(f"Citations · {len(triples)} edges", expanded=False):
                st.markdown(legend)
    elif results is not None and not results:
        st.info("Query returned no results — no graph evidence to answer from.")
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
elif run_btn and not nl_question:
    st.warning("Enter a question first.")
else:
    st.info("Select a query above and click **Run** to see the grounded answer, then the vector-vs-graph evidence below.")

# ---------------------------------------------------------------------------
# Evidence: side-by-side vector vs. graph (the "why graph wins" proof)
# ---------------------------------------------------------------------------

if run_btn and nl_question:
    col_vec, col_graph = st.columns([1, 1], gap="large")

    # ── Right: Ontology Reasoning ─────────────────────────────────────────
    with col_graph:
        st.markdown("<div class='ans-label'>&#11041; Graph traversal</div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.caption("Cypher over Neo4j — composes the full multi-hop chain.")
            if results:
                st.dataframe(pd.DataFrame(results), hide_index=True, use_container_width=True)
                st.caption(f"{len(results)} rows · {len(triples)} edges · {graph_label}")
            else:
                st.info("No results — check the graph is loaded and date filters match.")

            from src.graph.queries import QUERIES
            if cypher_used and not fallback_used:
                with st.expander("Cypher used", expanded=False):
                    st.code(cypher_used, language="cypher")
            elif query_key and query_key in QUERIES:
                with st.expander("Cypher used", expanded=False):
                    st.code(QUERIES[query_key]["cypher"].strip(), language="cypher")

    # ── Left: Vector Search ───────────────────────────────────────────────
    with col_vec:
        st.markdown("<div class='ans-label'>&#9672; Vector search</div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.caption("Top snippets by cosine similarity — finds facts, can't compose the chain.")
            with st.spinner("Searching ChromaDB …"):
                try:
                    hits = search(nl_question, top_k=top_k)
                    for i, hit in enumerate(hits, 1):
                        with st.container(border=True):
                            st.markdown(
                                f"<span style='color:#4ec9b0;font-size:0.75rem;font-weight:700;"
                                f"letter-spacing:0.05em;'>#{i}</span>"
                                f"<span style='color:#6b6252;font-size:0.75rem;'> · sim {hit.similarity:.3f}</span>",
                                unsafe_allow_html=True,
                            )
                            st.write(hit.text)
                            st.caption(f"tags: {hit.tags}")
                except RuntimeError as e:
                    st.error(str(e))

# ---------------------------------------------------------------------------
# Traversal path — full-width, below both columns
# ---------------------------------------------------------------------------
saved_triples = st.session_state.get("triples", [])
if saved_triples:
    st.subheader("◈ Traversal Path")
    _, g_col, _ = st.columns([1, 3, 1])
    with g_col:
        render_traversal_animated(saved_triples)
