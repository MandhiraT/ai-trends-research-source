import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_ai_trends_research_enhanced as runner
import summarize_local


def _fake_vtt(output_prefix, lang, text):
    Path(f"{output_prefix}.{lang}.vtt").write_text(
        f"""WEBVTT
Kind: captions
Language: {lang}

00:00:00.000 --> 00:00:01.000
{text}
""",
        encoding="utf-8",
    )


def test_parse_transcript_langs_normalizes_and_keeps_all_fallback():
    assert runner.parse_transcript_langs(" en, th ") == ["en", "th", "all"]
    assert runner.parse_transcript_langs("th,en,all") == ["th", "en", "all"]
    assert runner.parse_transcript_langs("") is None


def test_process_video_passes_transcript_langs_to_summarize(monkeypatch):
    captured = {}

    class FakeMod:
        @staticmethod
        def summarize_video(video_url, prompt_file=None, language="th", topic="", transcript_langs=None):
            captured["video_url"] = video_url
            captured["topic"] = topic
            captured["transcript_langs"] = transcript_langs
            return "# Thai summary\n\n" + "x" * 600

    class FakeSpec:
        loader = None

    def fake_spec_from_file_location(*_args, **_kwargs):
        return FakeSpec()

    def fake_module_from_spec(_spec):
        return FakeMod

    monkeypatch.setattr(runner.importlib.util, "spec_from_file_location", fake_spec_from_file_location)
    monkeypatch.setattr(runner.importlib.util, "module_from_spec", fake_module_from_spec)
    monkeypatch.setattr(FakeSpec, "loader", type("L", (), {"exec_module": staticmethod(lambda _mod: None)})())

    data = runner.process_video_with_summarize(
        "https://www.youtube.com/watch?v=abc",
        "Self Help Example",
        "Example video",
        detailed=True,
        transcript_langs=["en", "th", "all"],
    )

    assert data["raw_summary"].startswith("# Thai summary")
    assert captured["transcript_langs"] == ["en", "th", "all"]


def test_get_youtube_transcript_uses_explicit_english_before_thai(monkeypatch):
    calls = []

    def fake_run(cmd, capture_output, text, timeout):
        calls.append(cmd)
        output_prefix = cmd[cmd.index("--output") + 1]
        sub_lang = cmd[cmd.index("--sub-lang") + 1]
        if sub_lang == "en":
            _fake_vtt(output_prefix, "en", "English source transcript")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 1, "", "too many requests")

    monkeypatch.setattr(summarize_local.subprocess, "run", fake_run)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    transcript = summarize_local._get_youtube_transcript(
        "https://www.youtube.com/watch?v=english",
        preferred_langs=["en", "th", "all"],
    )

    assert "English source transcript" in transcript
    assert calls[0][calls[0].index("--sub-lang") + 1] == "en"


def test_summarize_video_uses_explicit_transcript_langs_without_topic_heuristic(monkeypatch, tmp_path):
    captured = {}

    def fake_get_transcript(video_url, preferred_langs=None):
        captured["preferred_langs"] = preferred_langs
        return "source transcript"

    def fake_call_provider(provider, prompt, system_prompt=""):
        return "สรุปภาษาไทย"

    prompt = tmp_path / "prompt.txt"
    prompt.write_text("system prompt", encoding="utf-8")

    monkeypatch.setattr(summarize_local, "_get_youtube_transcript", fake_get_transcript)
    monkeypatch.setattr(summarize_local, "_call_provider", fake_call_provider)

    result = summarize_local.summarize_video(
        "https://www.youtube.com/watch?v=explicit",
        prompt_file=str(prompt),
        language="th",
        topic="Any Topic Name",
        transcript_langs=["en", "th", "all"],
    )

    assert result == "สรุปภาษาไทย"
    assert captured["preferred_langs"] == ["en", "th", "all"]
