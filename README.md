# ATS — AI Trends Research Pipeline

> Autonomous multilingual research system that monitors YouTube channels across several niches, turns new uploads into structured Thai-language research reports, and distributes them automatically via Telegram and a GitHub reports repo.

## Overview

**ATS (AI Trends Source / "AI Trends Research Source")** is a fully automated research pipeline that scrapes YouTube channels and topics across multiple niches — AI/tech (including tool-specific subtopics like Claude Code and specific creators), finance, health, and self-help/psychology/habits/Thai mindfulness & dharma — then uses an LLM to produce detailed Thai-language summaries, publishes them to a GitHub-hosted reports repository, generates optional audio narration, and distributes daily digests over Telegram.

Built and operated solo by **Mandhira ("Mandy")** as the upstream intelligence layer of her content ecosystem (feeds FAW and MJS/HyperFrames).

## What It Does

- **Monitors** ~46 configured YouTube sources (channels, playlists, topic-search jobs, and per-tool "subtopic" jobs) across AI/tech, finance, health, and self-help verticals; 30 are currently enabled and 33 run on the daily cron
- **Scrapes** new uploads via `yt-dlp`, extracting captions with a Thai/English-aware fallback order and content-hash dedup so the same video is never reprocessed
- **Summarizes** each video into a structured Thai report using Vertex AI (Gemini 2.5 Flash via Application Default Credentials) as the sole default provider, with three selectable modes:
  - **standard** / **detailed** — thematic summary (2,000–3,000 words), good for trend/analysis content
  - **full-detail** — an on-demand, uncapped sequential walkthrough (no 4–7 "key points" compression) for step-by-step/listicle/tutorial videos, available for every topic, with its own report format matching the standard ATS report's metadata block, its own `/view/full-detail` viewer plus a "Download .md" link, and Thai-caption-preferred transcript extraction
- **Guards against empty-transcript hallucination** — summarization is skipped (not fabricated) when no real transcript is available
- **Generates audio** narration via Gemini TTS (`gemini-2.5-flash-preview-tts`, default voice "Aoede") for configured topics, chunked to stay under the API's per-call character limit
- **Publishes** reports to a GitHub repository via the GitHub Git Data API (blob-SHA diffing, no local clone) — avoids the multi-GB git-clone timeouts the pipeline used to hit
- **Distributes** daily morning/evening Telegram digests, routed through the shared cross-project "work-type bot" system (canonical route `ats_daily_summary`) instead of ad hoc sending, plus per-topic notifications and a separate audio-publish cron
- **Provides** a local web dashboard (port 8092) for job management, manual runs, on-demand/full-detail generation, searchable report index, content-asset generation, and cron configuration, sharing a unified sidebar/theme layer (with mobile hamburger menu) across ATS/FAW/MJS
- **Bridges** to MJS via `ats_to_mjs_bridge.py` (a `click`-based CLI) to export a report as a video brief for `mjs import-brief`

## Problem Solved

Manual research across dozens of channels is time-consuming and inconsistent. ATS eliminates the need to watch, summarize, and distribute trend research manually — producing consistent Thai-language intelligence reports on a daily schedule with zero manual intervention, plus an on-demand mode for one-off deep dives on a single video.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Scraping | `yt-dlp`, Python |
| AI Summarization | Vertex AI (Gemini 2.5 Flash, ADC) as the default; manual opt-in fallback to Qwen / GLM / Gemini via `TRENDS_EXTRA_PROVIDERS` (not automatic) |
| Storage | GitHub-hosted reports repo (Markdown), pushed via GitHub's Git Data API |
| Audio | Gemini TTS (`.wav`) |
| Distribution | Telegram, routed through shared work-type bot routing |
| Dashboard | Pure Python — `http.server`'s `ThreadingHTTPServer`/`BaseHTTPRequestHandler`, no web framework; port 8092 |
| Scheduling | Linux cron, systemd (`ats-dashboard.service`) |
| Runtime | Python 3 + Vertex ADC on production; dependencies: `yt-dlp`, `requests`, `python-dotenv`, `click` |

## Pipeline Architecture

```
YouTube Channels/Playlists/Topics
        │
        ▼
   yt-dlp scrape + hash dedup
   (Thai/English caption fallback order)
        │
        ▼
   LLM summarization (Vertex AI, Thai output)
   ├─ Empty-transcript guard (skip, don't fabricate)
   ├─ Content hash tracking
   ├─ Topic-specific system prompts
   └─ Mode: standard / detailed / full-detail (on-demand)
        │
        ▼
   ┌────┴────┐
   ▼         ▼
GitHub    Audio TTS (.wav, Gemini)
Reports    │
Repo       ▼
(via API)  Topic notifications
│          (Telegram/email)
▼
Daily Digest → Telegram (work-type bot routing)
(morning + evening summaries)
```

## Key Features

- **Vertex-AI-first summarization** — single default provider (Vertex AI / Gemini 2.5 Flash via ADC); older Qwen/GLM/Gemini/Gemma providers remain wired but only activate if explicitly requested via `TRENDS_EXTRA_PROVIDERS`, to avoid silent quota/key confusion in production
- **Full-detail summary mode** — opt-in, on-demand, uncapped walkthrough mode for enumerable/step-by-step content, now available for every topic (not just the original pilot channel), with report formatting that matches standard ATS reports, a dedicated viewer + download link, and Thai-caption-preferred transcripts
- **On-demand reports** — unique timestamped filenames (`{date}_{HHMM}_{slug}.md`) so several can exist per day; correctly included in the dashboard's Assets date-range filter (an earlier bug silently excluded them)
- **Content-hash dedup** — prevents reprocessing the same video twice
- **Topic-specific prompts** — each niche has tailored system prompts
- **Unified dashboard UX** — shares a `shared-ui/` sidebar + theme layer with FAW/MJS (desktop + mobile hamburger menu), with demo-domain path prefixes preserved in ATS's navigation
- **Work-type Telegram routing** — daily summaries and audio publishing route through the shared `telegram_worktype_routing.py` system rather than a one-off sender
- **GitHub API publishing** — reports push via the Git Data API (blob SHA diffing), replacing an earlier git-clone-based uploader that would time out on the multi-GB reports repo
- **Dashboard** — manage jobs, trigger manual/on-demand/full-detail runs, view logs, configure cron schedules, browse and search reports, generate content assets (scripts, audio, social copy)
- **Auto-cron-sync** — dashboard job save/delete rewrites crontab automatically

## Getting Started

```bash
# Install dependencies
pip3 install -r requirements.txt

# Run full pipeline for today
bash scripts/run_all_today.sh

# Or trigger via dashboard at localhost:8092
python3 dashboard/app.py
```

### Dashboard

- Local: `http://127.0.0.1:8092`
- Production: `https://ai-trends.thequietself.com` (Cloudflare Tunnel, Access-gated), also reachable via the unified `demo.thequietself.com` entry point alongside FAW/MJS

### Report Index Refresh Policy

The canonical search index lives under `ai_trends_reports/index/`. Refreshes use
`scripts/refresh_report_index.py`, not `build_report_index.py` directly.

- `run_daily_summary_cron.sh` refreshes the index after each completed summary group.
- Refresh failure is logged to `logs/report_index_refresh.log` and does not relabel a
  successfully uploaded report or Telegram summary as failed.
- A non-blocking lock prevents concurrent refreshes.
- Build and validation happen in a temporary sibling directory.
- JSONL, SQLite, keyword data, report references, ISO dates, on-demand report
  filenames, and abnormal record shrink are validated before promotion.
- The complete generated index directory is exchanged atomically on Linux; the prior
  generation is retained at `ai_trends_reports/.index-previous` for rollback.
- HTTP rebuild is disabled: GET and POST `/api/search/rebuild` both return HTTP 405.
  Refresh is available only through the local CLI and scheduler.

Safe operator checks:

```bash
# Validate current reports without changing the canonical index
python3 scripts/refresh_report_index.py --dry-run --json

# Refresh canonical generated index artifacts
python3 scripts/refresh_report_index.py --json
```

`--allow-shrink` and `--allow-date-gap` are break-glass overrides. Do not use them
without inspecting the source reports and preserving a known-good index backup.

### Configuration

- Job definitions: `config/research_jobs.json` (⚠️ `report_folder` must be **lowercase** — Linux is case-sensitive)
- Audio topic config: `config/audio_topics.json`
- Notification routing: `config/notification_routing.json`
- Shared env/paths: `config/environment.sh`, `config/paths.py`
- Credentials: sourced from `~/.credentials.env` (never commit)
- Topic prompts: `prompts/` (standard, detailed, and full-detail variants)

## Repository Structure

```
ai-trends-research-source/
├── config/                 # Job/audio/notification config, shared env + paths
├── scripts/                 # Core pipeline: scrape, summarize, publish, bridges, cron wrappers
├── prompts/                  # Per-mode Thai summary prompt templates
├── dashboard/                # Standalone http.server-based web dashboard (port 8092)
├── docs/                     # System workflow, design docs, task tracking
├── logs/                     # Per-source and dashboard logs
├── ai_trends_reports/        # Local cache of generated reports, audio, and search index
├── tests/                    # pytest suite (dashboard forms, report format, dependency contract, etc.)
├── requirements.txt
├── SETUP.md                  # Setup guide
└── CLAUDE.md                 # AI agent briefing
```

## Current Status

**Production-live** — Cron-driven daily pipeline running across enabled topics. Scraping, Thai summarization (standard/detailed/full-detail), hallucination/empty-transcript guard, TTS, GitHub API upload, work-type-routed Telegram digest, and dashboard are all operational. Last verified against the real commit history on 2026-10-08; most recent shipped change was a dependency-contract fix for the `click` package used by the MJS bridge (2026-09-15).

## Ecosystem Role

ATS is the **upstream intelligence/source layer** of Mandhira's content engine. Its outputs feed into:
- **FAW** — as source content for social media content generation (`ats_faw_bridge.py` / `ats_source_brief.py`)
- **MJS / HyperFrames** — as topic source for video content production, via `ats_to_mjs_bridge.py` → `mjs import-brief`
- **Obsidian** — as a searchable knowledge base for research and ideation

## Safety Notes

- Never commit `credentials.env` or API tokens
- `report_folder` in `config/research_jobs.json` must be lowercase
- Do not edit legacy OpenClaw paths referenced in agent docs

---

*ATS Pipeline — Owned and operated by Mandhira.T | README last verified: 2026-10-08*
