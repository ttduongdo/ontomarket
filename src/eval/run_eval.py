"""
OntoMarket benchmark runner.

Runs all 5 eval questions against both Neo4j (graph) and ChromaDB (vector),
scores each one, and prints a comparison table.

Usage
-----
    python -m src.eval.run_eval                  # full run, table to stdout
    python -m src.eval.run_eval --json           # JSON output
    python -m src.eval.run_eval --top-k 10       # use top-10 vector results
    python -m src.eval.run_eval --save           # also write a timestamped
                                                  # snapshot to data/eval/history/
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

EVAL_SET_PATH = Path(__file__).parents[2] / "data" / "eval" / "eval_set.json"
HISTORY_DIR   = Path(__file__).parents[2] / "data" / "eval" / "history"
TOP_K_DEFAULT = 5


def _load_eval_set() -> list[dict]:
    data = json.loads(EVAL_SET_PATH.read_text())
    return data["questions"]


def _run_graph(query_key: str) -> tuple[list[dict], float]:
    from src.query.router import run
    t0 = time.perf_counter()
    results, _ = run(query_key)
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    return results, latency_ms


def _run_vector(question: str, top_k: int) -> tuple[list, float]:
    from src.search.retriever import search
    t0 = time.perf_counter()
    hits = search(question, top_k=top_k)
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    return hits, latency_ms


def run_benchmark(top_k: int = TOP_K_DEFAULT) -> list[dict]:
    from src.eval.scorer import score_question

    questions = _load_eval_set()
    results = []

    for q in questions:
        print(f"  [{q['id']}] running…", end="", flush=True)

        try:
            graph_rows, graph_ms = _run_graph(q["query_key"])
            graph_error = None
        except Exception as exc:
            graph_rows, graph_ms, graph_error = [], 0.0, str(exc)

        try:
            vector_hits, vector_ms = _run_vector(q["question"], top_k)
            vector_error = None
        except Exception as exc:
            vector_hits, vector_ms, vector_error = [], 0.0, str(exc)

        scored = score_question(q, graph_rows, vector_hits)
        scored["graph_latency_ms"]  = graph_ms
        scored["vector_latency_ms"] = vector_ms
        scored["graph_error"]       = graph_error
        scored["vector_error"]      = vector_error

        results.append(scored)
        status = "✓" if not (graph_error or vector_error) else "✗"
        print(f" {status}")

    return results


def _print_table(results: list[dict]) -> None:
    hdr = (
        f"{'ID':<22} {'Hops':>4}  {'G-rows':>6}  "
        f"{'G-recall':>8}  {'G-prec':>7}  "
        f"{'V-recall':>8}  {'V-chain':>7}  "
        f"{'Δ recall':>8}  "
        f"{'G-lat ms':>9}  {'V-lat ms':>9}"
    )
    sep = "-" * len(hdr)
    print()
    print(hdr)
    print(sep)

    for r in results:
        flag = "" if r["rows_ok"] else " ⚠"
        print(
            f"{r['id']:<22} {r['hops']:>4}  {r['graph_rows']:>6}{flag}  "
            f"{r['graph_entity_recall']:>8.1%}  {r['graph_precision']:>7.1%}  "
            f"{r['vector_entity_recall']:>8.1%}  {r['vector_chain_recall']:>7.1%}  "
            f"{r['recall_delta']:>+8.1%}  "
            f"{r['graph_latency_ms']:>9.1f}  {r['vector_latency_ms']:>9.1f}"
        )

    print(sep)

    # Averages (skip errored rows)
    ok = [r for r in results if not r["graph_error"] and not r["vector_error"]]
    if ok:
        def avg(key):
            return sum(r[key] for r in ok) / len(ok)

        print(
            f"{'AVERAGE':<22} {'':>4}  {'':>6}  "
            f"{avg('graph_entity_recall'):>8.1%}  {avg('graph_precision'):>7.1%}  "
            f"{avg('vector_entity_recall'):>8.1%}  {avg('vector_chain_recall'):>7.1%}  "
            f"{avg('recall_delta'):>+8.1%}  "
            f"{avg('graph_latency_ms'):>9.1f}  {avg('vector_latency_ms'):>9.1f}"
        )

    print()
    print("Columns: G = graph (Neo4j Cypher), V = vector (ChromaDB cosine similarity)")
    print("  G-recall  — fraction of expected entities found in graph result rows")
    print("  G-prec    — fraction of result rows that contain at least one expected entity")
    print("  V-recall  — fraction of expected entities mentioned across top-K snippets")
    print("  V-chain   — 1.0 if a single snippet contains ALL expected entities (multi-hop = always 0)")
    print("  Δ recall  — G-recall minus V-recall (positive = graph wins)")
    print()

    # Errors
    for r in results:
        if r["graph_error"]:
            print(f"  GRAPH ERROR [{r['id']}]: {r['graph_error']}")
        if r["vector_error"]:
            print(f"  VECTOR ERROR [{r['id']}]: {r['vector_error']}")


def _save_snapshot(results: list[dict], top_k: int) -> Path:
    """
    Write a timestamped snapshot of this run to data/eval/history/ so
    regressions are visible as the dataset grows. Returns the written path.
    """
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = HISTORY_DIR / f"{timestamp}.json"

    ok = [r for r in results if not r["graph_error"] and not r["vector_error"]]
    averages = {}
    if ok:
        def avg(key):
            return round(sum(r[key] for r in ok) / len(ok), 3)
        averages = {
            "graph_entity_recall":  avg("graph_entity_recall"),
            "graph_precision":      avg("graph_precision"),
            "vector_entity_recall": avg("vector_entity_recall"),
            "vector_chain_recall":  avg("vector_chain_recall"),
            "recall_delta":         avg("recall_delta"),
            "graph_latency_ms":     avg("graph_latency_ms"),
            "vector_latency_ms":    avg("vector_latency_ms"),
        }

    snapshot = {
        "timestamp": timestamp,
        "top_k": top_k,
        "questions": results,
        "averages": averages,
    }
    path.write_text(json.dumps(snapshot, indent=2))
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="OntoMarket benchmark")
    parser.add_argument("--json",   action="store_true", help="Output JSON instead of table")
    parser.add_argument("--top-k",  type=int, default=TOP_K_DEFAULT, help="Vector search top-K")
    parser.add_argument("--save",   action="store_true", help="Save a timestamped snapshot to data/eval/history/")
    args = parser.parse_args()

    print(f"OntoMarket benchmark — top_k={args.top_k}")
    print("Running 5 questions against Neo4j + ChromaDB…")
    results = run_benchmark(top_k=args.top_k)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        _print_table(results)

    if args.save:
        path = _save_snapshot(results, args.top_k)
        print(f"Saved snapshot: {path.relative_to(Path(__file__).parents[2])}")


if __name__ == "__main__":
    main()
