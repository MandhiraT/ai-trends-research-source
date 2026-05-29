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
| `scripts/run_claude_code_subtopics_enhanced.py` | Claude Code subtopic researcher |
| `scripts/summarize_local.py` | Calls Vertex AI (ADC) → qwen → glm → gemini → gemma fallback chain |
| `scripts/ai_trends_daily_summary_thai.py` | Generates daily digest with GitHub links (Thai) |
| `scripts/upload_reports_to_github_fixed.py` | Clones reports repo → copies files → git push |
| `scripts/run_ai_trends_with_creds.sh` | Bash wrapper — sources credentials.env, calls Python |
| `scripts/run_claude_code_subtopics_with_creds.sh` | Same wrapper for subtopics script |
| `scripts/run_all_today.sh` | Runs full 29-step pipeline manually (same as cron) |
| `scripts/run_daily_summary_cron.sh` | Daily summary + GitHub upload + audio + Telegram step |
| `config/paths.py` | All path constants + `load_credentials()` — import at top of every script |
| `config/research_jobs.json` | Dashboard-managed research job config |
| `dashboard/app.py` | Local AI Trends dashboard for jobs, manual runs, reports, logs, and cron view |
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
| Claude Code base subtopics | YouTube search | search (obsidian, notebooklm, design, skills, remotion video, video) |
| Claude Code new subtopics | YouTube search | search (seedance, higgsfield, shopify, hyperframe) |
| Finance Money Coach | @THEMONEYCOACHTH channel | channel |
| Finance Money Buffalo | /c/MoneyBuffalo channel | channel |
| Finance A-Academy | /user/aacademychannel channel | channel |
| Finance Financial Diet | @thefinancialdiet channel | channel |
| Finance Humphrey Yang | @humphrey channel | channel |
| Boom BigNose | @BoomBigNose channel | channel |
| Health — อาหารบำรุงสุขภาพ | YouTube search | search (reports/health/health_food_nutrition) |
| Health — Top to Toe | Top to Toe playlist | playlist (reports/health/top_to_toe) |
| Self Help/Psychology — Therapy in a Nutshell | @TherapyinaNutshell channel | channel (reports/self_help/psychology/therapy_in_a_nutshell) |
| Self Help/Psychology — HealthyGamerGG | @HealthyGamerGG channel | channel (reports/self_help/psychology/healthygamergg) |
| Self Help/Psychology — Psych2Go | @Psych2go channel | channel (reports/self_help/psychology/psych2go) |
| Self Help/Psychology — The School of Life | @theschooloflifetv channel | channel (reports/self_help/psychology/school_of_life) |
| Self Help/Psychology — Dr. Tracey Marks | @DrTraceyMarks channel | channel (reports/self_help/psychology/dr_tracey_marks) |
| Self Help/Habits — Ali Abdaal | @aliabdaal channel | channel (reports/self_help/habits/ali_abdaal) |
| Self Help/Habits — James Clear | @jamesclear channel | channel (reports/self_help/habits/james_clear) |
| Self Help/Habits — Better Ideas | @betterideas channel | channel (reports/self_help/habits/better_ideas) |
| Self Help/Habits — Struthless | @struthless channel | channel (reports/self_help/habits/struthless) |
| Self Help/Habits — Clark Kegley | @clarkkegley channel | channel (reports/self_help/habits/clark_kegley) |
| Self Help/Modern Dharma — Doug's Dharma | @DougsDharma channel | channel (reports/self_help/modern_dharma/dougs_dharma) |
| Self Help/Modern Dharma — Einzelgänger | @einzelganger channel | channel (reports/self_help/modern_dharma/einzelganger) |
| Self Help/Modern Dharma — Pursuit of Wonder | @PursuitofWonder channel | channel (reports/self_help/modern_dharma/pursuit_of_wonder) |
| Self Help/Modern Dharma — The Mindful Movement | @TheMindfulMovement channel | channel (reports/self_help/modern_dharma/mindful_movement) |
| Self Help/Modern Dharma — Acharya Prashant | @AcharyaPrashant channel | channel (reports/self_help/modern_dharma/acharya_prashant) |

**Claude Code subtopics:** obsidian · notebooklm · design · skills · remotion video · video · seedance · higgsfield · shopify · hyperframe

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
| 06:55 | 23:55 prev | Claude Code Base Subtopics | `--max-results 3 --total-videos 18 --detailed` |
| 07:05 | 00:05 | Jacksons AI | `--max-results 3 --detailed` |
| 07:15 | 00:15 | Make Money Matt | `--max-results 3 --detailed` |
| 07:25 | 00:25 | Miss Luna Vega | `--max-results 3 --detailed` |
| 07:35 | 00:35 | Claude Code New Subtopics | `--only "seedance,higgsfield,shopify,hyperframe" --max-results 5 --total-videos 20 --detailed` |
| 07:45 | 00:45 | Finance Money Coach | `--channel @THEMONEYCOACHTH --max-results 3 --detailed` |
| 07:55 | 00:55 | Finance Money Buffalo | `--channel /c/MoneyBuffalo --max-results 3 --detailed` |
| 08:05 | 01:05 | Finance A-Academy | `--channel /user/aacademychannel --max-results 3 --detailed` |
| 08:15 | 01:15 | Finance Financial Diet | `--channel @thefinancialdiet --max-results 3 --detailed` |
| 08:25 | 01:25 | Finance Humphrey Yang | `--channel @humphrey --max-results 3 --detailed` |
| 08:35 | 01:35 | Boom BigNose | `--channel @BoomBigNose --max-results 3 --detailed` |
| 08:45 | 01:45 | Health — อาหารบำรุงสุขภาพ | `--report-folder health/health_food_nutrition --max-results 5 --detailed` |
| 09:00 | 02:00 | Health — Top to Toe | `--report-folder health/top_to_toe --channel playlist --max-results 5 --detailed` |
| 09:20 | 02:20 | Self Help/Psychology — Therapy in a Nutshell | `--report-folder self_help/psychology/therapy_in_a_nutshell --channel @TherapyinaNutshell --max-results 3 --detailed` |
| 09:30 | 02:30 | Self Help/Psychology — HealthyGamerGG | `--report-folder self_help/psychology/healthygamergg --channel @HealthyGamerGG --max-results 3 --detailed` |
| 09:40 | 02:40 | Self Help/Psychology — The School of Life | `--report-folder self_help/psychology/school_of_life --channel @theschooloflifetv --max-results 3 --detailed` |
| 09:50 | 02:50 | Self Help/Psychology — Dr. Tracey Marks | `--report-folder self_help/psychology/dr_tracey_marks --channel @DrTraceyMarks --max-results 3 --detailed` |
| 10:00 | 03:00 | Self Help/Habits — Ali Abdaal | `--report-folder self_help/habits/ali_abdaal --channel @aliabdaal --max-results 3 --detailed` |
| 10:10 | 03:10 | Self Help/Habits — James Clear | `--report-folder self_help/habits/james_clear --channel @jamesclear --max-results 3 --detailed` |
| 10:20 | 03:20 | Self Help/Habits — Better Ideas | `--report-folder self_help/habits/better_ideas --channel @betterideas --max-results 3 --detailed` |
| 10:30 | 03:30 | Self Help/Habits — Struthless | `--report-folder self_help/habits/struthless --channel @struthless --max-results 3 --detailed` |
| 10:40 | 03:40 | Self Help/Modern Dharma — Doug's Dharma | `--report-folder self_help/modern_dharma/dougs_dharma --channel @DougsDharma --max-results 3 --detailed` |
| 10:50 | 03:50 | Self Help/Modern Dharma — Einzelgänger | `--report-folder self_help/modern_dharma/einzelganger --channel @einzelganger --max-results 3 --detailed` |
| 11:00 | 04:00 | Self Help/Psychology — Psych2Go | `--report-folder self_help/psychology/psych2go --channel @Psych2go --max-results 3 --detailed` |
| 11:10 | 04:10 | Self Help/Habits — Clark Kegley | `--report-folder self_help/habits/clark_kegley --channel @clarkkegley --max-results 3 --detailed` |
| 11:20 | 04:20 | Self Help/Modern Dharma — Pursuit of Wonder | `--report-folder self_help/modern_dharma/pursuit_of_wonder --channel @PursuitofWonder --max-results 3 --detailed` |
| 11:30 | 04:30 | Self Help/Modern Dharma — The Mindful Movement | `--report-folder self_help/modern_dharma/mindful_movement --channel @TheMindfulMovement --max-results 3 --detailed` |
| 11:40 | 04:40 | Self Help/Modern Dharma — Acharya Prashant | `--report-folder self_help/modern_dharma/acharya_prashant --channel @AcharyaPrashant --max-results 3 --detailed` |
| 12:10 | 05:10 | Daily Summary + Audio + GitHub | moved later so full self-help Phase 1 reports can be included |

**Reports + audio available on GitHub ~12:20–12:45 Bangkok every day after finance/Thai AI/health/self-help jobs run.**

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
Telegram notification (daily digest ~12:10 Bangkok)
```

## Dashboard

The AI Trends dashboard is a non-invasive control panel. It does not replace production cron.

| URL | Purpose |
|-----|---------|
| `http://127.0.0.1:8092` | Local dashboard |
| `https://ai-trends.thequietself.com` | Cloudflare Tunnel route |

The public route reuses the existing `faw-dashboard` Cloudflare Tunnel. Confirm Cloudflare Access is enabled before treating the public URL as private.

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
bash scripts/run_claude_code_subtopics_with_creds.sh --max-results 3 --total-videos 18 --detailed
bash scripts/run_claude_code_subtopics_with_creds.sh --only "seedance,higgsfield,shopify" --max-results 5 --total-videos 15 --detailed
```

**Generate Thai daily summary + upload to GitHub:**
```bash
bash scripts/run_daily_summary_cron.sh
```

**Start local dashboard:**
```bash
python3 dashboard/app.py --host 127.0.0.1 --port 8092
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
