from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dashboard.app import report_date_key


def test_report_date_key_handles_daily_report_filename():
    assert report_date_key("2026-06-04.md", ".md") == "2026-06-04"


def test_report_date_key_handles_on_demand_timestamped_filename():
    assert (
        report_date_key(
            "2026-06-04_2320_use-claude-better-than-99-people_28TGfTZweqw.md",
            ".md",
        )
        == "2026-06-04"
    )


def test_report_date_key_keeps_non_date_filenames_searchable_by_stem():
    assert report_date_key("README.md", ".md") == "README"
