from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "dashboard" / "app.py"


def load_app():
    spec = importlib.util.spec_from_file_location("ats_dashboard_app", APP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schedule_slot_options_disables_used_slots_but_keeps_current_slot_available():
    app = load_app()
    jobs = [
        {"id": "existing", "name": "Existing Job", "enabled": True, "daily_cron_enabled": True, "schedule_time": "12:00"},
        {"id": "current", "name": "Current Job", "enabled": True, "daily_cron_enabled": True, "schedule_time": "12:10"},
    ]

    html = app.schedule_slot_options(jobs, current_job_id="current", current_value="12:10")

    assert 'value="12:00"' in html
    assert '12:00 — used by Existing Job' in html
    assert 'value="12:00"  disabled' in html
    assert 'value="12:10" selected ' in html
    assert 'Manual only / no daily cron' in html


def test_build_command_enforces_count_for_channel_jobs():
    app = load_app()
    cmd = app.build_command({
        "id": "vidiq",
        "source_type": "channel",
        "topic": "VidIQ",
        "source_url": "https://youtube.com/@vidiq",
        "max_videos": 3,
        "report_folder": "vidiq",
        "detailed": True,
        "transcript_langs": ["en", "th", "all"],
    })

    assert "--max-results" in cmd
    assert cmd[cmd.index("--max-results") + 1] == "3"
    assert "--count" in cmd
    assert cmd[cmd.index("--count") + 1] == "3"
    assert "--transcript-langs" in cmd
    assert cmd[cmd.index("--transcript-langs") + 1] == "en,th,all"


def test_schedule_slot_values_are_dropdown_safe_cron_times():
    app = load_app()
    slots = app.schedule_slot_values()

    assert slots[0] == "05:00"
    assert slots[-1] == "23:50"
    assert "12:00" in slots
    assert "12:10" in slots
    assert all(len(slot) == 5 and slot[2] == ":" for slot in slots)


def test_report_folder_blank_auto_generates_from_topic():
    app = load_app()

    folder = app.normalize_report_folder_for_save(
        "", "VidIQ", "VidIQ", "https://youtube.com/@vidiq", "vidiq", is_on_demand=False
    )

    assert folder == "vidiq"


def test_report_folder_research_job_reserved_for_normal_daily_jobs():
    app = load_app()

    folder = app.normalize_report_folder_for_save(
        "research_job", "OpenAI Codex", "OpenAI Codex", "", "opeai_codex", is_on_demand=False
    )

    assert folder == "openai_codex"


def test_report_folder_research_job_allowed_for_on_demand_reference_job():
    app = load_app()

    folder = app.normalize_report_folder_for_save(
        "research_job", "Claude", "On Demand", "", "speech", is_on_demand=True
    )

    assert folder == "research_job"


def test_unique_report_folder_adds_suffix_to_prevent_overwrite():
    app = load_app()
    jobs = [{"id": "vidiq", "topic": "VidIQ", "report_folder": "vidiq"}]

    assert app.unique_report_folder("vidiq", jobs, current_job_id="new_vidiq") == "vidiq_2"
    assert app.unique_report_folder("vidiq", jobs, current_job_id="vidiq") == "vidiq"
