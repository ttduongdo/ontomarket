import { useEffect, useRef } from "react";
import type { QueryResult, VectorHit, Triple } from "./api";

interface Props {
  result: QueryResult;
  vector: VectorHit[] | null;
  onDismiss: () => void; // scrolled back to top → return to graph
}

// wrap [n] / [8][9] citation runs in coral mono superscripts
function citeHtml(text: string): string {
  const esc = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return esc.replace(/(\[\d+\])+/g, (m) => `<sup>${m}</sup>`);
}

// triples arrive as [source, target, "AFFECTED_BY"] — rel is already the display name
function tripleLabel(t: Triple): string {
  const [s, tgt, rel] = t;
  return `${s} <em>—${rel}→</em> ${tgt}`;
}

export function AnswerSheet({ result, vector, onDismiss }: Props) {
  const readerRef = useRef<HTMLDivElement>(null);

  // Emerge: start scrolled partway so the sheet rises into view.
  useEffect(() => {
    const el = readerRef.current;
    if (!el) return;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: window.innerHeight * 0.55, behavior: reduced ? "auto" : "smooth" });
  }, []);

  return (
    <div
      className="reader"
      ref={readerRef}
      onScroll={(e) => {
        if (e.currentTarget.scrollTop <= 0) onDismiss();
      }}
    >
      <div className="spacer" />
      <div className="sheet">
        <div className="sheet-inner">
          <div className="ans-label">Answer</div>
          <div className="q-line">› {result.question}</div>
          {result.anchors.length > 0 && (
            <div className="ent-line">retrieved: {result.anchors.join(" · ")}</div>
          )}

          {result.answer ? (
            <div
              className="answer"
              dangerouslySetInnerHTML={{ __html: citeHtml(result.answer) }}
            />
          ) : (
            <div className="answer" style={{ color: "var(--dim)" }}>
              No grounded answer — the traversal returned no connected chain to cite.
            </div>
          )}

          <div className="cols">
            <div className="col">
              <h4>◈ Vector search — top snippets</h4>
              {vector === null ? (
                <div className="snip">searching…</div>
              ) : vector.length ? (
                vector.map((h) => (
                  <div className="snip" key={h.id}>
                    <span className="sim">sim {h.similarity.toFixed(3)}</span>
                    {h.text}
                  </div>
                ))
              ) : (
                <div className="snip">no snippets</div>
              )}
            </div>
            <div className="col">
              <h4>⬡ Cited traversal edges · {result.triples.length}</h4>
              <div className="cites">
                {result.triples.map((t, i) => (
                  <div
                    className="c"
                    key={i}
                    dangerouslySetInnerHTML={{
                      __html: `<b>[${i + 1}]</b>${tripleLabel(t)}`,
                    }}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
