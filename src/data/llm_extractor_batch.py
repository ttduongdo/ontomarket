"""
Batch extraction runner — processes all articles in data/raw/sample_articles.json
and writes results to data/raw/extracted_edges.json.

Usage:
  python -m src.data.llm_extractor_batch

Options (env vars):
  BATCH_THRESHOLD=0.7   minimum confidence to keep an item (default 0.7)
  BATCH_LIMIT=0         max articles to process (0 = all)
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

from src.data.llm_extractor import extract, OUTPUT_FILE  # noqa: E402

ARTICLES_FILE = Path(__file__).parents[2] / "data" / "raw" / "sample_articles.json"
THRESHOLD     = float(os.getenv("BATCH_THRESHOLD", "0.7"))
LIMIT         = int(os.getenv("BATCH_LIMIT", "0"))

# Seconds to wait between API calls (avoids rate-limit bursts)
_RATE_DELAY = 1.0


def run_batch() -> None:
    articles = json.loads(ARTICLES_FILE.read_text())
    if LIMIT:
        articles = articles[:LIMIT]

    total   = len(articles)
    results = []
    errors  = []

    print(f"Processing {total} articles  (threshold={THRESHOLD})\n")

    for i, article in enumerate(articles, 1):
        art_id = article["id"]
        source = article.get("source", "")
        text   = article["text"]

        print(f"[{i:02d}/{total}] {art_id}  —  {source}")
        try:
            extracted = extract(text, threshold=THRESHOLD)
            results.append({
                "id":        art_id,
                "source":    source,
                "text":      text,
                "extracted": extracted,
            })
            _print_summary(extracted)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            errors.append({"id": art_id, "error": str(exc)})

        if i < total:
            time.sleep(_RATE_DELAY)

    # Write consolidated output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(results, indent=2))

    print(f"\n{'─' * 60}")
    print(f"Done.  {len(results)} extracted,  {len(errors)} errors")
    if errors:
        print("Errors:")
        for e in errors:
            print(f"  {e['id']}: {e['error']}")
    print(f"Output → {OUTPUT_FILE}")


def _print_summary(extracted: dict) -> None:
    counts = {k: len(v) for k, v in extracted.items()}
    parts  = [f"{v} {k.replace('_', ' ')}" for k, v in counts.items() if v]
    print(f"  → {', '.join(parts) if parts else 'nothing extracted'}")


if __name__ == "__main__":
    run_batch()
