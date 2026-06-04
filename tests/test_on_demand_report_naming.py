import importlib.util
from datetime import datetime
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_ai_trends_research_enhanced.py"
spec = importlib.util.spec_from_file_location("run_ai_trends_research_enhanced", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
research = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research)


def test_daily_report_filename_stays_date_only():
    filename = research.build_report_filename(
        report_date="2026-06-04",
        generated_at=datetime(2026, 6, 4, 20, 45),
        on_demand=False,
        all_video_data=[{"title": "Ronny Chieng Address | Harvard Class Day 2026", "video_id": "ORq_Hi5dB-g"}],
        topic="Speech",
    )

    assert filename == "2026-06-04.md"


def test_on_demand_report_filename_uses_compact_readable_content_name():
    filename = research.build_report_filename(
        report_date="2026-06-04",
        generated_at=datetime(2026, 6, 4, 20, 45),
        on_demand=True,
        all_video_data=[{"title": "Ronny Chieng Address | Harvard Class Day 2026", "video_id": "ORq_Hi5dB-g"}],
        topic="Speech",
    )

    assert filename == "2026-06-04_2045_ronny-chieng-address-harvard-class-day_ORq_Hi5dB-g.md"
    assert len(filename) < 90


def test_on_demand_topic_search_filename_uses_topic_and_count():
    filename = research.build_report_filename(
        report_date="2026-06-04",
        generated_at=datetime(2026, 6, 4, 19, 47),
        on_demand=True,
        all_video_data=[
            {"title": "Obama Speech About AI", "video_id": "abc123"},
            {"title": "Jack Ma Speech About Future", "video_id": "def456"},
            {"title": "Leadership Keynote", "video_id": "ghi789"},
        ],
        topic="Speech",
    )

    assert filename == "2026-06-04_1947_speech-3-videos.md"


def test_compact_slug_removes_filler_and_keeps_meaning():
    slug = research.compact_title_slug("🔥 FULL VIDEO: How to Build Amazing AI Agents in 2026!!!", max_words=6)

    assert slug == "build-amazing-ai-agents-2026"
