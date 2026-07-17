import { useCallback, useEffect, useMemo, useState } from "react";
import { Graph, eKey, type Highlight } from "./Graph";
import { Spotlight } from "./Spotlight";
import { AnswerSheet } from "./AnswerSheet";
import {
  fetchGraph,
  fetchPresets,
  runQuery,
  runVector,
  type GraphData,
  type GraphNode,
  type Preset,
  type QueryResult,
  type RelT,
  type VectorHit,
} from "./api";

type Phase = "idle" | "retrieving" | "traversing" | "synthesizing" | "error";

export default function App() {
  const [data, setData] = useState<GraphData | null>(null);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const [focusId, setFocusId] = useState<string | null>(null);
  const [legend, setLegend] = useState<RelT | null>(null);
  const [chip, setChip] = useState<GraphNode | null>(null);

  const [spotOpen, setSpotOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [phaseMsg, setPhaseMsg] = useState("");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [vector, setVector] = useState<VectorHit[] | null>(null);
  const [reading, setReading] = useState(false); // answer sheet open

  useEffect(() => {
    fetchGraph().then(setData).catch((e) => setErr(String(e)));
    fetchPresets().then(setPresets).catch(() => {});
  }, []);

  // ⌘K / Esc global keys
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSpotOpen(true);
      } else if (e.key === "Escape") {
        if (spotOpen) setSpotOpen(false);
        else resetAll();
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  // Highlight precedence: query result > node focus > legend filter.
  const highlight: Highlight | null = useMemo(() => {
    if (!data) return null;
    if (result && result.triples.length) {
      const ns = new Set<string>();
      const es = new Set<string>();
      for (const [s, t, r] of result.triples) {
        ns.add(s);
        ns.add(t);
        // r is a display name, sometimes suffixed e.g. "EXECUTIVE_OF (former)".
        // Map the prefix back to the edge code used in /graph.
        const relCode = r.startsWith("SUPPLIES_TO")
          ? "st"
          : r.startsWith("COMPETES_WITH")
            ? "cw"
            : r.startsWith("EXECUTIVE_OF")
              ? "eo"
              : r.startsWith("AFFECTED_BY")
                ? "ab"
                : r;
        const edge = data.edges.find(
          (e) =>
            e.r === relCode &&
            ((e.s === s && e.t === t) ||
              (relCode === "cw" && e.s === t && e.t === s)),
        );
        if (edge) es.add(eKey(edge));
      }
      return { nodes: ns, edges: es };
    }
    if (focusId) {
      const ns = new Set([focusId]);
      const es = new Set<string>();
      data.edges.forEach((e) => {
        if (e.s === focusId || e.t === focusId) {
          es.add(eKey(e));
          ns.add(e.s);
          ns.add(e.t);
        }
      });
      return { nodes: ns, edges: es };
    }
    if (legend) {
      const ns = new Set<string>();
      const es = new Set<string>();
      data.edges.forEach((e) => {
        if (e.r === legend) {
          es.add(eKey(e));
          ns.add(e.s);
          ns.add(e.t);
        }
      });
      return { nodes: ns, edges: es };
    }
    return null;
  }, [data, result, focusId, legend]);

  const resetAll = useCallback(() => {
    setResult(null);
    setVector(null);
    setReading(false);
    setFocusId(null);
    setLegend(null);
    setChip(null);
    setPhase("idle");
  }, []);

  // Run the pipeline. The real backend does translate→traverse→synthesize in
  // one call, so we can't stream true stage boundaries — but we can show
  // honest staged copy while the single request is in flight, and fire the
  // vector search in parallel so its column fills as soon as it returns.
  const execute = useCallback(
    async (body: { preset_key?: string; question?: string }, question: string) => {
      setSpotOpen(false);
      setFocusId(null);
      setLegend(null);
      setResult(null);
      setVector(null);
      setReading(false);
      setPhase(body.preset_key ? "traversing" : "retrieving");
      setPhaseMsg(
        body.preset_key
          ? "Traversing the graph…"
          : "Retrieving entities & translating to Cypher…",
      );

      // vector search in parallel (independent of the graph pipeline)
      runVector(question).then(setVector).catch(() => setVector([]));

      try {
        // advance the copy while the one request runs
        const t1 = setTimeout(() => {
          setPhase("traversing");
          setPhaseMsg("Traversing the graph…");
        }, 900);
        const t2 = setTimeout(() => {
          setPhase("synthesizing");
          setPhaseMsg("Synthesizing the grounded answer…");
        }, 2200);
        const res = await runQuery(body);
        clearTimeout(t1);
        clearTimeout(t2);
        setResult(res);
        setPhase("idle");
      } catch (e) {
        setPhase("error");
        setPhaseMsg(String(e).slice(0, 140));
      }
    },
    [],
  );

  if (err)
    return (
      <div style={{ padding: 40, color: "var(--coral)" }}>
        Could not load graph: {err}
        <br />
        <span style={{ color: "var(--dim)", fontSize: 12 }}>
          Is the API running? venv/bin/python -m uvicorn api.main:app --port 8000
        </span>
      </div>
    );
  if (!data)
    return <div style={{ padding: 40, color: "var(--dim)" }}>Loading graph…</div>;

  const busy = phase === "retrieving" || phase === "traversing" || phase === "synthesizing";

  return (
    <>
      <Graph
        data={data}
        highlight={highlight}
        legendFilter={legend}
        onNodeClick={(n) => {
          if (result) return; // don't fight the query highlight
          setChip(n);
          setFocusId(n ? n.id : null);
          if (n) setLegend(null);
        }}
        onLegendToggle={(r) => {
          if (result) return;
          setLegend((cur) => (cur === r ? null : r));
          setFocusId(null);
        }}
      />

      <div className="wordmark">
        ONTO<span>MARKET</span>
      </div>
      {!result && (
        <div className="hint">
          drag background to pan · scroll to zoom
          <br />
          drag a node to stretch · click to focus · ⌘K to ask
        </div>
      )}

      <button
        className={`ask-pill${busy ? " busy" : ""}`}
        onClick={() => setSpotOpen(true)}
      >
        <span className="dot" /> Ask the graph <span className="k">⌘K</span>
      </button>

      {busy && (
        <div className="progress">
          <span className="spin" />
          <span className="stage">{phaseMsg}</span>
        </div>
      )}
      {phase === "error" && (
        <div className="progress err" onClick={() => setPhase("idle")}>
          {phaseMsg} — click to dismiss
        </div>
      )}

      {chip && !result && (
        <div className="chip">
          <span className="t">
            {{ c: "Company", p: "Person", e: "Event" }[chip.t]} ·{" "}
            {data.edges.filter((e) => e.s === chip.id || e.t === chip.id).length}{" "}
            edges
          </span>
          <b>{chip.label}</b>
          {chip.full !== chip.label ? chip.full : ""}
        </div>
      )}

      {spotOpen && (
        <Spotlight
          presets={presets}
          onRunPreset={(p) => execute({ preset_key: p.key }, p.question)}
          onRunFreeform={(q) => execute({ question: q }, q)}
          onClose={() => setSpotOpen(false)}
        />
      )}

      {/* result present, not yet reading → teaser + back */}
      {result && !reading && (
        <>
          <button className="back" onClick={resetAll}>
            ✕ back to the graph
          </button>
          <div className="teaser" onClick={() => setReading(true)}>
            <b>↑</b> scroll for the grounded answer
          </div>
        </>
      )}

      {result && reading && (
        <AnswerSheet
          result={result}
          vector={vector}
          onDismiss={() => setReading(false)}
        />
      )}
    </>
  );
}
