# AI Trends Research — Tasks & Project Status

> Working document for team/agent collaboration. Update this file whenever features change, bugs are found, or new work is planned. Keep statuses current.

**Last updated:** 2026-06-24 ICT
**Maintained by:** Sati (primary agent) / Mandhira / Mali

---

## Project Health

| Item | Status |
|------|--------|
| Daily pipeline | ✅ Running (system crontab, Bangkok/ICT timezone) |
| Detailed summaries | ✅ Working (--detailed flag in all cron jobs) |
| Audio TTS reports | ✅ Working (Gemini 2.5 Flash TTS, per-video mode) |
| GitHub upload | ✅ Hardened 2026-06-24 (fresh clone per publish, explicit publish-status warnings) |
| Dedup system | ✅ Working |
| Telegram daily digest | ✅ Working (includes audio status) |
| Per-topic report/voice notifications | ✅ Added 2026-05-27 — `run_daily_summary_cron.sh` sends configured email/Telegram topic notifications after report upload + audio upload, before final daily digest |
| Hallucination guard | ✅ Fixed 2026-05-24 (no downloadable captions → transcript unavailable; Thai captions are supported; production jobs now pass explicit transcript language order) |
| Cron project path | ✅ Fixed 2026-05-12 (`Desktop/Projects`, not lowercase `projects`) |
| Claude Code new subtopics | ✅ Working (Seedance, Higgsfield, Shopify, Hyperframe, Heygen) |
| Local dashboard | ✅ Working (`http://127.0.0.1:8092`) |
| Searchable report index | ✅ Working (385 summarized video sections indexed locally, no-AI-cost backfill) |
| Cloudflare dashboard route | ✅ Working (`https://ai-trends.thequietself.com`) |
| Dashboard systemd service | ✅ Working (user-level `ats-dashboard.service`, auto-restart, linger enabled) |
| Content asset generation | ✅ Working (`generate_content_assets.py`, dashboard Assets tab; manual audio/social works for all topics; asset JSON folders canonicalized to slug paths) |
| Daily asset-only automation | ✅ Added 2026-07-08 (`scripts/run_daily_assets_cron.py`; 12:20 ICT cron; today-only, skip existing, no AI/social/audio cost) |
| Dashboard Asset batch generate | ✅ Working (date range, skip existing, progress bar, per-row buttons; manual AI generation overrides default priority-topic policy) |
| Dashboard Existing Assets filters | ✅ Working (client-side topic/date table filter, verified Joanna today case) |
| Voice generation design / manual flow | ✅ Implemented for script-first workflow (`docs/VOICE-DESIGN.md`, Assets page) |
| Dashboard multi-video asset manage | ✅ Working — `/assets/manage?topic=&date=` per-video cards, bulk voice, script editor, no window.prompt() |
| Dashboard Assets date filter | ✅ Fixed 2026-05-21 (empty default — was defaulting to today, hiding all historical rows) |
| Finance/personal-finance channels | ✅ Added 2026-05-23 — 5 practical daily-life finance channels at 07:45–08:25 ICT |
| Health topics/playlists | ✅ Added 2026-05-27 — `Health/อาหารบำรุงสุขภาพ` search + `Health/Top to Toe` playlist at 08:45/09:00 ICT; daily summary moved to 09:30 ICT |
| Self-help Thai podcast playlist | ✅ Added 2026-06-06 — `Go with The Four` playlist under `self_help/thai/podcast/go_with_the_four` at 11:50 ICT; included in self-help daily summary |

---

## Current Features (Implemented)

| Feature | Description | Script |
|---------|-------------|--------|
| YouTube topic search | yt-dlp search by keyword, max-results configurable | `run_ai_trends_research_enhanced.py` |
| YouTube channel scrape | Fetch latest videos from specific channel | `run_ai_trends_research_enhanced.py --channel` |
| Content dedup | MD5 hash of title+description+duration, skip seen videos | All research scripts |
| Thai summarization | Vertex AI (ADC) → qwen → glm → gemini → gemma fallback chain | `summarize_local.py` |
| Standard prompt | Slide-based summary (~500 words) | `prompts/thai_summary_prompt.txt` |
| Detailed prompt | Section-based summary (2000-3000 words, 🎯📝🛠️📊💡 headers) | `prompts/thai_summary_prompt_detailed.txt` |
| Claude Code subtopics | Base + new subtopics: obsidian, notebooklm, design, skills, remotion video, video, seedance, higgsfield, shopify, hyperframe, heygen | `run_claude_code_subtopics_enhanced.py` |
| Daily Thai digest | Aggregates all topic reports + GitHub links + audio status | `ai_trends_daily_summary_thai.py` |
| Per-topic notification | Sends configured report/voice links by email and/or Telegram after daily report/audio upload | `notify_topic.py`, `config/notification_routing.json` |
| GitHub auto-upload | Clone reports repo → copy files → git push | `upload_reports_to_github_fixed.py` |
| Manual pipeline runner | `run_all_today.sh` runs all 29 steps sequentially | `scripts/run_all_today.sh` |
| Rate limit handling | Auto-retry with backoff on 429 errors | `summarize_local.py` |
| Audio TTS generation | Gemini 2.5 Flash TTS, per-video mode, FFmpeg concat, daily Telegram status | `generate_audio_report.py` |
| Hallucination guard | No downloadable captions → early return "transcript unavailable" (no AI hallucination); Thai/English/any caption tracks are attempted in job-specific order via `--transcript-langs` | `summarize_local.py` |
| Local web dashboard | Add/edit research jobs, manual runs, report/log browser, read-only cron view | `dashboard/app.py` |
|| Searchable report index | JSONL/SQLite/Markdown mobile indexes + CLI search for report archive | `scripts/build_report_index.py`, `scripts/search_reports.py` |
|| Dashboard search | Search reports by query/topic/tag from Dashboard UI | `dashboard/app.py` `/search`, `/api/search` |
| Dashboard content assets | Generate asset JSON, audio scripts, deep-dive scripts, social posts per report | `dashboard/app.py` `/assets`, `/api/assets/generate`, `/api/assets/generate-one`, `/api/assets/generate-deep-dive-script` |
| Daily asset-only cron | Generates structured JSON assets for today's reports only; skips existing files; no AI/social/audio generation | `scripts/run_daily_assets_cron.py` |
| Dashboard asset batch generate | Date range filter, skip existing, AI confirm, progress bar, per-row buttons | `dashboard/app.py` `/api/assets/progress` |
| Dashboard Existing Assets filters | Client-side table filtering by Topic + Date from/to; counter updates live | `dashboard/app.py` `/assets` |
| Voice generation manual flow | Script editor/save + Gemini TTS voice from saved full/deep-dive scripts only | `dashboard/app.py`, `scripts/voice_engine.py` |
| Dashboard multi-video manage page | `/assets/manage?topic=&date=` — per-video cards (status dots, explicit buttons), script editor, bulk voice checkboxes, Regen All Scripts; no window.prompt() anywhere | `dashboard/app.py` `/assets/manage`, `/api/assets/videos` |
| Dashboard job config | JSON-managed research job list for dashboard/manual execution | `config/research_jobs.json` |
| Specific video/manual report routing | Supports dashboard `--video-url`, `--report-folder`, `--config-job-id` | `run_ai_trends_research_enhanced.py` |

---

## Task Board

### In Progress

| Task | Status | Notes |
|------|--------|-------|
| ATS voice generation implementation — Phase 1 | ✅ Core completed, pending next phase | Added unified voice engine `scripts/voice_engine.py`, default voice profile `ats_female_narrator` = Gemini TTS `Aoede`, refactored `generate_audio_report.py` to use the shared engine wrappers, extended `config/audio_topics.json` with automation policy. Verification passed: py_compile, config JSON, voice engine dry-run, legacy CLI help, profile load. Next: optional Joanna automation after NATEHERK compatibility checks. |
| ATS output repo folder cleanup — Phase A | ✅ Local migration done, pending commit/push decision | Documented plan in `docs/OUTPUT-REPO-FOLDER-MIGRATION.md`. Restored stale deleted reports in `/tmp/ai-trends-research`, updated source upload path logic (`scripts/upload_audio_to_github.py`) to publish to canonical `voice/{topic}/`, changed `config/audio_topics.json` map `NATEHERK → nateherk`, and local-migrated output repo with `git mv`: 13 files `Voice/NateHerk/*.wav → voice/nateherk/*.wav`. Verified: `voice/nateherk` count=13, `voice/joanna_wiebe` count=8, legacy `Voice/` gone, `.ogg` count=0. `Content Marketing/` left untouched for separate duplicate/link review. Handoff: inspect source repo and `/tmp/ai-trends-research` git status; output repo currently has 13 staged renames unless committed/pushed later. |

### Recently Interrupted / Needs Resume

| Task | Status | Notes |
|------|--------|-------|
| Hermes model switch | ⏳ Config partially updated; resume needed | Requested: primary `openai-codex/gpt-5.5`, fallback `zai/glm-5`, then restart gateway. Completed before interruption: `model.provider=openai-codex`, `model.default=gpt-5.5`, `model.base_url=https://chatgpt.com/backend-api/codex`. Still need to update `fallback_providers` to `zai/glm-5`, verify config, restart gateway, confirm status. |

### Completed

| ID | Task | Completed | Notes |
|----|------|-----------|-------|
| T-001 | Initial pipeline setup (yt-dlp + Gemini summarize) | 2026-04-early | |
| T-002 | Add content dedup via MD5 hash | 2026-04-early | Prevents re-processing same video |
| T-003 | Add Gemini fallback providers (qwen → glm → gemini → gemma) | 2026-04-early | |
| T-004 | Add detailed Thai prompt (thai_summary_prompt_detailed.txt) | 2026-04-24 | 2000-3000 words target |
| T-005 | Switch to Vertex AI (ADC) as primary provider | 2026-04-24 | commit 4329304 |
| T-006 | Add Claude Code subtopics research (obsidian/notebooklm/design/skills) | 2026-04-25 | |
| T-007 | Add system crontab pipeline (replace OpenClaw cron) | 2026-04-25 | crontab UTC schedule |
| T-008 | **Fix: Add --detailed flag to crontab + run_all_today.sh** | 2026-04-26 | Bug: reports using standard prompt; crontab and run_all_today.sh both fixed |
| T-009 | **Fix: Add --detailed support to run_claude_code_subtopics_enhanced.py** | 2026-04-26 | Subtopics script had no --detailed arg; now supports it properly |
| T-010 | **Re-run all 2026-04-26 reports with --detailed** | 2026-04-26 | Cleared hashes, deleted short reports, re-ran full pipeline — all 7 steps ✅ |
| T-011 | **Create docs/TASKS.md project tracking document** | 2026-04-26 | New working doc for team/agent collaboration |
| T-012 | **Update CLAUDE.md — correct cron times, cron system, --detailed requirement** | 2026-04-26 | CLAUDE.md was referencing OpenClaw (disabled), wrong ICT times, missing --detailed |
| T-013 | **Add Audio TTS feature (Gemini 2.5 Flash)** | 2026-05-07 | `generate_audio_report.py` — per-video mode, condense prompt, FFmpeg concat, Telegram status |
| T-014 | **Add 3 new channels: Jacksons AI, Make Money Matt, Miss Luna Vega** | 2026-05-07 | Added to crontab at 07:05, 07:15, 07:25 Bangkok time |
| T-015 | **Fix cron schedule docs: Bangkok timezone (not UTC)** | 2026-05-07 | TASKS.md had wrong UTC times; corrected to Bangkok/ICT |
| T-016 | **Fix hallucination in summarize_local.py for non-English videos** | 2026-05-09 | Added early-return guard: no transcript → return "ไม่สามารถสรุปวิดีโอนี้ได้" instead of asking AI to summarize from knowledge |
| T-017 | **Re-summarize AI Agents + AI Viral Niche reports (2026-05-06 and 2026-05-07)** | 2026-05-09 | 8/9 videos properly summarized; 1/9 correctly marked unavailable (Thai video, no EN transcript) |
| T-018 | **Fix AI Trends cron lowercase project path** | 2026-05-12 | Updated installed crontab and docs from `/Desktop/projects/...` to `/Desktop/Projects/...`; backfilled 2026-05-12 summary successfully |
| T-019 | **Add Claude Code new subtopics: Seedance, Higgsfield, Shopify** | 2026-05-12 | Added `--only "seedance,higgsfield,shopify"` cron at 07:35 Bangkok, 5 clips each, reports under `reports/claude_code/{topic}/` |
| T-020 | **Add AI Trends Search dashboard MVP** | 2026-05-13 | Added local dashboard, JSON job config, manual run support, report/log browser, and read-only cron view |
| T-021 | **Expose AI Trends dashboard through existing Cloudflare Tunnel** | 2026-05-13 | Reused `faw-dashboard`; added `ai-trends.thequietself.com -> localhost:8092`; verified HTTP 200 |
| T-022 | **Add searchable report index + no-AI backfill** | 2026-05-14 | Added `build_report_index.py`, `search_reports.py`, tests, JSONL/SQLite/Markdown mobile indexes; backfilled 385 summarized video sections |
| T-023 | **Add Dashboard Search tab** | 2026-05-14 | Added `/search` UI + `/api/search` JSON endpoint + `/api/search/rebuild`; filters by query/topic/tag; uses existing JSONL index |
| T-024 | **Add Dashboard Assets tab with batch + per-row generate** | 2026-05-14 | Content asset layer: `generate_content_assets.py` + dashboard `/assets` UI + `/api/assets/generate` endpoint |
| T-025 | **Improve Assets tab UX: date range, skip existing, per-row buttons, confirm, progress** | 2026-05-17 | Added date-from/to filters, "Today"/"Last 7 days"/"All dates" shortcuts, skip-existing toggle, AI-mode confirm dialog, real-time progress bar, per-row generate buttons (📄🔊📱🚀), new `/api/assets/generate-one` and `/api/assets/progress` endpoints |
| T-026 | **Create systemd service for ATS Dashboard** | 2026-05-17 | User-level `~/.config/systemd/user/ats-dashboard.service`, auto-restart on failure, enabled + linger enabled for boot-time start |
| T-027 | **Fix ATS Dashboard Cloudflare tunnel (port 8092 down)** | 2026-05-17 | Dashboard process had died (no systemd service). Created `ats-dashboard.service` to auto-restart. Verified both `localhost:8092` and `ai-trends.thequietself.com` → HTTP 200 |
| T-028 | **Fix ATS Dashboard Assets filters** | 2026-05-17 | Fixed display-name vs folder-slug topic mismatch, skip_existing, per-row generate-one, and Existing Assets table filtering by topic/date. Verified Joanna+today → 1 row and full filter scenarios. |
| T-029 | **Design ATS voice generation architecture** | 2026-05-17 | Designed two voice types: full script voice (`vN.wav`) and deep dive voice (`vN-deep-dive.wav`), Gemini TTS chunking/concat, asset JSON extensions, and Dashboard voice UI. Design doc: `docs/VOICE-DESIGN.md`. Not implemented yet. |
| T-030 | **Implement ATS unified voice engine — Phase 1** | 2026-05-17 | Added `scripts/voice_engine.py`, `ats_female_narrator` voice profile (`Aoede`), refactored `generate_audio_report.py` wrappers to use the shared TTS/concat engine, and extended `config/audio_topics.json` with automation policy. Verified with py_compile, config JSON, engine dry-run, CLI help, profile load. |
| T-031 | **Implement ATS Dashboard manual voice flow — Phase 2** | 2026-05-17 | Added `/api/assets/script` GET/POST, `/api/assets/voice-status`, `/api/assets/generate-voice`, script editor on Assets page, and per-row 📝/📚/🎙️/🎧 controls. Voice is generated from saved script only; missing script returns explicit error. Verified 8/8 API tests and browser UI; no real TTS cost triggered. |
| T-032 | **ATS output repo folder cleanup — Phase A local migration** | 2026-05-17 | Migrated 13 WAV files `Voice/NateHerk → voice/nateherk`. Both repos committed and pushed. ✅ |
| T-045 | **Add Claude Code Heygen ATS subtopic** | 2026-06-04 | Added `claude code heygen` to `scripts/run_claude_code_subtopics_enhanced.py`, production 07:35 cron `--only` batch (`seedance,higgsfield,shopify,hyperframe,heygen`, `--total-videos 25`), daily summary topic `CC Heygen`, dashboard job config, and report folder `reports/claude_code/claude_code_heygen/`. |
| T-033 | **Enable Joanna Wiebe daily voice automation** | 2026-05-17 | Added `joanna_wiebe` to `enabled_topics` + `github_folder_map`, set `automated_voice_topics.joanna_wiebe.enabled=true, publish=true`. NATEHERK verified (9.9MB today). Generated and published `voice/joanna_wiebe/2026-05-17.wav` (9.2MB). From tomorrow cron generates + publishes Joanna audio automatically. |
| T-034 | **Fix Dashboard Assets all-topic manual audio/social generation** | 2026-05-17 | Fixed `name '_slug' is not defined` in `scripts/generate_content_assets.py`, added explicit manual generation override so Dashboard `+Audio`, `+Social`, and `+All` work for any topic while `PRIORITY_TOPICS` remains default automation policy only. Updated full-script prompt framing to “คนที่เพิ่งดูมาแล้วอยากบอกเล่าสิ่งที่ได้เรียนรู้”, hook-first opening, no “คลิปนี้” opening, and banned over-casual words (`แก`, `เว้ย`, `แกๆ`, `โห`, `โคตร`, `เจ๋ง`, `อ่ะ`). Verification: py_compile passed, unit/fake-AI all-topic test passed, local `/assets` + asset endpoints 5/5, browser page loads via Cloudflare route with no console errors, real `jacksons_ai` audio-script generation returned 200 and created `audio_scripts/jacksons_ai/2026-05-17-v1.md`. |
| T-035 | **Add Dashboard deep-dive script generation** | 2026-05-17 | Added script-first `📖 Generate deep dive script` button and `POST /api/assets/generate-deep-dive-script`. The endpoint creates only `audio_scripts/{topic}/{date}-vN-deep-dive.md` with `## Deep Dive Script`; it does not create voice. Existing scripts are not overwritten unless `force=1`. Added deep-dive prompt based on the Full Episode Formula plus a quality retry guard for forbidden greetings/openings. Verification: new tests 5/5 for generator + Dashboard workflow, full test suite 9/9, py_compile passed, local `/assets` 200, Cloudflare Assets page shows 📖 controls with no console errors, real `jacksons_ai` deep-dive script generated (8,482 chars) and no WAV was created. |
| T-036 | **Fix Dashboard asset duplicate rows + nested underscore topic generation** | 2026-05-17 | Root cause: legacy/display-name asset folders (`AI Agents/`, `Jacksons AI/`, `NATEHERK/`, `claude code design/`) coexisted with canonical slug folders, and `/api/assets/generate-one` could not resolve nested subtopic reports such as `reports/claude_code/claude_code_design/2026-05-17.md`, then falsely fell back to an unrelated date match (`NATEHERK`). Fixes: added slug-safe nested report resolver, fixed `find_reports()` for nested underscore topics, added Dashboard asset-row dedupe, added success validation so audio/social modes error if no output file is created, canonicalized all asset JSON files to slug folders, and removed legacy empty folders after backup. Verification: `15 passed`, py_compile passed, asset audit shows `duplicate_key_count=0`, `space_dir_count=0`, `noncanonical_count=0`; real `claude_code_design/2026-05-17` audio script generation created v1/v2/v3 markdown files and Dashboard 📝 status is green. |
| T-040 | **Add finance/personal-finance channels to ATS daily cron** | 2026-05-23 | Added 5 channel jobs for practical daily-life finance summaries: Finance Money Coach (`@THEMONEYCOACHTH`), Finance Money Buffalo (`/c/MoneyBuffalo`), Finance A-Academy (`/user/aacademychannel`), Finance Financial Diet (`@thefinancialdiet`), Finance Humphrey Yang (`@humphrey`). Cron runs 07:45–08:25 ICT, max-results 3 each, `--detailed`; daily summary moved from 07:55 to 08:55 ICT so tomorrow's digest can include finance reports. Updated `config/research_jobs.json`, `scripts/ai_trends_daily_summary_thai.py`, and `scripts/run_all_today.sh`. |
| T-042 | **Add Boom BigNose Thai AI channel to ATS daily cron** | 2026-05-24 | Added `Boom BigNose` (`@BoomBigNose`) as a production channel job at 08:35 ICT, max-results 3, `--detailed`. Updated `config/research_jobs.json`, `scripts/ai_trends_daily_summary_thai.py`, `scripts/run_all_today.sh`, `CLAUDE.md`, and installed crontab so tomorrow's 08:55 digest can include the report if new content is found. Verification: JSON load, py_compile, bash -n, crontab grep, and yt-dlp metadata probe. |
| T-043 | **Add Health topics/playlists to ATS daily cron** | 2026-05-27 | Added two production jobs under `reports/health/`: `Health — อาหารบำรุงสุขภาพ` as YouTube search at 08:45 ICT (`--report-folder health/health_food_nutrition --max-results 5 --detailed`) and `Health — Top to Toe` playlist at 09:00 ICT (`--report-folder health/top_to_toe --channel playlist --max-results 5 --detailed`). Daily summary moved to 09:30 ICT so Health reports can be included. Updated installed crontab, `config/research_jobs.json`, `scripts/ai_trends_daily_summary_thai.py`, `scripts/run_all_today.sh`, and `CLAUDE.md`. |
| T-044 | **Add per-topic report/voice notifications to end-of-day pipeline** | 2026-05-27 | `run_daily_summary_cron.sh` now runs in this order: upload Markdown reports → generate enabled audio → upload WAV/audio scripts → `notify_topic.py --all` email/Telegram per routing config → final Thai Telegram daily digest with audio status. Routing config currently enables `nateherk` email+Telegram, `health_food_nutrition` email, and keeps `joanna_wiebe` disabled. Fixed notification URL resolution so nested Health report folders and mapped audio folders resolve correctly. |
| T-041 | **Fix Thai transcript support for finance channel summaries** | 2026-05-24 | Root cause: `summarize_local.py` downloaded only `--sub-lang en`; Thai finance channels had usable `th` captions while English auto-translation could fail with 429, so reports incorrectly said “ไม่มี transcript ภาษาอังกฤษ”. Fixed transcript extraction to try Thai first, then English, then any caption track before returning unavailable. Updated unavailable reason text to no longer say English-only. Added regression tests for Thai-first extraction and English fallback. Verification: `python3 -m py_compile scripts/summarize_local.py` ✅, `pytest tests/test_summarize_local_transcripts.py tests/test_report_index.py -q` = 6 passed ✅, live no-AI transcript smoke tests found Thai transcripts for Finance Money Coach, Finance Money Buffalo, and Finance A-Academy first videos ✅. Full `pytest tests -q` is currently blocked by pre-existing `dashboard/app.py` SyntaxError at line 1906 (unrelated to this change). |
| T-037 | **Fix Dashboard Assets page showing empty table (date filter defaulted to today)** | 2026-05-21 | Root causes: (1) `date_from`/`date_to` inputs defaulted to today's date, so `filterTable()` on DOMContentLoaded hid all historical rows; (2) no asset JSONs generated since 2026-05-18 (asset generation is manual). Fix: changed both date inputs to `value=""`. Verified: May 18 rows visible on fresh page load, "Today" and "Last 7 days" shortcuts still work. |
| T-038 | **Add Hyperframe to Claude Code new subtopics** | 2026-05-21 | Added `hyperframe` to `--only` list, bumped `--total-videos` from 15 to 20. Updated `CLAUDE.md` and `docs/TASKS.md`. |
| T-039 | **Implement Dashboard multi-video asset manage page** | 2026-05-21 | Full multi-video manage implementation in `dashboard/app.py`. New: `GET /assets/manage?topic=&date=` (per-video cards with status dots, explicit script/voice buttons, script editor, bulk voice with checkboxes + confirm, Regen All Scripts), `GET /api/assets/videos` JSON endpoint (per-video `full_script.exists`, `deep_dive_script.exists`, `full_voice.exists`, `deep_dive_voice.exists`). Main `/assets` page: Script/Voice column → Manage column (🎛️ link), aggregate count badges (📝📖🎙️🎧 in N/T green/yellow/gray format), script editor removed, old prompt-based `generateDeepDiveScript`/`generateVoice`/`openScript`/`saveScript` JS removed. No `window.prompt()` anywhere. Plan doc `DASHBOARD-ASSET-MANAGE-PAGE-PLAN.md` updated with 7 implementation gaps + open question answers. All 32 ISC + 3 anti-criteria verified. |
| T-040 | **Add explicit transcript language routing to production jobs** | 2026-05-29 | Added `--transcript-langs` CLI support so each production job controls caption order explicitly instead of guessing from topic names. English/international jobs use `en,th,all`; Thai jobs use `th,en,all`. Updated installed crontab, `config/research_jobs.json`, `scripts/run_all_today.sh`, `dashboard/app.py`, `run_ai_trends_research_enhanced.py`, and `summarize_local.py`. Added regression tests for parser, summarize propagation, and explicit English-first extraction. |
| T-041 | **Add Psych2Go to Self-help Phase 1 psychology batch** | 2026-05-29 | Added `Self Help/Psychology — Psych2Go` (`@Psych2go`) under `self_help/psychology/psych2go`, English-first transcript routing, production cron at 11:00 ICT. Rationale: was present in the research matrix as a mass-reach psychology/animation reference but omitted from first top-10 production batch due simplified-content caution; Mandy requested it in Phase 1. |
| T-042 | **Reconcile Self Help Channel DOCX and expand Phase 1 to 15 channels** | 2026-05-29 | Extracted Mandy's `Self Help Channel.docx` into `docs/SELF-HELP-CHANNEL-DOCX-EXTRACTED.md`, added reconciliation note `docs/SELF-HELP-PHASE1-DOCX-RECONCILIATION.md`, and expanded production self-help Phase 1 with the four remaining DOCX gaps: Clark Kegley, Pursuit of Wonder, The Mindful Movement, and Acharya Prashant. Daily summary moved to 12:10 ICT so the 11:40 job can finish. |
| T-046 | **Add Go with The Four Thai podcast playlist to ATS self-help cron** | 2026-06-06 | Added playlist job `self_help_thai_go_with_the_four` at 11:50 ICT, max 5 videos, Thai-first transcript routing, report folder `self_help/thai/podcast/go_with_the_four`, and self-help daily summary inclusion. |

| T-047 | **Harden ATS output-repo publishing against stale clone corruption** | 2026-06-24 | Root cause of missed 2026-06-23/24 daily summaries was a corrupted long-lived output clone. Permanent fix: added shared `github_output_repo.py`, switched reports/audio publishers to fresh clone per run with explicit push auth, moved default checkout path from `/tmp` to `~/.cache/ai-trends-research/github-output-repo`, and changed `run_daily_summary_cron.sh` + `ai_trends_daily_summary_thai.py` so Telegram summaries still send with publish warnings if GitHub upload fails. Verification: `py_compile` on 4 scripts ✅, `bash -n scripts/run_daily_summary_cron.sh` ✅, full `pytest -q` = 79 passed ✅. |
|
### Backlog

| ID | Task | Priority | Notes |
|----|------|----------|-------|
| T-013 | Sync production runtime (workspace-atlas) with source | Medium | `/home/mandhira/.openclaw/workspace-atlas/scripts/` is missing `import time` + `time.sleep(15)`. Low risk — crontab points to source directly. |
| T-014 | Add Joanna Wiebe path consistency check (saves to joanna_wiebe not joanna-wiebe) | Low | Check if path mismatch causes any GitHub upload issues |
| T-015 | Add AI Viral Niche channel source (currently search-only) | Low | Consider adding a dedicated channel for viral AI content |
| T-016 | Add report word count / quality check to daily digest | Low | Alert if a report is under 500 words (indicates standard prompt was used) |
| T-017 | Add new topic: Prompt Engineering | Low | Potential high-value topic |
| T-018 | Confirm Cloudflare Access policy for AI Trends dashboard | High | Local verification cannot confirm Access policy. Dashboard can run local scripts, so `ai-trends.thequietself.com` should require Cloudflare Access login. |
|| ~~T-019~~ | **Add Dashboard Search tab backed by report index** | ~~High~~ | ✅ Completed 2026-05-14 as T-023: `/search` UI + `/api/search` JSON endpoint + `/api/search/rebuild` |
|| ~~T-020~~ | **Add content asset layer for audio/social/Sonar scripts** | ~~High~~ | ✅ Completed 2026-05-14 as T-024: `generate_content_assets.py` + dashboard Assets tab |
| T-021 | **Implement ATS voice generation** | Medium | NATEHERK + Joanna Wiebe daily automation fully enabled. Both publish to `voice/{topic}/` in output repo. Deep-dive script + voice generation available from Dashboard manage page. Remaining: optional short-script voice if needed. |
| T-048 | **Add "full detail" summary mode (on-demand, NATEHERK-first)** | High | Mandy reported `--detailed` mode compresses instructional/tutorial videos into 4-7 thematic bullets, losing individual steps (example: 42-command camera-movement tutorial → only ~15 commands surfaced across 5 themes). Root cause + fix design written: `docs/FULL-DETAIL-SUMMARY-MODE-DESIGN-2026-07-13.md`. Revised per Mandy's feedback: NOT a per-job cron default — an **on-demand** "🔎 Full Detail" button on `/assets/manage`, gated to NATEHERK only for now, writes a sibling `{date}-v{N}-full-detail.md` file (existing report/audio/digest untouched), badge shown when it exists. Audio impact checked: NATEHERK's per-video TTS condenser already self-caps at ~10 paragraphs independent of source length, and is a separate manual action, so daily automated audio/email is unaffected. Design done, **not implemented** — awaiting Mandy's go-ahead. |

---

## Known Bugs / Issues

| ID | Bug | Severity | Status | Found |
|----|-----|----------|--------|-------|
| B-001 | **--detailed flag missing from crontab/run_all_today.sh** | High | ✅ Fixed 2026-04-26 | Reports on 2026-04-26 were short slide-based format instead of detailed sections |
| B-002 | workspace-atlas scripts out of sync with source | Low | Open | Missing `import time` and `time.sleep(15)` — low risk since crontab uses source directly |
| B-003 | Subtopic hash files saved inside reports/claude_code/ not ai_trends_reports/ | Low | Open | Inconsistent path: `ai_trends_reports/reports/claude_code/content_hashes_*.json` vs `ai_trends_reports/content_hashes_*.json` for other topics |
| B-004 | AI Trends cron used lowercase `/Desktop/projects/...` path | High | ✅ Fixed 2026-05-12 | Root cause of missed 2026-05-12 daily summary; crontab now uses `/Desktop/Projects/...` |
| B-005 | Dashboard Assets duplicate rows / false "เสร็จแล้ว" for nested underscore topics | High | ✅ Fixed 2026-05-17 | Caused by display-name asset JSON folders plus generate-one fallback resolving `claude_code_design` to unrelated `NATEHERK` report. Fixed in T-036. |
| B-006 | Thai finance videos with Thai captions incorrectly marked “ไม่มี transcript ภาษาอังกฤษ” | High | ✅ Fixed 2026-05-24 | `summarize_local.py` was English-caption-only; now tries `th`, `en`, then `all` caption tracks before returning unavailable. |
| B-007 | ATS output repo publisher could fail on stale/corrupted long-lived clone and block daily summary | High | ✅ Fixed 2026-06-24 | Replaced reused temp clone flow with fresh-clone-per-run publisher + summary warnings on upload failure. Root cause of missing daily summaries on 2026-06-23/24. |
| B-008 | Dashboard Assets page silently drops topics past 100 total assets | High | ✅ Fixed 2026-07-13 | `existing[-100:]` capped by `rglob()` traversal order (alphabetical topic, then date) instead of actual recency — topics sorting early alphabetically (e.g. `ai_viral_niche`) fell off the list entirely once total asset count passed 100, even for a JSON generated moments earlier. Mandy hit this generating AI Viral Niche assets and not seeing them afterward. Fixed by sorting `existing` by date before capping (`dashboard/app.py`, commit `80f544a`); verified live — all 4 recent ai_viral_niche rows now appear. |

---

## Architecture Decisions (Don't Re-debate)

| Decision | Reason |
|----------|--------|
| Dedup by MD5 content hash, not video ID | Catches near-duplicate content across multiple searches |
| `summarize_local.py` not `summarize` CLI | External `summarize` CLI removed; local script gives full provider chain control |
| System crontab (Bangkok/ICT), not OpenClaw cron | OpenClaw cron jobs are all disabled; system crontab is more reliable |
| Source dir is canonical, workspace-atlas is legacy | Edit source, crontab points to source directly; workspace-atlas not used for new runs |
| Thai output only | All summaries in Thai regardless of video language |
| Reports repo ≠ source repo | `ai-trends-research` (reports) and `ai-trends-research-source` (code) are separate repos |
| `--detailed` flag for all cron/manual runs | Standard prompt produces ~500 word slide summaries; detailed produces 2000-3000 word section-based reports which are significantly more useful |
| Dashboard is non-invasive | Dashboard manual/config layer does not replace production cron; cron remains the production source of truth |
| Reuse existing Cloudflare Tunnel | `ai-trends.thequietself.com` uses the existing `faw-dashboard` tunnel; no new tunnel was created |
| Dashboard runs as user systemd service | `ats-dashboard.service` auto-restarts on failure, starts at boot via linger; no sudo required |
| Voice generation remains separate from script generation | Current `generate_content_assets.py --with-audio` creates scripts only. Voice implementation should create WAV outputs via Gemini TTS from saved scripts, with separate full-script and deep-dive voice types. |

---

## Cron Schedule (Current — Bangkok/ICT)

> System crontab runs on Bangkok time on this machine. Research jobs now run in two reporting rounds: morning jobs 05:00–09:00 with morning upload/audio/digest at 09:30 ICT, then self-help jobs 09:40–11:40 with self-help upload/digest at 12:10 ICT.

| Bangkok Time | Topic | Args |
|--------------|-------|------|
| 05:00 | AI Agents (search) | `--max-results 5 --detailed` |
| 05:20 | Claude Code (search) | `--max-results 5 --detailed` |
| 05:40 | AI Viral Niche (search) | `--max-results 5 --detailed` |
| 06:00 | NATEHERK (channel) | `--max-results 3 --detailed` |
| 06:25 | Joanna Wiebe (channel) | `--max-results 3 --detailed` |
| 06:55 | Claude Code base subtopics | `--max-results 3 --total-videos 18 --transcript-langs "en,th,all" --detailed` |
| 07:05 | Jacksons AI (channel) | `--max-results 3 --detailed` |
| 07:15 | Make Money Matt (channel) | `--max-results 3 --detailed` |
| 07:25 | Miss Luna Vega (playlist) | `--max-results 3 --detailed` |
| 07:35 | Claude Code new subtopics | `--only "seedance,higgsfield,shopify,hyperframe,heygen" --max-results 5 --total-videos 25 --transcript-langs "en,th,all" --detailed` |
| 07:45–08:25 | Finance channels | 5 channel jobs, `--max-results 3 --detailed` |
| 08:35 | Boom BigNose (channel) | `--max-results 3 --detailed` |
| 08:45 | Health — อาหารบำรุงสุขภาพ (search) | `--report-folder health/health_food_nutrition --max-results 5 --detailed` |
| 09:00 | Health — Top to Toe (playlist) | `--report-folder health/top_to_toe --channel playlist --max-results 5 --detailed` |
| 09:40–11:40 | Self-help reviewed set | 13 channel jobs under `self_help/{psychology,habits,thai}`; English jobs use `en,th,all`, Thai jobs use `th,en,all` |
| 09:30 | Morning pipeline | `run_daily_summary_cron.sh --group morning`: upload reports → generate enabled audio → upload audio/scripts → per-topic notifications (`notify_topic.py --all`) → morning Telegram digest excluding self-help |
| 12:10 | Self-help pipeline | `run_daily_summary_cron.sh --group self_help`: upload reports → self-help-only Telegram digest |

---

## How to Run Manually

```bash
cd /home/mandhira/Desktop/Projects/ai-trends-research-source

# Full pipeline (all 34 steps, detailed summaries + end-of-day upload/audio/notifications)
bash scripts/run_all_today.sh

# Single topic
bash scripts/run_ai_trends_with_creds.sh --topic "AI Agents" --max-results 5 --detailed

# Single channel
bash scripts/run_ai_trends_with_creds.sh \
  --topic "NATEHERK" \
  --channel "https://youtube.com/@NATEHERK" \
  --max-results 3 --detailed

# Claude Code subtopics only
bash scripts/run_claude_code_subtopics_with_creds.sh --max-results 3 --total-videos 18 --transcript-langs "en,th,all" --detailed

# Claude Code new subtopics only
bash scripts/run_claude_code_subtopics_with_creds.sh --only "seedance,higgsfield,shopify,hyperframe,heygen" --max-results 5 --total-videos 25 --transcript-langs "en,th,all" --detailed

# End-of-day pipeline only: GitHub upload → audio → audio upload → per-topic notifications → daily digest
bash scripts/run_daily_summary_cron.sh

# Start local dashboard
python3 dashboard/app.py --host 127.0.0.1 --port 8092

# Build searchable report index (no AI/TTS cost)
python3 scripts/build_report_index.py

# Search report archive from CLI
python3 scripts/search_reports.py "NATEHERK claude code" --limit 10
python3 scripts/search_reports.py --tag ai-coding --limit 10
```

Dashboard URLs:

- Local: `http://127.0.0.1:8092`
- Public route: `https://ai-trends.thequietself.com`
- Cloudflare Access must be checked in Cloudflare Zero Trust before treating the public route as private.

Dashboard service management (user systemd):

```bash
systemctl --user status ats-dashboard     # check status
systemctl --user restart ats-dashboard    # restart
systemctl --user stop ats-dashboard       # stop
systemctl --user start ats-dashboard      # start
journalctl --user -u ats-dashboard -f     # live logs
```

Service file: `~/.config/systemd/user/ats-dashboard.service`

---

## Re-run Reports for a Specific Date (If Reports Are Wrong)

If reports were generated with the wrong prompt (e.g., standard instead of detailed):

```bash
cd /home/mandhira/Desktop/Projects/ai-trends-research-source
DATE="2026-04-26"  # change as needed

# 1. Check which hash files changed (how many new hashes per topic from logs)
grep "Updated content hashes tracker" logs/*.log | tail -20

# 2. Trim N hashes from end of each hash file (N = number printed above)
python3 -c "
import json
# Edit these pairs: (filepath, n_to_remove)
pairs = [
    ('ai_trends_reports/content_hashes_ai_agents.json', 1),
    ('ai_trends_reports/content_hashes_claude_code.json', 2),
    ('ai_trends_reports/content_hashes_NATEHERK.json', 1),
    ('ai_trends_reports/content_hashes_joanna_wiebe.json', 1),
    ('ai_trends_reports/reports/claude_code/content_hashes_claude_code_obsidian.json', 1),
    ('ai_trends_reports/reports/claude_code/content_hashes_claude_code_notebooklm.json', 2),
]
for fpath, n in pairs:
    import os
    if not os.path.exists(fpath): continue
    hashes = json.load(open(fpath))
    json.dump(hashes[:-n], open(fpath,'w'), indent=2)
    print(f'Trimmed {n} from {fpath}')
"

# 3. Delete the wrong reports
find ai_trends_reports/reports -name "${DATE}.md" -delete

# 4. Re-run pipeline
bash scripts/run_all_today.sh
```

---

## Output Locations

| Output | Local Path | GitHub |
|--------|-----------|--------|
| AI Agents report | `ai_trends_reports/reports/ai_agents/YYYY-MM-DD.md` | `reports/ai_agents/` |
| Claude Code report | `ai_trends_reports/reports/claude_code/YYYY-MM-DD.md` | `reports/claude_code/` |
| AI Viral Niche | `ai_trends_reports/reports/ai_viral_niche/YYYY-MM-DD.md` | `reports/ai_viral_niche/` |
| NATEHERK | `ai_trends_reports/reports/NATEHERK/YYYY-MM-DD.md` | `reports/NATEHERK/` |
| Joanna Wiebe | `ai_trends_reports/reports/joanna_wiebe/YYYY-MM-DD.md` | `reports/joanna-wiebe/` |
| CC Obsidian | `ai_trends_reports/reports/claude_code/claude_code_obsidian/YYYY-MM-DD.md` | `reports/claude_code/claude_code_obsidian/` |
| CC NotebookLM | `ai_trends_reports/reports/claude_code/claude_code_notebooklm/YYYY-MM-DD.md` | `reports/claude_code/claude_code_notebooklm/` |
| CC Design | `ai_trends_reports/reports/claude_code/claude_code_design/YYYY-MM-DD.md` | `reports/claude_code/claude_code_design/` |
| CC Skills | `ai_trends_reports/reports/claude_code/claude_code_skills/YYYY-MM-DD.md` | `reports/claude_code/claude_code_skills/` |
| CC Remotion Video | `ai_trends_reports/reports/claude_code/claude_code_remotion_video/YYYY-MM-DD.md` | `reports/claude_code/claude_code_remotion_video/` |
| CC Video | `ai_trends_reports/reports/claude_code/claude_code_video/YYYY-MM-DD.md` | `reports/claude_code/claude_code_video/` |
| CC Seedance | `ai_trends_reports/reports/claude_code/claude_code_seedance/YYYY-MM-DD.md` | `reports/claude_code/claude_code_seedance/` |
| CC Higgsfield | `ai_trends_reports/reports/claude_code/claude_code_higgsfield/YYYY-MM-DD.md` | `reports/claude_code/claude_code_higgsfield/` |
| CC Shopify | `ai_trends_reports/reports/claude_code/claude_code_shopify/YYYY-MM-DD.md` | `reports/claude_code/claude_code_shopify/` |
| Search index JSONL | `ai_trends_reports/index/reports_index.jsonl` | To be uploaded with reports repo in future phase |
| Search index SQLite | `ai_trends_reports/index/reports_index.sqlite` | Local/Dashboard search backend |
| Mobile Markdown index | `ai_trends_reports/index/README.md`, `by-topic/`, `by-keyword/`, `by-tag/`, `by-date/` | Browseable Markdown pages |

---

## Contacts / Ownership

| Role | Name | Notes |
|------|------|-------|
| Owner | Mandhira | owllulla@gmail.com |
| Primary agent | Sati (main) | Handles implementation, fixes, re-runs |
| Research agent | Atlas | Previously used for OpenClaw cron (now disabled) |
