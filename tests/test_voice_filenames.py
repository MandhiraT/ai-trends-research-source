from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from voice_filenames import topic_slug, voice_filename, voice_glob_patterns, find_voice_files


def test_topic_slug_normalizes_display_names():
    assert topic_slug("NATEHERK") == "nateherk"
    assert topic_slug("Joanna Wiebe") == "joanna_wiebe"
    assert topic_slug("claude-code design") == "claude_code_design"


def test_voice_filename_whole_and_per_video():
    assert voice_filename("NATEHERK", "2026-05-18", variant="whole") == "nateherk-2026-05-18.wav"
    assert voice_filename("NATEHERK", "2026-05-18", video_no=1) == "nateherk-2026-05-18-v1.wav"
    assert voice_filename("joanna_wiebe", "2026-05-18", video_no=2) == "joanna_wiebe-2026-05-18-v2.wav"


def test_voice_filename_deep_dive():
    assert voice_filename("Joanna Wiebe", "2026-05-15", video_no=1, variant="deep_dive") == "joanna_wiebe-2026-05-15-v1-deep-dive.wav"


def test_voice_glob_patterns_prefer_new_then_legacy():
    assert voice_glob_patterns("NATEHERK", "2026-05-18") == [
        "nateherk-2026-05-18-v*.wav",
        "nateherk-2026-05-18.wav",
        "2026-05-18-v*.wav",
        "2026-05-18.wav",
    ]


def test_find_voice_files_prefers_new_names_then_legacy(tmp_path):
    names = [
        "2026-05-18-v1.wav",
        "nateherk-2026-05-18-v1.wav",
        "nateherk-2026-05-18-v2.wav",
        "2026-05-18.wav",
    ]
    for name in names:
        (tmp_path / name).write_bytes(b"RIFFfake")

    found = [p.name for p in find_voice_files(tmp_path, "NATEHERK", "2026-05-18")]
    assert found == [
        "nateherk-2026-05-18-v1.wav",
        "nateherk-2026-05-18-v2.wav",
        "2026-05-18-v1.wav",
        "2026-05-18.wav",
    ]


def test_find_voice_files_nonexistent_dir_returns_empty(tmp_path):
    missing = tmp_path / "no_such_dir"
    assert find_voice_files(missing, "NATEHERK", "2026-05-18") == []
