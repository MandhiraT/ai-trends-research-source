#!/usr/bin/env python3

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "config"))
try:
    from paths import PROJECT_ROOT, REPORTS_DIR, load_credentials
except ImportError:
    PROJECT_ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
    REPORTS_DIR = _os.path.join(PROJECT_ROOT, "ai_trends_reports")
    def load_credentials():
        return None

"""
Upload AI Trends Research reports to GitHub repository via API.

Uses GitHub Git Data API — no local git clone required.
Scales to any repo size: only uploads files that actually changed
by comparing git blob SHAs locally before making any API calls.
"""

import os
from datetime import datetime
from pathlib import Path

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from github_api_upload import upload_subtrees, ApiError

load_credentials()

REPORTS_SOURCE = _os.path.join(REPORTS_DIR, "reports")
DATE_STR = datetime.now().strftime("%Y-%m-%d")


def upload_reports() -> bool:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("❌ GITHUB_TOKEN not set")
        return False

    subtrees: list[tuple[Path, str]] = []

    reports_source = Path(REPORTS_SOURCE)
    if not reports_source.exists():
        print(f"❌ Reports source not found: {reports_source}")
        return False
    subtrees.append((reports_source, "reports"))

    joanna_source = Path(PROJECT_ROOT) / "joanna_wiebe_reports" / "joanna-wiebe"
    if joanna_source.exists():
        subtrees.append((joanna_source, "Content Marketing/Joanna-Wiebe"))

    total_local = sum(
        sum(1 for f in src.rglob("*") if f.is_file())
        for src, _ in subtrees
    )
    print(f"\n📊 Total local files: {total_local}")

    try:
        changed = upload_subtrees(
            token=token,
            subtrees=subtrees,
            commit_message=f"AI Trends Research Reports - {DATE_STR}",
        )
    except ApiError as exc:
        print(f"❌ API error: {exc}")
        return False

    if changed:
        print(f"\n✅ Successfully published reports to GitHub")
    return True


if __name__ == "__main__":
    if upload_reports():
        url = "https://github.com/MandhiraT/ai-trends-research/tree/master/reports"
        print(f"\n🔗 GitHub Reports URL: {url}")
    else:
        import sys
        sys.exit(1)
