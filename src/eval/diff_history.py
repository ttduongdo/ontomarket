"""
Diff two saved benchmark snapshots from data/eval/history/.

Usage
-----
    python -m src.eval.diff_history <old.json> <new.json>
    python -m src.eval.diff_history --latest-two   # diff the two most recent snapshots
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HISTORY_DIR = Path(__file__).parents[2] / "data" / "eval" / "history"

METRICS = [
    "graph_entity_recall",
    "graph_precision",
    "vector_entity_recall",
    "vector_chain_recall",
    "recall_delta",
]


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _latest_two() -> tuple[Path, Path]:
    snapshots = sorted(HISTORY_DIR.glob("*.json"))
    if len(snapshots) < 2:
        raise SystemExit(f"Need at least 2 snapshots in {HISTORY_DIR}, found {len(snapshots)}")
    return snapshots[-2], snapshots[-1]


def _fmt_delta(old: float, new: float) -> str:
    delta = round(new - old, 3)
    sign = "+" if delta >= 0 else ""
    return f"{old:>6.1%} -> {new:>6.1%}  ({sign}{delta:.1%})"


def diff(old_path: Path, new_path: Path) -> None:
    old = _load(old_path)
    new = _load(new_path)

    print(f"OLD: {old_path.name}  (top_k={old.get('top_k')})")
    print(f"NEW: {new_path.name}  (top_k={new.get('top_k')})")
    print()

    old_by_id = {q["id"]: q for q in old["questions"]}
    new_by_id = {q["id"]: q for q in new["questions"]}

    for qid in new_by_id:
        if qid not in old_by_id:
            print(f"[{qid}] new question, not present in old snapshot")
            continue
        o, n = old_by_id[qid], new_by_id[qid]
        print(f"[{qid}]")
        for metric in METRICS:
            if o.get(metric) is None or n.get(metric) is None:
                continue
            print(f"    {metric:<22} {_fmt_delta(o[metric], n[metric])}")
        print()

    if old.get("averages") and new.get("averages"):
        print("AVERAGES")
        for metric in METRICS:
            o_avg = old["averages"].get(metric)
            n_avg = new["averages"].get(metric)
            if o_avg is None or n_avg is None:
                continue
            print(f"    {metric:<22} {_fmt_delta(o_avg, n_avg)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diff two OntoMarket eval snapshots")
    parser.add_argument("old", nargs="?", help="Path to older snapshot JSON")
    parser.add_argument("new", nargs="?", help="Path to newer snapshot JSON")
    parser.add_argument("--latest-two", action="store_true", help="Diff the two most recent snapshots in data/eval/history/")
    args = parser.parse_args()

    if args.latest_two:
        old_path, new_path = _latest_two()
    elif args.old and args.new:
        old_path, new_path = Path(args.old), Path(args.new)
    else:
        parser.error("Provide old and new snapshot paths, or use --latest-two")

    diff(old_path, new_path)


if __name__ == "__main__":
    main()
