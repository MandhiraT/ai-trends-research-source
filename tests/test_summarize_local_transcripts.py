import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import summarize_local


def test_get_youtube_transcript_uses_thai_captions_before_english(monkeypatch):
    calls = []

    def fake_run(cmd, capture_output, text, timeout):
        calls.append(cmd)
        output_prefix = cmd[cmd.index("--output") + 1]
        sub_lang = cmd[cmd.index("--sub-lang") + 1]
        if sub_lang == "th":
            Path(f"{output_prefix}.th.vtt").write_text(
                """WEBVTT
Kind: captions
Language: th

00:00:00.000 --> 00:00:01.000
สวัสดีครับ <c>นี่คือ</c> transcript ภาษาไทย
""",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 1, "", "no captions")

    monkeypatch.setattr(summarize_local.subprocess, "run", fake_run)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    transcript = summarize_local._get_youtube_transcript("https://www.youtube.com/watch?v=thai")

    assert "transcript ภาษาไทย" in transcript
    assert calls[0][calls[0].index("--sub-lang") + 1] == "th"


def test_get_youtube_transcript_falls_back_to_english_when_thai_missing(monkeypatch):
    calls = []

    def fake_run(cmd, capture_output, text, timeout):
        calls.append(cmd)
        output_prefix = cmd[cmd.index("--output") + 1]
        sub_lang = cmd[cmd.index("--sub-lang") + 1]
        if sub_lang == "en":
            Path(f"{output_prefix}.en.vtt").write_text(
                """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:01.000
English transcript is available
""",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 1, "", "missing")

    monkeypatch.setattr(summarize_local.subprocess, "run", fake_run)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    transcript = summarize_local._get_youtube_transcript("https://www.youtube.com/watch?v=en")

    assert "English transcript is available" in transcript
    used_langs = [call[call.index("--sub-lang") + 1] for call in calls]
    assert "th" in used_langs
    assert "en" in used_langs
