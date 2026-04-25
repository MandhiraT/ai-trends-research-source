# AI Trends Research — New Machine Setup Guide

## What This System Does
Automated daily research pipeline that:
- Scrapes YouTube videos from 5 channels/topics using yt-dlp
- Summarizes content in Thai using Gemini AI
- Generates daily markdown reports
- Auto-pushes reports to GitHub (MandhiraT/ai-trends-research)

**Runs automatically via 6 cron jobs (09:30–11:15 ICT)**

---

## Requirements
- Python 3.6+
- `yt-dlp` (YouTube scraping)
- `git` CLI
- `summarize` CLI (Claude Code tool — for Gemini summarization)
- Internet access

---

## Quick Start

```bash
# 1. Clone source code
git clone https://github.com/MandhiraT/ai-trends-research-source.git
cd ai-trends-research-source

# 2. Install Python dependencies
pip3 install -r requirements.txt

# 3. Add credentials
cp credentials.env.example credentials.env
# Edit credentials.env — fill in GEMINI_API_KEY and GITHUB_TOKEN

# 4. Run setup (creates dirs + cron jobs)
bash deploy/setup.sh
```

---

## Credentials Needed

| Key | Where to Get |
|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com → API Keys |
| `GITHUB_TOKEN` | https://github.com/settings/tokens (repo scope) |

---

## Directory Structure

```
ai-trends-research-source/
├── scripts/                    # Core automation scripts
│   ├── run_ai_trends_with_creds.sh           # Cron entry point 1
│   ├── run_ai_trends_research_enhanced.py    # Main research engine
│   ├── run_claude_code_subtopics_with_creds.sh  # Cron entry point 2
│   ├── run_claude_code_subtopics_enhanced.py # Subtopics engine
│   ├── upload_reports_to_github_fixed.py     # GitHub uploader
│   └── ai_trends_daily_summary_thai.py       # Daily Thai summary
├── prompts/
│   ├── thai_summary_prompt.txt               # Gemini prompt (short)
│   └── thai_summary_prompt_detailed.txt      # Gemini prompt (detailed)
├── config/
│   ├── environment.sh    # Shell path config (auto-loaded)
│   └── paths.py          # Python path config (auto-loaded)
├── ai_trends_reports/    # Generated reports (NOT in git — see reports repo)
├── credentials.env       # Your API keys (NOT in git — never commit)
├── requirements.txt
└── SETUP.md
```

---

## How Paths Work

All scripts auto-detect their own location — no manual config needed.

**Shell scripts** source `config/environment.sh` which sets:
- `$PROJECT_ROOT` — root of the repo
- `$SCRIPTS_DIR`, `$PROMPTS_DIR`, `$REPORTS_DIR`, `$CREDENTIALS_FILE`

**Python scripts** import `config/paths.py` which sets:
- `PROJECT_ROOT`, `CREDENTIALS_FILE`, `REPORTS_DIR`, `GITHUB_TEMP_CLONE`, etc.

Override any path via environment variable:
```bash
PROJECT_ROOT=/my/custom/path python3 scripts/run_ai_trends_research_enhanced.py
```

---

## Cron Jobs (set up manually or via setup.sh)

| Time (ICT) | Script | Topics |
|---|---|---|
| 09:30 | run_ai_trends_with_creds.sh | AI Agents, Claude Code |
| 09:45 | run_ai_trends_with_creds.sh | Joanna Wiebe channel |
| 10:00 | run_ai_trends_with_creds.sh | AI Viral Niche |
| 10:30 | run_ai_trends_with_creds.sh | NATEHERK channel |
| 10:45 | ai_trends_daily_summary_thai.py | Thai daily summary |
| 11:15 | run_claude_code_subtopics_with_creds.sh | Claude Code (4 subtopics) |

---

## Reports Repository

Generated reports are pushed separately to:
`https://github.com/MandhiraT/ai-trends-research`

This source code repo and reports repo are separate — source code here, output there.

---

## Migrating to a New Agent (Hermes, Claude, etc.)

1. Clone this repo on the new machine
2. `pip3 install -r requirements.txt`
3. Copy your `credentials.env`
4. Set up cron jobs pointing to `$PROJECT_ROOT/scripts/`
5. No dependency on OpenClaw or any specific agent framework
