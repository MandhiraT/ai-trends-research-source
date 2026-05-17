# AI Trends Research — Tasks & Project Status

> Working document for team/agent collaboration. Update this file whenever features change, bugs are found, or new work is planned. Keep statuses current.

**Last updated:** 2026-05-17 ICT  
**Maintained by:** Sati (primary agent) / Mandhira / Mali

---

## Project Health

| Item | Status |
|------|--------|
| Daily pipeline | ✅ Running (system crontab, Bangkok/ICT timezone) |
| Detailed summaries | ✅ Working (--detailed flag in all cron jobs) |
| Audio TTS reports | ✅ Working (Gemini 2.5 Flash TTS, per-video mode) |
| GitHub upload | ✅ Working |
| Dedup system | ✅ Working |
| Telegram daily digest | ✅ Working (includes audio status) |
| Hallucination guard | ✅ Fixed 2026-05-09 (non-English → transcript unavailable) |
| Cron project path | ✅ Fixed 2026-05-12 (`Desktop/Projects`, not lowercase `projects`) |
| Claude Code new subtopics | ✅ Working (Seedance, Higgsfield, Shopify) |
| Local dashboard | ✅ Working (`http://127.0.0.1:8092`) |
| Searchable report index | ✅ Working (385 summarized video sections indexed locally, no-AI-cost backfill) |
| Cloudflare dashboard route | ✅ Working (`https://ai-trends.thequietself.com`) |
| Dashboard systemd service | ✅ Working (user-level `ats-dashboard.service`, auto-restart, linger enabled) |
| Content asset generation | ✅ Working (`generate_content_assets.py`, dashboard Assets tab; manual audio/social works for all topics) |
| Dashboard Asset batch generate | ✅ Working (date range, skip existing, progress bar, per-row buttons; manual AI generation overrides default priority-topic policy) |
| Dashboard Existing Assets filters | ✅ Working (client-side topic/date table filter, verified Joanna today case) |
| Voice generation design | 📝 Designed, not implemented (`docs/VOICE-DESIGN.md`) |

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
| Claude Code subtopics | Base + new subtopics: obsidian, notebooklm, design, skills, remotion video, video, seedance, higgsfield, shopify | `run_claude_code_subtopics_enhanced.py` |
| Daily Thai digest | Aggregates all topic reports + GitHub links | `ai_trends_daily_summary_thai.py` |
| GitHub auto-upload | Clone reports repo → copy files → git push | `upload_reports_to_github_fixed.py` |
| Manual pipeline runner | `run_all_today.sh` runs all 11 steps sequentially | `scripts/run_all_today.sh` |
| Rate limit handling | Auto-retry with backoff on 429 errors | `summarize_local.py` |
| Audio TTS generation | Gemini 2.5 Flash TTS, per-video mode, FFmpeg concat, daily Telegram status | `generate_audio_report.py` |
| Hallucination guard | Non-English video → early return "transcript unavailable" (no AI hallucination) | `summarize_local.py` |
| Local web dashboard | Add/edit research jobs, manual runs, report/log browser, read-only cron view | `dashboard/app.py` |
|| Searchable report index | JSONL/SQLite/Markdown mobile indexes + CLI search for report archive | `scripts/build_report_index.py`, `scripts/search_reports.py` |
|| Dashboard search | Search reports by query/topic/tag from Dashboard UI | `dashboard/app.py` `/search`, `/api/search` |
| Dashboard content assets | Generate asset JSON, audio scripts, social posts per report | `dashboard/app.py` `/assets`, `/api/assets/generate`, `/api/assets/generate-one` |
| Dashboard asset batch generate | Date range filter, skip existing, AI confirm, progress bar, per-row buttons | `dashboard/app.py` `/api/assets/progress` |
| Dashboard Existing Assets filters | Client-side table filtering by Topic + Date from/to; counter updates live | `dashboard/app.py` `/assets` |
| Voice generation design | Two voice types planned: full script voice + deep dive voice; not implemented yet | `docs/VOICE-DESIGN.md` |
| Dashboard job config | JSON-managed research job list for dashboard/manual execution | `config/research_jobs.json` |
| Specific video/manual report routing | Supports dashboard `--video-url`, `--report-folder`, `--config-job-id` | `run_ai_trends_research_enhanced.py` |

---

## Task Board

### In Progress

| Task | Status | Notes |
|------|--------|-------|
| ATS voice generation implementation — Phase 1 | ✅ Core completed, pending next phase | Added unified voice engine `scripts/voice_engine.py`, default voice profile `ats_female_narrator` = Gemini TTS `Aoede`, refactored `generate_audio_report.py` to use the shared engine wrappers, extended `config/audio_topics.json` with automation policy. Verification passed: py_compile, config JSON, voice engine dry-run, legacy CLI help, profile load. Next: script save/edit Dashboard flow + optional Joanna automation after NATEHERK compatibility checks. |
| ATS Dashboard manual voice flow — Phase 2 | ✅ Backend/UI completed, real TTS not triggered | Added script load/save APIs, voice status API, generate voice from saved script API, Assets page script editor, per-row 📝/📚 script edit and 🎙️/🎧 voice buttons. Voice generation blocks if script is missing and never creates script implicitly. Verified 8/8 API tests + browser UI/console + Joanna/date filter. |
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
| T-033 | **Enable Joanna Wiebe daily voice automation** | 2026-05-17 | Added `joanna_wiebe` to `enabled_topics` + `github_folder_map`, set `automated_voice_topics.joanna_wiebe.enabled=true, publish=true`. NATEHERK verified (9.9MB today). Generated and published `voice/joanna_wiebe/2026-05-17.wav` (9.2MB). From tomorrow cron generates + publishes Joanna audio automatically. |
| T-034 | **Fix Dashboard Assets all-topic manual audio/social generation** | 2026-05-17 | Fixed `name '_slug' is not defined` in `scripts/generate_content_assets.py`, added explicit manual generation override so Dashboard `+Audio`, `+Social`, and `+All` work for any topic while `PRIORITY_TOPICS` remains default automation policy only. Updated full-script prompt framing to “คนที่เพิ่งดูมาแล้วอยากบอกเล่าสิ่งที่ได้เรียนรู้”, hook-first opening, no “คลิปนี้” opening, and banned over-casual words (`แก`, `เว้ย`, `แกๆ`, `โห`, `โคตร`, `เจ๋ง`, `อ่ะ`). Verification: py_compile passed, unit/fake-AI all-topic test passed, local `/assets` + asset endpoints 5/5, browser page loads via Cloudflare route with no console errors, real `jacksons_ai` audio-script generation returned 200 and created `audio_scripts/jacksons_ai/2026-05-17-v1.md`. |

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
| T-021 | **Implement ATS voice generation** | Medium | NATEHERK + Joanna Wiebe daily automation fully enabled. Both publish to `voice/{topic}/` in output repo. Remaining: deep-dive script generator, per-video voice status counts in Dashboard. |

---

## Known Bugs / Issues

| ID | Bug | Severity | Status | Found |
|----|-----|----------|--------|-------|
| B-001 | **--detailed flag missing from crontab/run_all_today.sh** | High | ✅ Fixed 2026-04-26 | Reports on 2026-04-26 were short slide-based format instead of detailed sections |
| B-002 | workspace-atlas scripts out of sync with source | Low | Open | Missing `import time` and `time.sleep(15)` — low risk since crontab uses source directly |
| B-003 | Subtopic hash files saved inside reports/claude_code/ not ai_trends_reports/ | Low | Open | Inconsistent path: `ai_trends_reports/reports/claude_code/content_hashes_*.json` vs `ai_trends_reports/content_hashes_*.json` for other topics |
| B-004 | AI Trends cron used lowercase `/Desktop/projects/...` path | High | ✅ Fixed 2026-05-12 | Root cause of missed 2026-05-12 daily summary; crontab now uses `/Desktop/Projects/...` |

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

> System crontab runs on Bangkok time on this machine. Reports are normally available around 08:00 Bangkok.

| Bangkok Time | Topic | Args |
|--------------|-------|------|
| 05:00 | AI Agents (search) | `--max-results 5 --detailed` |
| 05:20 | Claude Code (search) | `--max-results 5 --detailed` |
| 05:40 | AI Viral Niche (search) | `--max-results 5 --detailed` |
| 06:00 | NATEHERK (channel) | `--max-results 3 --detailed` |
| 06:25 | Joanna Wiebe (channel) | `--max-results 3 --detailed` |
| 06:55 | Claude Code base subtopics | `--max-results 3 --total-videos 18 --detailed` |
| 07:05 | Jacksons AI (channel) | `--max-results 3 --detailed` |
| 07:15 | Make Money Matt (channel) | `--max-results 3 --detailed` |
| 07:25 | Miss Luna Vega (playlist) | `--max-results 3 --detailed` |
| 07:35 | Claude Code new subtopics | `--only "seedance,higgsfield,shopify" --max-results 5 --total-videos 15 --detailed` |
| 07:55 | Daily Summary + GitHub Upload + Audio + Telegram | — |

---

## How to Run Manually

```bash
cd /home/mandhira/Desktop/Projects/ai-trends-research-source

# Full pipeline (all 11 steps, detailed summaries)
bash scripts/run_all_today.sh

# Single topic
bash scripts/run_ai_trends_with_creds.sh --topic "AI Agents" --max-results 5 --detailed

# Single channel
bash scripts/run_ai_trends_with_creds.sh \
  --topic "NATEHERK" \
  --channel "https://youtube.com/@NATEHERK" \
  --max-results 3 --detailed

# Claude Code subtopics only
bash scripts/run_claude_code_subtopics_with_creds.sh --max-results 3 --total-videos 18 --detailed

# Claude Code new subtopics only
bash scripts/run_claude_code_subtopics_with_creds.sh --only "seedance,higgsfield,shopify" --max-results 5 --total-videos 15 --detailed

# Daily summary + GitHub upload only
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
