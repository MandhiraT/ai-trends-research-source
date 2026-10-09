import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_ai_trends_research_enhanced.py"
spec = importlib.util.spec_from_file_location("run_ai_trends_research_enhanced_hashes", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def _video(video_id: str, title: str):
    return {
        "id": video_id,
        "title": title,
        "description": f"description-{video_id}",
        "duration": 100,
    }


def test_only_successfully_processed_videos_are_marked_seen():
    selected = [_video("video-a", "A"), _video("video-b", "B"), _video("video-c", "C")]
    successful = [
        {"video_id": "video-a"},
        {"video_id": "video-c"},
    ]

    result = runner.processed_content_hashes(selected, successful)

    assert result == {
        runner.create_content_hash("A", "description-video-a", 100),
        runner.create_content_hash("C", "description-video-c", 100),
    }


def test_unselected_candidates_are_not_marked_seen():
    selected = [_video("video-a", "A")]
    successful = [{"video_id": "video-a"}]

    result = runner.processed_content_hashes(selected, successful)

    assert runner.create_content_hash("A", "description-video-a", 100) in result
    assert runner.create_content_hash("B", "description-video-b", 100) not in result


def test_successful_short_url_is_marked_seen_even_when_legacy_video_id_is_blank():
    selected = [_video("l7IU2eMQjVs", "Short")]
    successful = [
        {
            "video_id": "",
            "source_url": "https://www.youtube.com/shorts/l7IU2eMQjVs",
        }
    ]

    result = runner.processed_content_hashes(selected, successful)

    assert result == {
        runner.create_content_hash("Short", "description-l7IU2eMQjVs", 100)
    }


def test_extract_youtube_video_id_supports_watch_short_and_youtu_be_urls():
    assert runner.extract_youtube_video_id("https://youtube.com/watch?v=abc123_XYZ0") == "abc123_XYZ0"
    assert runner.extract_youtube_video_id("https://youtube.com/shorts/abc123_XYZ0") == "abc123_XYZ0"
    assert runner.extract_youtube_video_id("https://youtu.be/abc123_XYZ0?t=2") == "abc123_XYZ0"


def test_post_run_notification_command_targets_exact_report_and_requires_email_success(tmp_path):
    report = tmp_path / "2026-10-09_1234_marketing-3-videos.md"

    cmd = runner.build_post_run_notification_command("marketing", report)

    assert "--topic" in cmd
    assert cmd[cmd.index("--topic") + 1] == "marketing"
    assert "--report-path" in cmd
    assert cmd[cmd.index("--report-path") + 1] == str(report.resolve())
    assert "--email-only" in cmd
    assert "--require-sent" in cmd
