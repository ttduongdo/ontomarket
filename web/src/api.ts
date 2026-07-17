// API types + client. Paths go through the Vite dev proxy (/api → :8000).

export type NodeT = "c" | "p" | "e";
export interface GraphNode {
  id: string;
  label: string;
  full: string;
  t: NodeT;
}
export type RelT = "cw" | "st" | "eo" | "ab";
export interface GraphEdge {
  s: string;
  t: string;
  r: RelT;
}
export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Preset {
  key: string;
  label: string;
  description: string;
  question: string;
}

export type Triple = [string, string, string]; // [source, target, rel]

export interface QueryResult {
  question: string;
  query_key: string | null;
  graph_label: string | null;
  fallback_used: boolean;
  anchors: string[];
  rationale: string | null;
  cypher: string | null;
  results: Record<string, unknown>[];
  triples: Triple[];
  answer: string | null;
}

export interface VectorHit {
  id: string;
  text: string;
  tags: string;
  similarity: number;
}

const API = "/api";

export async function fetchGraph(): Promise<GraphData> {
  const r = await fetch(`${API}/graph`);
  if (!r.ok) throw new Error(`/graph ${r.status}`);
  return r.json();
}

export async function fetchPresets(): Promise<Preset[]> {
  const r = await fetch(`${API}/presets`);
  if (!r.ok) throw new Error(`/presets ${r.status}`);
  return r.json();
}

export async function runQuery(body: {
  preset_key?: string;
  question?: string;
  top_k?: number;
}): Promise<QueryResult> {
  const r = await fetch(`${API}/query`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`/query ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function runVector(
  question: string,
  top_k = 5,
): Promise<VectorHit[]> {
  const r = await fetch(`${API}/vector`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, top_k }),
  });
  if (!r.ok) throw new Error(`/vector ${r.status}`);
  return r.json();
}
