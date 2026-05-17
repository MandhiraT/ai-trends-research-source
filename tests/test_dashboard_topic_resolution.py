from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dashboard.app import _resolve_report_path
from generate_content_assets import find_reports


def test_resolve_report_path_handles_nested_underscore_topic():
    report_path, topic_slug = _resolve_report_path("claude_code_design", "2026-05-17")

    assert report_path is not None
    assert report_path.relative_to(ROOT / "ai_trends_reports" / "reports").as_posix() == "claude_code/claude_code_design/2026-05-17.md"
    assert topic_slug == "claude_code_design"


def test_resolve_report_path_does_not_fallback_to_unrelated_topic():
    report_path, topic_slug = _resolve_report_path("claude_cdoe_design", "2026-05-17")

    assert report_path is None
    assert topic_slug == "claude_cdoe_design"


def test_find_reports_handles_nested_underscore_topic():
    reports = find_reports("claude_code_design", ROOT / "ai_trends_reports" / "reports")

    assert reports
    assert all(p.parent.name == "claude_code_design" for p in reports)
    assert any(p.name == "2026-05-17.md" for p in reports)


def test_find_reports_does_not_return_unrelated_topic_for_typo():
    reports = find_reports("claude_cdoe_design", ROOT / "ai_trends_reports" / "reports")

    assert reports == []
