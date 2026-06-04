from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dashboard.app import schedule_time_conflicts


def test_schedule_time_conflicts_reports_enabled_daily_jobs_at_same_time():
    jobs = [
        {
            "id": "existing_1500",
            "name": "Existing 15:00",
            "enabled": True,
            "daily_cron_enabled": True,
            "schedule_time": "15:00",
        },
        {
            "id": "disabled_1500",
            "name": "Disabled 15:00",
            "enabled": False,
            "daily_cron_enabled": True,
            "schedule_time": "15:00",
        },
        {
            "id": "manual_1500",
            "name": "Manual 15:00",
            "enabled": True,
            "daily_cron_enabled": False,
            "schedule_time": "15:00",
        },
        {
            "id": "other_time",
            "name": "Other Time",
            "enabled": True,
            "daily_cron_enabled": True,
            "schedule_time": "15:10",
        },
    ]

    conflicts = schedule_time_conflicts(jobs, "15:00", current_job_id="new_job")

    assert conflicts == [jobs[0]]


def test_schedule_time_conflicts_ignores_current_job():
    jobs = [
        {
            "id": "current",
            "name": "Current",
            "enabled": True,
            "daily_cron_enabled": True,
            "schedule_time": "15:00",
        }
    ]

    assert schedule_time_conflicts(jobs, "15:00", current_job_id="current") == []
