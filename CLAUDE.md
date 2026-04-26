# AI Trends Research — Session Briefing

> Read this first. Everything you need is here — no codebase exploration needed.

---

## What this is

Automated daily AI trends research from YouTube. Scrapes videos → generates Thai summaries → pushes reports to GitHub. Runs fully on OpenClaw cron jobs (not system crontab).

**Source code (edit here):** `/home/mandhira/Desktop/projects/ai-trends-research-source/`  
**Production runtime:** `/home/mandhira/.openclaw/workspace-atlas/scripts/` (synced from source)  
**Reports repo (output):** https://github.com/MandhiraT/ai-trends-research  
**Source repo:** https://github.com/MandhiraT/ai-trends-research-source

---

## Key Files

| File | Purpose |
|------|---------|
| `scripts/run_ai_trends_research_enhanced.py` | Main researcher — yt-dlp search → summarize CLI → markdown report |
| `scripts/run_claude_code_subtopics_enhanced.py` | Same but for 4 Claude Code subtopics |
| `scripts/ai_trends_daily_summary_thai.py` | Generates daily digest with GitHub links (Thai) |
| `scripts/upload_reports_to_github_fixed.py` | Clones reports repo → copies files → git push |
| `scripts/run_ai_trends_with_creds.sh` | Bash wrapper — sources credentials.env, calls Python |
| `scripts/run_claude_code_subtopics_with_creds.sh` | Same wrapper for subtopics script |
| `config/paths.py` | All path constants + `load_credentials()` — import at top of every script |
| `credentials.env` | API keys (not committed — see credentials.env.example) |
| `prompts/thai_summary_prompt.txt` | Standard Thai summary prompt |
| `prompts/thai_summary_prompt_detailed.txt` | Detailed Thai summary prompt |

---

## Monitored Channels / Topics

| Topic | Source | Schedule |
|-------|--------|----------|
| AI Agents | YouTube search | 09:30 ICT |
| Claude Code | YouTube search | 09:30 ICT |
| Joanna Wiebe | @joanna-wiebe channel | 09:45 ICT |
| AI Viral Niche | YouTube search | 10:00 ICT |
| NATEHERK | @NATEHERK channel | 10:30 ICT |
| Daily Summary (Thai) | Aggregates all above | 10:45 ICT |
| Claude Code subtopics | 4 subtopics below | 11:15 ICT |

**Claude Code subtopics:** obsidian · notebooklm · design · skills

---

## Cron Schedule (OpenClaw — NOT system crontab)

All jobs run via OpenClaw scheduled jobs. Check/manage at:
```bash
openclaw cron list   # or via OpenClaw dashboard
```

| Time (ICT) | Agent | What runs |
|------------|-------|-----------|
| 09:30 | atlas | AI Agents + Claude Code topics → GitHub upload |
| 09:45 | main | Joanna Wiebe channel → GitHub upload |
| 10:00 | main | AI Viral Niche → GitHub upload |
| 10:30 | main | NATEHERK channel → GitHub upload |
| 10:45 | atlas | Daily Thai summary → Telegram |
| 11:15 | main | Claude Code subtopics (4x) → GitHub upload |

---

## Data Flow

```
YouTube (yt-dlp search/channel scrape)
  ↓
Duplicate check (MD5 content hash in ai_trends_reports/content_hashes_*.json)
  ↓
summarize CLI  →  Gemini API (gemini-3-flash or Vertex)  →  Thai markdown
  ↓
Save to ai_trends_reports/reports/{topic}/{YYYY-MM-DD}.md
  ↓
upload_reports_to_github_fixed.py → git push → MandhiraT/ai-trends-research
  ↓
Telegram notification (daily digest at 10:45)
```

---

## Report Storage

```
ai_trends_reports/
├── reports/
│   ├── ai_agents/           → YouTube search "AI Agents"
│   ├── ai_viral_niche/      → YouTube search "AI Viral Niche"
│   ├── NATEHERK/            → @NATEHERK channel
│   ├── joanna-wiebe/        → @joanna-wiebe channel
│   └── claude_code/
│       ├── obsidian/
│       ├── notebooklm/
│       ├── design/
│       └── skills/
├── content_hashes_*.json    → Dedup tracking per topic
└── last_processed_*.json    → Last run timestamp per topic
```

---

## Credentials

**File:** `credentials.env` (in project root, not committed)

| Key | Used for |
|-----|---------|
| `GEMINI_API_KEY` | Video summarization via summarize CLI |
| `GITHUB_TOKEN` | Push reports to MandhiraT/ai-trends-research |
| `GITHUB_REPO` | `MandhiraT/ai-trends-research` |
| `GIT_USER_EMAIL` / `GIT_USER_NAME` | Git commit identity |

---

## Common Tasks

**Run a topic manually:**
```bash
cd /home/mandhira/Desktop/projects/ai-trends-research-source
source credentials.env
python3 scripts/run_ai_trends_research_enhanced.py --topic "AI Agents" --max-results 5
```

**Run Claude Code subtopics manually:**
```bash
source credentials.env
python3 scripts/run_claude_code_subtopics_enhanced.py --max-results 3 --total-videos 8
```

**Generate Thai daily summary:**
```bash
source credentials.env
python3 scripts/ai_trends_daily_summary_thai.py
```

**Upload reports to GitHub:**
```bash
source credentials.env
python3 scripts/upload_reports_to_github_fixed.py
```

**Check today's reports:**
```bash
ls ai_trends_reports/reports/*/$(date +%Y-%m-%d).md 2>/dev/null
find ai_trends_reports/reports -name "$(date +%Y-%m-%d).md"
```

**Check content hashes (dedup state):**
```bash
python3 -c "import json; print(json.load(open('ai_trends_reports/content_hashes_ai_agents.json')))"
```

---

## Key Design Decisions (don't re-debate)

- **Dedup by MD5 hash** — not by video ID, to catch near-duplicate content across searches
- **`summarize` CLI** — external tool wrapping Gemini/yt-dlp; not a Python import
- **workspace-atlas** = production runtime; desktop project = source (edit here, sync there)
- **`config/paths.py`** must be on `sys.path` before any other import in every script
- **Thai output only** — all summaries generated in Thai regardless of video language
- **GitHub reports repo ≠ source repo** — reports go to `ai-trends-research`, code to `ai-trends-research-source`
