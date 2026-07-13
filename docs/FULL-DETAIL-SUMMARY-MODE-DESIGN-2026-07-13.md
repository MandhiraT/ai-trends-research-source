# ATS Full-Detail Summary Mode — Design (not implemented)

**Status:** 🟡 Design done — awaiting Mandy's decisions before implementation
**Date:** 2026-07-13
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

## 4. Open questions for Mandy

1. **Which jobs should default to full_detail?** My guess based on content type: tool-tutorial-heavy
   topics (Claude Code subtopics, NATEHERK, Jacksons AI, Make Money Matt) are more likely candidates
   than trend-roundup topics (AI Agents, AI Viral Niche) or opinion channels (The School of Life,
   HealthyGamerGG). Want her actual list rather than guessing.
2. **On-demand form:** confirm full_detail should be selectable for one-off manual runs too (not just
   recurring cron jobs) — her own trigger case was an on-demand run.
3. **Cost/latency trade-off:** full_detail prompts will be longer (up to ~120k chars of transcript)
   and outputs longer (up to 2x current for enumeration-heavy videos), so Vertex calls will cost more
   and take longer per video. Confirming this is acceptable given it's opt-in per job.
4. **Daily digest / Telegram distinction:** should full_detail reports be visually flagged in the
   daily digest (e.g., a "📘 Full Detail" badge) so Mandy can tell at a glance which reports are the
   enumerative kind vs. the analytical kind, or is the report content itself enough?

---

**Next Actions (once Mandy answers the above):**
1. Write `prompts/thai_summary_prompt_full_detail.txt`
2. Add `summary_mode` to `research_jobs.json` schema + migrate existing jobs (default = current `detailed` value)
3. Extend `process_video_with_summarize()` / `summarize_video()` for 3-way mode + mode-gated transcript/output limits
4. Update dashboard job-edit form + on-demand form (dropdown instead of checkbox)
5. Test against the HOjCT6TxlHM video specifically — confirm all 42 commands appear in the new report
6. Update `docs/TASKS.md` and this doc's status to Implemented
