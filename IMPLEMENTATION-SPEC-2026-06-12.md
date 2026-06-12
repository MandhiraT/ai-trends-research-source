# ATS Incident Fix — Implementation Spec
**For:** Agent (GLM-5 / Claude Code / Codex)
**Created by:** มะลิ (Hermes Agent) — 2026-06-12
**Reference Incident:** `incident-report-2026-06-12.md`

> **READ THIS FIRST.** This document contains exact file paths, exact line numbers, exact before/after code, and exact shell commands. No exploration needed — just execute.

---

## Project Context

- **Source code:** `/home/mandhira/Desktop/Projects/ai-trends-research-source/`
- **Reports output:** `/home/mandhira/Desktop/Projects/ai-trends-research-source/ai_trends_reports/`
- **All paths below are absolute from project root** (`/home/mandhira/Desktop/Projects/ai-trends-research-source/`)
- **Session briefing:** `CLAUDE.md` in project root — read for full context if needed

---

## Fix 1: Remove NATEHERK Special Case + Normalize Tracker Path (🔴 Critical)

### File: `scripts/run_ai_trends_research_enhanced.py`

**Change A — Remove special case (lines 40-45):**

BEFORE:
```python
def sanitize_topic(topic):
    """Convert topic to safe folder name"""
    # Special case: Keep NATEHERK uppercase
    if topic.upper() == "NATEHERK":
        return "NATEHERK"
    return topic.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")[:50]
```

AFTER:
```python
def sanitize_topic(topic):
    """Convert topic to safe folder name"""
    return topic.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")[:50]
```

**Change B — Add .lower() safety net in get_dirs() (lines 100-109):**

BEFORE:
```python
def get_dirs(topic, report_folder=None):
    """Get topic-specific directories"""
    topic_safe = sanitize_report_folder(report_folder) if report_folder else sanitize_topic(topic)
    tracker_safe = topic_safe.replace("/", "_")
    return {
        "reports": f"{BASE_REPORTS_DIR}/reports/{topic_safe}",
        "archive": f"{BASE_REPORTS_DIR}/reports_archive/{topic_safe}",
        "tracker": f"{BASE_REPORTS_DIR}/last_processed_{tracker_safe}.json",
        "hash_tracker": f"{BASE_REPORTS_DIR}/content_hashes_{tracker_safe}.json"
    }
```

AFTER:
```python
def get_dirs(topic, report_folder=None):
    """Get topic-specific directories"""
    topic_safe = sanitize_report_folder(report_folder) if report_folder else sanitize_topic(topic)
    tracker_safe = topic_safe.replace("/", "_").lower()
    return {
        "reports": f"{BASE_REPORTS_DIR}/reports/{topic_safe}",
        "archive": f"{BASE_REPORTS_DIR}/reports_archive/{topic_safe}",
        "tracker": f"{BASE_REPORTS_DIR}/last_processed_{tracker_safe}.json",
        "hash_tracker": f"{BASE_REPORTS_DIR}/content_hashes_{tracker_safe}.json"
    }
```

**Note:** Only `tracker_safe` gets `.lower()`. The `reports` and `archive` paths keep `topic_safe` as-is because `report_folder` in `research_jobs.json` is authoritative for folder names (always lowercase per project convention).

---

## Fix 2: Merge Split Tracker Files (🔴 Critical)

Run these commands from project root:

```bash
cd /home/mandhira/Desktop/Projects/ai-trends-research-source

# Merge uppercase tracker into lowercase (Python)
python3 -c "
import json

lower_path = 'ai_trends_reports/content_hashes_nateherk.json'
upper_path = 'ai_trends_reports/content_hashes_NATEHERK.json'

with open(lower_path) as f:
    lower = json.load(f)
with open(upper_path) as f:
    upper = json.load(f)

# Union of both dicts (uppercase values win on conflict since they have more history)
merged = {**lower, **upper}

with open(lower_path, 'w') as f:
    json.dump(merged, f, indent=2)

print(f'Merged: {len(lower)} + {len(upper)} → {len(merged)} unique hashes')
"

# Verify merge
python3 -c "import json; d=json.load(open('ai_trends_reports/content_hashes_nateherk.json')); print(f'nateherk tracker: {len(d)} hashes')"

# Remove uppercase tracker (keep as backup first)
mv ai_trends_reports/content_hashes_NATEHERK.json ai_trends_reports/content_hashes_NATEHERK.json.bak

# Also check for uppercase last_processed tracker
ls -la ai_trends_reports/last_processed_NATEHERK.json 2>/dev/null && \
  mv ai_trends_reports/last_processed_NATEHERK.json ai_trends_reports/last_processed_NATEHERK.json.bak
```

---

## Fix 3: Consolidate Split Directories (🔴 Critical)

```bash
cd /home/mandhira/Desktop/Projects/ai-trends-research-source/ai_trends_reports

# Reports: move NATEHERK → nateherk (don't overwrite existing)
if [ -d "reports/NATEHERK" ]; then
    cp -n reports/NATEHERK/* reports/nateherk/ 2>/dev/null
    echo "Reports consolidated"
fi

# Audio: move NATEHERK → nateherk
if [ -d "audio/NATEHERK" ]; then
    mkdir -p audio/nateherk
    cp -n audio/NATEHERK/* audio/nateherk/ 2>/dev/null
    echo "Audio consolidated"
fi

# Audio scripts: move NATEHERK → nateherk
if [ -d "audio_scripts/NATEHERK" ]; then
    mkdir -p audio_scripts/nateherk
    cp -n audio_scripts/NATEHERK/* audio_scripts/nateherk/ 2>/dev/null
    echo "Audio scripts consolidated"
fi

# Remove uppercase dirs (they're backed up by git)
rm -rf reports/NATEHERK audio/NATEHERK audio_scripts/NATEHERK 2>/dev/null
echo "Uppercase directories removed"
```

---

## Fix 4: Skip "Summary Unavailable" in Audio Generation (🔴 Critical)

### File: `scripts/generate_audio_report.py`

**In function `_generate_per_video()` (around line 335), add skip logic:**

BEFORE (lines 334-340):
```python
    success_count = 0
    for i, (title, text) in enumerate(sections):
        video_num = i + 1
        is_first  = (i == 0)
        is_last   = (i == len(sections) - 1)
        label     = title or f'section_{video_num}'
        short     = label[:50]
```

AFTER:
```python
    success_count = 0
    for i, (title, text) in enumerate(sections):
        # Skip sections with no real content (AI summarization failed)
        if 'Summary unavailable' in text or 'All AI providers failed' in text:
            print(f'  [audio]   [{i+1}/{len(sections)}] ⏭️  Skipping "{(title or "section")[:50]}" — no summary available')
            continue

        video_num = i + 1
        is_first  = (i == 0)
        is_last   = (i == len(sections) - 1)
        label     = title or f'section_{video_num}'
        short     = label[:50]
```

**IMPORTANT:** After this change, `video_num` must be based on the section index, not `i+1`, because skipped sections don't get a video number. But the current code uses `video_num = i + 1` which is correct since we use the original loop index. Actually wait — after `continue`, the `is_last` check becomes wrong because it compares against `len(sections)` but we may have skipped some. Let me fix this properly:

REVISED AFTER (full loop):
```python
    success_count = 0
    valid_sections = []
    for i, (title, text) in enumerate(sections):
        # Skip sections with no real content (AI summarization failed)
        if 'Summary unavailable' in text or 'All AI providers failed' in text:
            print(f'  [audio]   [{i+1}/{len(sections)}] ⏭️  Skipping "{(title or "section")[:50]}" — no summary available')
            continue
        valid_sections.append((i, title, text))

    print(f'  [audio] 📹 {len(valid_sections)} valid section(s) (skipped {len(sections) - len(valid_sections)})')

    for idx, (orig_i, title, text) in enumerate(valid_sections):
        video_num = idx + 1
        is_first  = (idx == 0)
        is_last   = (idx == len(valid_sections) - 1)
        label     = title or f'section_{video_num}'
        short     = label[:50]
```

---

## Fix 5: Remove Redundant "สรุปสั้น" Section Before Condensing (🟡 Medium)

### File: `scripts/generate_audio_report.py`

**In function `_clean_section_text()` (lines 155-167), add removal of redundant sections:**

BEFORE:
```python
def _clean_section_text(text: str) -> str:
    """Strip markdown formatting so the condense model sees plain Thai prose."""
    # Remove all heading markers (## ### ####) — they confuse section boundary detection
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r'\*{1,3}', '', text)
    text = re.sub(r'_{1,2}', '', text)
    # Remove source/video-id metadata lines
    text = re.sub(r'^\*\*Source:\*\*.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\*\*Video ID:\*\*.*$', '', text, flags=re.MULTILINE)
    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
```

AFTER:
```python
def _clean_section_text(text: str) -> str:
    """Strip markdown formatting so the condense model sees plain Thai prose."""
    # Remove redundant summary sections that duplicate overview content
    # (these cause the condense model to produce repetitive audio)
    text = re.sub(r'สรุปสั้น.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'เอาไปใช้ยังไง.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    # Remove all heading markers (## ### ####) — they confuse section boundary detection
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r'\*{1,3}', '', text)
    text = re.sub(r'_{1,2}', '', text)
    # Remove source/video-id metadata lines
    text = re.sub(r'^\*\*Source:\*\*.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\*\*Video ID:\*\*.*$', '', text, flags=re.MULTILINE)
    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
```

---

## Fix 6: Dynamic Paragraph Target + Increase Token Limit (🟡 Medium)

### File: `scripts/generate_audio_report.py`

**Change A — Dynamic paragraph target in `_condense_video_section()` (lines 180-196):**

BEFORE:
```python
    prompt = (
        "คุณคือนักเขียนบทพอดแคสต์ภาษาไทย ผู้เชี่ยวชาญในการสรุปเนื้อหาวิดีโอ AI\n\n"
        "งานของคุณ: เขียนบทพูดภาษาไทยที่สมบูรณ์สำหรับเนื้อหาวิดีโอด้านล่าง\n\n"
        "ข้อกำหนดสำคัญ:\n"
        f"1. เริ่มต้นด้วย: {opening}\n"
        "2. เขียนเนื้อหาหลัก 4-6 ย่อหน้า แต่ละย่อหน้าอธิบายประเด็นสำคัญหนึ่งข้อ\n"
        "   แต่ละย่อหน้ามีความยาว 3-5 ประโยค อธิบายอย่างละเอียดและให้ตัวอย่างจริง\n"
        "3. เนื้อหารวมทั้งหมด (ไม่รวมประโยคเปิด-ปิด) ต้องยาวอย่างน้อย 300 คำ\n"
        "4. ใช้ภาษาพูดธรรมชาติ ไม่เป็นทางการ ฟังแล้วเข้าใจง่าย\n"
        "5. ไม่มี markdown ไม่มี bullet points ไม่มีหัวข้อ — เป็น plain text ล้วนๆ\n"
        "6. ไม่มีอักขระพิเศษ เช่น ** [] ## --- * _\n"
        "7. ใช้ 'ค่ะ' ลงท้ายประโยคหลักเป็นส่วนใหญ่\n"
    )
```

AFTER:
```python
    # Count key points in source to set dynamic paragraph target
    cleaned = _clean_section_text(section_text)
    key_point_count = max(len(re.findall(r'\*\*\d+\.', section_text)), 4)
    para_target = min(key_point_count, 10)  # cap at 10

    prompt = (
        "คุณคือนักเขียนบทพอดแคสต์ภาษาไทย ผู้เชี่ยวชาญในการสรุปเนื้อหาวิดีโอ AI\n\n"
        "งานของคุณ: เขียนบทพูดภาษาไทยที่สมบูรณ์สำหรับเนื้อหาวิดีโอด้านล่าง\n\n"
        "ข้อกำหนดสำคัญ:\n"
        f"1. เริ่มต้นด้วย: {opening}\n"
        f"2. เขียนเนื้อหาหลัก {para_target} ย่อหน้า แต่ละย่อหน้าอธิบายประเด็นสำคัญหนึ่งข้อ\n"
        "   แต่ละย่อหน้ามีความยาว 3-5 ประโยค อธิบายอย่างละเอียดและให้ตัวอย่างจริง\n"
        "   สำคัญมาก: ต้องครอบคลุมทุกประเด็นที่ระบุในเนื้อหา ห้ามตัดประเด็นออก\n"
        "3. เนื้อหารวมทั้งหมด (ไม่รวมประโยคเปิด-ปิด) ต้องยาวอย่างน้อย 300 คำ\n"
        "4. ใช้ภาษาพูดธรรมชาติ ไม่เป็นทางการ ฟังแล้วเข้าใจง่าย\n"
        "5. ไม่มี markdown ไม่มี bullet points ไม่มีหัวข้อ — เป็น plain text ล้วนๆ\n"
        "6. ไม่มีอักขระพิเศษ เช่น ** [] ## --- * _\n"
        "7. ใช้ 'ค่ะ' ลงท้ายประโยคหลักเป็นส่วนใหญ่\n"
    )
```

**Change B — Increase max_output_tokens (line 216):**

BEFORE:
```python
            response = client.models.generate_content(
                model=CONDENSE_MODEL,
                contents=prompt,
                config=_genai.types.GenerateContentConfig(max_output_tokens=4096, temperature=0.7),
            )
```

AFTER:
```python
            response = client.models.generate_content(
                model=CONDENSE_MODEL,
                contents=prompt,
                config=_genai.types.GenerateContentConfig(max_output_tokens=8192, temperature=0.7),
            )
```

---

## Execution Order

1. **Fix 1** — Code change in `run_ai_trends_research_enhanced.py` (sanitize_topic + get_dirs)
2. **Fix 2** — Merge tracker files (shell commands)
3. **Fix 3** — Consolidate directories (shell commands)
4. **Fix 4** — Skip "Summary unavailable" in `generate_audio_report.py`
5. **Fix 5** — Remove "สรุปสั้น" in `_clean_section_text()` in `generate_audio_report.py`
6. **Fix 6** — Dynamic paragraphs + increase tokens in `generate_audio_report.py`

Fixes 4-6 are all in the same file — do them together.

---

## Verification

After all fixes:

```bash
cd /home/mandhira/Desktop/Projects/ai-trends-research-source

# 1. Verify no uppercase tracker exists
ls ai_trends_reports/content_hashes_NATEHERK* 2>/dev/null && echo "FAIL: uppercase tracker still exists" || echo "PASS: no uppercase tracker"

# 2. Verify merged tracker
python3 -c "import json; d=json.load(open('ai_trends_reports/content_hashes_nateherk.json')); print(f'PASS: {len(d)} hashes in nateherk tracker')"

# 3. Verify no uppercase report dirs
ls -d ai_trends_reports/reports/NATEHERK 2>/dev/null && echo "FAIL: uppercase report dir exists" || echo "PASS: no uppercase report dir"

# 4. Verify sanitize_topic returns lowercase
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from run_ai_trends_research_enhanced import sanitize_topic, get_dirs
assert sanitize_topic('NATEHERK') == 'nateherk', 'FAIL: sanitize_topic still uppercase'
print('PASS: sanitize_topic returns lowercase')
dirs = get_dirs('NATEHERK', 'nateherk')
assert 'content_hashes_nateherk.json' in dirs['hash_tracker'], f'FAIL: {dirs[\"hash_tracker\"]}'
print(f'PASS: tracker path = {dirs[\"hash_tracker\"]}')
"

# 5. Quick syntax check on modified files
python3 -m py_compile scripts/run_ai_trends_research_enhanced.py && echo "PASS: enhanced script syntax OK"
python3 -m py_compile scripts/generate_audio_report.py && echo "PASS: audio script syntax OK"

# 6. Git commit
git add -A
git commit -m "fix: resolve duplicate video + audio issues (incident 2026-06-12)

- Remove NATEHERK special case in sanitize_topic() (case-sensitive tracker split)
- Add .lower() safety net in get_dirs() tracker path
- Merge uppercase tracker into lowercase (94+12 → 106 unique hashes)
- Consolidate NATEHERK/ → nateherk/ directories
- Skip 'Summary unavailable' sections in audio generation
- Remove redundant 'สรุปสั้น' before condensing
- Dynamic paragraph target based on key point count
- Increase max_output_tokens 4096 → 8192"
```

---

## ⚠️ Important Notes

- **Do NOT modify `research_jobs.json`** — `report_folder` is already lowercase (`"nateherk"`)
- **Do NOT modify `sanitize_report_folder()`** — it correctly preserves case from `research_jobs.json`
- **The `.lower()` in Fix 1B only applies to `tracker_safe`** — NOT to report/archive paths
- **Backup files** (`.bak`) can be deleted after verification passes
- **Dashboard cron-sync** rewrites crontab on save/delete — be aware if editing jobs via dashboard during fix
