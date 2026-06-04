from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dashboard.app import build_command


def test_build_command_passes_on_demand_flag_from_job_config():
    cmd = build_command(
        {
            "id": "speech",
            "name": "On Demand",
            "enabled": True,
            "source_type": "video",
            "topic": "Speech",
            "source_url": "https://youtu.be/ORq_Hi5dB-g",
            "max_videos": 1,
            "detailed": True,
            "report_folder": "on_demand/research_job",
            "on_demand": True,
        }
    )

    assert "--on-demand" in cmd


def test_build_command_does_not_infer_on_demand_from_report_folder():
    cmd = build_command(
        {
            "id": "legacy_folder",
            "name": "Legacy Folder",
            "enabled": True,
            "source_type": "topic",
            "topic": "Speech",
            "max_videos": 1,
            "detailed": True,
            "report_folder": "on_demand/research_job",
            "on_demand": False,
        }
    )

    assert "--on-demand" not in cmd
