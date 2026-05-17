from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.app import _dedupe_asset_entries


def test_dedupe_asset_entries_merges_display_name_and_slug_folder_duplicates():
    entries = [
        {
            "topic": "Jacksons AI",
            "topic_folder": "jacksons_ai",
            "topic_raw": "Jacksons AI",
            "date": "2026-05-17",
            "path": "Jacksons AI/2026-05-17.json",
            "has_script_file": True,
            "has_voice_file": False,
            "has_social_file": False,
        },
        {
            "topic": "Jacksons AI",
            "topic_folder": "jacksons_ai",
            "topic_raw": "jacksons_ai",
            "date": "2026-05-17",
            "path": "jacksons_ai/2026-05-17.json",
            "has_script_file": False,
            "has_voice_file": True,
            "has_social_file": True,
        },
    ]

    deduped = _dedupe_asset_entries(entries)

    assert len(deduped) == 1
    only = deduped[0]
    assert only["topic_folder"] == "jacksons_ai"
    assert only["topic_raw"] == "jacksons_ai"
    assert only["path"] == "jacksons_ai/2026-05-17.json"
    assert only["has_script_file"] is True
    assert only["has_voice_file"] is True
    assert only["has_social_file"] is True


def test_dedupe_asset_entries_keeps_different_dates_and_topics_separate():
    entries = [
        {"topic_folder": "jacksons_ai", "topic_raw": "jacksons_ai", "date": "2026-05-17", "path": "jacksons_ai/2026-05-17.json"},
        {"topic_folder": "jacksons_ai", "topic_raw": "jacksons_ai", "date": "2026-05-18", "path": "jacksons_ai/2026-05-18.json"},
        {"topic_folder": "joanna_wiebe", "topic_raw": "joanna_wiebe", "date": "2026-05-17", "path": "joanna_wiebe/2026-05-17.json"},
    ]

    deduped = _dedupe_asset_entries(entries)

    assert len(deduped) == 3
