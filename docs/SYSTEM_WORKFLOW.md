# AI Trends Research — System Workflow

> อ่านไฟล์นี้เพื่อเข้าใจระบบทั้งหมด

---

## ระบบคืออะไร

ระบบ scrape YouTube ทุกวันอัตโนมัติ → สรุปเนื้อหาเป็น Thai markdown → push ขึ้น GitHub

**Source code:** `/home/mandhira/Desktop/Projects/ai-trends-research-source/`  
**GitHub (source):** https://github.com/MandhiraT/ai-trends-research-source  
**GitHub (reports):** https://github.com/MandhiraT/ai-trends-research

---

## Pipeline ทุกวัน

```
05:00  AI Agents search (5 videos)
  └─ yt-dlp search → dedup → summarize_local.py (Gemini) → .md report

05:20  Claude Code search (5 videos)
  └─ เหมือนกัน

05:40  AI Viral Niche search (5 videos)
  └─ เหมือนกัน

06:00  NATEHERK channel (max 3 videos)
  └─ yt-dlp fetch channel → dedup → summarize → .md report

06:25  Joanna Wiebe channel (max 3 videos)
  └─ เหมือนกัน

06:55  Claude Code Subtopics (4 topics × 3 videos, cap 8 total)
  └─ obsidian · notebooklm · design · skills

07:40  Daily Thai Summary + GitHub Upload
  └─ ai_trends_daily_summary_thai.py → สรุปรวม
  └─ upload_reports_to_github_fixed.py → git push ไป reports repo
```

**Reports พร้อมอ่าน ~07:45 Bangkok ทุกวัน**

---

## Data Flow

```
YouTube (yt-dlp)
    │
    ▼
Dedup check
(MD5 hash ใน ai_trends_reports/content_hashes_*.json)
    │
    ├─ ซ้ำ → skip
    └─ ใหม่ ▼
         summarize_local.py
         (Gemini API → Thai summary)
              │
              ▼
         ai_trends_reports/reports/{topic}/{YYYY-MM-DD}.md
              │
              ▼  (07:40)
         upload_reports_to_github_fixed.py
              │
              ▼
         github.com/MandhiraT/ai-trends-research
```

---

## ไฟล์สำคัญ

| ไฟล์ | หน้าที่ |
|------|---------|
| `scripts/run_ai_trends_with_creds.sh` | Wrapper หลัก — source credentials + รัน Python script |
| `scripts/run_claude_code_subtopics_with_creds.sh` | Wrapper สำหรับ 4 Claude Code subtopics |
| `scripts/run_daily_summary_cron.sh` | Daily summary + GitHub upload (รันตอน 07:40) |
| `scripts/run_ai_trends_research_enhanced.py` | Python หลัก — search/channel fetch + dedup + summarize |
| `scripts/run_claude_code_subtopics_enhanced.py` | Python สำหรับ subtopics |
| `scripts/summarize_local.py` | เรียก Gemini API สร้าง Thai summary |
| `scripts/upload_reports_to_github_fixed.py` | Clone reports repo → copy files → git push |
| `scripts/ai_trends_daily_summary_thai.py` | สร้าง daily digest รวม links ทุก topic |
| `config/paths.py` | Path constants ทั้งหมด + load_credentials() |
| `config/environment.sh` | Auto-detect PROJECT_ROOT, set paths |
| `credentials.env` | API keys (ไม่ commit) |
| `ai_trends_reports/content_hashes_*.json` | Dedup state ต่อ topic |
| `ai_trends_reports/reports/{topic}/` | Report files แยก topic |

---

## Cron Jobs (System Crontab)

```bash
# ดู crontab ปัจจุบัน
crontab -l | grep "ai_trends\|NATEHERK\|Joanna\|subtopics\|daily_summary"
```

| เวลา (Bangkok) | Script | Arguments |
|---|---|---|
| 12:00 | run_ai_trends_with_creds.sh | `--topic "AI Agents" --max-results 5 --detailed` |
| 12:20 | run_ai_trends_with_creds.sh | `--topic "Claude Code" --max-results 5 --detailed` |
| 12:40 | run_ai_trends_with_creds.sh | `--topic "AI Viral Niche" --max-results 5 --detailed` |
| 13:00 | run_ai_trends_with_creds.sh | `--topic "NATEHERK" --channel @NATEHERK --max-results 3 --detailed` |
| 13:25 | run_ai_trends_with_creds.sh | `--topic "Joanna Wiebe" --channel @joanna-wiebe --max-results 3 --detailed` |
| 13:55 | run_claude_code_subtopics_with_creds.sh | `--max-results 3 --total-videos 8 --detailed` |
| 14:40 | run_daily_summary_cron.sh | — |

> หมายเหตุ: Crontab ใช้ UTC — เวลา Bangkok = UTC+7. **Reports พร้อม ~14:45 Bangkok ทุกวัน**

---

## Channels & Topics

| Topic | Source | Type | Notes |
|-------|--------|------|-------|
| AI Agents | YouTube search | search | |
| Claude Code | YouTube search | search | |
| AI Viral Niche | YouTube search | search | |
| NATEHERK | @NATEHERK | channel | dedup → ~1–3 videos/day |
| Joanna Wiebe | @joanna-wiebe | channel | dedup → ~1–3 videos/day |
| Claude Code Subtopics | YouTube search | search | obsidian, notebooklm, design, skills |

---

## Credentials

**ไฟล์:** `credentials.env` (project root)

| Key | ใช้ทำอะไร |
|-----|-----------|
| `GEMINI_API_KEY` | สร้าง Thai summaries |
| `GITHUB_TOKEN` | Push reports ขึ้น GitHub |
| `GITHUB_REPO` | `MandhiraT/ai-trends-research` |
| `GIT_USER_EMAIL` / `GIT_USER_NAME` | Git commit identity |

---

## รัน Manual

```bash
cd /home/mandhira/Desktop/Projects/ai-trends-research-source

# รัน topic เดียว
bash scripts/run_ai_trends_with_creds.sh --topic "AI Agents" --max-results 5

# รัน channel
bash scripts/run_ai_trends_with_creds.sh \
  --topic "NATEHERK" \
  --channel "https://youtube.com/@NATEHERK" \
  --max-results 3

# รัน Claude Code subtopics
bash scripts/run_claude_code_subtopics_with_creds.sh --max-results 3 --total-videos 8

# รัน daily summary + GitHub upload
bash scripts/run_daily_summary_cron.sh

# รัน pipeline ทั้งหมดวันนี้ (sequential)
bash scripts/run_all_today.sh
```

---

## ดู Error Logs

### Log ต่อ Job
```bash
PROJ="/home/mandhira/Desktop/Projects/ai-trends-research-source"

# ดู log ล่าสุดของแต่ละ job
tail -50 $PROJ/logs/ai_agents.log
tail -50 $PROJ/logs/claude_code.log
tail -50 $PROJ/logs/ai_viral_niche.log
tail -50 $PROJ/logs/nateherk.log
tail -50 $PROJ/logs/joanna_wiebe.log
tail -50 $PROJ/logs/claude_code_subtopics.log
tail -50 $PROJ/logs/daily_summary.log
```

### ดู Error ทั้งหมดวันนี้ (ทุก log)
```bash
grep -h "ERROR\|❌\|error\|Error" \
  /home/mandhira/Desktop/Projects/ai-trends-research-source/logs/*.log \
  | grep "$(date '+%Y-%m-%d')"
```

### ดูว่า report วันนี้มีแล้วหรือยัง
```bash
find /home/mandhira/Desktop/Projects/ai-trends-research-source/ai_trends_reports/reports \
  -name "$(date '+%Y-%m-%d').md" 2>/dev/null
```

### ดู dedup state (ว่า video ไหนถูก skip แล้ว)
```bash
python3 -c "
import json, glob
for f in sorted(glob.glob('ai_trends_reports/content_hashes_*.json')):
    data = json.load(open(f))
    print(f'{f.split(\"/\")[-1]}: {len(data)} hashes')
"
```

### Live tail ระหว่าง manual run
```bash
tail -f /home/mandhira/Desktop/Projects/ai-trends-research-source/logs/ai_agents.log
```

---

## Report Structure

```
ai_trends_reports/
├── reports/
│   ├── ai_agents/
│   │   └── 2026-04-26.md      ← report วันนี้
│   ├── claude_code/
│   │   ├── 2026-04-26.md
│   │   ├── obsidian/
│   │   │   └── 2026-04-26.md
│   │   ├── notebooklm/
│   │   ├── design/
│   │   └── skills/
│   ├── ai_viral_niche/
│   ├── NATEHERK/
│   └── joanna-wiebe/
├── content_hashes_ai_agents.json     ← dedup state
├── content_hashes_claude_code.json
└── last_processed_*.json             ← last run timestamp
```

---

## Troubleshooting

| ปัญหา | สาเหตุ | วิธีแก้ |
|-------|--------|---------|
| `❌ Credentials file not found` | `credentials.env` หาย | Copy จาก `credentials.env.example` แล้วใส่ key |
| `No new unique videos found` | ทุก video ซ้ำใน dedup | ปกติ — content hash ทำงานถูกต้อง |
| `yt-dlp error` | YouTube rate limit หรือ network | รอสักครู่แล้ว retry |
| `GitHub push failed` | `GITHUB_TOKEN` หมดอายุ | Renew token ใน GitHub Settings |
| Report ไม่ขึ้น GitHub | upload script error | ดู `logs/daily_summary.log` |

---

*Last updated: 2026-04-26*
