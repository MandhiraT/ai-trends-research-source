# ATS Voice Filename Unification Handoff Plan

> **For Claude Code:** Implement this plan carefully, task-by-task. This is a production ATS workflow used by daily cron, Dashboard manual generation, GitHub publishing, and Telegram notifications. Do **not** run expensive real TTS or full ATS generation unless Mandy explicitly approves.

**Date prepared:** 2026-05-18  
**Prepared by:** มะลิ / Hermes  
**Goal:** Make ATS voice filenames unique across topics by including the canonical topic slug in the WAV filename, consistently across cron automation and Dashboard/manual content asset flows.

**Current problem:** Voice files are currently named mostly by date only, e.g. `2026-05-18-v1.wav`. Because each topic stores files in separate folders, GitHub paths are unique, but downloaded files collide on Mandy's machine. Example: downloading `voice/nateherk/2026-05-18-v1.wav` and `voice/joanna_wiebe/2026-05-18-v1.wav` produces the same local filename.

**Target naming convention:**

```text
{topic_slug}-{YYYY-MM-DD}.wav                         # whole-day / legacy-compatible daily audio
{topic_slug}-{YYYY-MM-DD}-v{N}.wav                    # normal/full per-video voice
{topic_slug}-{YYYY-MM-DD}-v{N}-deep-dive.wav          # deep-dive per-video voice
```

Examples:

```text
nateherk-2026-05-18-v1.wav
nateherk-2026-05-18-v2.wav
joanna_wiebe-2026-05-18-v1.wav
joanna_wiebe-2026-05-15-v1-deep-dive.wav
```

---

## Important Context / Constraints

1. **Do not change prompts in this task.** Mandy only asked for filename uniqueness. A separate caveat exists: daily cron audio (`generate_audio_report.py`) and Dashboard/content asset manual script flow still have different prompt paths. Record/keep that in mind, but do not fix prompt behavior here unless separately approved.
2. **Do not run real Gemini TTS unless Mandy approves.** Real TTS costs API quota and may publish artifacts.
3. **Do not push unless Mandy asks.** Implement locally, run non-expensive tests, then report status.
4. **Voice format stays `.wav` or `.mp4` only.** ATS voice output must never be `.ogg`.
5. **All ATS outputs remain Thai.** This task should not alter Thai report/audio/social content.
6. **Use Gemini TTS / Aoede only if a real voice test is explicitly approved.** Use dry-run/unit tests for normal verification.
7. **Backward compatibility matters.** Existing files in output repo and local folders use old names. The code must read both old and new naming during transition.
8. **Avoid broad file moves.** Do not rename historical files in `/tmp/ai-trends-research` unless Mandy specifically asks for a migration.
9. **Source repo:** `/home/mandhira/Desktop/Projects/ai-trends-research-source`
10. **Output repo clone:** `/tmp/ai-trends-research`
11. **Output repo remote:** `https://github.com/MandhiraT/ai-trends-research`

---

## Current Code Findings

### Cron auto voice generation

File: `scripts/generate_audio_report.py`

Current behavior:

```text
whole-file: ai_trends_reports/audio/{topic}/{date}.wav
per-video:  ai_trends_reports/audio/{topic}/{date}-v{N}.wav
scripts:    ai_trends_reports/audio_scripts/{topic}/{date}-v{N}.md
```

Relevant locations observed:

```text
scripts/generate_audio_report.py:214 output_path = AUDIO_DIR/topic_key/{date}.wav
scripts/generate_audio_report.py:217 skip_path = AUDIO_DIR/topic_key/{date}-v1.wav in per-video mode
scripts/generate_audio_report.py:271 script_path = audio_scripts/{topic}/{date}-v{N}.md
scripts/generate_audio_report.py:337 wav_path = audio_dir/{date}-v{N}.wav
```

### Cron upload to GitHub

File: `scripts/upload_audio_to_github.py`

Current behavior:

```text
source: ai_trends_reports/audio/{topic}/{date}*.wav
dest:   /tmp/ai-trends-research/voice/{topic_slug}/{same_filename}
```

Relevant locations observed:

```text
scripts/upload_audio_to_github.py:69-71 matches f'{date_str}*.wav'
scripts/upload_audio_to_github.py:80-83 copies basename unchanged
scripts/upload_audio_to_github.py:89-105 copies matching audio scripts, not WAV naming-sensitive except script filename pattern
```

### Telegram daily audio status

File: `scripts/ai_trends_daily_summary_thai.py`

Current behavior:

```text
checks ai_trends_reports/audio/{topic}/ for name.startswith(date_str) and name.endswith('.wav')
```

Relevant locations observed:

```text
scripts/ai_trends_daily_summary_thai.py:92-126 build_audio_status()
scripts/ai_trends_daily_summary_thai.py:116 name.startswith(date_str)
```

If filename changes to `{topic_slug}-{date}-...`, this will report missing audio unless updated.

### Dashboard manual voice generation

File: `dashboard/app.py`

Current behavior:

```text
full voice:      ai_trends_reports/voice/{topic}/{date}-v{N}.wav
deep-dive voice: ai_trends_reports/voice/{topic}/{date}-v{N}-deep-dive.wav
```

Relevant locations observed:

```text
dashboard/app.py:744-774 _voice_script_paths()
dashboard/app.py:934-959 api_assets_generate_voice() returns voice_path
dashboard/app.py:819,844 metadata sidecar is Path(str(voice_path) + '.json')
```

### Dashboard table/download behavior

File: `dashboard/app.py`

Current behavior:

```text
render_assets() checks audio_base = ai_trends_reports/audio and glob(f'{date}*.wav')
/api/audio/serve serves from ai_trends_reports/audio/{topic}/ and sets Content-Disposition filename to wav_path.name
/api/audio/serve candidate patterns: {date}-v*.wav, {date}.wav
```

Relevant locations observed:

```text
dashboard/app.py:979 audio_base = PROJECT_ROOT / 'ai_trends_reports' / 'audio'
dashboard/app.py:998-999 script/voice status in table
dashboard/app.py:1761-1790 api_audio_serve()
dashboard/app.py:1777 candidate glob(f'{date}-v*.wav') + glob(f'{date}.wav')
dashboard/app.py:1788 Content-Disposition filename uses basename
```

This is the most visible user problem: browser download receives duplicate basenames.

### Unified TTS engine

File: `scripts/voice_engine.py`

`voice_engine.generate_voice_from_text()` accepts an output path from callers and writes WAV + metadata. It does not decide filenames by itself. Filename changes should be made in callers / shared helper, not inside low-level TTS logic.

---

## Recommended Architecture

Create one small shared filename helper, then use it everywhere. Do not duplicate string formatting in four separate files.

Recommended new module:

```text
scripts/voice_filenames.py
```

Why under `scripts/`:

- `dashboard/app.py` already inserts `scripts/` into `sys.path` in this project.
- Existing tests import modules from `scripts/` by adding `ROOT / 'scripts'`.
- Keeps filename policy near voice/report scripts.

### Required helper behavior

Implement functions roughly like this:

```python
from __future__ import annotations

import re
from pathlib import Path


def topic_slug(value: str) -> str:
    """Canonical topic slug for voice filenames/folders."""
    return str(value or "").strip().replace(" ", "_").replace("-", "_").lower()


def voice_filename(topic: str, date: str, *, video_no: int | None = None, variant: str = "full") -> str:
    """Return canonical ATS voice filename.

    variant:
    - "whole" or None: {topic}-{date}.wav
    - "full": {topic}-{date}-vN.wav; requires video_no
    - "deep_dive": {topic}-{date}-vN-deep-dive.wav; requires video_no
    """
    slug = topic_slug(topic)
    if not slug or not re.match(r"^[a-z0-9_]+$", slug):
        raise ValueError(f"invalid topic slug: {topic!r}")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date or ""):
        raise ValueError(f"invalid date: {date!r}")

    if variant in ("whole", None):
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

    Used by upload/status/download. New patterns must come first so new files are preferred.
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
    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in voice_glob_patterns(topic, date, include_legacy=include_legacy):
        for path in sorted(topic_dir.glob(pattern)):
            if path not in seen:
                seen.add(path)
                files.append(path)
    return files
```

Keep this helper intentionally narrow. Do not add unrelated voice/TTS logic.

---

## Implementation Tasks

### Task 0 — Pre-flight checks, no code changes

**Objective:** Confirm working tree and current status before edits.

**Commands:**

```bash
cd /home/mandhira/Desktop/Projects/ai-trends-research-source
git status --short --branch
git remote -v
python3 --version
```

**Expected:**

- Source repo should be on `main` and ideally clean before starting.
- If dirty files exist, inspect them before editing. Do not overwrite another agent's changes.
- Do not touch `/tmp/ai-trends-research` except read-only unless Mandy approves publish/migration.

---

### Task 1 — Add filename helper + unit tests

**Objective:** Create one shared source of truth for voice filenames and legacy fallback matching.

**Files:**

- Create: `scripts/voice_filenames.py`
- Create: `tests/test_voice_filenames.py`

**Tests to add first:**

```python
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from voice_filenames import topic_slug, voice_filename, voice_glob_patterns, find_voice_files


def test_topic_slug_normalizes_display_names():
    assert topic_slug("NATEHERK") == "nateherk"
    assert topic_slug("Joanna Wiebe") == "joanna_wiebe"
    assert topic_slug("claude-code design") == "claude_code_design"


def test_voice_filename_whole_and_per_video():
    assert voice_filename("NATEHERK", "2026-05-18", variant="whole") == "nateherk-2026-05-18.wav"
    assert voice_filename("NATEHERK", "2026-05-18", video_no=1) == "nateherk-2026-05-18-v1.wav"
    assert voice_filename("joanna_wiebe", "2026-05-18", video_no=2) == "joanna_wiebe-2026-05-18-v2.wav"


def test_voice_filename_deep_dive():
    assert voice_filename("Joanna Wiebe", "2026-05-15", video_no=1, variant="deep_dive") == "joanna_wiebe-2026-05-15-v1-deep-dive.wav"


def test_voice_glob_patterns_prefer_new_then_legacy():
    assert voice_glob_patterns("NATEHERK", "2026-05-18") == [
        "nateherk-2026-05-18-v*.wav",
        "nateherk-2026-05-18.wav",
        "2026-05-18-v*.wav",
        "2026-05-18.wav",
    ]


def test_find_voice_files_prefers_new_names_then_legacy(tmp_path):
    names = [
        "2026-05-18-v1.wav",
        "nateherk-2026-05-18-v1.wav",
        "nateherk-2026-05-18-v2.wav",
        "2026-05-18.wav",
    ]
    for name in names:
        (tmp_path / name).write_bytes(b"RIFFfake")

    found = [p.name for p in find_voice_files(tmp_path, "NATEHERK", "2026-05-18")]
    assert found == [
        "nateherk-2026-05-18-v1.wav",
        "nateherk-2026-05-18-v2.wav",
        "2026-05-18-v1.wav",
        "2026-05-18.wav",
    ]
```

**Run:**

```bash
python3 -m pytest tests/test_voice_filenames.py -q
```

**Expected:** PASS after implementation.

---

### Task 2 — Update cron auto generation filenames

**Objective:** Make daily automated voice files use the new canonical topic-prefixed filenames.

**File:**

- Modify: `scripts/generate_audio_report.py`

**Required changes:**

1. Import helper with a safe import pattern compatible with running as script:

```python
from voice_filenames import voice_filename
```

If import fails because `scripts/` path is not present, add `SCRIPT_DIR` to `sys.path` near existing config import setup.

2. Replace whole-file output path:

Current:

```python
output_path = os.path.join(AUDIO_DIR, topic_key, f'{date_str}.wav')
```

Target:

```python
output_path = os.path.join(AUDIO_DIR, topic_key, voice_filename(topic_key, date_str, variant="whole"))
```

3. Replace per-video skip sentinel:

Current:

```python
skip_path = os.path.join(AUDIO_DIR, topic_key, f'{date_str}-v1.wav') if per_video else output_path
```

Target:

```python
skip_path = os.path.join(AUDIO_DIR, topic_key, voice_filename(topic_key, date_str, video_no=1)) if per_video else output_path
```

4. Update skip log label from hardcoded old filename to `os.path.basename(skip_path)`.

5. Replace per-video output path:

Current:

```python
wav_path = os.path.join(audio_dir, f'{date_str}-v{video_num}.wav')
print(f'... TTS → {date_str}-v{video_num}.wav...')
```

Target:

```python
fname = voice_filename(topic_key, date_str, video_no=video_num)
wav_path = os.path.join(audio_dir, fname)
print(f'... TTS → {fname}...')
```

**Important:** Do not rename `audio_scripts/{topic}/{date}-vN.md` in this task. Script filenames do not collide in download flow and are referenced by many existing docs/UI paths. Only WAV filenames need topic prefix.

**Tests to add/update:**

Create or extend a lightweight source-level test, e.g. `tests/test_voice_filename_integration.py`, to assert old hardcoded patterns are no longer used in output WAV creation.

Suggested tests:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATE_AUDIO = ROOT / "scripts" / "generate_audio_report.py"


def test_generate_audio_report_uses_voice_filename_helper_for_wavs():
    source = GENERATE_AUDIO.read_text(encoding="utf-8")
    assert "from voice_filenames import" in source
    assert "voice_filename(topic_key, date_str, variant=\"whole\")" in source
    assert "voice_filename(topic_key, date_str, video_no=video_num)" in source
    assert "f'{date_str}-v{video_num}.wav'" not in source
```

**Run:**

```bash
python3 -m pytest tests/test_voice_filenames.py tests/test_voice_filename_integration.py -q
/usr/bin/python3 -m py_compile scripts/voice_filenames.py scripts/generate_audio_report.py
```

---

### Task 3 — Update upload matching for new + legacy filenames

**Objective:** Ensure `upload_audio_to_github.py` finds canonical new filenames and still picks up old files during transition.

**File:**

- Modify: `scripts/upload_audio_to_github.py`

**Required changes:**

1. Import helper:

```python
from voice_filenames import find_voice_files
```

2. Replace the current single glob:

Current:

```python
wav_files = sorted(_glob.glob(os.path.join(topic_audio_dir, f'{date_str}*.wav')))
```

Target pattern:

```python
wav_files = [str(p) for p in find_voice_files(Path(topic_audio_dir), topic, date_str)]
```

3. Add `from pathlib import Path`.

4. Keep destination logic unchanged: copy basename into `voice/{dest_folder}/`. The basename will now be unique.

**Tests to add/update:**

In `tests/test_voice_filename_integration.py` add source-level test:

```python
UPLOAD_AUDIO = ROOT / "scripts" / "upload_audio_to_github.py"


def test_upload_audio_uses_legacy_aware_voice_file_finder():
    source = UPLOAD_AUDIO.read_text(encoding="utf-8")
    assert "find_voice_files" in source
    assert "f'{date_str}*.wav'" not in source
```

**Run:**

```bash
python3 -m pytest tests/test_voice_filenames.py tests/test_voice_filename_integration.py -q
/usr/bin/python3 -m py_compile scripts/upload_audio_to_github.py
```

---

### Task 4 — Update daily Telegram audio status matching

**Objective:** Prevent Telegram summary from saying audio is missing after filenames change.

**File:**

- Modify: `scripts/ai_trends_daily_summary_thai.py`

**Required changes:**

1. Import helper:

```python
from pathlib import Path
from voice_filenames import find_voice_files
```

2. Replace manual `os.listdir()` + `name.startswith(date_str)` logic with helper:

Current:

```python
wav_files = sorted(
    _os.path.join(topic_audio_dir, name)
    for name in _os.listdir(topic_audio_dir)
    if name.startswith(date_str) and name.endswith('.wav')
)
```

Target:

```python
wav_files = [str(p) for p in find_voice_files(Path(topic_audio_dir), topic, date_str)]
```

3. Update docstring to mention both canonical and legacy accepted names.

**Tests to add/update:**

Add source-level or functional test. Functional preferred if easy:

```python
# tests/test_voice_filename_integration.py
DAILY_SUMMARY = ROOT / "scripts" / "ai_trends_daily_summary_thai.py"


def test_daily_summary_uses_legacy_aware_voice_file_finder():
    source = DAILY_SUMMARY.read_text(encoding="utf-8")
    assert "find_voice_files" in source
    assert "name.startswith(date_str)" not in source
```

**Run:**

```bash
python3 -m pytest tests/test_voice_filenames.py tests/test_voice_filename_integration.py -q
/usr/bin/python3 -m py_compile scripts/ai_trends_daily_summary_thai.py
```

---

### Task 5 — Update Dashboard manual voice path filenames

**Objective:** Manual Dashboard-generated voice files also use topic-prefixed canonical filenames.

**File:**

- Modify: `dashboard/app.py`

**Required changes in `_voice_script_paths()`:**

Current:

```python
if script_type == "deep_dive":
    script_path = audio_scripts_base / actual_scripts_folder / f"{date}-v{vno}-deep-dive.md"
    voice_path  = voice_base / actual_voice_folder / f"{date}-v{vno}-deep-dive.wav"
else:
    script_path = audio_scripts_base / actual_scripts_folder / f"{date}-v{vno}.md"
    voice_path  = voice_base / actual_voice_folder / f"{date}-v{vno}.wav"
```

Target:

```python
from voice_filenames import voice_filename

if script_type == "deep_dive":
    script_path = audio_scripts_base / actual_scripts_folder / f"{date}-v{vno}-deep-dive.md"
    voice_path  = voice_base / actual_voice_folder / voice_filename(actual_voice_folder, date, video_no=vno, variant="deep_dive")
else:
    script_path = audio_scripts_base / actual_scripts_folder / f"{date}-v{vno}.md"
    voice_path  = voice_base / actual_voice_folder / voice_filename(actual_voice_folder, date, video_no=vno)
```

**Important:** Keep script filenames unchanged (`{date}-vN.md`, `{date}-vN-deep-dive.md`). Mandy edits/reviews scripts by those names already.

**Metadata impact:** Metadata sidecars are based on `voice_path`, so new files will get:

```text
nateherk-2026-05-18-v1.wav.json
joanna_wiebe-2026-05-15-v1-deep-dive.wav.json
```

No separate metadata change should be needed.

**Tests to add/update:**

Extend `tests/test_voice_filename_integration.py`:

```python
DASHBOARD_APP = ROOT / "dashboard" / "app.py"


def test_dashboard_voice_paths_use_topic_prefixed_helper():
    source = DASHBOARD_APP.read_text(encoding="utf-8")
    path_fn_start = source.index("def _voice_script_paths")
    path_fn_end = source.index("def _extract_voice_text", path_fn_start)
    body = source[path_fn_start:path_fn_end]
    assert "voice_filename" in body
    assert 'f"{date}-v{vno}.wav"' not in body
    assert 'f"{date}-v{vno}-deep-dive.wav"' not in body
```

**Run:**

```bash
python3 -m pytest tests/test_voice_filename_integration.py tests/test_dashboard_deep_dive_workflow.py -q
/usr/bin/python3 -m py_compile dashboard/app.py
```

---

### Task 6 — Update Dashboard asset table voice status + download endpoint

**Objective:** Dashboard should detect and serve both new and legacy cron audio files, preferring new canonical names so downloads are unique.

**File:**

- Modify: `dashboard/app.py`

**Required changes:**

1. Import helper:

```python
from voice_filenames import find_voice_files
```

2. In `render_assets()`, replace:

```python
has_voice_file  = bool(audio_dir and list(audio_dir.glob(f"{date}*.wav")))
```

with:

```python
has_voice_file = bool(audio_dir and find_voice_files(audio_dir, topic_folder, date))
```

Be careful: `topic_folder` is already a slug; `raw_name` may be display/case. Either is okay if helper slugs it, but use `topic_folder` for consistency.

3. In `api_audio_serve()`, replace:

```python
candidates = sorted(topic_dir.glob(f"{date}-v*.wav")) + list(topic_dir.glob(f"{date}.wav"))
```

with:

```python
candidates = find_voice_files(topic_dir, topic, date)
```

4. Keep `Content-Disposition` unchanged. Since `fname = wav_path.name`, it will now return unique download names when canonical files exist.

**Legacy behavior required:** If only old `2026-05-18-v1.wav` exists, Dashboard should still serve it. If both new and old exist, Dashboard should serve new first.

**Tests to add/update:**

Source-level test:

```python
def test_dashboard_download_uses_legacy_aware_voice_file_finder():
    source = DASHBOARD_APP.read_text(encoding="utf-8")
    audio_serve_start = source.index("def api_audio_serve")
    social_start = source.index("def api_social_view", audio_serve_start)
    body = source[audio_serve_start:social_start]
    assert "find_voice_files" in body
    assert 'glob(f"{date}-v*.wav")' not in body
    assert 'glob(f"{date}.wav")' not in body
```

Optional functional test if time allows:

- Create temp audio dir with both legacy and canonical file names.
- Assert helper returns canonical first.
- The helper unit test from Task 1 already covers this core behavior.

**Run:**

```bash
python3 -m pytest tests/test_voice_filenames.py tests/test_voice_filename_integration.py -q
/usr/bin/python3 -m py_compile dashboard/app.py
```

---

### Task 7 — Dry-run / no-cost integration checks

**Objective:** Verify CLI modules compile and no filename logic broke basic entrypoints without generating real TTS.

**Commands:**

```bash
cd /home/mandhira/Desktop/Projects/ai-trends-research-source

# Syntax / import checks
/usr/bin/python3 -m py_compile \
  scripts/voice_filenames.py \
  scripts/generate_audio_report.py \
  scripts/upload_audio_to_github.py \
  scripts/ai_trends_daily_summary_thai.py \
  scripts/voice_engine.py \
  dashboard/app.py

# Unit/source tests
python3 -m pytest \
  tests/test_voice_filenames.py \
  tests/test_voice_filename_integration.py \
  tests/test_dashboard_deep_dive_workflow.py \
  tests/test_dashboard_topic_resolution.py \
  tests/test_dashboard_asset_dedupe.py \
  -q

# CLI help only — should not generate audio
/usr/bin/python3 scripts/generate_audio_report.py --help >/tmp/ats-generate-audio-help.txt
/usr/bin/python3 scripts/upload_audio_to_github.py --help >/tmp/ats-upload-audio-help.txt || true
```

**Expected:**

- py_compile passes
- pytest passes
- help commands do not call Gemini TTS

---

### Task 8 — Optional local no-TTS function smoke tests

**Objective:** Confirm path construction without calling TTS.

Add a temporary Python one-liner or small test that imports helper and validates expected filenames:

```bash
python3 - <<'PY'
from pathlib import Path
import sys
ROOT = Path('/home/mandhira/Desktop/Projects/ai-trends-research-source')
sys.path.insert(0, str(ROOT / 'scripts'))
from voice_filenames import voice_filename, voice_glob_patterns

checks = [
    voice_filename('NATEHERK', '2026-05-18', video_no=1),
    voice_filename('joanna_wiebe', '2026-05-18', video_no=1),
    voice_filename('Joanna Wiebe', '2026-05-15', video_no=1, variant='deep_dive'),
    voice_filename('NATEHERK', '2026-05-18', variant='whole'),
]
for c in checks:
    print(c)

assert checks == [
    'nateherk-2026-05-18-v1.wav',
    'joanna_wiebe-2026-05-18-v1.wav',
    'joanna_wiebe-2026-05-15-v1-deep-dive.wav',
    'nateherk-2026-05-18.wav',
]
print('ok')
PY
```

Expected output ends with `ok`.

---

## Manual Acceptance Checklist

After implementation, before reporting done to Mandy:

- [ ] No real TTS was run unless Mandy explicitly approved.
- [ ] No files were pushed to GitHub unless Mandy explicitly approved.
- [ ] `scripts/voice_filenames.py` exists and is the only source of filename policy.
- [ ] New generated cron filename would be `nateherk-YYYY-MM-DD-v1.wav`, not `YYYY-MM-DD-v1.wav`.
- [ ] New generated Dashboard full voice filename would be `{topic_slug}-YYYY-MM-DD-vN.wav`.
- [ ] New generated Dashboard deep-dive filename would be `{topic_slug}-YYYY-MM-DD-vN-deep-dive.wav`.
- [ ] Upload script finds new canonical names and old legacy names.
- [ ] Telegram daily summary audio status finds new canonical names and old legacy names.
- [ ] Dashboard `/api/audio/serve` prefers canonical names, falls back to legacy names, and sends unique `Content-Disposition` filename.
- [ ] Existing old files remain readable/downloadable.
- [ ] Tests pass.
- [ ] `git status --short --branch` is reviewed and only intended files are changed.

---

## Regression Risks / Pitfalls

### 1. Telegram says audio missing even when generated

Likely cause: `ai_trends_daily_summary_thai.py` still checks `name.startswith(date_str)`.

Fix: Use `find_voice_files()` with canonical + legacy fallback.

### 2. Upload pushes no audio

Likely cause: `upload_audio_to_github.py` still uses `f'{date_str}*.wav'`.

Fix: Use `find_voice_files()`.

### 3. Dashboard download still gives duplicate filename

Likely cause: `/api/audio/serve` still chooses legacy file first or only sees old files.

Fix: `find_voice_files()` must prefer canonical files first. If only legacy exists, duplicate basename is expected for old files until historical migration.

### 4. Dashboard generated voice goes to `voice/` but table checks `audio/`

Existing design caveat: Dashboard manual voice generation currently writes `ai_trends_reports/voice/{topic}/...`, while asset table/download audio checks use `ai_trends_reports/audio/{topic}/...`. Do not mix this with the filename fix unless you intentionally scope it.

Minimum for this task:

- Make manual generated voice paths unique in `voice/`.
- Make cron/download paths unique in `audio/`.
- Do not attempt a full `audio/` vs `voice/` architecture migration unless Mandy approves.

### 5. Import path failures

Because scripts are run directly, make sure imports work when called as:

```bash
/usr/bin/python3 scripts/generate_audio_report.py --help
/usr/bin/python3 scripts/upload_audio_to_github.py --help
/usr/bin/python3 scripts/ai_trends_daily_summary_thai.py
```

If needed, insert `SCRIPT_DIR` into `sys.path` before importing `voice_filenames`.

### 6. Historical file migration temptation

Do not rename existing output repo files unless separately approved. This plan is for forward-compatible generation + legacy read fallback.

Historical examples currently present:

```text
/tmp/ai-trends-research/voice/nateherk/2026-05-18-v1.wav
/tmp/ai-trends-research/voice/nateherk/2026-05-18-v2.wav
/tmp/ai-trends-research/voice/joanna_wiebe/2026-05-18-v1.wav
/tmp/ai-trends-research/voice/joanna_wiebe/2026-05-15-v1-deep-dive.wav
```

These should remain accessible until/unless Mandy approves a cleanup migration.

---

## Suggested Commit Breakdown

If committing locally, use small commits:

```bash
git add scripts/voice_filenames.py tests/test_voice_filenames.py
git commit -m "feat: add ATS voice filename helper"

git add scripts/generate_audio_report.py scripts/upload_audio_to_github.py scripts/ai_trends_daily_summary_thai.py tests/test_voice_filename_integration.py
git commit -m "fix: use topic-prefixed voice filenames in ATS cron audio"

git add dashboard/app.py tests/test_voice_filename_integration.py
git commit -m "fix: use topic-prefixed voice filenames in ATS dashboard voice"
```

Only push if Mandy approves.

---

## Final Report Template for Mandy

Use this format after implementation:

```text
พี่ Mandy แก้ filename uniqueness ของ ATS voice เสร็จแล้วค่ะ

เปลี่ยนเป็น:
- nateherk-YYYY-MM-DD-v1.wav
- joanna_wiebe-YYYY-MM-DD-v1.wav
- {topic_slug}-YYYY-MM-DD-vN-deep-dive.wav

สิ่งที่แก้:
- scripts/voice_filenames.py เพิ่ม helper กลาง
- generate_audio_report.py ใช้ filename ใหม่สำหรับ cron
- upload_audio_to_github.py หาได้ทั้งชื่อใหม่/เก่า
- ai_trends_daily_summary_thai.py status หาได้ทั้งชื่อใหม่/เก่า
- dashboard/app.py manual voice/download ใช้ชื่อใหม่และ fallback ชื่อเก่า

ทดสอบแล้ว:
- py_compile: PASS
- pytest: X passed
- no real TTS run
- no push unless approved

ข้อควรทราบ:
- ไฟล์เก่าใน GitHub ยังเป็นชื่อ date-first; ยังรองรับอยู่
- ไฟล์ใหม่หลังจากนี้จะ unique ตอน download
```

---

## Out of Scope for This Task

- Prompt unification between `generate_audio_report.py` and `generate_content_assets.py`
- Removing hardcoded greeting/opening in daily cron voice scripts
- Fixing `VERTEX_PROJECT_ID not set`
- Migrating historical GitHub audio filenames
- Changing audio script `.md` filename convention
- Changing Dashboard architecture from `audio/` vs `voice/` folders
- Enabling/disabling topics or changing cron schedule
