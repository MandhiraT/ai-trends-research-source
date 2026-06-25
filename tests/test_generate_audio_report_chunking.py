from __future__ import annotations

import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_audio_report as gar


def _write_fake_wav(path: str | Path, frames: int = 2400) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(b"\x00\x00" * frames)


def test_text_to_wav_chunks_long_scripts_before_tts(monkeypatch, tmp_path):
    calls: list[str] = []

    def fake_text_to_wav(text, output_path, voice="Aoede", model=None, retry_count=4):
        calls.append(text)
        _write_fake_wav(output_path)
        return Path(output_path)

    monkeypatch.setattr(gar, "text_to_wav", fake_text_to_wav)
    monkeypatch.setattr(gar.time, "sleep", lambda *_args, **_kwargs: None)

    long_text = ("ประโยคสั้นเพื่อทดสอบการแบ่ง chunk ค่ะ " * 140).strip()
    output = tmp_path / "out.wav"
    gar._text_to_wav(long_text, str(output))

    assert output.exists()
    assert len(calls) >= 2
    assert all(len(chunk) <= gar.AUTO_TTS_SAFE_CHARS for chunk in calls)


def test_text_to_wav_keeps_short_scripts_single_request(monkeypatch, tmp_path):
    calls: list[str] = []

    def fake_text_to_wav(text, output_path, voice="Aoede", model=None, retry_count=4):
        calls.append(text)
        _write_fake_wav(output_path)
        return Path(output_path)

    monkeypatch.setattr(gar, "text_to_wav", fake_text_to_wav)

    short_text = "สคริปต์สั้นสำหรับทดสอบค่ะ"
    output = tmp_path / "short.wav"
    gar._text_to_wav(short_text, str(output))

    assert output.exists()
    assert calls == [short_text]
