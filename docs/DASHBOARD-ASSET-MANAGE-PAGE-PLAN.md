# ATS Dashboard Asset Manage Page Implementation Plan

> **For Hermes / Claude Code / Codex:** This is a design + implementation plan only. Do **not** implement until Mandy explicitly approves.

**Goal:** Make multi-video ATS reports easy and safe to manage from the Dashboard without cluttering the main `/assets` table.

**Architecture:** Keep `/assets` as a high-level summary table. Move per-video operations (open script, generate deep-dive script, generate voice, inspect status) into a dedicated manage page for one topic/date: `/assets/manage?topic={topic_slug}&date={YYYY-MM-DD}`. All script/voice actions must explicitly include `video=N` so the system never defaults silently to v1.

**Tech Stack:** Python stdlib HTTP server (`dashboard/app.py`), existing ATS asset/script/voice APIs, filesystem-backed markdown/JSON/WAV artifacts, pytest tests.

---

## Current Behavior / Problem

When a report has multiple videos, example:

```text
ai_trends_reports/reports/claude_code/claude_code_design/2026-05-17.md
```

and it contains 3 videos, the current audio script generation correctly creates separate files:

```text
ai_trends_reports/audio_scripts/claude_code_design/2026-05-17-v1.md
ai_trends_reports/audio_scripts/claude_code_design/2026-05-17-v2.md
ai_trends_reports/audio_scripts/claude_code_design/2026-05-17-v3.md
```

Each normal audio-script file contains:

```text
## Full Script
...

## Short Script
...
```

However, the current main `/assets` row-level buttons are ambiguous:

```text
📝 📖 📚 🎙️ 🎧
```

Those buttons default to `video=1` if no video number is passed. This means:

- `📝` opens v1 only
- `📖` generates deep-dive script for v1 only
- `📚` opens deep-dive editor for v1 only
- `🎙️` generates voice from v1 full script only
- `🎧` generates voice from v1 deep-dive script only

This is confusing for reports with more than one video because the row represents the whole report, but the action silently targets v1.

---

## UX Decision

### Do NOT add per-video icons directly inside each main row

Rejected pattern:

```text
📝v1 📝v2 📝v3 📖v1 📖v2 📖v3 🎙️v1 🎙️v2 🎙️v3
```

Reason:

- Too cluttered when a report has more than 3 videos
- Hard to use on mobile
- Higher risk of clicking the wrong video/action
- Difficult to show status, stale voice state, and progress clearly

### Recommended pattern: summary row + manage page

Main `/assets` page stays compact:

```text
Date        Topic                 Videos   Status                         Action
2026-05-17  claude code design    3        📄 ✓  📝 3/3  🎙️ 0/3  📱 0/3   🎛️ Manage
```

Clicking `🎛️ Manage` opens:

```text
/assets/manage?topic=claude_code_design&date=2026-05-17
```

The manage page shows one topic/date and lists all videos with per-video status/actions.

---

## Desired Main `/assets` Page

### Main table remains a summary view

Keep columns mostly the same:

```text
Date | Topic | Videos | Status | Manage | Path | Gen
```

Replace row-level script/voice action cluster with one clear button:

```text
🎛️ Manage
```

### Status badges should become aggregate counts

For each row:

```text
📄 Asset JSON: always ready if row exists
📝 Full scripts: {existing_count}/{total_videos}
📖 Deep-dive scripts: {existing_count}/{total_videos}
🎙️ Full voices: {existing_count}/{total_videos}
🎧 Deep-dive voices: {existing_count}/{total_videos}
📱 Social: ready/not ready or count if per-video social is later added
```

Example:

```text
📄 ✓  📝 3/3  📖 0/3  🎙️ 0/3  🎧 0/3  📱 0/3
```

Keep colors:

- green if count equals total
- yellow/blue if partial
- gray if zero
- red/orange if stale/error

### Main row generation buttons

Keep existing generation buttons for report-level creation:

```text
📄 JSON only
🔊 Generate all normal audio scripts
📱 Generate social
🚀 Generate audio + social
```

Clarify tooltip for `🔊`:

```text
Generate normal audio scripts for all videos in this report.
```

Do not keep row-level `🎙️` voice buttons on the main page unless they open Manage.

---

## Desired Manage Page

### Route

```text
GET /assets/manage?topic={topic_slug}&date={YYYY-MM-DD}
```

Example:

```text
/assets/manage?topic=claude_code_design&date=2026-05-17
```

### Header

Show:

```text
Claude Code Design — 2026-05-17
3 videos
Back to Assets
Report path: claude_code/claude_code_design/2026-05-17.md
Asset path: claude_code_design/2026-05-17.json
```

### Per-video cards/table

Each video should have its own card or row:

```text
Video 1
Title: How to Actually Use Claude Design Like a Pro (Real Use Cases)
Source: https://youtube.com/watch?v=...

Status:
- Full script: ✅ exists, 2,577 chars
- Short script: ✅ exists, 697 chars
- Deep-dive script: — missing
- Full voice: — missing
- Deep-dive voice: — missing

Actions:
[Open Full Script]
[Generate Deep-Dive Script]
[Open Deep-Dive Script]
[Generate Full Voice]
[Generate Deep-Dive Voice]
```

For Video 2 and Video 3, all actions must pass `video=2` / `video=3` explicitly.

### Action rules

#### Open Full Script

Calls existing endpoint:

```text
GET /api/assets/script?topic={topic}&date={date}&video={N}&type=full
```

Then opens the existing script editor with hidden fields:

```text
topic={topic}
date={date}
video={N}
type=full
```

#### Generate Deep-Dive Script

Calls existing endpoint:

```text
POST /api/assets/generate-deep-dive-script
```

Payload:

```text
topic={topic}
date={date}
video={N}
```

Rules:

- Must generate text only
- Must not generate voice
- Must not overwrite existing deep-dive script unless `force=1`

#### Generate Full Voice

Calls existing endpoint:

```text
POST /api/assets/generate-voice
```

Payload:

```text
topic={topic}
date={date}
video={N}
type=full
```

Rules:

- Must use saved `audio_scripts/{topic}/{date}-v{N}.md`
- Must extract only `## Full Script`
- Must not use `## Short Script`
- Must return clear error if script is missing

#### Generate Deep-Dive Voice

Calls existing endpoint:

```text
POST /api/assets/generate-voice
```

Payload:

```text
topic={topic}
date={date}
video={N}
type=deep_dive
```

Rules:

- Must use saved `audio_scripts/{topic}/{date}-v{N}-deep-dive.md`
- Must extract only `## Deep Dive Script`
- Must return clear error if script is missing

---

## Bulk Actions on Manage Page

Bulk actions should live only on the manage page, never on the main `/assets` row.

### Bulk generate missing normal scripts

Button:

```text
Generate missing normal scripts for all videos
```

This can call existing report-level `generate-one?mode=audio`, because normal audio generation is intended to create v1/v2/v3/... for all videos.

### Bulk generate selected voices

UI:

```text
Voice type:
( ) Full Script
( ) Deep Dive

Videos:
[x] v1
[x] v2
[ ] v3

[Generate selected voices]
```

Before generating, show confirm dialog:

```text
This will generate 2 WAV files using Gemini TTS:
- claude_code_design/2026-05-17-v1.wav
- claude_code_design/2026-05-17-v2.wav

This may take time and use paid API credits. Continue?
```

Rules:

- Disabled unless at least one video is selected
- Disabled if selected script is missing
- Must show per-video progress/result
- Do not silently generate scripts while generating voice

### Bulk generate missing deep-dive scripts

Potential future feature. Lower priority because deep-dive generation can be expensive and long.

If implemented, must:

- Require confirm
- Skip existing deep-dive scripts by default
- Show per-video result
- Never generate voice automatically

---

## API Additions Recommended

### New endpoint: video-level status

Add:

```text
GET /api/assets/videos?topic={topic_slug}&date={YYYY-MM-DD}
```

Purpose: one source of truth for the manage page. Avoid duplicating filesystem status logic in JavaScript.

Example response:

```json
{
  "topic": "claude_code_design",
  "date": "2026-05-17",
  "report_path": "claude_code/claude_code_design/2026-05-17.md",
  "asset_path": "claude_code_design/2026-05-17.json",
  "total_videos": 3,
  "videos": [
    {
      "video": 1,
      "title": "How to Actually Use Claude Design Like a Pro (Real Use Cases)",
      "source_url": "https://youtube.com/watch?v=...",
      "full_script": {
        "exists": true,
        "path": "ai_trends_reports/audio_scripts/claude_code_design/2026-05-17-v1.md",
        "chars": 2577
      },
      "short_script": {
        "exists": true,
        "chars": 697
      },
      "deep_dive_script": {
        "exists": false,
        "path": "ai_trends_reports/audio_scripts/claude_code_design/2026-05-17-v1-deep-dive.md",
        "chars": 0
      },
      "full_voice": {
        "exists": false,
        "stale": false,
        "path": "ai_trends_reports/voice/claude_code_design/2026-05-17-v1.wav"
      },
      "deep_dive_voice": {
        "exists": false,
        "stale": false,
        "path": "ai_trends_reports/voice/claude_code_design/2026-05-17-v1-deep-dive.wav"
      }
    }
  ]
}
```

### Optional new endpoint: aggregate row status

If main `/assets` rendering gets too complex, add:

```text
GET /api/assets/summary?topic={topic}&date={date}
```

But prefer server-side rendering first to keep the implementation simple.

---

## File Changes When Approved

Expected files to modify/create:

```text
dashboard/app.py
scripts/generate_content_assets.py          # only if a shared helper is needed
tests/test_dashboard_asset_manage_page.py   # new
tests/test_dashboard_asset_video_status.py  # new or combined
```

Docs to update:

```text
docs/TASKS.md
```

No changes should be made to voice engine behavior unless tests reveal missing `video` handling.

---

## Implementation Tasks

### Task 1: Add tests for video status helper

**Objective:** Ensure the backend can report v1/v2/v3 script/voice status accurately.

**Files:**

- Create: `tests/test_dashboard_asset_video_status.py`
- Modify: `dashboard/app.py`

**Test cases:**

1. Multi-video report returns all videos
2. v1/v2/v3 script paths are distinct
3. full script chars are counted from `## Full Script`
4. deep-dive script status uses `-deep-dive.md`
5. voice paths use `voice/{topic}/{date}-vN.wav`
6. missing script returns `exists=false`, not an exception

**Verification command:**

```bash
python3 -m pytest tests/test_dashboard_asset_video_status.py -q
```

Expected:

```text
6 passed
```

---

### Task 2: Implement `GET /api/assets/videos`

**Objective:** Provide one JSON endpoint for manage page status.

**Files:**

- Modify: `dashboard/app.py`

**Implementation notes:**

- Use existing `_resolve_report_path(topic, date)`
- Use `build_asset_from_report()` to get video titles/source URLs
- Use existing `_voice_script_paths(topic, date, video, type)` for paths
- Use existing `extract_script_text()` for character counts
- Return HTTP 404 only if the report does not exist
- Return per-video missing statuses normally

**Verification:**

```bash
curl -sS 'http://127.0.0.1:8092/api/assets/videos?topic=claude_code_design&date=2026-05-17' | python3 -m json.tool
```

Expected:

- `total_videos` is `3`
- videos array has `video: 1`, `video: 2`, `video: 3`
- script paths include `v1.md`, `v2.md`, `v3.md`

---

### Task 3: Add manage page route

**Objective:** Add a dedicated page for one topic/date.

**Files:**

- Modify: `dashboard/app.py`
- Test: `tests/test_dashboard_asset_manage_page.py`

**Route:**

```text
GET /assets/manage?topic={topic}&date={date}
```

**Page requirements:**

- Back link to `/assets`
- Header with topic/date/total videos
- Video cards or table rows
- Per-video status labels
- Per-video action buttons
- Existing script editor section can be reused on this page

**Verification:**

```bash
curl -sS 'http://127.0.0.1:8092/assets/manage?topic=claude_code_design&date=2026-05-17' -o /tmp/manage.html
```

Expected:

- HTML contains `Video 1`, `Video 2`, `Video 3`
- HTML contains `openScript('claude_code_design','2026-05-17','full',1)` or equivalent explicit video parameter
- HTML contains no ambiguous row-level voice button without video number

---

### Task 4: Update main `/assets` row actions

**Objective:** Remove ambiguity from the main page.

**Files:**

- Modify: `dashboard/app.py`

**Changes:**

- Replace row-level script/voice cluster with `🎛️ Manage`
- Keep report-level generation buttons (`📄`, `🔊`, `📱`, `🚀`)
- Change status badges to aggregate counts where possible
- Tooltips must explain that `🔊` generates scripts for all videos

**Acceptance criteria:**

Main row should not have buttons that silently operate on v1.

---

### Task 5: Make JS `openScript()` video-explicit

**Objective:** Ensure every script editor open/save/generate voice action uses explicit video number.

**Files:**

- Modify: `dashboard/app.py`

**Rules:**

- `openScript(topic, date, type, video)` should require video argument from manage page
- If no video is provided, default can remain `1` internally for backward compatibility, but UI must always pass explicit video
- `generateVoice(topic, date, type, video)` should require explicit video from manage page
- `generateVoiceFromEditor()` should read hidden `scriptVideo`

**Tests:**

- Manage page HTML includes explicit video args
- Saving script from editor preserves correct `video=N`

---

### Task 6: Add bulk selected voice generation UI

**Objective:** Allow intentional multi-video TTS without cluttering the main page.

**Files:**

- Modify: `dashboard/app.py`
- Test: `tests/test_dashboard_asset_manage_page.py`

**Phase 1 implementation can be simple:**

- Checkboxes for each video
- Radio buttons for `full` vs `deep_dive`
- JS loops over selected videos and calls existing `/api/assets/generate-voice`
- Confirm dialog before starting
- Show per-video result messages

**Do not implement parallel TTS initially.** Sequential generation is safer and easier to debug.

---

### Task 7: Documentation + verification

**Objective:** Record behavior so future agents do not reintroduce ambiguous v1 defaults.

**Files:**

- Modify: `docs/TASKS.md`

**Add note:**

- Normal audio script generation creates one script file per video: `v1`, `v2`, `v3`, ...
- Voice generation is video-specific and must always pass `video=N`
- Main `/assets` page is summary only; manage page is per-video operation center

**Verification commands:**

```bash
python3 -m pytest tests/test_dashboard_asset_video_status.py tests/test_dashboard_asset_manage_page.py tests/test_dashboard_asset_dedupe.py tests/test_dashboard_topic_resolution.py -q
/usr/bin/python3 -m py_compile dashboard/app.py scripts/generate_content_assets.py
systemctl --user stop ats-dashboard.service
systemctl --user start ats-dashboard.service
curl -sS -o /tmp/assets.html -w '%{http_code}\n' http://127.0.0.1:8092/assets
curl -sS -o /tmp/manage.html -w '%{http_code}\n' 'http://127.0.0.1:8092/assets/manage?topic=claude_code_design&date=2026-05-17'
```

Expected:

```text
all tests pass
py_compile passes
/assets returns 200
/assets/manage returns 200
```

---

## Acceptance Criteria

Implementation is complete only when all are true:

1. Main `/assets` page has no ambiguous row-level voice button that silently targets v1.
2. Multi-video report status shows aggregate counts, e.g. `📝 3/3`, `🎙️ 0/3`.
3. Manage page exists for one topic/date.
4. Manage page shows every video in the report.
5. Every per-video action passes explicit `video=N`.
6. Full voice generation uses only `## Full Script` from the selected `vN.md` file.
7. Deep-dive voice generation uses only `## Deep Dive Script` from selected `vN-deep-dive.md` file.
8. Bulk voice generation requires explicit video selection and a confirm dialog.
9. Missing script blocks voice generation with a clear error.
10. Tests cover nested underscore topics such as `claude_code_design`.

---

## Safety / Cost Rules

- Do not trigger real Gemini TTS in tests.
- Do not generate voice automatically after script generation.
- Do not bulk-generate voice from the main `/assets` page.
- Voice generation must always be intentional and confirm paid/heavy API usage.
- Script generation can remain report-level because it is designed to create v1/v2/v3/... for all videos.
- Deep-dive generation should remain per-video by default.

---

## Recommended Implementation Order

1. Add `/api/assets/videos` tests.
2. Implement `/api/assets/videos`.
3. Add manage page tests.
4. Implement `/assets/manage` with static per-video actions.
5. Replace main row script/voice action cluster with `🎛️ Manage`.
6. Add aggregate counts in main status column.
7. Add selected bulk voice UI on manage page.
8. Update docs/TASKS.md.
9. Restart Dashboard and verify through Cloudflare.
10. Commit + push only after Mandy approves implementation.

---

## Open Questions — Resolved 2026-05-21

1. **Main row action label** → `🎛️ Manage` ✅

2. **Manage page layout** → Card view (2-column responsive grid) ✅
   Reason: Cards are clearer when each video has 5+ action states to show. Degrades better to mobile.

3. **Bulk voice default** → No videos selected by default ✅
   Reason: Voice generation is intentional; force explicit opt-in.

4. **Normal audio script generation** → Remains “all videos at once” at report level ✅
   Per-video force-regenerate available via “Regen All Scripts” button on manage page (regenerates all videos for the report).

5. **Deep-dive bulk in v1** → No, skip — add only when requested ✅

---

## Implementation Gaps Resolved 2026-05-21

The following gaps were identified in pre-implementation analysis and resolved:

### Gap 1 — Voice directory: `audio/` vs `voice/`
WAV files exist in both `ai_trends_reports/audio/` (legacy) and `ai_trends_reports/voice/` (current output).
- `_voice_script_paths()` correctly uses `voice/` for all new generation
- Aggregate voice counts in main table check `voice/` via `find_voice_files()`
- `api_audio_serve` (download) continues to check `audio/` for backward compatibility
- **Decision:** Aggregate status badges on main page and manage page read from `voice/`

### Gap 2 — Partial script scenario (e.g. v1 missing, v2+v3 exist)
Real data: `claude_code_design/2026-05-17-v2.md` and `v3.md` exist, `v1.md` missing.
- Manage page shows each video's script status independently
- Missing script shows “— Full Script missing” with Regen All button
- No crash or silent fallback for the missing video
- **Decision:** Show per-video missing state clearly; “Regen All” regenerates all from the report

### Gap 3 — Per-video force-regenerate normal script
No endpoint for single-video script regeneration exists.
- **Decision:** “Regen All Scripts” button on each card calls `generate-one?mode=audio` which regenerates all videos' scripts for that topic+date. Confirm dialog explicitly states “all videos”.
- Individual video regeneration can be added later when needed.

### Gap 4 — Script editor removal from main `/assets` page
- **Decision:** Script editor HTML removed from main `/assets` page. Editor lives only on manage page. Main page is summary-only.

### Gap 5 — Generation in-progress state on manage page
- `generateVoiceDirect` and `generateDeepDiveScriptDirect` update a `bulkVoiceStatus` span inline
- Page reloads automatically after successful completion (2s delay)
- No localStorage polling needed for manage page (single-operation flow)

### Gap 6 — Short Script voice scope
- **Decision:** Short Script voice is out of scope for this implementation. Script files contain `## Short Script` section but no UI exposes it. Can be added later as a variant.

### Gap 7 — Single-video row hybrid UX
- **Decision:** All rows show `🎛️ Manage` in v1 for consistency. Hybrid (quick buttons for single-video rows) can be added later if UX feedback warrants it.
