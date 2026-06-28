"""
scripts/ingest.py
Run this once (or whenever you add new data) to seed ChromaDB.

Usage:
  python scripts/ingest.py                          # ingests sample data
  python scripts/ingest.py --slack path/to/export.json
  python scripts/ingest.py --notion path/to/export.md
  python scripts/ingest.py --reset                  # wipe + re-ingest
"""

import argparse
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag_engine import ingest_notion, ingest_slack, reset_collection, collection_stats


def main():
    parser = argparse.ArgumentParser(description="Ingest documents into the knowledge base.")
    parser.add_argument("--slack", default="data/sample/slack_export.json", help="Path to Slack export JSON")
    parser.add_argument("--notion", default="data/sample/notion_export.md", help="Path to Notion export MD")
    parser.add_argument("--reset", action="store_true", help="Wipe the knowledge base before ingesting")
    args = parser.parse_args()

    if args.reset:
        print("Resetting knowledge base...")
        reset_collection()

    total = 0

    if Path(args.slack).exists():
        print(f"\nIngesting Slack export: {args.slack}")
        n = ingest_slack(args.slack)
        print(f"  ✓ {n} chunks stored from Slack")
        total += n
    else:
        print(f"  ✗ Slack file not found: {args.slack}")

    if Path(args.notion).exists():
        print(f"\nIngesting Notion export: {args.notion}")
        n = ingest_notion(args.notion)
        print(f"  ✓ {n} chunks stored from Notion")
        total += n
    else:
        print(f"  ✗ Notion file not found: {args.notion}")

    print(f"\n{'─'*40}")
    stats = collection_stats()
    print(f"Total chunks in knowledge base: {stats['total_chunks']}")
    print(f"ChromaDB path: {stats['chroma_path']}")
    print(f"\nDone! Ingested {total} new chunks.")
    print("\nTest a query:")
    print("  curl -X POST http://localhost:8000/query \\")
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"query": "What is the leave policy?"}\'')


if __name__ == "__main__":
    main()
