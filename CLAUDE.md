# AI Trends Research — Session Briefing

> Read this first. Everything you need is here — no codebase exploration needed.  
> For full task board and feature list, see `docs/TASKS.md`.

---

## What this is

Automated daily AI trends research from YouTube. Scrapes videos → generates **detailed Thai summaries (2000-3000 words)** → pushes reports to GitHub. Runs on **system crontab** (not OpenClaw).

**Source code (edit here):** `/home/mandhira/Desktop/Projects/ai-trends-research-source/`  
**Reports repo (output):** https://github.com/MandhiraT/ai-trends-research  
**Source repo:** https://github.com/MandhiraT/ai-trends-research-source

> ⚠️ `/home/mandhira/.openclaw/workspace-atlas/scripts/` is legacy — all cron jobs now point to source directly. Do NOT edit workspace-atlas.

---

## Key Files

| File | Purpose |
|------|---------|
| `scripts/run_ai_trends_research_enhanced.py` | Main researcher — yt-dlp search/channel → summarize_local.py → markdown report |
| `scripts/run_claude_code_subtopics_enhanced.py` | Same but for 4 Claude Code subtopics |
| `scripts/summarize_local.py` | Calls Vertex AI (ADC) → qwen → glm → gemini → gemma fallback chain |
| `scripts/ai_trends_daily_summary_thai.py` | Generates daily digest with GitHub links (Thai) |
| `scripts/upload_reports_to_github_fixed.py` | Clones reports repo → copies files → git push |
| `scripts/run_ai_trends_with_creds.sh` | Bash wrapper — sources credentials.env, calls Python |
| `scripts/run_claude_code_subtopics_with_creds.sh` | Same wrapper for subtopics script |
| `scripts/run_all_today.sh` | Runs full 7-step pipeline manually (same as cron) |
| `scripts/run_daily_summary_cron.sh` | Daily summary + GitHub upload step |
| `config/paths.py` | All path constants + `load_credentials()` — import at top of every script |
| `credentials.env` | API keys (not committed — see credentials.env.example) |
| `prompts/thai_summary_prompt.txt` | Standard Thai summary (slide-based, ~500 words) — NOT used in prod |
| `prompts/thai_summary_prompt_detailed.txt` | Detailed Thai summary (section-based, 2000-3000 words) — **always use this** |
| `docs/TASKS.md` | Task board, feature list, known bugs, backlog |
| `docs/SYSTEM_WORKFLOW.md` | Full architecture and troubleshooting guide |

---

## Monitored Channels / Topics

| Topic | Source | Type |
|-------|--------|------|
| AI Agents | YouTube search | search |
| Claude Code | YouTube search | search |
| AI Viral Niche | YouTube search | search |
| NATEHERK | @NATEHERK channel | channel |
| Joanna Wiebe | @joanna-wiebe channel | channel |
| Claude Code subtopics | YouTube search | search (4 subtopics) |

**Claude Code subtopics:** obsidian · notebooklm · design · skills

---

## Cron Schedule (System Crontab — Bangkok time / ICT)

> ⚠️ System timezone is **Asia/Bangkok (+07)**. All cron times are **Bangkok time (ICT)**, NOT UTC.

| Bangkok (ICT) | UTC | Topic | Notes |
|--------------|-----|-------|-------|
| 05:00 | 22:00 prev | AI Agents | `--max-results 5 --detailed` |
| 05:20 | 22:20 prev | Claude Code | `--max-results 5 --detailed` |
| 05:40 | 22:40 prev | AI Viral Niche | `--max-results 5 --detailed` |
| 06:00 | 23:00 prev | NATEHERK | `--max-results 3 --detailed` |
| 06:25 | 23:25 prev | Joanna Wiebe | `--max-results 3 --detailed` |
| 06:55 | 23:55 prev | Claude Code Subtopics | `--max-results 3 --total-videos 8 --detailed` |
| 07:05 | 00:05 | Jacksons AI | `--max-results 3 --detailed` |
| 07:15 | 00:15 | Make Money Matt | `--max-results 3 --detailed` |
| 07:25 | 00:25 | Miss Luna Vega | `--max-results 3 --detailed` |
| 07:55 | 00:55 | Daily Summary + Audio + GitHub | — |

**Reports + audio available on GitHub ~08:10–08:30 Bangkok every day.**

> To view/edit crontab: `crontab -l` / `crontab -e`

---

## Data Flow

```
YouTube (yt-dlp search/channel scrape)
  ↓
Duplicate check (MD5 hash of title+description+duration)
  stored in: ai_trends_reports/content_hashes_*.json
  ↓
summarize_local.py  →  Vertex AI ADC (primary)  →  Thai detailed markdown
                    →  fallback: qwen → glm → gemini → gemma
  ↓
Save to ai_trends_reports/reports/{topic}/{YYYY-MM-DD}.md
  ↓
upload_reports_to_github_fixed.py → git push → MandhiraT/ai-trends-research
  ↓
Telegram notification (daily digest ~07:55 Bangkok)
```

---

## Report Storage

```
ai_trends_reports/
├── reports/
│   ├── ai_agents/           → YouTube search "AI Agents"
│   ├── ai_viral_niche/      → YouTube search "AI Viral Niche"
│   ├── NATEHERK/            → @NATEHERK channel
│   ├── joanna_wiebe/        → @joanna-wiebe channel
│   └── claude_code/
│       ├── claude_code_obsidian/
│       ├── claude_code_notebooklm/
│       ├── claude_code_design/
│       └── claude_code_skills/
├── content_hashes_*.json    → Dedup state per topic
└── last_processed_*.json    → Last run timestamp per topic
```

---

## Credentials

**File:** `credentials.env` (in project root, not committed)

| Key | Used for |
|-----|---------|
| `GEMINI_API_KEY` | Fallback summarization |
| `GITHUB_TOKEN` | Push reports to MandhiraT/ai-trends-research |
| `GITHUB_REPO` | `MandhiraT/ai-trends-research` |
| `GIT_USER_EMAIL` / `GIT_USER_NAME` | Git commit identity |

Vertex AI uses **Application Default Credentials (ADC)** — no key in credentials.env.

---

## Common Tasks

**Run full pipeline manually (with detailed summaries):**
```bash
cd /home/mandhira/Desktop/Projects/ai-trends-research-source
bash scripts/run_all_today.sh
```

**Run a single topic:**
```bash
bash scripts/run_ai_trends_with_creds.sh --topic "AI Agents" --max-results 5 --detailed
```

**Run a channel topic:**
```bash
bash scripts/run_ai_trends_with_creds.sh \
  --topic "NATEHERK" \
  --channel "https://youtube.com/@NATEHERK" \
  --max-results 3 --detailed
```

**Run Claude Code subtopics:**
```bash
bash scripts/run_claude_code_subtopics_with_creds.sh --max-results 3 --total-videos 8 --detailed
```

**Generate Thai daily summary + upload to GitHub:**
```bash
bash scripts/run_daily_summary_cron.sh
```

**Check today's reports:**
```bash
find ai_trends_reports/reports -name "$(date +%Y-%m-%d).md"
```

**Check dedup state (hash counts per topic):**
```bash
python3 -c "
import json, glob
for f in sorted(glob.glob('ai_trends_reports/content_hashes_*.json') +
                glob.glob('ai_trends_reports/reports/claude_code/content_hashes_*.json')):
    d = json.load(open(f))
    print(f'{f.split(\"/\")[-1]}: {len(d)} hashes')
"
```

---

## Key Design Decisions (don't re-debate)

- **`--detailed` flag is always required** — standard prompt produces ~500-word slide summaries; detailed produces 2000-3000 word section-based reports. All cron and manual runs must include `--detailed`.
- **Dedup by MD5 hash** — not by video ID, to catch near-duplicate content across searches
- **`summarize_local.py`** — local Python module, NOT the external `summarize` CLI (which was removed)
- **System crontab** is the scheduler — OpenClaw cron jobs are all disabled, do not use them
- **Source dir is canonical** — workspace-atlas is legacy and out of sync; do not edit it
- **`config/paths.py`** must be on `sys.path` before any other import in every script
- **Thai output only** — all summaries generated in Thai regardless of video language
- **GitHub reports repo ≠ source repo** — reports go to `ai-trends-research`, code to `ai-trends-research-source`

---

*Last updated: 2026-04-26 — Fixed --detailed flag in crontab/run_all_today.sh/subtopics script; re-ran all reports; created docs/TASKS.md*
