"""Mandy's /reports?file=... inline preview (render_files(), the PLURAL route she
actually uses) was dumping raw escaped markdown text in a <pre> block instead of
rendering it — headers, bold, lists all showed as literal "# ", "**", "- " text.

Root cause: the .md branch of that inline preview never called the markdown
renderer that view_report()/view_full_detail()/render_single_report() already
use elsewhere in this dashboard.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.app import build_file_preview_html


def test_md_file_renders_as_formatted_html_not_raw_pre():
    text = "# Title\n\n**bold** and a list:\n\n- one\n- two\n"
    html = build_file_preview_html(text, "on_demand/research_job/2026-07-18.md", ".md")
    assert "<h1>Title</h1>" in html
    assert "<strong>bold</strong>" in html
    assert "<li>one</li>" in html
    assert "markdown-body" in html
    assert "<pre style=\"white-space:pre-wrap" not in html


def test_log_file_still_renders_as_plain_text_pre():
    # .log files go through the same render_files() function with suffix=".log"
    # and must keep showing raw text (no markdown parsing of log lines).
    text = "2026-07-18 08:07 INFO # not a heading\n**not bold**\n"
    html = build_file_preview_html(text, "dashboard.log", ".log")
    assert "<pre style=\"white-space:pre-wrap;word-break:break-word\">" in html
    assert "<h1>" not in html
    assert "<strong>" not in html


def test_selected_filename_is_escaped_in_heading():
    html = build_file_preview_html("body", "<script>x</script>.md", ".md")
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html
