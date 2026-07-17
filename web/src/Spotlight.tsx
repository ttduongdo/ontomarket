import { useEffect, useRef, useState } from "react";
import type { Preset } from "./api";

interface Props {
  presets: Preset[];
  onRunPreset: (p: Preset) => void;
  onRunFreeform: (q: string) => void;
  onClose: () => void;
}

export function Spotlight({ presets, onRunPreset, onRunFreeform, onClose }: Props) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = presets.filter(
    (p) =>
      p.label.toLowerCase().includes(q.toLowerCase()) ||
      p.question.toLowerCase().includes(q.toLowerCase()),
  );
  // A trimmed query that matches no preset becomes a freeform option.
  const freeform = q.trim().length > 0 && filtered.length === 0;
  const rows = freeform ? 1 : filtered.length;

  useEffect(() => {
    inputRef.current?.focus();
  }, []);
  useEffect(() => {
    setSel(0);
  }, [q]);

  function commit() {
    if (freeform) {
      onRunFreeform(q.trim());
    } else if (filtered[sel]) {
      onRunPreset(filtered[sel]);
    }
  }

  return (
    <div className="spot" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="spot-box">
        <input
          ref={inputRef}
          value={q}
          placeholder="Ask the graph…  (or pick a preset)"
          autoComplete="off"
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            else if (e.key === "ArrowDown") setSel((s) => Math.min(s + 1, rows - 1));
            else if (e.key === "ArrowUp") setSel((s) => Math.max(s - 1, 0));
            else if (e.key === "Enter") commit();
          }}
        />
        <div className="spot-list">
          {freeform ? (
            <div className="spot-item sel freeform" onClick={commit}>
              <span>Ask freeform: “{q.trim()}”</span>
              <small>NL → Cypher</small>
            </div>
          ) : filtered.length ? (
            filtered.map((p, i) => (
              <div
                key={p.key}
                className={`spot-item${i === sel ? " sel" : ""}`}
                onMouseEnter={() => setSel(i)}
                onClick={() => onRunPreset(p)}
              >
                <span>{p.label}</span>
                <small>{p.key}</small>
              </div>
            ))
          ) : (
            <div className="spot-item">type a question, or clear to see presets</div>
          )}
        </div>
        <div className="spot-note">
          ↑↓ navigate · ⏎ run · esc close — freeform runs the live NL→Cypher pipeline
        </div>
      </div>
    </div>
  );
}
