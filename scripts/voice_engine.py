#!/usr/bin/env python3
"""
voice_engine.py — Unified ATS voice/TTS engine.

Single source of truth for Gemini TTS voice generation used by:
- Dashboard/manual voice generation from saved scripts
- Existing daily audio generation wrappers such as generate_audio_report.py

Policy:
- ATS default voice profile is ats_female_narrator = Gemini TTS Aoede.
- Voice is generated from saved script text/files; orchestration decides when scripts are created.
- Output is WAV only.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tempfile
import time
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

TTS_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_VOICE_PROFILE = "ats_female_narrator"
DEFAULT_VOICE = "Aoede"
DEFAULT_LANGUAGE_HINT = "th-TH"
SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2
CHANNELS = 1
MAX_TTS_CHARS = 4500

VOICE_PROFILES = {
    "ats_female_narrator": {
        "provider": "gemini",
        "model": TTS_MODEL,
        "voice": DEFAULT_VOICE,
        "language_hint": DEFAULT_LANGUAGE_HINT,
        "script_style": "Thai female narrator, warm, natural, conversational, uses ค่ะ",
    }
}


@dataclass
class VoiceMetadata:
    path: str
    script_path: str | None
    script_sha256: str
    voice_profile: str
    voice: str
    model: str
    language_hint: str
    chunks: int
    generated_at: str
    status: str = "ready"


def script_sha256(text: str) -> str:
    """Return SHA256 for saved script text, normalized only by exact file content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_script_text(text: str, script_type: str = "full") -> str:
    """Strip metadata header from a saved script .md file, returning only spoken content.

    Looks for a named section (## Full Script / ## Deep Dive Script) and returns
    its body. Falls back to stripping known metadata header lines.
    """
    text = (text or "").strip()
    if not text:
        return ""
    heading_map = {
        "full": r"^##\s+Full Script\s*$",
        "deep_dive": r"^##\s+Deep Dive Script\s*$",
    }
    pattern = heading_map.get(script_type, heading_map["full"])
    m = re.search(pattern + r"([\s\S]*?)(?=^##\s+|\Z)", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    # Fallback: strip known metadata header lines and H1 title
    lines = text.splitlines()
    while lines and (
        not lines[0].strip()
        or lines[0].startswith(("#", "Date:", "Topic:", "Video:", "Source:",
                                "แหล่งที่มา:", "หัวข้อ:", "เวอร์ชัน:"))
    ):
        lines.pop(0)
    return "\n".join(lines).strip() or text


def load_voice_profile(profile_name: str | None = None, *, voice_override: str | None = None) -> dict:
    """Load built-in voice profile, optionally overriding voice name for CLI compatibility."""
    name = profile_name or DEFAULT_VOICE_PROFILE
    profile = dict(VOICE_PROFILES.get(name, VOICE_PROFILES[DEFAULT_VOICE_PROFILE]))
    profile["name"] = name
    if voice_override:
        profile["voice"] = voice_override
    return profile


def chunk_script(text: str, max_chars: int = MAX_TTS_CHARS) -> list[str]:
    """Split text into Gemini-TTS-safe chunks at paragraph/sentence boundaries."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    # Prefer paragraph boundaries; fall back to Thai/English sentence punctuation.
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    units: list[str] = []
    for paragraph in paragraphs or [text]:
        if len(paragraph) <= max_chars:
            units.append(paragraph)
            continue
        parts = re.split(
            r"(?<=[.!?。！？])\s+|(?<=ค่ะ)\s+|(?<=ครับ)\s+|(?<=นะคะ)\s+|(?<=นะครับ)\s+",
            paragraph,
        )
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if len(part) <= max_chars:
                units.append(part)
            else:
                # Last resort: hard split very long text without natural boundaries.
                for i in range(0, len(part), max_chars):
                    units.append(part[i:i + max_chars].strip())

    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = unit if not current else current + "\n\n" + unit
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = unit
    if current:
        chunks.append(current)
    return chunks


def text_to_wav(text: str, output_path: str | Path, *, voice: str = DEFAULT_VOICE,
                model: str = TTS_MODEL, retry_count: int = 4) -> Path:
    """Call Gemini TTS and save a single text chunk as WAV."""
    project = os.environ.get("VERTEX_PROJECT_ID", "")
    location = os.environ.get("VERTEX_LOCATION", "us-central1")
    if not project:
        raise EnvironmentError("VERTEX_PROJECT_ID not set")

    from google import genai as _genai
    from google.genai.types import (
        GenerateContentConfig,
        PrebuiltVoiceConfig,
        SpeechConfig,
        VoiceConfig,
    )

    client = _genai.Client(vertexai=True, project=project, location=location)
    response = None
    for attempt in range(retry_count):
        try:
            response = client.models.generate_content(
                model=model,
                contents=text,
                config=GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=SpeechConfig(
                        voice_config=VoiceConfig(
                            prebuilt_voice_config=PrebuiltVoiceConfig(voice_name=voice)
                        )
                    ),
                ),
            )
            break
        except Exception as e:
            if ("429" in str(e) or "Connection reset" in str(e)) and attempt < retry_count - 1:
                wait = 30 * (2 ** attempt)
                print(f"  [voice] ⏳ TTS rate limit/reset — waiting {wait}s...")
                time.sleep(wait)
                continue
            raise

    if response is None:
        raise RuntimeError("No TTS response")
    raw = response.candidates[0].content.parts[0].inline_data.data
    audio_bytes = raw if isinstance(raw, bytes) else base64.b64decode(raw)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_bytes)
    return output


def concat_wavs(wav_paths: Sequence[str | Path], output_path: str | Path) -> Path:
    """Concatenate WAV files with ATS standard format into one output file."""
    frames = b""
    for path in wav_paths:
        with wave.open(str(path), "rb") as wf:
            frames += wf.readframes(wf.getnframes())

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(frames)
    return output


def generate_voice_from_text(script_text: str, output_path: str | Path, *,
                             script_path: str | Path | None = None,
                             raw_script_text: str | None = None,
                             voice_profile: str | None = None,
                             voice_override: str | None = None,
                             max_chars: int = MAX_TTS_CHARS,
                             metadata_path: str | Path | None = None,
                             pause_between_chunks: int = 8,
                             dry_run: bool = False) -> VoiceMetadata:
    """Generate WAV from saved/reviewed script text and write sidecar metadata.

    raw_script_text: full file content before extraction; used for sha256 so
    is_voice_stale() (which reads the raw file) stays consistent.
    """
    script_text = (script_text or "").strip()
    if not script_text:
        raise ValueError("Script text is empty")

    profile = load_voice_profile(voice_profile, voice_override=voice_override)
    chunks = chunk_script(script_text, max_chars=max_chars)
    output = Path(output_path)
    sha = script_sha256(raw_script_text if raw_script_text is not None else script_text)

    meta = VoiceMetadata(
        path=str(output),
        script_path=str(script_path) if script_path else None,
        script_sha256=sha,
        voice_profile=profile["name"],
        voice=profile["voice"],
        model=profile.get("model", TTS_MODEL),
        language_hint=profile.get("language_hint", DEFAULT_LANGUAGE_HINT),
        chunks=len(chunks),
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        status="dry_run" if dry_run else "ready",
    )

    if dry_run:
        return meta

    if len(chunks) == 1:
        text_to_wav(chunks[0], output, voice=profile["voice"], model=profile.get("model", TTS_MODEL))
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            seg_paths: list[Path] = []
            for idx, chunk in enumerate(chunks, start=1):
                if idx > 1 and pause_between_chunks > 0:
                    time.sleep(pause_between_chunks)
                seg = Path(tmpdir) / f"chunk_{idx:02d}.wav"
                print(f"  [voice] chunk {idx}/{len(chunks)} ({len(chunk)} chars) → TTS")
                text_to_wav(chunk, seg, voice=profile["voice"], model=profile.get("model", TTS_MODEL))
                seg_paths.append(seg)
            concat_wavs(seg_paths, output)

    meta_file = Path(metadata_path) if metadata_path else output.with_suffix(output.suffix + ".json")
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    meta_file.write_text(json.dumps(asdict(meta), ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def generate_voice_from_saved_script(script_path: str | Path, output_path: str | Path, **kwargs) -> VoiceMetadata:
    """Generate voice from an already saved script file. This is the canonical manual-flow entrypoint.

    Automatically strips metadata header (Date/Topic/Video/Source) so TTS only
    receives the spoken script content. sha256 is computed on the full raw file
    so is_voice_stale() stays consistent.
    """
    path = Path(script_path)
    if not path.exists():
        raise FileNotFoundError(f"Script missing — generate script first: {path}")
    script_type = kwargs.pop("script_type", "full")
    raw_text = path.read_text(encoding="utf-8")
    voice_text = extract_script_text(raw_text, script_type)
    if not voice_text:
        raise ValueError(f"No usable voice text found in script: {path}")
    return generate_voice_from_text(
        voice_text, output_path,
        script_path=path, raw_script_text=raw_text,
        **kwargs,
    )


def is_voice_stale(script_path: str | Path, metadata_path: str | Path) -> bool:
    """Return True when saved script hash differs from voice metadata hash."""
    sp = Path(script_path)
    mp = Path(metadata_path)
    if not sp.exists() or not mp.exists():
        return True
    current = script_sha256(sp.read_text(encoding="utf-8"))
    try:
        meta = json.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        return True
    return meta.get("script_sha256") != current


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate ATS WAV voice from a saved script")
    parser.add_argument("--script", required=True, help="Saved script text/markdown file")
    parser.add_argument("--output", required=True, help="Output WAV path")
    parser.add_argument("--voice-profile", default=DEFAULT_VOICE_PROFILE)
    parser.add_argument("--voice", default=None, help="Override Gemini prebuilt voice name")
    parser.add_argument("--script-type", default="full", choices=["full", "deep_dive"],
                        help="Script section to extract: full (default) or deep_dive")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    metadata = generate_voice_from_saved_script(
        args.script,
        args.output,
        voice_profile=args.voice_profile,
        voice_override=args.voice,
        script_type=args.script_type,
        dry_run=args.dry_run,
    )
    print(json.dumps(asdict(metadata), ensure_ascii=False, indent=2))
