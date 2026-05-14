#!/usr/bin/env python3
"""Search AI Trends report index.

Build the index first:
  python3 scripts/build_report_index.py

Search examples:
  python3 scripts/search_reports.py "NATEHERK claude code"
  python3 scripts/search_reports.py --topic NATEHERK --keyword claude-code
  python3 scripts/search_reports.py --tag ai-coding
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from build_report_index import INDEX_DIR, load_jsonl, search_records  # noqa: E402


def _format_result(record: dict) -> str:
    tags = ", ".join(record.get("tags", [])) or "-"
    keywords = ", ".join(record.get("keywords_normalized", [])[:8]) or "-"
    lines = [
        f"{record.get('date')} | {record.get('topic')} | {record.get('video_title')}",
        f"  Thai title: {record.get('thai_title')}",
        f"  Summary: {record.get('summary_short')}",
        f"  Tags: {tags}",
        f"  Keywords: {keywords}",
        f"  Report: ai_trends_reports/reports/{record.get('report_path')}",
    ]
    if record.get("source_url"):
        lines.append(f"  Source: {record.get('source_url')}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search AI Trends report index")
    parser.add_argument("query", nargs="?", default="", help="Search terms, e.g. 'NATEHERK claude design'")
    parser.add_argument("--index", default=str(INDEX_DIR / "reports_index.jsonl"), help="Path to reports_index.jsonl")
    parser.add_argument("--topic", help="Filter by topic")
    parser.add_argument("--keyword", help="Filter by normalized keyword, e.g. claude-code")
    parser.add_argument("--tag", help="Filter by tag, e.g. ai-coding")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument("--json", action="store_true", help="Output JSON lines")
    args = parser.parse_args()

    records = load_jsonl(args.index)
    if not records:
        print(f"No index records found at {args.index}. Run: python3 scripts/build_report_index.py", file=sys.stderr)
        sys.exit(1)

    results = search_records(records, args.query, topic=args.topic, keyword=args.keyword, tag=args.tag)
    results = results[: args.limit]

    if args.json:
        import json
        for record in results:
            print(json.dumps(record, ensure_ascii=False, sort_keys=True))
        return

    print(f"Found {len(results)} result(s) for query={args.query!r}")
    if args.topic:
        print(f"Filter topic: {args.topic}")
    if args.keyword:
        print(f"Filter keyword: {args.keyword}")
    if args.tag:
        print(f"Filter tag: {args.tag}")
    print()
    for i, record in enumerate(results, 1):
        print(f"[{i}] " + _format_result(record))
        print()


if __name__ == "__main__":
    main()
