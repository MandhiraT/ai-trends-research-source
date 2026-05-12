# AI Trends Research — Current Status

> **Last updated:** 2026-05-13 ICT  
> **For:** AI agents and team members joining this project  
> **Quick start:** Read `CLAUDE.md` first — it has everything you need in one file.

---

## What This Project Is

Automated daily AI trends research pipeline. Scrapes YouTube videos → generates detailed Thai summaries (2000-3000 words) → produces audio versions → pushes reports + audio to GitHub → sends Telegram digest.

**Runs fully on system crontab at Bangkok time (ICT). No manual intervention needed.**

| Item | Value |
|------|-------|
| Source code | `/home/mandhira/Desktop/Projects/ai-trends-research-source/` |
| Reports output repo | https://github.com/MandhiraT/ai-trends-research |
| Source code repo | https://github.com/MandhiraT/ai-trends-research-source |
| Primary language | Thai (all summaries in Thai regardless of video language) |
| AI provider | Vertex AI ADC (primary) → Qwen → GLM → Gemini → Gemma |

---

## Pipeline Health (2026-05-12)

| Component | Status | Notes |
|-----------|--------|-------|
| Daily cron | ✅ Running | System crontab, Bangkok timezone |
| YouTube scraping | ✅ Working | yt-dlp, dedup by MD5 hash |
| Thai summarization | ✅ Working | Vertex AI primary; `--detailed` flag always used |
| Hallucination guard | ✅ Fixed 2026-05-09 | Non-English videos → "transcript unavailable" (no AI hallucination) |
| Audio TTS generation | ✅ Working | Gemini 2.5 Flash TTS, per-video mode, Telegram notification |
| GitHub upload | ✅ Working | Auto-push after daily summary |
| Telegram digest | ✅ Working | Sent ~07:55 Bangkok daily |
| Cron path | ✅ Fixed 2026-05-12 | Installed crontab uses `/home/mandhira/Desktop/Projects/...` |
| AI Trends dashboard | ✅ Working | Local `127.0.0.1:8092`, public `https://ai-trends.thequietself.com` |
| Cloudflare tunnel route | ✅ Working | Reuses existing `faw-dashboard` tunnel; FAW route unchanged |

---

## Monitored Topics (17 total in daily digest)

| Topic | Source | Schedule (Bangkok) | Args |
|-------|--------|--------------------|------|
| AI Agents | YouTube search | 05:00 | `--max-results 5 --detailed` |
| Claude Code | YouTube search | 05:20 | `--max-results 5 --detailed` |
| AI Viral Niche | YouTube search | 05:40 | `--max-results 5 --detailed` |
| NATEHERK | @NATEHERK channel | 06:00 | `--max-results 3 --detailed` |
| Joanna Wiebe | @joanna-wiebe channel | 06:25 | `--max-results 3 --detailed` |
| Claude Code Base Subtopics (×6) | YouTube search | 06:55 | `--max-results 3 --total-videos 18 --detailed` |
| Jacksons AI | @Jacksons_ai channel | 07:05 | `--max-results 3 --detailed` |
| Make Money Matt | @makemoneymatt channel | 07:15 | `--max-results 3 --detailed` |
| Miss Luna Vega | YouTube playlist | 07:25 | `--max-results 3 --detailed` |
| Claude Code New Subtopics (×3) | YouTube search | 07:35 | `--only "seedance,higgsfield,shopify" --max-results 5 --total-videos 15 --detailed` |
| Daily Summary + Audio + GitHub | — | 07:55 | — |

**Reports + audio available on GitHub ~08:10–08:30 Bangkok every day.**

---

## Recently Completed

### 2026-05-13 — AI Trends Dashboard + Cloudflare Route

- Added dashboard MVP for managing AI Trends research jobs without editing cron manually
- Added dashboard job config at `config/research_jobs.json`
- Added manual run support, report browser, log browser, and read-only production cron view
- Added `--video-url`, `--report-folder`, and `--config-job-id` support to the main researcher script
- Reused existing Cloudflare Tunnel `faw-dashboard`; added `ai-trends.thequietself.com -> localhost:8092`
- Verified public dashboard route returns HTTP 200 and renders the AI Trends Dashboard
- Production daily cron and 07:55 summary/upload/audio/Telegram flow were not changed

### 2026-05-12 — Cron Path Fix + New Claude Code Subtopics

- Fixed installed AI Trends cron paths from lowercase `/home/mandhira/Desktop/projects/...` to the real uppercase `/home/mandhira/Desktop/Projects/...`
- Backfilled 2026-05-12 reports and daily summary; Telegram digest completed at 09:22 ICT
- Added new Claude Code subtopics: Seedance, Higgsfield, Shopify
- Added 07:35 Bangkok cron job for the new subtopics with `--max-results 5 --total-videos 15 --detailed`
- Re-ran summary/upload after new topics; daily digest included CC Seedance, CC Higgsfield, and CC Shopify

### 2026-05-09 — Hallucination Fix

- `scripts/summarize_local.py`: Added early-return guard when no English transcript available
- Non-English videos (Thai/other) now return standardized "ไม่สามารถสรุปวิดีโอนี้ได้" message instead of AI hallucinating generic content
- Re-summarized all 4 affected reports (2026-05-06 and 2026-05-07 for AI Agents + AI Viral Niche) — 8/9 videos got proper summaries, 1/9 correctly marked unavailable

### 2026-05-07 — Audio TTS Feature

- `scripts/generate_audio_report.py`: Gemini 2.5 Flash TTS generates audio for daily reports
- `--per-video` mode: splits report by video section, TTS each, concatenates with FFmpeg
- Condense prompt: 300-400 word paragraphs, retry on short output
- Audio status included in daily Telegram digest
- Wired into daily cron (`run_daily_summary_cron.sh`)

### 2026-05-07 — New Channels Added

- Jacksons AI (`@Jacksons_ai`) at 07:05
- Make Money Matt (`@makemoneymatt`) at 07:15
- Miss Luna Vega (playlist) at 07:25
- All use `--max-results 3 --detailed`

### 2026-04-26 — Pipeline Stabilization

- Fixed `--detailed` flag missing from crontab and `run_all_today.sh`
- Fixed Claude Code subtopics script to support `--detailed`
- Re-ran all reports with correct detailed prompt
- Corrected CLAUDE.md: system is Bangkok timezone (not UTC), cron times updated

---

## Task Board

### ✅ Completed

| ID | Task | Date |
|----|------|------|
| T-001 | Initial pipeline (yt-dlp + summarize) | 2026-04-early |
| T-002 | Content dedup via MD5 hash | 2026-04-early |
| T-003 | Gemini fallback chain (qwen→glm→gemini→gemma) | 2026-04-early |
| T-004 | Detailed Thai prompt (2000-3000 words) | 2026-04-24 |
| T-005 | Vertex AI as primary provider | 2026-04-24 |
| T-006 | Claude Code subtopics (4 subtopics) | 2026-04-25 |
| T-007 | System crontab (replaced OpenClaw) | 2026-04-25 |
| T-008 | Fix --detailed flag in crontab | 2026-04-26 |
| T-009 | Fix --detailed in subtopics script | 2026-04-26 |
| T-010 | Re-run all reports with --detailed | 2026-04-26 |
| T-011 | Create docs/TASKS.md | 2026-04-26 |
| T-012 | Fix CLAUDE.md cron times (Bangkok, not UTC) | 2026-04-26 |
| T-013 | Audio TTS feature (Gemini 2.5 Flash) | 2026-05-07 |
| T-014 | Add 3 new channels (Jacksons AI, Make Money Matt, Miss Luna Vega) | 2026-05-07 |
| T-015 | Fix hallucination: non-English video → transcript unavailable | 2026-05-09 |
| T-016 | Re-summarize AI Agents + AI Viral Niche 2026-05-06/07 reports | 2026-05-09 |
| T-017 | Fix lowercase cron project path | 2026-05-12 |
| T-018 | Add Claude Code Seedance/Higgsfield/Shopify subtopics | 2026-05-12 |
| T-019 | AI Trends Search dashboard MVP | 2026-05-13 |
| T-020 | Cloudflare route for AI Trends dashboard | 2026-05-13 |

### 🔄 Backlog

| ID | Task | Priority | Notes |
|----|------|----------|-------|
| B-001 | Add AI Viral Niche dedicated channel | Low | Currently search-only |
| B-002 | Report word-count quality check | Low | Alert if under 500 words (wrong prompt) |
| B-003 | Prompt Engineering topic | Low | High-value potential topic |
| B-004 | Fix subtopic hash file path inconsistency | Low | Saved to `reports/claude_code/` instead of `ai_trends_reports/` |
| B-005 | Confirm Cloudflare Access for AI Trends dashboard | High | Public route works; Access policy must be confirmed in Cloudflare Zero Trust |

---

## Known Issues

| ID | Issue | Severity | Status |
|----|-------|----------|--------|
| B-001 | workspace-atlas scripts out of sync | Low | Open (crontab uses source directly — no impact) |
| B-002 | Subtopic hash files in inconsistent path | Low | Open |
| B-003 | AI Trends cron used lowercase `/Desktop/projects/...` path | High | ✅ Fixed 2026-05-12 |

---

## Key Design Decisions (Don't Re-debate)

| Decision | Reason |
|----------|--------|
| `--detailed` flag always required | Standard prompt = 500 word slides; detailed = 2000-3000 word sections |
| Dedup by MD5 hash, not video ID | Catches near-duplicate content across searches |
| `summarize_local.py` not `summarize` CLI | External CLI removed; local module gives full provider chain control |
| System crontab (Bangkok time) | OpenClaw cron disabled; system crontab is reliable |
| Source dir is canonical | workspace-atlas is legacy; edit source only |
| Thai output only | All summaries in Thai regardless of video language |
| No hallucination on missing transcript | Guard added 2026-05-09 — if no English transcript, return "unavailable" message; never ask AI to summarize from knowledge |
| Reports repo ≠ source repo | `ai-trends-research` (reports) and `ai-trends-research-source` (code) |
| Dashboard does not replace cron | Dashboard is for configuration/manual runs; production cron remains the daily source of truth |
| AI Trends reuses FAW tunnel | `ai-trends.thequietself.com` is routed through existing `faw-dashboard` tunnel |

---

## Working With This Project

**Before starting any task:**
1. Read `CLAUDE.md` — complete session briefing
2. Check this file for current status
3. Run `crontab -l | grep ai_trends` to verify cron is active

**Key scripts:**
```bash
# Run full pipeline manually
cd /home/mandhira/Desktop/Projects/ai-trends-research-source
bash scripts/run_all_today.sh

# Single topic
bash scripts/run_ai_trends_with_creds.sh --topic "AI Agents" --max-results 5 --detailed

# Check today's reports
find ai_trends_reports/reports -name "$(date +%Y-%m-%d).md"

# Start local dashboard
python3 dashboard/app.py --host 127.0.0.1 --port 8092
```

Dashboard URLs:

- Local: `http://127.0.0.1:8092`
- Public: `https://ai-trends.thequietself.com`
