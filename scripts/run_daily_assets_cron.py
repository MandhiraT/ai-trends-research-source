#!/usr/bin/env python3
"""Generate ATS content asset JSON for daily reports only.

Safe daily mode: asset JSON only, no AI social/audio generation.
Intended cron use after daily report jobs finish.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_content_assets import (  # noqa: E402
    ASSETS_DIR,
    REPORTS_ROOT,
    _slug,
    build_asset_from_report,
    save_asset,
)


def _valid_date(value: str) -> str:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", value or ""):
        raise argparse.ArgumentTypeError("date must be YYYY-MM-DD")
    return value


def _today() -> str:
    # Cron runs in Bangkok system timezone on Mandy's ATS host.
    return datetime.now().strftime("%Y-%m-%d")


def _asset_path_for(asset: dict, assets_dir: Path) -> Path:
    topic = asset.get("topic", "unknown")
    date = asset.get("date", "unknown")
    return assets_dir / _slug(topic) / f"{date}.json"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _today_reports(reports_root: Path, date: str) -> list[Path]:
    if not reports_root.exists():
        return []
    filename = f"{date}.md"
    return sorted(
        p for p in reports_root.rglob(filename)
        if p.is_file() and not any(part.startswith(".") for part in p.parts)
    )


def run_daily_assets(*, date: str, reports_root: Path, assets_dir: Path, force: bool = False, dry_run: bool = False) -> dict:
    reports = _today_reports(reports_root, date)
    result: dict = {
        "date": date,
        "reports_found": len(reports),
        "generated": 0,
        "skipped_existing": 0,
        "skipped_parse": 0,
        "errors": 0,
        "total_videos": 0,
        "assets": [],
    }

    for report_path in reports:
        rel_report = report_path.relative_to(reports_root).as_posix()
        try:
            asset = build_asset_from_report(report_path, reports_root)
            if not asset:
                result["skipped_parse"] += 1
                print(f"SKIP parse-empty {rel_report}")
                continue

            asset_path = _asset_path_for(asset, assets_dir)
            videos = int(asset.get("total_videos", 0) or 0)
            result["total_videos"] += videos

            if asset_path.exists() and not force:
                result["skipped_existing"] += 1
                print(f"SKIP existing {rel_report} -> {_display_path(asset_path)} ({videos} videos)")
                continue

            if dry_run:
                result["assets"].append(_display_path(asset_path))
                print(f"DRYRUN generate {rel_report} -> {_display_path(asset_path)} ({videos} videos)")
                continue

            saved_path = save_asset(asset, assets_dir)
            result["generated"] += 1
            result["assets"].append(_display_path(saved_path))
            print(f"OK generated {rel_report} -> {_display_path(saved_path)} ({videos} videos)")
        except Exception as exc:  # keep processing other reports; return non-zero at end
            result["errors"] += 1
            print(f"ERROR {rel_report}: {exc}", file=sys.stderr)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate asset-only JSON for today's ATS reports")
    parser.add_argument("--date", type=_valid_date, default=_today(), help="Report date YYYY-MM-DD (default: today)")
    parser.add_argument("--reports-root", default=str(REPORTS_ROOT), help="Reports root directory")
    parser.add_argument("--assets-dir", default=str(ASSETS_DIR), help="Assets output directory")
    parser.add_argument("--force", action="store_true", help="Overwrite existing asset JSON")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files")
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary JSON")
    args = parser.parse_args()

    reports_root = Path(args.reports_root).resolve()
    assets_dir = Path(args.assets_dir).resolve()
    result = run_daily_assets(
        date=args.date,
        reports_root=reports_root,
        assets_dir=assets_dir,
        force=args.force,
        dry_run=args.dry_run,
    )

    print(
        "SUMMARY "
        f"date={result['date']} reports={result['reports_found']} "
        f"generated={result['generated']} skipped_existing={result['skipped_existing']} "
        f"skipped_parse={result['skipped_parse']} errors={result['errors']} "
        f"videos={result['total_videos']}"
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
