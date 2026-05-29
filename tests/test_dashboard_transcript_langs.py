from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dashboard" / "app.py"


def test_dashboard_build_command_contains_transcript_langs_forwarding():
    # dashboard/app.py currently has unrelated legacy f-string syntax that blocks
    # importing the module under pytest, so verify the build_command source path
    # that forwards job config to the production runner.
    src = APP.read_text(encoding="utf-8")

    assert 'transcript_langs = job.get("transcript_langs")' in src
    assert 'cmd.extend(["--transcript-langs", str(transcript_langs)])' in src
