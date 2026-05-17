# Voice Generation — Design Document

## สถานะปัจจุบัน

### ระบบที่มีแล้ว

| Component | Script | ทำอะไร | Output |
|---|---|---|---|
| Asset JSON | `generate_content_assets.py` | Build structured asset per report | `assets/{topic}/{date}.json` |
| Audio Scripts | `generate_content_assets.py --with-audio` | AI generates `audio_script_full` (~400 words) + `audio_script_short` (~150 words) per video | Embedded in asset JSON + `audio_scripts/{topic}/{date}-vN.md` |
| Audio Report | `generate_audio_report.py` | Condense full report → script → TTS WAV (whole-file or per-video) | `audio/{topic}/{date}.wav` |
| Voice Files | Manual / ad-hoc | `vN.wav` (full script voice) + `vN-deep-dive.wav` (deep dive voice) per video | `voice/{topic}/{date}-vN.wav`, `voice/{topic}/{date}-vN-deep-dive.wav` |

### ช่องว่าง — ที่ยังไม่มี

1. **Voice generation ไม่ได้ integrate กับ asset/Dashboard flow** — ไฟล์เสียงใน `voice/` folder สร้างด้วยมือ/ad-hoc ไม่ได้เป็นส่วนหนึ่งของ asset generation flow
2. **Dashboard ไม่รู้จัก voice** — Assets page แสดง script status แต่ไม่แสดง voice file status
3. **Deep dive script** — ยังไม่มี prompt สำหรับสร้าง deep dive script แยกจาก full script
4. **Script → Voice step ยังไม่ใช่ workflow แบบ reviewable** — ต้องบังคับให้สร้าง/บันทึก script ก่อน แล้วค่อยสร้าง voice จาก script ที่ save แล้วเท่านั้น
5. **มีระบบเสียงเดิมของ NATEHERK แยกอยู่** — `generate_audio_report.py` รันทุกวันจาก cron เพื่อสร้าง `audio/{topic}/{date}.wav`; ต้องนำมารวมกับ voice generator ตัวเดียวกัน ไม่สร้างโปรแกรม TTS ซ้ำซ้อน

---

## Voice Types — 2 ประเภท

### Type 1: Full Script Voice (`vN.wav`)
- **Source:** `audio_script_full` (~400 words, ~2000 chars) จาก asset JSON
- **Tone:** "ดูมาแล้วมาเล่าให้ฟัง" — เพื่อนเล่าให้เพื่อน
- **Length:** ~3-4 นาที
- **Use case:** Podcast episode, YouTube Short voiceover

### Type 2: Deep Dive Voice (`vN-deep-dive.wav`)
- **Source:** Deep dive script ใหม่ — ขยายเนื้อหาเดียวกันให้ละเอียดกว่า
- **Tone:** วิเคราะห์เชิงลึก อธิบายเพิ่มเติม ยกตัวอย่าง ให้ความเห็น
- **Length:** ~10-20 นาที (ขึ้นกับเนื้อหา)
- **Use case:** Long-form podcast, detailed analysis
- **Language:** ไทยเท่านั้นสำหรับ ATS output ตาม project policy

---

## Required Workflow — Script First, Voice Second

Mandy requirement: **ต้องสร้าง script ก่อนเสมอ แล้วค่อยสร้าง voice จาก script ที่ save แล้ว**

### Workflow states

```text
Report exists
  ↓
Generate Asset JSON
  ↓
Generate/Edit Script
  ├─ Full Script: audio_scripts/{topic}/{date}-vN.md
  └─ Deep Dive:   audio_scripts/{topic}/{date}-vN-deep-dive.md
  ↓
Review + Edit in Dashboard
  ↓
Save Script
  ↓
Generate Voice from the saved script only
  ├─ voice/{topic}/{date}-vN.wav
  └─ voice/{topic}/{date}-vN-deep-dive.wav
```

### Rules

1. **Generate Voice must NOT silently create script and voice in one click.**
   - If script is missing, show: `Script missing — generate script first`.
   - Offer a separate `Generate Script` action.
2. **Voice reads from saved script file / saved asset JSON only.**
   - This ensures Mandy can edit the wording before spending TTS cost.
3. **After script edit + Save, existing voice becomes stale.**
   - Store `script_sha256` with the voice metadata.
   - If the saved script hash changes, Dashboard should show `Voice stale — regenerate`.
4. **Two independent script buttons:**
   - `Generate Full Script` → creates/updates `vN.md`
   - `Generate Deep Dive Script` → creates/updates `vN-deep-dive.md`
5. **Two independent voice buttons:**
   - `Generate Full Voice` → allowed only after full script exists/saved
   - `Generate Deep Dive Voice` → allowed only after deep dive script exists/saved


## Architecture Design

```
                    ┌──────────────┐
                    │  Report .md  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Asset JSON  │  ← generate_content_assets.py (existing)
                    │  (metadata)  │
                    └──────┬───────┘
                           │
               ┌───────────┼───────────┐
               │           │           │
        ┌──────▼──────┐    │    ┌──────▼──────┐
        │ Full Script │    │    │ Deep Dive   │
        │ (~400 words)│    │    │ Script      │
        │ (existing)  │    │    │ (~1500 words│
        └──────┬──────┘    │    │  NEW)       │
               │           │    └──────┬──────┘
        ┌──────▼──────┐    │           │
        │  Chunk +    │    │    ┌──────▼──────┐
        │  TTS → WAV  │    │    │  Chunk +    │
        │  (~3 min)   │    │    │  TTS → WAV  │
        └──────┬──────┘    │    │  (~15 min)  │
               │           │    └──────┬──────┘
        ┌──────▼──────┐    │           │
        │ vN.wav      │    │    ┌──────▼──────────┐
        │ voice/{t}/  │    │    │ vN-deep-dive.wav │
        └─────────────┘    │    │ vN-deep-dive-    │
                           │    │   thai.wav       │
                           │    └──────────────────┘
                           │
                    ┌──────▼──────┐
                    │ Social JSON │  ← existing
                    └─────────────┘
```

---

## New Components

### 1. Deep Dive Script Generator

**Prompt concept:** รับ `section_text` (เนื้อหา video section เต็ม) → สร้าง deep dive script ที่ละเอียดกว่า full script 3-5 เท่า

```
Key differences from full script prompt:
- Target: ~1500 words (vs 400)
- Tone: วิเคราะห์เชิงลึก (vs เล่าให้ฟัง)
- Structure: มี background → analysis → examples → opinion → conclusion
- Can include "ในมุมของ..." sections for multi-angle analysis
- ใช้ section_text เต็ม (ไม่ truncate) — ส่งได้ถึง 15K chars
```

**Storage:** `audio_script_deep_dive` field ใน asset JSON per video

### 2. Unified Voice Engine

**New canonical module:** `scripts/voice_engine.py` or `scripts/generate_voice.py`

This must become the **single TTS/voice generation engine** for both:

1. Dashboard/Assets voice generation (`voice/{topic}/{date}-vN*.wav`)
2. Existing daily NATEHERK audio cron (`audio/{topic}/{date}.wav` pushed to GitHub `Voice/NateHerk/{date}.wav`)

Do **not** keep two separate TTS implementations long-term. Existing `generate_audio_report.py` should either:
- become a thin wrapper around the unified voice engine, or
- be refactored so its `_text_to_wav`, chunking, retry, and concat logic move into the shared engine.

```
Functions:
  generate_voice_from_saved_script(script_path, output_path, voice_type) → Path
    - Reads saved script from disk
    - Computes script_sha256
    - Chunks if needed
    - Calls Gemini TTS
    - Concats segments
    - Writes WAV + metadata

  generate_daily_topic_audio(topic, date, mode="per-video") → Path
    - Replaces current direct TTS logic in generate_audio_report.py
    - Used by existing NATEHERK daily cron
    - Keeps output compatibility: ai_trends_reports/audio/{topic}/{date}.wav

  _chunk_script(script_text, max_chars=4500) → list[str]
    - Split at sentence/paragraph boundaries
    - Keep each chunk ≤ 4500 chars (Gemini TTS limit)
  
  _tts_chunk(text_chunk, voice, output_path) → Path
    - Call Gemini TTS API (gemini-2.5-flash-preview-tts, voice Aoede)
    - Return temp WAV path
  
  _concat_wavs(wav_paths, output_path) → Path
    - Merge all chunks into single WAV
```

### 3. Voice Output Structure

```text
ai_trends_reports/voice/
  {topic}/
    {date}-v1.wav                    ← Full script voice (ไทย, per-video)
    {date}-v1-deep-dive.wav          ← Deep dive voice (ไทย, per-video)
    {date}-v2.wav
    {date}-v2-deep-dive.wav
    ...

ai_trends_reports/audio/
  {topic}/
    {date}.wav                       ← Daily topic audio / legacy-compatible output
```

**Compatibility note:** The existing NATEHERK daily job currently creates `audio/NATEHERK/{date}.wav` and uploads it to GitHub `Voice/NateHerk/{date}.wav`. Keep this output path working, but generate it through the same unified voice engine.


### 4. Asset JSON Extension

```json
{
  "videos": [{
    "video_no": 1,
    "audio_script_full": "... (~400 words)",
    "audio_script_short": "... (~150 words)",
    "audio_script_deep_dive": "... (~1500 words) ← NEW",
    "social_posts": {...},
    "voice_files": {                          ← NEW
      "full": {
        "path": "voice/joanna_wiebe/2026-05-15-v1.wav",
        "script_sha256": "...",
        "generated_at": "2026-05-17T...",
        "status": "ready"
      },
      "deep_dive": {
        "path": "voice/joanna_wiebe/2026-05-15-v1-deep-dive.wav",
        "script_sha256": "...",
        "generated_at": "2026-05-17T...",
        "status": "ready"
      }
    }
  }]
}
```

---

## TTS Pipeline Detail — Chunking Strategy

### ปัญหา: Gemini TTS input limit
- Gemini `gemini-2.5-flash-preview-tts` รับ text ได้ ~5000 chars ต่อ request
- Full script (~400 words ≈ ~2000 chars) → **ส่งได้ใน 1 request** ✅
- Deep dive script (~1500 words ≈ ~7000 chars) → **ต้อง chunk เป็น 2 ส่วน** ⚠️

### Chunking algorithm:
```
1. Split text at natural sentence boundaries:
   - Thai: หลัง "ค่ะ", "ครับ", "นะคะ", "เลย", "ด้วย"
   - English: after ".", "!", "?"
2. Accumulate sentences until approaching 4500 chars
3. Start new chunk at next sentence boundary
4. TTS each chunk → WAV segment
5. Concatenate all segments → final WAV
```

### Rate limiting:
- รอ 8 วินาทีระหว่าง chunk (ตาม generate_audio_report.py pattern)
- Retry 429 errors with exponential backoff (30s, 60s, 120s)

---

## Dashboard Integration

### Assets page — เพิ่ม voice status columns:

| DATE | TOPIC | VIDEOS | SCRIPT | VOICE | DEEP DIVE | SOCIAL | GEN |
|------|-------|--------|--------|-------|-----------|--------|-----|
| 05-15 | joanna_wiebe | 4 | ✅ | 🔊2/4 | 🔊1/4 | 📱 | 🚀 |

**Per-row buttons เพิ่ม:**
- 📝 = Generate/Edit full script
- 📚 = Generate/Edit deep dive script
- 💾 = Save script edits
- 🎙️ = Generate full voice from saved full script only
- 🎧 = Generate deep dive voice from saved deep dive script only

**Batch mode เพิ่ม:**
- "Generate Full Scripts" = script files only, no voice
- "Generate Deep Dive Scripts" = deep dive script files only, no voice
- "Generate Full Voice" = voice only from existing saved full scripts
- "Generate Deep Dive Voice" = voice only from existing saved deep dive scripts

**Important UX rule:** voice actions must not create scripts implicitly. If script is missing, Dashboard should block voice generation and ask Mandy to create/save script first.

---

## Automated Daily Voice Generation

Manual Dashboard generation and daily automation should be **separate orchestration flows** but share the **same unified voice engine**.

### Current automation state

Existing daily cron already runs NATEHERK audio through:

```text
scripts/run_daily_summary_cron.sh
  → scripts/generate_audio_report.py --all-enabled --per-video --date TODAY
  → scripts/upload_audio_to_github.py --date TODAY
```

Current config:

```json
{
  "enabled_topics": ["NATEHERK"],
  "voice": "Aoede",
  "language_hint": "th-TH",
  "github_folder_map": {
    "NATEHERK": "NateHerk"
  }
}
```

This means NATEHERK is already the first automated voice topic. Joanna can be added by config after the unified voice/script workflow is ready.

### Desired automation behavior

For selected topics such as `NATEHERK` and `joanna_wiebe`, the daily job should automatically:

```text
Daily report exists
  ↓
Generate / update asset JSON
  ↓
Generate full script if missing
  ↓
Generate full voice from saved generated script
  ↓
Upload report assets + voice to output repo
  ↓
Telegram daily summary includes voice status
```

Important: automation may generate script + voice sequentially, but it is still conceptually two steps:

1. create/save script artifact
2. create voice from that saved script artifact

This keeps the system consistent with the manual script-first workflow and leaves a reviewable script file in GitHub/local storage.

### Separation of concerns

| Layer | Purpose | Trigger | Uses unified voice engine? |
|---|---|---|---|
| Manual Dashboard | Mandy chooses a report/video, edits script, saves, generates voice | Button click | Yes |
| Daily Automation | Pre-approved topics generate scripts + voice every day without manual review | Cron | Yes |
| Voice Engine | TTS/chunk/retry/concat + metadata | Called by both | Core shared module |

### Suggested config extension

Replace the current simple `enabled_topics` audio config with a richer policy:

```json
{
  "automated_voice_topics": {
    "NATEHERK": {
      "enabled": true,
      "script_type": "full",
      "voice_type": "full",
      "per_video": true,
      "publish": true,
      "github_folder": "NateHerk"
    },
    "joanna_wiebe": {
      "enabled": true,
      "script_type": "full",
      "voice_type": "full",
      "per_video": true,
      "publish": true,
      "github_folder": "Joanna_Wiebe"
    }
  },
  "voice_profiles": {
    "ats_female_narrator": {
      "provider": "gemini",
      "model": "gemini-2.5-flash-preview-tts",
      "voice": "Aoede",
      "language_hint": "th-TH",
      "script_style": "Thai female narrator, warm, natural, conversational, uses ค่ะ"
    }
  },
  "default_voice_profile": "ats_female_narrator"
}
```

### What should be automated first

Recommended Phase 1 automation:

- Create `ats_female_narrator` as the default voice profile using Gemini TTS `Aoede` (the current NATEHERK female voice Mandy likes)
- NATEHERK: keep current daily behavior, refactor to shared voice engine
- Joanna Wiebe: add daily full script + full voice only after NATEHERK compatibility tests pass
- Deep dive voice: keep manual first, because it costs more and usually benefits from review/editing

Recommended Phase 2 automation:

- Add per-topic policy for deep dive automation only after Mandy confirms quality/cost
- Add skip/stale logic:
  - if script exists and voice exists with matching `script_sha256`, skip
  - if script exists but voice missing, generate voice
  - if script changed after voice generation, regenerate voice

### Important implementation rule

Do **not** create a separate `generate_auto_voice.py` that duplicates TTS logic. If a new cron wrapper is needed, it should only orchestrate:

```text
find today's reports → ensure scripts → call unified voice engine → upload
```

All TTS/chunk/concat logic must live in the unified voice engine.

---

## Output Repo Folder Policy

Generated publish artifacts must be copied/pushed to the output repo:

```text
https://github.com/MandhiraT/ai-trends-research
local clone: /tmp/ai-trends-research
```

The output repo currently has mixed/legacy folders (`Voice/`, `voice/`, `Content Marketing/`, topic-name variants). This must be cleaned up before broad voice automation.

### Canonical top-level folders

Use lowercase top-level folders only:

```text
reports/{topic}/{date}.md                 ← canonical Thai daily reports
assets/{topic}/{date}.json                ← structured asset JSON
audio_scripts/{topic}/{date}-vN.md        ← editable/reviewable scripts
audio_scripts/{topic}/{date}-vN-deep-dive.md
voice/{topic}/{date}-vN.wav               ← final full-script voice
voice/{topic}/{date}-vN-deep-dive.wav     ← final deep-dive voice
social/{topic}/{date}.json                ← generated social posts
social/{topic}/{date}.md                  ← readable social posts
```

### Topic folder naming

Use stable slugs for topic folders:

```text
NATEHERK      → nateherk
joanna_wiebe  → joanna_wiebe
AI Agents     → ai_agents
Claude Code   → claude_code
```

Exception: Existing legacy `Voice/NateHerk/{date}.wav` should be migrated to `voice/nateherk/{date}.wav` with a compatibility note/update in upload scripts, not duplicated forever.

### Rules

1. Output repo is for publishable artifacts only; source code stays in `ai-trends-research-source`.
2. Prefer one canonical path per artifact; do not keep both `Voice/` and `voice/` long-term.
3. Voice files must be `.wav` or `.mp4` only — never `.ogg`.
4. Dashboard/manual generation may write locally under source repo first, but publish step must copy to the canonical output repo paths.
5. Before moving/deleting legacy folders in output repo, create a migration plan and verify GitHub links that may already be shared.

---

## Cost Estimation

| Type | Script (text AI) | Voice (TTS) | Total/video |
|------|-------------------|-------------|-------------|
| Full script voice | ~400 words (Gemini Flash — ~$0.001) | ~3 min WAV (~$0.005) | ~$0.006 |
| Deep dive voice | ~1500 words (Gemini Flash — ~$0.003) | ~15 min WAV (~$0.02) | ~$0.023 |
| Both per video | ~1900 words | ~18 min | ~$0.029 |
| **4 videos/report** | | | **~$0.12** |

---

## Implementation Order

1. **Create unified voice engine** — `scripts/voice_engine.py` or `scripts/generate_voice.py`
   - Move/reuse Gemini TTS call, retry, WAV concat, and chunking from `generate_audio_report.py`
   - Add `generate_voice_from_saved_script()`
   - Add script hash metadata so edited scripts mark voices stale

2. **Refactor existing daily audio** — `generate_audio_report.py`
   - Keep CLI compatibility for cron: `generate_audio_report.py --all-enabled --per-video --date ...`
   - Internally call the unified voice engine
   - Keep existing NATEHERK output compatibility: `ai_trends_reports/audio/NATEHERK/{date}.wav` and GitHub `Voice/NateHerk/{date}.wav`

3. **Extend script generation only** — `generate_content_assets.py`
   - Keep `--with-audio` as script-only (current behavior)
   - Add deep dive script generation, but do not auto-run TTS
   - Store `audio_script_deep_dive` in asset JSON

4. **Extend Dashboard** — Assets page
   - New script editor/review UI
   - Save script endpoint
   - New voice/deep-dive status columns
   - Voice buttons disabled/blocked until saved script exists
   - Voice file playback (HTML5 audio player)

5. **Dashboard API** — New endpoints
   - `GET/POST /api/assets/script` — load/save full/deep-dive script
   - `POST /api/assets/generate-script` — generate script only
   - `POST /api/assets/generate-voice` — generate voice only from saved script
   - `GET /api/assets/voice-status` — check voice file existence + stale hash status

---

## Key Design Decisions

1. **Script-first workflow is mandatory** → Generate script, review/edit/save, then generate voice. No one-click script+voice generation.
2. **Voice generator must be single-source** → Dashboard voice and existing daily NATEHERK audio must use the same TTS/chunk/concat engine.
3. **Keep cron/output compatibility** → Existing `generate_audio_report.py` CLI and `audio/{topic}/{date}.wav` output should continue working, but implemented as a wrapper around the shared voice engine.
4. **Voice folder = topic-based** (ไม่ใช่ flat) → `voice/{topic}/{date}-vN-{type}.wav` for per-video voice files.
5. **Daily topic audio remains supported** → `audio/{topic}/{date}.wav` for the current daily NATEHERK published audio.
6. **Deep dive = separate script** → ไม่ใช่ full script ตัวเดียวกัน — ต้องเขียน prompt ต่างกัน
7. **Chunk at sentence level** → ไม่ตัดกลางประโยค เสียงจะได้ natural
8. **WAV output** → ไม่แปลงเป็น MP3 — according to ATS policy (voice = .wav/.mp4 only)
9. **Thai output only** → ATS voice/script/social output is Thai unless Mandy explicitly creates a non-ATS exception.
10. **Stale voice detection** → store `script_sha256`; if script changes after voice generation, mark voice stale and require regeneration.
