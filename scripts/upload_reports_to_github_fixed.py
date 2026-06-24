#!/usr/bin/env python3

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "config"))
try:
    from paths import PROJECT_ROOT, REPORTS_DIR, GITHUB_TEMP_CLONE, load_credentials
except ImportError:
    PROJECT_ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
    REPORTS_DIR = _os.path.join(PROJECT_ROOT, "ai_trends_reports")
    GITHUB_TEMP_CLONE = _os.path.expanduser("~/.cache/ai-trends-research/github-output-repo")
    def load_credentials():
        return None

"""
Upload AI Trends Research reports to GitHub repository.

Permanent hardening decisions:
- do NOT reuse a long-lived git working tree from previous runs
- always clone a fresh output repo checkout before publishing
- stage only the touched report/content-marketing subtrees
- keep auth explicit via GITHUB_TOKEN rather than relying on a stale remote URL
"""

import os
from datetime import datetime
from pathlib import Path

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from github_output_repo import (
    GitRepoError,
    prepare_fresh_checkout,
    replace_tree,
    stage_paths,
    commit_and_push,
)

load_credentials()

GITHUB_REPO = "https://github.com/MandhiraT/ai-trends-research.git"
LOCAL_REPO_PATH = GITHUB_TEMP_CLONE
REPORTS_SOURCE = _os.path.join(REPORTS_DIR, "reports")
DATE_STR = datetime.now().strftime("%Y-%m-%d")


def upload_reports() -> bool:
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = prepare_fresh_checkout(GITHUB_REPO, LOCAL_REPO_PATH, token=token)

    reports_source = Path(REPORTS_SOURCE)
    if not reports_source.exists():
        print(f"❌ Reports source not found: {reports_source}")
        return False

    reports_dest = repo / "reports"
    replace_tree(reports_source, reports_dest)

    touched_paths = ["reports"]

    joanna_source = Path(PROJECT_ROOT) / "joanna_wiebe_reports" / "joanna-wiebe"
    if joanna_source.exists():
        joanna_dest = repo / "Content Marketing" / "Joanna-Wiebe"
        replace_tree(joanna_source, joanna_dest)
        touched_paths.append(str(Path("Content Marketing") / "Joanna-Wiebe"))

    uploaded_files = [str(p) for p in reports_dest.rglob("*") if p.is_file()]
    if joanna_source.exists():
        uploaded_files.extend(str(p) for p in (repo / "Content Marketing" / "Joanna-Wiebe").rglob("*") if p.is_file())

    if not uploaded_files:
        print("❌ No reports found")
        return False

    print(f"\n📊 Total files to upload: {len(uploaded_files)}")

    try:
        stage_paths(repo, touched_paths)
        changed = commit_and_push(repo, f"AI Trends Research Reports - {DATE_STR} (fresh clone publish)", token=token)
    except GitRepoError as exc:
        print(f"Git error: {exc}")
        return False

    if not changed:
        print("\n⚠️ No changes to commit - files already up to date")
        return True

    print(f"\n✅ Successfully uploaded {len(uploaded_files)} file(s) to GitHub")
    return True


if __name__ == "__main__":
    if upload_reports():
        url = "https://github.com/MandhiraT/ai-trends-research/tree/master/reports"
        print(f"\n🔗 GitHub Reports URL: {url}")
    else:
        import sys
        sys.exit(1)
