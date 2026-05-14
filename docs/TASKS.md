# AI Trends Research — Tasks & Project Status

> Working document for team/agent collaboration. Update this file whenever features change, bugs are found, or new work is planned. Keep statuses current.

**Last updated:** 2026-05-14 ICT  
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
| Searchable report index | JSONL/SQLite/Markdown mobile indexes + CLI search for report archive | `scripts/build_report_index.py`, `scripts/search_reports.py` |
| Dashboard job config | JSON-managed research job list for dashboard/manual execution | `config/research_jobs.json` |
| Specific video/manual report routing | Supports dashboard `--video-url`, `--report-folder`, `--config-job-id` | `run_ai_trends_research_enhanced.py` |

---

## Task Board

### In Progress

_None_

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

### Backlog

| ID | Task | Priority | Notes |
|----|------|----------|-------|
| T-013 | Sync production runtime (workspace-atlas) with source | Medium | `/home/mandhira/.openclaw/workspace-atlas/scripts/` is missing `import time` + `time.sleep(15)`. Low risk — crontab points to source directly. |
| T-014 | Add Joanna Wiebe path consistency check (saves to joanna_wiebe not joanna-wiebe) | Low | Check if path mismatch causes any GitHub upload issues |
| T-015 | Add AI Viral Niche channel source (currently search-only) | Low | Consider adding a dedicated channel for viral AI content |
| T-016 | Add report word count / quality check to daily digest | Low | Alert if a report is under 500 words (indicates standard prompt was used) |
| T-017 | Add new topic: Prompt Engineering | Low | Potential high-value topic |
| T-018 | Confirm Cloudflare Access policy for AI Trends dashboard | High | Local verification cannot confirm Access policy. Dashboard can run local scripts, so `ai-trends.thequietself.com` should require Cloudflare Access login. |
| T-019 | Add Dashboard Search tab backed by report index | High | Use `reports_index.sqlite`/JSONL to search by topic, keyword, tag, date, and video title from UI. |
| T-020 | Add content asset layer for audio/social/Sonar scripts | High | Generate cached sidecars only for selected topics/videos to control cost. |

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
