import { useEffect, useRef } from "react";
import type { GraphData, GraphNode, GraphEdge, RelT } from "./api";

// Highlight the graph should focus on (traversal path, node neighborhood, or
// relationship type). null = full globe, no dimming.
export interface Highlight {
  nodes: Set<string>;
  edges: Set<string>; // eKey values
}

interface Props {
  data: GraphData;
  highlight: Highlight | null;
  legendFilter: RelT | null;
  onNodeClick: (n: GraphNode | null) => void;
  onLegendToggle: (r: RelT) => void;
}

const NODE_COLOR: Record<string, string> = {
  c: "#e0b877",
  p: "#7fcbb0",
  e: "#e39a86",
};
const EDGE_COLOR: Record<RelT, string> = {
  st: "#4ec9b0",
  cw: "#c96a5a",
  eo: "#b48ead",
  ab: "#d9a441",
};

export const eKey = (e: GraphEdge) => `${e.s}|${e.t}|${e.r}`;

// internal sim node — extends the API node with physics fields
interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  d: number;
  r: number;
  pinned?: boolean;
  hx?: number;
  hy?: number;
  springHome?: { x: number; y: number; t: number };
}

export function Graph({
  data,
  highlight,
  legendFilter,
  onNodeClick,
  onLegendToggle,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // Everything the animation loop needs lives in refs — never React state,
  // so a 60fps sim doesn't trigger 60 re-renders/sec.
  const hlRef = useRef<Highlight | null>(highlight);
  const dragHlRef = useRef<Highlight | null>(null);
  hlRef.current = highlight;

  useEffect(() => {
    const cv = canvasRef.current!;
    const ctx = cv.getContext("2d")!;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

    // ---- build sim graph ----
    const nodes: SimNode[] = data.nodes.map((n) => ({
      ...n,
      x: 0,
      y: 0,
      vx: 0,
      vy: 0,
      d: 0,
      r: 0,
    }));
    const byId: Record<string, SimNode> = {};
    nodes.forEach((n) => (byId[n.id] = n));
    const edges = data.edges;
    edges.forEach((e) => {
      if (byId[e.s]) byId[e.s].d++;
      if (byId[e.t]) byId[e.t].d++;
    });
    nodes.forEach((n, i) => {
      n.r = (n.t === "c" ? 4.5 : 3) + Math.sqrt(n.d) * 2.1;
      const g = i * 2.39996;
      const ring = n.d ? 120 + Math.random() * 160 : 300 + Math.random() * 120;
      n.x = Math.cos(g) * ring;
      n.y = Math.sin(g) * ring;
    });

    let alpha = 1;
    function tick() {
      const REP = 1600,
        SPRING = 0.02,
        REST = 85,
        CENTER = 0.012;
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          let dx = b.x - a.x,
            dy = b.y - a.y,
            d2 = dx * dx + dy * dy || 1;
          if (d2 < 90000) {
            const f = REP / d2,
              d = Math.sqrt(d2),
              fx = (dx / d) * f,
              fy = (dy / d) * f;
            a.vx -= fx;
            a.vy -= fy;
            b.vx += fx;
            b.vy += fy;
          }
        }
        a.vx -= a.x * CENTER;
        a.vy -= a.y * CENTER;
      }
      edges.forEach((e) => {
        const a = byId[e.s],
          b = byId[e.t];
        if (!a || !b) return;
        const dx = b.x - a.x,
          dy = b.y - a.y,
          d = Math.sqrt(dx * dx + dy * dy) || 1;
        const f = (d - REST) * SPRING,
          fx = (dx / d) * f,
          fy = (dy / d) * f;
        a.vx += fx;
        a.vy += fy;
        b.vx -= fx;
        b.vy -= fy;
      });
      nodes.forEach((n) => {
        n.vx *= 0.82;
        n.vy *= 0.82;
        if (n.pinned) {
          n.vx = 0;
          n.vy = 0;
          return;
        }
        if (n.springHome) {
          n.vx += (n.springHome.x - n.x) * 0.07;
          n.vy += (n.springHome.y - n.y) * 0.07;
          const close =
            Math.abs(n.springHome.x - n.x) < 1.5 &&
            Math.abs(n.springHome.y - n.y) < 1.5;
          if (--n.springHome.t <= 0 || close) delete n.springHome;
        }
        n.x += n.vx * alpha;
        n.y += n.vy * alpha;
      });
      if (alpha > 0.02) alpha *= 0.995;
    }

    // ---- camera / canvas ----
    let W = 0,
      H = 0,
      DPR = 1;
    const cam = { x: 0, y: 0, k: 1 };
    function resize() {
      DPR = window.devicePixelRatio || 1;
      W = window.innerWidth;
      H = window.innerHeight;
      cv.width = W * DPR;
      cv.height = H * DPR;
      cv.style.width = W + "px";
      cv.style.height = H + "px";
      cam.k = Math.min(W, H) / 760;
    }
    window.addEventListener("resize", resize);
    resize();
    const toScreen = (x: number, y: number): [number, number] => [
      W / 2 + (x - cam.x) * cam.k,
      H / 2 + (y - cam.y) * cam.k,
    ];
    const toWorld = (px: number, py: number): [number, number] => [
      (px - W / 2) / cam.k + cam.x,
      (py - H / 2) / cam.k + cam.y,
    ];

    let dimT = 0;
    let raf = 0;
    function draw() {
      tick();
      const eff = dragHlRef.current || hlRef.current;
      dimT += ((eff ? 1 : 0) - dimT) * (reduced ? 1 : 0.08);
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      ctx.clearRect(0, 0, W, H);

      edges.forEach((e) => {
        const a = byId[e.s],
          b = byId[e.t];
        if (!a || !b) return;
        const [ax, ay] = toScreen(a.x, a.y),
          [bx, by] = toScreen(b.x, b.y);
        const hot = eff ? eff.edges.has(eKey(e)) : false;
        const base = hot ? 0.95 : 0.3;
        const dimmed = hot ? 0.95 : 0.05;
        ctx.globalAlpha = base + (dimmed - base) * dimT;
        ctx.strokeStyle = EDGE_COLOR[e.r];
        ctx.lineWidth = hot ? 1.6 + 0.9 * dimT : 0.8;
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        ctx.stroke();
      });

      const mono = getComputedStyle(document.documentElement).getPropertyValue(
        "--mono",
      );
      nodes.forEach((n) => {
        const [x, y] = toScreen(n.x, n.y);
        const hot = eff ? eff.nodes.has(n.id) : false;
        const orphan = n.d === 0;
        const base = orphan ? 0.45 : 0.92;
        const dimmed = hot ? 1 : 0.1;
        ctx.globalAlpha = base + (dimmed - base) * dimT;
        const r = n.r * cam.k * (hot ? 1.25 : 1);
        if (hot) {
          ctx.shadowColor = NODE_COLOR[n.t];
          ctx.shadowBlur = 18;
        } else ctx.shadowBlur = 0;
        ctx.fillStyle = NODE_COLOR[n.t];
        if (n.t === "e") {
          ctx.save();
          ctx.translate(x, y);
          ctx.rotate(Math.PI / 4);
          ctx.fillRect(-r * 0.8, -r * 0.8, r * 1.6, r * 1.6);
          ctx.restore();
        } else {
          ctx.beginPath();
          ctx.arc(x, y, r, 0, 7);
          ctx.fill();
        }
        ctx.shadowBlur = 0;
        const showLbl = (n.t === "c" && cam.k > 0.55) || hot || cam.k > 1.7;
        if (showLbl) {
          ctx.globalAlpha = hot
            ? 1
            : (n.t === "c" ? 0.75 : 0.5) * (1 - dimT * 0.9);
          ctx.fillStyle = hot ? "#f4efe4" : "#b3a78f";
          ctx.font = `${hot ? 600 : 400} ${Math.max(9, 10 * cam.k) | 0}px ${mono}`;
          ctx.textAlign = "center";
          const lbl = n.label.length > 22 ? n.label.slice(0, 21) + "…" : n.label;
          ctx.fillText(lbl, x, y + r + 12);
        }
      });
      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(draw);
    }
    raf = requestAnimationFrame(draw);

    // ---- interaction ----
    const neighborhood = (id: string): Highlight => {
      const ns = new Set([id]),
        es = new Set<string>();
      edges.forEach((e) => {
        if (e.s === id || e.t === id) {
          es.add(eKey(e));
          ns.add(e.s);
          ns.add(e.t);
        }
      });
      return { nodes: ns, edges: es };
    };
    const hitNode = (cx: number, cy: number): SimNode | null => {
      const [wx, wy] = toWorld(cx, cy);
      let best: SimNode | null = null,
        bd = 1e9;
      nodes.forEach((n) => {
        const dx = n.x - wx,
          dy = n.y - wy,
          d = dx * dx + dy * dy;
        if (d < bd && Math.sqrt(d) < Math.max(12 / cam.k, n.r + 6)) {
          bd = d;
          best = n;
        }
      });
      return best;
    };

    let dragging = false,
      moved = false,
      px = 0,
      py = 0,
      dragN: SimNode | null = null;
    const pointers = new Map<number, [number, number]>();

    const onDown = (e: PointerEvent) => {
      pointers.set(e.pointerId, [e.clientX, e.clientY]);
      dragging = true;
      moved = false;
      px = e.clientX;
      py = e.clientY;
      cv.setPointerCapture(e.pointerId);
      const n = pointers.size === 1 ? hitNode(e.clientX, e.clientY) : null;
      if (n) {
        dragN = n;
        n.pinned = true;
        n.hx = n.x;
        n.hy = n.y;
        delete n.springHome;
        dragHlRef.current = neighborhood(n.id);
        onNodeClick(n);
        alpha = Math.max(alpha, 0.5);
      } else {
        cv.classList.add("grabbing");
      }
    };
    const onMove = (e: PointerEvent) => {
      if (!dragging) return;
      if (pointers.size === 2) {
        const pts = [...pointers.values()];
        const d0 = Math.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]);
        pointers.set(e.pointerId, [e.clientX, e.clientY]);
        const p2 = [...pointers.values()];
        const d1 = Math.hypot(p2[0][0] - p2[1][0], p2[0][1] - p2[1][1]);
        cam.k = Math.min(4, Math.max(0.3, cam.k * (d1 / (d0 || 1))));
        moved = true;
        return;
      }
      pointers.set(e.pointerId, [e.clientX, e.clientY]);
      const dx = e.clientX - px,
        dy = e.clientY - py;
      if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
      if (dragN) {
        const [wx, wy] = toWorld(e.clientX, e.clientY);
        dragN.x = wx;
        dragN.y = wy;
        alpha = Math.max(alpha, 0.4);
      } else {
        cam.x -= dx / cam.k;
        cam.y -= dy / cam.k;
      }
      px = e.clientX;
      py = e.clientY;
    };
    const onUp = (e: PointerEvent) => {
      pointers.delete(e.pointerId);
      dragging = pointers.size > 0;
      cv.classList.remove("grabbing");
      if (dragN) {
        dragN.pinned = false;
        dragN.springHome = { x: dragN.hx!, y: dragN.hy!, t: 120 };
        alpha = Math.max(alpha, 0.5);
        if (!moved) onNodeClick(dragN); // click = focus (App decides)
        dragHlRef.current = null;
        dragN = null;
        return;
      }
      if (!moved) onNodeClick(null);
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const f = Math.exp(-e.deltaY * 0.0016);
      const [wx, wy] = toWorld(e.clientX, e.clientY);
      cam.k = Math.min(4, Math.max(0.3, cam.k * f));
      const [nx, ny] = toWorld(e.clientX, e.clientY);
      cam.x += wx - nx;
      cam.y += wy - ny;
    };

    cv.addEventListener("pointerdown", onDown);
    cv.addEventListener("pointermove", onMove);
    cv.addEventListener("pointerup", onUp);
    cv.addEventListener("wheel", onWheel, { passive: false });

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      cv.removeEventListener("pointerdown", onDown);
      cv.removeEventListener("pointermove", onMove);
      cv.removeEventListener("pointerup", onUp);
      cv.removeEventListener("wheel", onWheel);
    };
    // Rebuild the sim only when the underlying data changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  return (
    <>
      <canvas ref={canvasRef} className="stage" />
      <div className="legend">
        <div className="row">
          <span>
            <i style={{ background: "var(--gold)" }} />
            Company
          </span>
          <span>
            <i style={{ background: "var(--sea)" }} />
            Person
          </span>
          <span>
            <i style={{ background: "var(--coral)" }} />
            Event
          </span>
        </div>
        <div className="row">
          {(
            [
              ["st", "SUPPLIES_TO", "--teal"],
              ["cw", "COMPETES_WITH", "--rust"],
              ["eo", "EXECUTIVE_OF", "--mauve"],
              ["ab", "AFFECTED_BY", "--amber"],
            ] as [RelT, string, string][]
          ).map(([r, name, c]) => (
            <span
              key={r}
              className={`lg${legendFilter === r ? " on" : ""}`}
              onClick={() => onLegendToggle(r)}
            >
              <s style={{ background: `var(${c})` }} />
              {name}
            </span>
          ))}
        </div>
      </div>
    </>
  );
}
