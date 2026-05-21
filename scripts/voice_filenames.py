from __future__ import annotations

import re
from pathlib import Path


def topic_slug(value: str) -> str:
    """Canonical topic slug for voice filenames/folders."""
    return str(value or "").strip().replace(" ", "_").replace("-", "_").lower()


def voice_filename(topic: str, date: str, *, video_no: int | None = None, variant: str = "full") -> str:
    """Return canonical ATS voice filename.

    variant:
    - "whole": {topic}-{date}.wav  (whole-day / legacy-compatible daily audio)
    - "full":  {topic}-{date}-vN.wav  (requires video_no)
    - "deep_dive": {topic}-{date}-vN-deep-dive.wav  (requires video_no)
    """
    slug = topic_slug(topic)
    if not slug or not re.match(r"^[a-z0-9_]+$", slug):
        raise ValueError(f"invalid topic slug: {topic!r}")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date or ""):
        raise ValueError(f"invalid date: {date!r}")

    if variant == "whole":
        return f"{slug}-{date}.wav"

    if video_no is None:
        raise ValueError("video_no is required for per-video voice filenames")
    vno = int(video_no)
    if vno < 1 or vno > 99:
        raise ValueError(f"invalid video number: {video_no!r}")

    if variant == "full":
        return f"{slug}-{date}-v{vno}.wav"
    if variant == "deep_dive":
        return f"{slug}-{date}-v{vno}-deep-dive.wav"
    raise ValueError(f"unknown voice filename variant: {variant!r}")


def voice_glob_patterns(topic: str, date: str, *, include_legacy: bool = True) -> list[str]:
    """Return preferred-new then fallback-legacy glob patterns for a topic/date.

    New patterns come first so new files are preferred over legacy ones.
    """
    slug = topic_slug(topic)
    patterns = [
        f"{slug}-{date}-v*.wav",
        f"{slug}-{date}.wav",
    ]
    if include_legacy:
        patterns.extend([
            f"{date}-v*.wav",
            f"{date}.wav",
        ])
    return patterns


def find_voice_files(topic_dir: Path, topic: str, date: str, *, include_legacy: bool = True) -> list[Path]:
    """Find voice files in deterministic order, preferring canonical filenames."""
    if not topic_dir.is_dir():
        return []
    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in voice_glob_patterns(topic, date, include_legacy=include_legacy):
        for path in sorted(topic_dir.glob(pattern)):
            if path not in seen:
                seen.add(path)
                files.append(path)
    return files
