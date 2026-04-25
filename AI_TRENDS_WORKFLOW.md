# AI Trends Research System - Complete Workflow Documentation

**Version:** 1.0  
**Last Updated:** 2026-04-25  
**Maintainer:** Atlas Research Agent  
**Language:** English with Thai summaries

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture & Data Flow](#architecture--data-flow)
3. [Cron Jobs Schedule](#cron-jobs-schedule)
4. [Directory Structure](#directory-structure)
5. [Scripts Documentation](#scripts-documentation)
6. [Workflow Details](#workflow-details)
7. [Configuration & Environment](#configuration--environment)
8. [Daily Operations](#daily-operations)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance](#maintenance)

---

## 🎯 System Overview

### Purpose
Automated daily research of AI trends from YouTube channels with Thai language summaries, duplicate prevention, and GitHub archiving.

### Core Features
- ✅ **Content Hash Tracking** - Prevents duplicate content processing
- ✅ **Date Filtering** - Filters channels for today's content only
- ✅ **Thai Summaries** - Generates comprehensive Thai summaries using Gemini AI
- ✅ **GitHub Integration** - Auto-uploads all reports to GitHub repository
- ✅ **Multi-Channel Support** - Researches multiple AI-focused channels
- ✅ **Duplicate Prevention** - MD5-based content hashing

### Target Channels
1. **NATEHERK** - AI Trends Channel (https://youtube.com/@NATEHERK)
2. **Joanna Wiebe** - Content Marketing (https://youtube.com/@joanna-wiebe)
3. **YouTube Search** - AI Agents, Claude Code, AI Viral Niche
4. **Claude Code Subtopics** - Obsidian, NotebookLM, Design, Skills

---

## 🏗 Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CRON SCHEDULER (OpenClaw)                       │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐       │
│  │ 09:30 ICT │  │ 09:45 ICT │  │ 10:00 ICT │  │ 10:30 ICT │       │
│  │   Atlas   │  │   Main    │  │   Main    │  │   Main    │       │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘       │
└────────┼───────────────┼───────────────┼───────────────┼────────────┘
         │               │               │               │
         ▼               ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 WRAPPER SCRIPTS (Bash)                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ run_ai_trends_with_creds.sh                                 │   │
│  │  ├─ Sources credentials.env                                 │   │
│  │  └─ Calls Python script with arguments                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│            PYTHON RESEARCH SCRIPTS                                 │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ run_ai_trends_research_enhanced.py                          │   │
│  │  ├─ Search YouTube (yt-dlp)                                │   │
│  │  ├─ Filter duplicates (content hash)                       │   │
│  │  ├─ Process with summarize CLI (Gemini)                   │   │
│  │  └─ Generate Thai Markdown reports                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ run_claude_code_subtopics_enhanced.py                        │   │
│  │  ├─ Multi-subtopic search                                   │   │
│  │  ├─ Trending topic detection                               │   │
│  │  ├─ Reduced duplicate filtering for trends                  │   │
│  │  └─ Generate per-subtopic reports                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│               SUMMARIZE CLI (Gemini API)                             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ summarize --youtube auto --language th --model gemini-3-flash│   │
│  │  ├─ Transcribe video content                               │   │
│  │  ├─ Generate Thai summary                                   │   │
│  │  └─ Return structured markdown                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              REPORT GENERATION & STORAGE                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ ai_trends_reports/reports/{topic}/{date}.md                 │   │
│  │  ├─ AI Agents → ai_agents/2026-04-25.md                   │   │
│  │  ├─ Claude Code → claude_code/{subtopic}/2026-04-25.md     │   │
│  │  ├─ AI Viral Niche → ai_viral_niche/2026-04-25.md          │   │
│  │  ├─ NATEHERK → NATEHERK/2026-04-25.md                      │   │
│  │  └─ Joanna Wiebe → joanna-wiebe/2026-04-25.md               │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              GITHUB UPLOAD SCRIPT                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ upload_reports_to_github_fixed.py                            │   │
│  │  ├─ Clone/Update GitHub repo (temp)                          │   │
│  │  ├─ Recursive copy of all reports                           │   │
│  │  ├─ Git add, commit, push                                   │   │
│  │  └─ Report success to owner (Telegram)                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              GITHUB REPOSITORY                                      │
│  https://github.com/MandhiraT/ai-trends-research                   │
│  └─ master/reports/ (All reports archived here)                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ⏰ Cron Jobs Schedule

### Daily Schedule (ICT - Asia/Bangkok)

| Time | Job Name | Agent | Target | Description |
|------|----------|-------|--------|-------------|
| 09:30 | AI Trends Research - Atlas | atlas | isolated | AI Agents + Claude Code topics |
| 09:45 | Joanna Wiebe Content Marketing | main | isolated | Content marketing channel research |
| 10:00 | AI Trends Research - Viral Niche | main | isolated | AI Viral Niche topic search |
| 10:30 | AI Trends Research - NATEHERK | main | isolated | NATEHERK channel research |
| 10:45 | AI Trends Daily Summary (Thai) | atlas | session:atlas:main | Generate daily summary links |
| 11:15 | Claude Code Subtopics Research | main | isolated | 4 subtopics (Obsidian, NotebookLM, Design, Skills) |

### Cron Job Details

#### 1. AI Trends Research - Atlas (09:30 ICT)

**Job ID:** `d882ca55-bd6d-467e-88bf-368838149603`  
**Agent:** atlas  
**Session Target:** isolated  
**Schedule:** `30 9 * * *` (Asia/Bangkok)  
**Delivery:** Telegram announcement to 1043709932

**Payload:**
```bash
/home/mandhira/.openclaw/workspace-atlas/scripts/run_ai_trends_with_creds.sh --topic "AI Agents" --max-results 5
/home/mandhira/.openclaw/workspace-atlas/scripts/run_ai_trends_with_creds.sh --topic "Claude Code" --max-results 5
python3 /home/mandhira/.openclaw/workspace-atlas/scripts/upload_reports_to_github_fixed.py
```

**Output:**
- GitHub: https://github.com/MandhiraT/ai-trends-research/tree/master/reports/ai_agents
- GitHub: https://github.com/MandhiraT/ai-trends-research/tree/master/reports/claude_code

---

#### 2. Joanna Wiebe Content Marketing (09:45 ICT)

**Job ID:** `d86aaa39-45ad-4f06-b61e-d795a3f38c5a`  
**Agent:** main  
**Session Target:** isolated  
**Schedule:** `45 9 * * *` (Asia/Bangkok)  
**Delivery:** Telegram announcement to 1043709932

**Payload:**
```bash
/home/mandhira/.openclaw/workspace-atlas/scripts/run_ai_trends_with_creds.sh --topic "Joanna Wiebe" --channel "https://youtube.com/@joanna-wiebe" --max-results 20
python3 /home/mandhira/.openclaw/workspace-atlas/scripts/upload_reports_to_github_fixed.py
```

**Output:**
- GitHub: https://github.com/MandhiraT/ai-trends-research/tree/master/Content%20Marketing/Joanna-Wiebe

---

#### 3. AI Trends Research - Viral Niche (10:00 ICT)

**Job ID:** `3585b54a-737e-4761-bdb9-677c480641e5`  
**Agent:** main  
**Session Target:** isolated  
**Schedule:** `0 10 * * *` (Asia/Bangkok)  
**Delivery:** Telegram announcement to 1043709932

**Payload:**
```bash
/home/mandhira/.openclaw/workspace-atlas/scripts/run_ai_trends_with_creds.sh --topic "AI Viral Niche" --max-results 20
python3 /home/mandhira/.openclaw/workspace-atlas/scripts/upload_reports_to_github_fixed.py
```

**Output:**
- GitHub: https://github.com/MandhiraT/ai-trends-research/tree/master/reports/ai_viral_niche

---

#### 4. AI Trends Research - NATEHERK Channel (10:30 ICT)

**Job ID:** `a987dccd-c4dc-426e-87d9-4a011f47ebbc`  
**Agent:** main  
**Session Target:** isolated  
**Schedule:** `30 10 * * *` (Asia/Bangkok)  
**Delivery:** Telegram announcement to 1043709932

**Payload:**
```bash
/home/mandhira/.openclaw/workspace-atlas/scripts/run_ai_trends_with_creds.sh --topic "NATEHERK" --channel "https://youtube.com/@NATEHERK" --max-results 20
python3 /home/mandhira/.openclaw/workspace-atlas/scripts/upload_reports_to_github_fixed.py
```

**Output:**
- GitHub: https://github.com/MandhiraT/ai-trends-research/tree/master/reports/NATEHERK

---

#### 5. AI Trends Daily Summary (Thai) - Atlas (10:45 ICT)

**Job ID:** `4a453c45-b709-465d-8bb2-846b24ac52c3`  
**Agent:** atlas  
**Session Target:** session:atlas:main  
**Schedule:** `45 10 * * *` (Asia/Bangkok)  
**Delivery:** Telegram announcement to 1043709932

**Payload:**
```bash
python3 /home/mandhira/.openclaw/workspace-atlas/scripts/ai_trends_daily_summary_thai.py
```

**Output:**
- Telegram: Daily summary with links to all reports in Thai

---

#### 6. Claude Code Subtopics Research (11:15 ICT)

**Job ID:** `c6be850e-6597-428b-96a8-2828ecb18526`  
**Agent:** main  
**Session Target:** isolated  
**Schedule:** `15 11 * * *` (Asia/Bangkok)  
**Delivery:** Telegram announcement to 1043709932

**Payload:**
```bash
/home/mandhira/.openclaw/workspace-atlas/scripts/run_claude_code_subtopics_with_creds.sh --max-results 3 --total-videos 8
python3 /home/mandhira/.openclaw/workspace-atlas/scripts/upload_reports_to_github_fixed.py
```

**Subtopics:**
1. claude code obsidian
2. claude code notebooklm
3. claude code design
4. claude code skills

**Output:**
- GitHub: https://github.com/MandhiraT/ai-trends-research/tree/master/reports/claude_code

---

## 📁 Directory Structure

```
/home/mandhira/.openclaw/workspace-atlas/
│
├── scripts/
│   ├── run_ai_trends_with_creds.sh          # Wrapper script
│   ├── run_claude_code_subtopics_with_creds.sh  # Wrapper script
│   ├── run_ai_trends_research_enhanced.py   # Main research script
│   ├── run_claude_code_subtopics_enhanced.py # Subtopics script
│   ├── upload_reports_to_github_fixed.py    # GitHub upload script
│   ├── ai_trends_daily_summary_thai.py      # Daily summary generator
│   ├── thai_summary_prompt.txt              # Standard Thai prompt
│   └── thai_summary_prompt_detailed.txt     # Detailed Thai prompt
│
├── ai_trends_reports/
│   ├── reports/
│   │   ├── ai_agents/
│   │   │   ├── 2026-04-25.md
│   │   │   └── content_hashes_ai_agents.json
│   │   ├── claude_code/
│   │   │   ├── obsidian/
│   │   │   │   ├── 2026-04-25.md
│   │   │   │   └── content_hashes_obsidian.json
│   │   │   ├── notebooklm/
│   │   │   │   ├── 2026-04-25.md
│   │   │   │   └── content_hashes_notebooklm.json
│   │   │   ├── design/
│   │   │   │   ├── 2026-04-25.md
│   │   │   │   └── content_hashes_design.json
│   │   │   ├── skills/
│   │   │   │   ├── 2026-04-25.md
│   │   │   │   └── content_hashes_skills.json
│   │   │   └── 2026-04-25.md
│   │   ├── ai_viral_niche/
│   │   │   ├── 2026-04-25.md
│   │   │   └── content_hashes_ai_viral_niche.json
│   │   └── NATEHERK/
│   │       ├── 2026-04-25.md
│   │       └── content_hashes_NATEHERK.json
│   └── reports_archive/
│       └── {topic}/ (Archived reports)
│
├── joanna_wiebe_reports/
│   └── joanna-wiebe/
│       ├── 2026-04-25.md
│       └── content_hashes_joanna_wiebe.json
│
└── AI_TRENDS_WORKFLOW.md  # This file

/tmp/ai-trends-research/  # Temporary GitHub clone
├── reports/
│   ├── ai_agents/
│   ├── claude_code/
│   ├── ai_viral_niche/
│   └── NATEHERK/
└── .git/
```

---

## 📜 Scripts Documentation

### 1. Wrapper Scripts (Bash)

#### `run_ai_trends_with_creds.sh`

**Purpose:** Sources environment credentials and calls Python research script

**Location:** `/home/mandhira/.openclaw/workspace-atlas/scripts/run_ai_trends_with_creds.sh`

**Usage:**
```bash
./run_ai_trends_with_creds.sh --topic "AI Agents" --max-results 5
./run_ai_trends_with_creds.sh --topic "Joanna Wiebe" --channel "https://youtube.com/@joanna-wiebe" --max-results 20
```

**Flow:**
1. Load `GEMINI_API_KEY` from `/home/mandhira/.openclaw/credentials.env`
2. Export all environment variables
3. Pass all arguments to `run_ai_trends_research_enhanced.py`

**Environment Variables Required:**
- `GEMINI_API_KEY` - Gemini API key for summarize CLI

---

#### `run_claude_code_subtopics_with_creds.sh`

**Purpose:** Sources environment credentials and calls subtopics research script

**Location:** `/home/mandhira/.openclaw/workspace-atlas/scripts/run_claude_code_subtopics_with_creds.sh`

**Usage:**
```bash
./run_claude_code_subtopics_with_creds.sh --max-results 3 --total-videos 8
```

**Flow:**
1. Load `GEMINI_API_KEY` from `/home/mandhira/.openclaw/credentials.env`
2. Export all environment variables
3. Pass all arguments to `run_claude_code_subtopics_enhanced.py`

**Environment Variables Required:**
- `GEMINI_API_KEY` - Gemini API key for summarize CLI

---

### 2. Main Research Scripts (Python)

#### `run_ai_trends_research_enhanced.py`

**Purpose:** Research AI trends from YouTube, generate Thai summaries, prevent duplicates

**Location:** `/home/mandhira/.openclaw/workspace-atlas/scripts/run_ai_trends_research_enhanced.py`

**Arguments:**
```bash
--topic TOPIC              # Research topic (required)
--channel URL             # YouTube channel URL (optional)
--max-results N           # Max videos to fetch (default: 20)
--count N                 # Number of new videos to process (default: all)
--use-date-filter         # Use date filter for channels (today only)
--detailed                # Use detailed prompt for comprehensive summary
```

**Workflow:**

**Step 1: Get Videos**
```python
# Channel mode with date filter
videos = get_videos_from_channel_with_date(channel_url, max_results)

# Topic search mode
videos = search_videos_by_topic(topic, max_results)
```

**Step 2: Duplicate Prevention**
```python
# Load existing content hashes
existing_hashes = load_content_hashes(hash_file)

# Create hash for each video
content_hash = create_content_hash(title, description, duration)

# Filter out duplicates
if content_hash not in existing_hashes:
    unique_videos.append(video)
```

**Step 3: Process Videos**
```python
for video in videos_to_process:
    video_url = f"https://youtube.com/watch?v={video_id}"
    
    # Call summarize CLI
    video_data = process_video_with_summarize(video_url, topic, title)
    
    # Store results
    all_video_data.append(video_data)
```

**Step 4: Generate Report**
```python
# Create markdown report with Thai summaries
report_content = f"""# AI Trends Research - {topic}

**Date:** {report_date}
**Videos Processed:** {len(all_video_data)}

## Video 1: {title}

### 📝 Full Summary (Thai)
{raw_summary}
"""

# Save report
with open(report_file, "w") as f:
    f.write(report_content)
```

**Step 5: Update Trackers**
```python
# Update last processed tracker
with open(tracker_file, "w") as f:
    json.dump({
        "last_video_id": video_id,
        "last_processed_at": datetime.now().isoformat()
    }, f)

# Update content hashes
all_hashes = existing_hashes.union(new_hashes)
save_content_hashes(hash_file, all_hashes)
```

**Output Files:**
- Report: `ai_trends_reports/reports/{topic}/{date}.md`
- Tracker: `ai_trends_reports/reports/last_processed_{topic}.json`
- Hash Tracker: `ai_trends_reports/reports/content_hashes_{topic}.json`

---

#### `run_claude_code_subtopics_enhanced.py`

**Purpose:** Research 4 Claude Code subtopics, detect trends, generate Thai summaries

**Location:** `/home/mandhira/.openclaw/workspace-atlas/scripts/run_claude_code_subtopics_enhanced.py`

**Subtopics:**
1. `claude code obsidian`
2. `claude code notebooklm`
3. `claude code design` (Trending topic - reduced duplicate filtering)
4. `claude code skills` (Trending topic - reduced duplicate filtering)

**Arguments:**
```bash
--max-results N     # Max videos per subtopic (default: 3)
--total-videos N    # Total videos across all subtopics (default: 8)
```

**Workflow:**

**Step 1: Multi-Subtopic Search**
```python
subtopics = [
    "claude code obsidian",
    "claude code notebooklm", 
    "claude code design",
    "claude code skills"
]

for subtopic in subtopics:
    videos = search_videos_by_topic(subtopic, max_results)
```

**Step 2: Enhanced Search for Trending Topics**
```python
# For design/skills topics, use broader queries
if "design" in topic or "skills" in topic:
    queries = [
        f"ytsearch{max}:{topic}",
        f"ytsearch{max}:claude design",
        f"ytsearch{max}:claude code ui",
        f"ytsearch{max}:claude skills"
    ]
    
    for query in queries:
        videos.extend(search_videos(query))
```

**Step 3: Reduced Duplicate Filtering for Trends**
```python
# For trending topics (design/skills), accept all content
if "design" in subtopic or "skills" in subtopic:
    # No duplicate filtering
    unique_videos = videos
else:
    # Standard duplicate filtering
    unique_videos = filter_duplicates(videos)
```

**Step 4: Process & Generate Reports**
```python
for subtopic in subtopics:
    for video in videos:
        video_data = process_video_with_summarize(url, subtopic, title)
        
    # Generate per-subtopic report
    report_file = f"claude_code/{subtopic}/{date}.md"
    with open(report_file, "w") as f:
        f.write(report_content)
```

**Output Files:**
- Reports: `ai_trends_reports/reports/claude_code/{subtopic}/{date}.md`
- Hash Trackers: `ai_trends_reports/reports/claude_code/content_hashes_{subtopic}.json`

---

#### `upload_reports_to_github_fixed.py`

**Purpose:** Upload all AI Trends reports to GitHub repository with recursive directory copy

**Location:** `/home/mandhira/.openclaw/workspace-atlas/scripts/upload_reports_to_github_fixed.py`

**Configuration:**
```python
GITHUB_REPO = "https://github.com/MandhiraT/ai-trends-research.git"
LOCAL_REPO_PATH = "/tmp/ai-trends-research"
REPORTS_SOURCE = "/home/mandhira/.openclaw/workspace-atlas/ai_trends_reports/reports"
```

**Workflow:**

**Step 1: Clone/Update Repository**
```python
# Create local repo if not exists
if not os.path.exists(LOCAL_REPO_PATH):
    subprocess.run(["git", "init"], cwd=LOCAL_REPO_PATH)
    subprocess.run(["git", "remote", "add", "origin", GITHUB_REPO], cwd=LOCAL_REPO_PATH)

# Pull latest changes
subprocess.run(["git", "pull", "origin", "master"], cwd=LOCAL_REPO_PATH)
```

**Step 2: Configure Git User**
```python
subprocess.run(["git", "config", "user.email", "mandhira@thequietself.com"], cwd=LOCAL_REPO_PATH)
subprocess.run(["git", "config", "user.name", "MandhiraT"], cwd=LOCAL_REPO_PATH)
```

**Step 3: Recursive Copy Reports**
```python
def copy_recursive(src_dir, dest_dir):
    """Recursively copy all files from source to destination"""
    for root, dirs, files in os.walk(src_dir):
        rel_path = os.path.relpath(root, src_dir)
        dest_subdir = os.path.join(dest_dir, rel_path)
        os.makedirs(dest_subdir, exist_ok=True)
        
        for file in files:
            src_file = os.path.join(root, file)
            dest_file = os.path.join(dest_subdir, file)
            shutil.copy2(src_file, dest_file)
```

**Step 4: Copy All Topic Directories**
```python
for topic_dir in os.listdir(REPORTS_SOURCE):
    topic_path = os.path.join(REPORTS_SOURCE, topic_dir)
    
    # Clear destination first
    if os.path.exists(dest_topic_dir):
        shutil.rmtree(dest_topic_dir)
    
    # Copy recursively
    copy_recursive(topic_path, dest_topic_dir)
```

**Step 5: Git Commit & Push**
```python
# Check for changes
result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=LOCAL_REPO_PATH)
if result.returncode == 0:
    print("No changes to commit - files already up to date")
    return True

# Commit
commit_msg = f"AI Trends Research Reports - {DATE_STR} (FIXED - Recursive Upload)"
subprocess.run(["git", "commit", "-m", commit_msg], cwd=LOCAL_REPO_PATH)

# Push
subprocess.run(["git", "push", "origin", "master"], cwd=LOCAL_REPO_PATH)
```

**Output:**
- GitHub URL: `https://github.com/MandhiraT/ai-trends-research/tree/master/reports`

---

#### `ai_trends_daily_summary_thai.py`

**Purpose:** Generate daily Thai summary with links to all reports

**Location:** `/home/mandhira/.openclaw/workspace-atlas/scripts/ai_trends_daily_summary_thai.py`

**Workflow:**

**Step 1: Generate Summary**
```python
summary = f"""# สรุปงานวิจัยเทรนด์ AI - {date}

รายงานวิจัยเทรนด์ AI รายวันได้รับการอัปโหลดเรียบร้อยแล้วค่ะ! 📊

## 🔗 ลิงก์รายงานทั้งหมด

• [เทรนด์ AI Agents](https://github.com/...)
• [ระบบนิเวศ Claude](https://github.com/...)
• [เทรนด์ AI Viral Niche](https://github.com/...)
• [ช่อง NATEHERK](https://github.com/...)

รายงานทั้งหมดอยู่ใน repository: [MandhiraT/ai-trends-research](...)
"""
```

**Step 2: Output**
```python
print(summary)
```

**Output:**
- Thai summary with GitHub links (sent via Telegram)

---

### 3. Prompt Files

#### `thai_summary_prompt.txt`

**Purpose:** Standard prompt for AI Trends video summarization

**Location:** `/home/mandhira/.openclaw/workspace-atlas/scripts/thai_summary_prompt.txt`

**Usage:**
```bash
summarize {url} --prompt-file thai_summary_prompt.txt --language th --length xl
```

#### `thai_summary_prompt_detailed.txt`

**Purpose:** Detailed prompt for comprehensive video analysis

**Location:** `/home/mandhira/.openclaw/workspace-atlas/scripts/thai_summary_prompt_detailed.txt`

**Usage:**
```bash
summarize {url} --prompt-file thai_summary_prompt_detailed.txt --language th --length xl
```

---

## 🔄 Workflow Details

### Complete Daily Workflow (Timeline)

```
09:30 ICT  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  └─ AI Trends Research - Atlas
     ├─ Search "AI Agents" (5 videos)
     ├─ Search "Claude Code" (5 videos)
     ├─ Process with summarize CLI
     ├─ Generate Thai summaries
     ├─ Save to ai_trends_reports/reports/ai_agents/2026-04-25.md
     └─ Save to ai_trends_reports/reports/claude_code/2026-04-25.md

09:45 ICT  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  └─ Joanna Wiebe Content Marketing
     ├─ Fetch from @joanna-wiebe channel (20 videos, today only)
     ├─ Process with summarize CLI
     ├─ Generate Thai summaries
     └─ Save to joanna_wiebe_reports/joanna-wiebe/2026-04-25.md

10:00 ICT  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  └─ AI Trends Research - Viral Niche
     ├─ Search "AI Viral Niche" (20 videos)
     ├─ Process with summarize CLI
     ├─ Generate Thai summaries
     └─ Save to ai_trends_reports/reports/ai_viral_niche/2026-04-25.md

10:30 ICT  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  └─ AI Trends Research - NATEHERK
     ├─ Fetch from @NATEHERK channel (20 videos, today only)
     ├─ Process with summarize CLI
     ├─ Generate Thai summaries
     └─ Save to ai_trends_reports/reports/NATEHERK/2026-04-25.md

10:45 ICT  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  └─ AI Trends Daily Summary (Thai)
     └─ Generate Thai summary with links to all reports
        └─ Send via Telegram to owner

11:15 ICT  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  └─ Claude Code Subtopics Research
     ├─ Search "claude code obsidian" (3 videos)
     ├─ Search "claude code notebooklm" (3 videos)
     ├─ Search "claude code design" (3 videos, trending)
     ├─ Search "claude code skills" (3 videos, trending)
     ├─ Process with summarize CLI
     ├─ Generate Thai summaries
     └─ Save to claude_code/{subtopic}/2026-04-25.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  AFTER ALL JOBS COMPLETE - GITHUB UPLOAD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  └─ upload_reports_to_github_fixed.py
     ├─ Clone/Update GitHub repo (temp)
     ├─ Recursive copy of all reports
     ├─ Git add, commit, push
     └─ Report success to owner (Telegram)
```

---

## 🔧 Configuration & Environment

### Environment Variables

**File:** `/home/mandhira/.openclaw/credentials.env`

**Required Variables:**
```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

**How Wrapper Scripts Load Credentials:**
```bash
#!/bin/bash
# Source credentials
CREDENTIALS_FILE="/home/mandhira/.openclaw/credentials.env"
if [ -f "$CREDENTIALS_FILE" ]; then
    set -a
    source "$CREDENTIALS_FILE"
    set +a
    echo "✅ Loaded credentials from $CREDENTIALS_FILE"
else
    echo "❌ Error: Credentials file not found"
    exit 1
fi

# Run Python script with sourced environment
python3 /path/to/script.py "$@"
```

### Cron Job Configuration

**All AI Trends cron jobs use:**
- **Session Target:** `isolated` (except Atlas daily summary)
- **Wake Mode:** `now`
- **Payload:** `kind: agentTurn`
- **Delivery:** `mode: announce` → Telegram (to: 1043709932)

**Important:**
- Cron jobs do NOT read from `credentials.env` directly
- Cron jobs call **wrapper scripts** which source `credentials.env`
- This allows credential updates without modifying cron job payloads

---

## 📅 Daily Operations

### Manual Execution

**Run a single research job manually:**
```bash
# AI Agents research
/home/mandhira/.openclaw/workspace-atlas/scripts/run_ai_trends_with_creds.sh \
  --topic "AI Agents" --max-results 5

# Channel research (Joanna Wiebe)
/home/mandhira/.openclaw/workspace-atlas/scripts/run_ai_trends_with_creds.sh \
  --topic "Joanna Wiebe" \
  --channel "https://youtube.com/@joanna-wiebe" \
  --max-results 20

# Claude Code subtopics
/home/mandhira/.openclaw/workspace-atlas/scripts/run_claude_code_subtopics_with_creds.sh \
  --max-results 3 --total-videos 8

# Upload to GitHub
python3 /home/mandhira/.openclaw/workspace-atlas/scripts/upload_reports_to_github_fixed.py

# Daily summary
python3 /home/mandhira/.openclaw/workspace-atlas/scripts/ai_trends_daily_summary_thai.py
```

### Monitoring

**Check recent reports:**
```bash
# List today's reports
ls -lh /home/mandhira/.openclaw/workspace-atlas/ai_trends_reports/reports/*/*/$(date +%Y-%m-%d).md

# View a specific report
cat /home/mandhira/.openclaw/workspace-atlas/ai_trends_reports/reports/ai_agents/2026-04-25.md
```

**Check tracker files:**
```bash
# Last processed tracker
cat /home/mandhira/.openclaw/workspace-atlas/ai_trends_reports/reports/last_processed_ai_agents.json

# Content hashes tracker
cat /home/mandhira/.openclaw/workspace-atlas/ai_trends_reports/reports/content_hashes_ai_agents.json
```

**Check GitHub status:**
```bash
# View GitHub repo
git -C /tmp/ai-trends-research log --oneline -10

# Check remote status
git -C /tmp/ai-trends-repository remote -v
```

---

## 🔍 Troubleshooting

### Common Issues & Solutions

#### 1. "GEMINI_API_KEY not found"

**Problem:** Wrapper script cannot find credentials file

**Solution:**
```bash
# Check if credentials file exists
ls -l /home/mandhira/.openclaw/credentials.env

# Check if GEMINI_API_KEY is set
grep GEMINI_API_KEY /home/mandhira/.openclaw/credentials.env

# If missing, update credentials.env with correct key
```

---

#### 2. "yt-dlp error: No videos found"

**Problem:** YouTube search returns no results

**Possible Causes:**
- Network issue
- YouTube API blocked
- Invalid search query

**Solution:**
```bash
# Test yt-dlp manually
yt-dlp --flat-playlist --dump-json "ytsearch5:AI Agents"

# Check network connection
ping youtube.com

# Update yt-dlp
pip3 install --upgrade yt-dlp
```

---

#### 3. "Summarize error: API key invalid"

**Problem:** Gemini API key is invalid or expired

**Solution:**
```bash
# Test summarize CLI manually
summarize --version
summarize "https://youtube.com/watch?v=test" --youtube auto --language th

# If failed, update GEMINI_API_KEY in credentials.env
# Then update wrapper scripts (they auto-source)
```

---

#### 4. "No new unique videos found"

**Problem:** All videos are duplicates (content hash matches)

**Solution:**
```bash
# View content hashes
cat /home/mandhira/.openclaw/workspace-atlas/ai_trends_reports/reports/content_hashes_ai_agents.json

# If needed, reset hashes (use with caution)
rm /home/mandhira/.openclaw/workspace-atlas/ai_trends_reports/reports/content_hashes_*.json
```

---

#### 5. "Git error: Failed to push"

**Problem:** GitHub upload fails

**Possible Causes:**
- Invalid GitHub credentials
- Network issue
- Repository changed on remote

**Solution:**
```bash
# Check git status
cd /tmp/ai-trends-research
git status

# Try manual pull/push
git pull origin master
git push origin master

# Check remote URL
git remote -v

# If credentials issue, update GitHub token
# (Note: Currently uses SSH/HTTPS auth, not token)
```

---

#### 6. "Cron job not triggering"

**Problem:** Cron job fails to execute

**Solution:**
```bash
# Check cron job status
openclaw cron list | grep "AI Trends"

# Check job logs
openclaw cron runs <job-id>

# Test job manually
openclaw cron run <job-id>

# If job disabled, enable it
openclaw cron update <job-id> --patch '{"enabled": true}'
```

---

## 🛠 Maintenance

### Regular Maintenance Tasks

#### Weekly
1. **Check GitHub repository sync**
   - Verify all reports are uploaded
   - Check for merge conflicts

2. **Review content hash trackers**
   - Check if hash files are growing too large
   - Archive old hashes if needed

3. **Monitor API usage**
   - Check Gemini API quota
   - Monitor summarize CLI performance

#### Monthly
1. **Clean up old reports**
   - Move reports older than 30 days to archive
   - Compress archive directories

2. **Update dependencies**
   ```bash
   pip3 install --upgrade yt-dlp
   pip3 install --upgrade summarize
   ```

3. **Review cron job performance**
   - Check execution times
   - Optimize if jobs are running too long

#### Quarterly
1. **Audit content hashes**
   - Remove duplicate or stale hashes
   - Reset hash trackers if needed

2. **Review GitHub repository size**
   - Check repository growth
   - Consider repository splitting if too large

3. **Backup configuration**
   - Backup cron job configurations
   - Backup prompt files
   - Document any custom changes

---

## 📊 Performance Metrics

### Expected Performance

| Metric | Target | Notes |
|--------|--------|-------|
| AI Agents research | ~30-45s | 2 topics × 5 videos |
| Joanna Wiebe research | ~60-90s | 20 videos from channel |
| AI Viral Niche research | ~60-90s | 20 videos topic search |
| NATEHERK research | ~60-90s | 20 videos from channel |
| Claude Code subtopics | ~90-120s | 4 subtopics × 3 videos |
| GitHub upload | ~15-30s | Depends on file count |

### Token Usage

- **Summarize CLI:** ~500-1000 tokens per video
- **Daily total:** ~10,000-20,000 tokens
- **Monthly estimate:** ~300,000-600,000 tokens

### API Costs

- **Gemini API:** Free tier (Flash model)
- **GitHub:** Free (public repository)
- **yt-dlp:** Free (YouTube scraping)

---

## 📞 Support & Contact

### System Administrator
- **Name:** Nong Som (Personal Secretary)
- **Channel:** #ops (Telegram)
- **Contact:** Via direct message to owner

### Agent Responsible
- **Name:** Atlas Research Agent
- **Session Key:** `agent:atlas:main`
- **Role:** AI Trends Research & Maintenance

### GitHub Repository
- **URL:** https://github.com/MandhiraT/ai-trends-research
- **Issues:** Report via GitHub Issues or contact agent

---

## 📝 Change Log

### Version 1.0 (2026-04-25)
- Initial comprehensive documentation
- All 6 cron jobs documented
- All 6 scripts documented
- Complete workflow timeline
- Troubleshooting guide added

---

## 📚 Related Documentation

- **MEMORY.md** - System memory and lessons learned
- **HEARTBEAT.md** - Daily operations checklist
- **AGENTS.md** - Agent team structure
- **Cron Job Documentation** - OpenClaw cron system

---

**End of Document**

*This document is maintained by Nong Som. Last updated: 2026-04-25*
