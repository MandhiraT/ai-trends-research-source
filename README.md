# ATS — AI Trends Research Pipeline

> Autonomous multilingual trend-intelligence system that monitors YouTube channels, converts videos into structured Thai-language research reports, and distributes them automatically.

## Overview

**ATS (AI Trends Source)** is a fully automated research pipeline that scrapes YouTube channels across multiple niches — AI/tech, self-help, finance, health, and more — then uses LLMs to produce detailed Thai-language summaries (2,000–3,000 words per source) and publishes them to a GitHub-hosted reports repository with daily digests, audio TTS, and Telegram delivery.

Built and operated solo by **Mandhira.T** as the upstream intelligence layer of her content ecosystem.

## What It Does

- **Monitors** 29+ YouTube channels/playlists across AI/tech, finance, health, and self-help (psychology, habits, Thai mindfulness & dharma) verticals
- **Scrapes** new uploads via `yt-dlp` with content-hash deduplication
- **Summarizes** each video into a structured Thai report (2,000–3,000 words) with key insights, actionable takeaways, and source metadata
- **Generates audio** narration (TTS) for select reports
- **Publishes** reports to a GitHub repository with tiered folder structure
- **Distributes** daily morning/evening digests via Telegram
- **Provides** a web dashboard (port 8092) for job management, manual runs, log viewing, and cron configuration

## Problem Solved

Manual research across dozens of channels is time-consuming and inconsistent. ATS eliminates the need to watch, summarize, and distribute trend research manually — producing consistent, high-quality Thai-language intelligence reports on a daily schedule with zero manual intervention.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Scraping | `yt-dlp`, Python |
| AI Summarization | Vertex AI (primary), with fallback chain: Qwen → GLM → Gemini → Gemma |
| Storage | GitHub-hosted reports repo (Markdown) |
| Audio | TTS (.wav / .mp4) |
| Distribution | Telegram Bot API |
| Dashboard | Python Flask, port 8092 |
| Scheduling | Linux cron, systemd |
| Runtime | Python 3, `/usr/bin/python3` + Vertex ADC on production |

## Pipeline Architecture

```
YouTube Channels/Playlists
        │
        ▼
   yt-dlp scrape + hash dedup
        │
        ▼
   LLM summarization (Thai, 2k–3k words)
   ├─ Hallucination guard
   ├─ Content hash tracking
   └─ Topic-specific system prompts
        │
        ▼
   ┌────┴────┐
   ▼         ▼
GitHub    Audio TTS (.wav)
Reports    │
Repo       ▼
│       Telegram
│       Audio delivery
│
▼
Daily Digest → Telegram
(morning + evening summaries)
```

## Key Features

- **Multi-provider fallback chain** — if Vertex AI is unavailable, automatically falls back through Qwen → GLM → Gemini → Gemma
- **Hallucination guard** — validates that summary content is grounded in the source transcript
- **Content-hash dedup** — prevents reprocessing the same video twice
- **Topic-specific prompts** — each niche (self-help, finance, health, AI, etc.) has tailored system prompts
- **Dashboard** — manage jobs, trigger manual runs, view logs, configure cron schedules, browse reports
- **Auto-cron-sync** — dashboard saves/deletes rewrite crontab automatically
- **On-demand mode** — local/gitignored on-demand reports with `on_demand` flag

## Getting Started

```bash
# Install dependencies
pip3 install -r requirements.txt

# Run full pipeline for today
bash scripts/run_all_today.sh

# Or trigger via dashboard at localhost:8092
```

### Dashboard

- Local: `http://127.0.0.1:8092`
- Production: `https://ai-trends.thequietself.com` (Cloudflare Tunnel, Access-gated)

### Configuration

- Job definitions: `research_jobs.json` (⚠️ `report_folder` must be **lowercase** — Linux is case-sensitive)
- Credentials: sourced from `~/.credentials.env` (never commit)
- Topic prompts: per-niche system prompts in `src/`

## Repository Structure

```
ai-trends-research-source/
├── src/                    # Core pipeline scripts
├── scripts/                # Cron wrappers & run-all scripts
├── dashboard/              # Flask web dashboard (port 8092)
├── docs/                   # System workflow, current status, setup
├── logs/                   # Per-source and dashboard logs
├── ai_trends_reports/      # Local cache of generated reports + audio
├── requirements.txt
├── research_jobs.json      # Job/topic definitions
├── SETUP.md                # Setup guide
└── CLAUDE.md               # AI agent briefing
```

## Current Status

✅ **Production-live** — Cron-driven daily pipeline running across all configured topics. Scraping, Thai summarization, hallucination guard, TTS, GitHub upload, Telegram digest, and dashboard all operational.

## Portfolio Angle

ATS demonstrates:
- **Autonomous AI pipeline design** — end-to-end automation from data ingestion to multi-channel distribution
- **Multi-provider AI orchestration** — graceful fallback across 5 LLM providers
- **Thai-first NLP engineering** — high-quality Thai-language summarization at scale
- **Production reliability** — hallucination guards, dedup, idempotent runs, automated scheduling
- **Operational tooling** — custom dashboard for job management and monitoring

## Ecosystem Role

ATS is the **upstream intelligence/source layer** of Mandhira's content engine. Its outputs feed into:
- **FAW** — as source content for social media content generation (ATS → FAW bridge)
- **Obsidian** — as searchable knowledge base for research and ideation
- **MJS / HyperFrames** — as topic source for video content production

## Safety Notes

- Never commit `credentials.env` or API tokens
- `report_folder` in `research_jobs.json` must be lowercase
- Do not edit legacy OpenClaw paths referenced in agent docs

---

*ATS Pipeline — Owned and operated by Mandhira.T | Last updated: 2026-07-04*
