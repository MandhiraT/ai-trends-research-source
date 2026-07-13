# ATS Full-Detail Summary Mode — Design (not implemented)

**Status:** 🟡 Design revised per Mandy's feedback — awaiting go-ahead to implement
**Date:** 2026-07-13 (updated same day after Mandy's answers)
**Triggered by:** Mandy reported that the current `--detailed` Thai summary mode loses step-by-step
detail on instructional/tutorial videos (example: a camera-movement-prompt tutorial with 42 distinct
commands, where the report only surfaces ~15 of them grouped into 5 themes). She wants a new,
optional "full detail" mode — selectable per cron job / per on-demand run — that preserves every
step/example/command the video actually teaches, in Thai, without the current mode's compression.
This document analyzes root cause and proposes an implementation approach. **No code has been
changed.**

---

## 1. The complaint, verified against a real report

Example video: https://youtu.be/HOjCT6TxlHM (42 named AI-video camera-movement prompts)
Report produced: `ai_trends_reports/reports/on_demand/research_job/2026-07-13_2209_https-youtu-be-hojct6txlhm-si-dttlwwao2llzqufa.md`

Read in full. Confirmed: the report groups the 42 commands into 5 thematic "key points" (Dolly,
Zoom/Focus, Orbital/Drone, Style/Timing, etc.), each explained generally with 2-3 example commands
quoted as illustrations. A reader cannot recover the other ~27 commands from the report — the
report is a faithful summary of *themes*, not a usable reference of *everything the video
demonstrated*. This matches exactly what Mandy described.

This is not a bug in the sense of something crashing or misbehaving — it is the mode doing exactly
what it was designed to do (`prompts/thai_summary_prompt_detailed.txt` explicitly caps "ประเด็นสำคัญ"
at 4-7 items and "Insight" at 3-5 items). That structure is well suited to trend/analysis/opinion
videos. It is the wrong tool for enumerative/instructional videos (tool tutorials, prompt
collections, step-by-step workflows, "N ways to do X" videos).

## 2. Root causes (two independent ones)

### 2a. Prompt structure caps item count (primary cause)
`prompts/thai_summary_prompt_detailed.txt` §3 instructs "สรุปเป็นหัวข้อย่อย 4–7 ข้อ" — a hard
thematic-compression instruction. For a video that teaches 42 discrete things, the model has no
choice but to group them into a handful of categories. This is the direct cause of the complaint.

### 2b. Transcript truncation (secondary, currently latent but will bite on longer videos)
Independent of the prompt, `scripts/summarize_local.py` truncates the transcript twice before the
model ever sees it:
- `_parse_vtt()` caps the parsed caption text at 30,000 characters (line 62)
- `summarize_video()` re-slices to the first 25,000 characters of that when building the prompt for
  detailed mode (line 250)

This particular 12-minute video's transcript was short enough that this likely wasn't the binding
constraint (the report is only 413 words vs. the claimed 2000-3000 word target for detailed mode —
under-length for a different reason: the model chose brevity within its 4-7-bullet budget). But for
longer tutorial videos (30-60+ min, more steps to enumerate), both caps will silently drop the back
half of the transcript before any prompt engineering can help — an invisible failure mode, since
nothing errors, the model just never sees the rest of the video. The current production model
(`gemini-2.5-flash` via Vertex, already in use) has a 1M-token context window, so there is no
technical reason to keep such a low character cap once a mode is designed to actually use all of it.

## 3. Proposed solution: a third, opt-in summary mode

Add "full detail" (ครบทุกขั้นตอน) as a **third mode alongside — not replacing — standard and
detailed.** Mandy asked for this to be a per-job choice, since most existing topics (trend
roundups, opinion/analysis channels) are well served by the current detailed mode and don't need
this.

### 3a. New prompt file: `prompts/thai_summary_prompt_full_detail.txt`
Sequential, enumerative structure instead of thematic compression:
1. Title
2. Short intro (1 paragraph: what the video covers, who it's for) — not the current 1-3 paragraph
   "ภาพรวม," kept brief on purpose since the walkthrough is the payload
3. **Sequential walkthrough** (the bulk of the document) — every distinct step / example / command /
   tool / list item the video demonstrates, in the order presented, explained in natural Thai (not a
   verbatim/mechanical translation of the transcript — same "เขียนเหมือนคนเขียนบล็อค" voice as the
   existing detailed prompt, just without a bullet-count ceiling). Explicit instruction: "ห้ามจำกัด
   จำนวนหัวข้อย่อยหรือขั้นตอน — ถ้าคลิปพูดถึง N ขั้นตอน/ตัวอย่าง/คำสั่ง ให้ครบ N ข้อ ห้ามยุบรวมเพื่อ
   ความกระชับ"
4. Short closing summary (2-4 sentences)

No separate "Insight" or "เอาไปใช้ยังไง" section required — this mode optimizes for completeness and
follow-along usability, not analytical framing (that remains detailed mode's job). Same anti-AI-tell
writing rules carried over from the existing prompt (no greetings, no "แน่นอน!", no filler).

### 3b. Raise transcript limits — gated to full_detail mode only
Add a mode-aware transcript character budget in `summarize_local.py` instead of the current fixed
25,000/30,000 char caps: keep the existing caps unchanged for standard/detailed (don't touch
behavior nobody complained about), and use a much higher cap (proposal: 120,000 characters — well
above any realistic single YouTube video's caption length, comfortably inside Gemini 2.5 Flash's
context window) when full_detail is selected.

### 3c. Raise output token budget — gated to full_detail mode only
Current Vertex call uses `max_output_tokens=16384` for all modes. A 40+ item walkthrough in
explanatory Thai could plausibly exceed that for content-dense videos. Proposal: raise to 32768 for
full_detail only.

### 3d. Wiring — CLI, per-job config, dashboard
- `research_jobs.json`: each job already has a `"detailed": true/false` boolean. Add a new
  `"summary_mode": "standard" | "detailed" | "full_detail"` field, additive and backward compatible
  (existing jobs default to their current `detailed` value unchanged — nobody's report format
  changes unless Mandy opts a job in).
- `run_ai_trends_research_enhanced.py`: extend `process_video_with_summarize(..., detailed=False)`
  to accept `summary_mode` and select one of the three prompt files. Keep `--detailed` working as
  today (maps to `summary_mode="detailed"`) and add `--summary-mode` for the new three-way choice, so
  no existing cron invocation needs to change.
- `dashboard/app.py`: the job-edit form's existing "Detailed Thai summary" checkbox (line ~732)
  becomes a 3-option dropdown (Standard / Detailed / Full Detail). Same treatment for the on-demand
  ("run specific video") form, since Mandy's own example was an on-demand run, not a recurring cron
  job — full_detail should be selectable there too.

### What is intentionally *not* changing
- Standard and detailed modes: prompt text, transcript limits, output token budget — untouched.
- Pipeline stages downstream of summarization (GitHub upload, daily digest, Telegram notify,
  dashboard report viewer, search index) — full_detail reports are still markdown files in the same
  `reports/{topic}/{date}.md` location, so no changes needed there.

## 4. Mandy's answers (2026-07-13) — revised scope

1. Not a per-job cron default for now. Scope to **NATEHERK only** to start; other channels later, her choice.
2. Must be selectable **on-demand**, not just as a job setting.
3. NATEHERK first, no other channels yet.
4. Yes to a badge marking which reports/videos have a full-detail version.

She also raised a real dependency I hadn't checked: **NATEHERK already has automated TTS audio**
(`config/audio_topics.json` → `automated_voice_topics.nateherk`, `script_type: full`, `per_video:
true`) **emailed to her daily**, and asked whether turning on full_detail for NATEHERK would change
that audio. She then reconsidered the whole delivery model: rather than a per-job cron setting, she
wants **on-demand control** — read a report, decide a specific video needs more detail, and trigger
regeneration herself — and asked whether this fits on the existing Assets page
(`https://ai-trends.thequietself.com/assets` → `/assets/manage?topic=&date=`).

### 4a. Audio impact analysis (traced through `scripts/generate_audio_report.py`)

The per-video audio path (`_generate_per_video` → `_condense_video_section`, used for NATEHERK) does
**not** read the report's bullet count directly into the spoken script — it runs its own separate
condensation LLM call, and already caps itself independent of source detail:
`key_point_count = max(len(re.findall(r'\*\*\d+\.', section_text)), 4)` then
`para_target = min(key_point_count, 10)` (lines 193-194). So even a 42-item full-detail section would
only ever produce up to ~10 spoken paragraphs of audio, not a 42-item read-aloud — the audio length
is naturally bounded regardless of report length.

More importantly: **audio generation and full-detail generation should be separate, independent
actions**, not linked. If full_detail is added as an on-demand button on the Assets/manage page
(rather than baked into the NATEHERK cron job itself), the daily automated report + audio + email
pipeline for NATEHERK is **completely unaffected** — nothing changes unless Mandy manually triggers
full_detail for a specific video, and even then, regenerating audio for that video is a separate
existing button she'd click independently if she wants updated audio too. This addresses her FYI
concern directly: on-demand-only means zero default impact on the thing she already receives daily.

### 4b. Assets/manage page — confirmed feasible

Checked `/assets/manage?topic=&date=` (`dashboard/app.py` `render_assets_manage` /
`api_assets_videos`, ~line 2443). Each video card already has everything needed:
- `source_url` per video (line 2495) — required to re-run summarization against that exact video
- Existing precedent for per-video on-demand actions on this same page: "Generate script",
  "Generate deep-dive script", "Generate voice" all already work this way (`/api/assets/generate-one`,
  `/api/assets/generate-deep-dive-script`, `/api/assets/generate-voice`)

So a new "🔎 Full Detail" button per video card, calling a new
`/api/assets/generate-full-detail` endpoint, fits the page's existing pattern exactly — same shape as
the buttons already there.

**Storage decision:** write the full-detail output to its own new file per video (e.g.
`ai_trends_reports/reports/nateherk/{date}-v{N}-full-detail.md`), not into the existing report file.
Reasons: (1) the existing report is what the daily digest, search index, and the audio condenser's
section-splitting regex all already parse — overwriting or restructuring it risks breaking those
without any upside; (2) Mandy wants this as an *additional*, opt-in artifact she pulls up when she
wants more, not a replacement of what's already working. The badge on `/assets/manage` (and later
`/reports` if wanted) simply reflects whether this sibling file exists for a given video, the same
way `full_voice`/`deep_dive_voice` existence is already checked and shown today.

**Scope gate:** show the "🔎 Full Detail" button only when `topic == nateherk` for this first phase
(a one-line condition, trivial to lift to other topics later once proven), per Mandy's "NATEHERK
first" instruction.

### 4c. "Isn't this the same as Deep Dive?" — checked, it is not

Mandy asked whether this duplicates the existing "Deep Dive" script feature already on
`/assets/manage`, and separately flagged that the page already has too many buttons/icons to keep
track of. Traced `scripts/generate_content_assets.py` `generate_deep_dive_script()` (line 396) to
answer precisely:

| | Deep Dive (existing) | Full Detail (proposed) |
|---|---|---|
| **Source data** | `video["section_text"]` — text already pulled from the finished `--detailed` **report** (`generate_content_assets.py:409`), capped at 12,000 chars | The original YouTube **transcript**, direct from the video |
| **Can it recover content already lost by `--detailed`?** | **No** — it only rephrases/narrates what survived into the report. If a report already dropped 27 of 42 commands, Deep Dive has nothing to expand from — it never re-reads the transcript | **Yes** — this is the entire point: re-summarize from source, uncapped |
| **Output shape** | Spoken **podcast script**, plain text only, no lists/bullets/markdown, 8-12 min target (`DEEP_DIVE_SCRIPT_PROMPT`, line 122) | Written **article**, sequential numbered walkthrough, markdown, for reading |
| **Consumed by** | TTS voice generation | Read directly (or fed to TTS later like any other report) |

So Deep Dive solves a different problem (turning a written report into a narrated audio experience)
and, being built on the report rather than the transcript, structurally cannot fix what Mandy
reported. Full Detail is not redundant with it — but she is right that the page is between them
getting cluttered, so the UI plan below consolidates rather than just adding a 5th button.

### 4d. UI consolidation, not just another button

Current per-video card on `/assets/manage` already shows, per video: Gen/Regen Script, Open/Edit
Script, Gen/Regen Deep-Dive, Open DD Script, Full Voice, DD Voice, plus conditional download links —
6+ controls before this feature. Rather than bolt on a 5th "generate" and 3rd "open" button,
consolidate the generate-type actions into two dropdown controls:
- **"🤖 Generate ▾"** — one button, options: Full Script / Deep-Dive / Full Detail (replaces the two
  separate "Gen Script" + "Gen Deep-Dive" buttons)
- **"📄 View ▾"** — one button, options: Full Script / Deep-Dive / Full Detail (replaces "Open
  Script" + "Open DD Script")

Net effect: adding the third content type while *reducing* visible buttons on the card (4 buttons →
2 dropdowns), directly addressing the "too many icons, can't remember what does what" complaint
rather than making it worse. Voice generation buttons stay as-is (unrelated to this change — full
detail output isn't fed to TTS in this phase).

---

**Next Actions:**
1. Write `prompts/thai_summary_prompt_full_detail.txt`
2. Add `/api/assets/generate-full-detail` endpoint (topic/date/video_no/source_url in, writes
   `{date}-v{N}-full-detail.md`, mode-gated transcript (~120k char) and output (~32k token) limits)
3. Add "🔎 Full Detail" button + badge to `/assets/manage`, gated to `topic == nateherk`
4. Test against the HOjCT6TxlHM video specifically — confirm all 42 commands appear in the output
5. Update `docs/TASKS.md` and this doc's status to Implemented
6. Confirm with Mandy before starting whether she wants the go-ahead now
