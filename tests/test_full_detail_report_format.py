"""Mandy asked for Full Detail .md output to match the standard ATS report
shape (# AI Trends Research - ... metadata block, ## Video N:, ### Full
Summary section) instead of the old ad-hoc "# Full Detail: ..." plain
header with the raw on-demand filename stem shown as "Date:".
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.app import build_full_detail_report_content


def test_header_matches_standard_report_metadata_block_shape():
    content = build_full_detail_report_content(
        topic="research job", date="2026-07-18_0807_make-any-topic-addictive-social-media_LvuoNlYRs7g",
        video_no=1, video_title="How to Make ANY Topic Addictive on Social Media",
        thai_title="", source_url="https://www.youtube.com/watch?v=LvuoNlYRs7g",
        video_id="LvuoNlYRs7g", result_text="เนื้อหาภาษาไทย",
    )
    assert content.startswith("# AI Trends Research - research job\n\n")
    assert "**Date:**" in content
    assert "**Topic:** research job" in content
    assert "**Mode:** Full Detail" in content
    assert "**Videos Processed:** 1" in content
    assert "**Dashboard Job ID:**" in content


def test_date_field_uses_clean_date_prefix_not_the_full_on_demand_stem():
    # This was the actual bug reported: "Date:" showed the whole filename
    # stem (date+time+slug+video-id) instead of just the date.
    content = build_full_detail_report_content(
        topic="research job", date="2026-07-18_0807_make-any-topic-addictive-social-media_LvuoNlYRs7g",
        video_no=1, video_title="Title", thai_title="", source_url="https://x",
        video_id="abc", result_text="text",
    )
    assert "**Date:** 2026-07-18" in content
    assert "LvuoNlYRs7g" not in content.split("\n")[2]  # the Date line specifically


def test_date_field_works_for_a_plain_regular_report_date_too():
    content = build_full_detail_report_content(
        topic="AI Agents", date="2026-07-18", video_no=1, video_title="Title",
        thai_title="", source_url="https://x", video_id="abc", result_text="text",
    )
    assert "**Date:** 2026-07-18" in content


def test_video_section_matches_standard_report_shape():
    content = build_full_detail_report_content(
        topic="research job", date="2026-07-18", video_no=1,
        video_title="English Title", thai_title="ชื่อไทย",
        source_url="https://www.youtube.com/watch?v=abc123", video_id="abc123",
        result_text="เนื้อหา",
    )
    assert "## Video 1: ชื่อไทย" in content  # prefers thai_title, like standard reports
    assert "**Source:** https://www.youtube.com/watch?v=abc123" in content
    assert "**Video ID:** abc123" in content
    assert "### 📝 Full Summary (Thai)" in content
    assert "เนื้อหา" in content


def test_falls_back_to_video_title_when_no_thai_title():
    content = build_full_detail_report_content(
        topic="t", date="2026-07-18", video_no=2, video_title="English Only",
        thai_title="", source_url="https://x", video_id="abc", result_text="text",
    )
    assert "## Video 2: English Only" in content


def test_preserves_original_video_number_from_source_report():
    # A Full Detail file re-summarizes one specific video from a multi-video
    # daily report — the video number should reflect its position there.
    content = build_full_detail_report_content(
        topic="t", date="2026-07-18", video_no=3, video_title="Third video",
        thai_title="", source_url="https://x", video_id="abc", result_text="text",
    )
    assert "## Video 3: Third video" in content
