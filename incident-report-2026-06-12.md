# 🔴 Incident Report — ATS Pipeline Issues
**Date:** 2026-06-12  
**Reported by:** Mandhira  
**Investigated by:** มะลิ (Hermes Agent)  
**Status:** Root Cause Identified — Fixes Ready

---

## Executive Summary

3 ปัญหาหลักที่พบ มาจาก 2 root causes:

1. **Case-sensitive tracker split** → vdo ซ้ำ + สร้างเสียงซ้ำ
2. **Condense model limitations** → เสียงไม่ครบเนื้อหา + เสียง hallucinate จาก "Summary unavailable"

---

## Issue #1: ระบบสรุป Video ซ้ำข้ามวัน

### อาการ
- nateherk report 12/6 มีหัวข้อซ้ำกับ 11/6
- Video IDs: `8QQ_INxAhRs`, `dYrrEKXtttk`, `e18sdZLwP7o` ปรากฏซ้ำ

### Root Cause: Case-Sensitive Tracker File Split

**ไฟล์ tracker แยกเป็น 2 ไฟล์:**
- `content_hashes_nateherk.json` (12 hashes) — ใช้โดย cron path
- `content_hashes_NATEHERK.json` (94 hashes) — ใช้โดย dashboard/manual path

**แค่ 7 hashes ที่ทับซ้อนกัน** → vdo ที่เคยสรุปแล้วจาก path นึง ไม่ถูกตรวจจับเป็น duplicate ในอีก path

### Code ที่เป็นต้นเหตุ

**ไฟล์:** `scripts/run_ai_trends_research_enhanced.py`

```python
# Lines 40-45: sanitize_topic() มี special case ทำให้ NATEHERK เป็นตัวใหญ่
def sanitize_topic(topic):
    if topic.upper() == "NATEHERK":
        return "NATEHERK"  # ← ต้นเหตุ! ทำให้ tracker path เป็นตัวใหญ่
    return topic.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")[:50]
```

```python
# Lines 100-109: get_dirs() ใช้ topic_safe ที่ไม่ได้ normalize
def get_dirs(topic, report_folder=None):
    topic_safe = sanitize_report_folder(report_folder) if report_folder else sanitize_topic(topic)
    tracker_safe = topic_safe.replace("/", "_")
    return {
        "tracker": f"{BASE_REPORTS_DIR}/content_hashes_{tracker_safe}.json",  # ← case-sensitive!
    }
```

**2 code paths ให้ผลต่างกัน:**
- Cron: `--topic NATEHERK --report-folder nateherk` → `sanitize_report_folder("nateherk")` → tracker: `content_hashes_nateherk.json`
- Dashboard: `--topic NATEHERK` (ไม่มี --report-folder) → `sanitize_topic("NATEHERK")` → tracker: `content_hashes_NATEHERK.json`

### Fix
1. **ลบ special case ใน `sanitize_topic()`** — ให้ทุก topic เป็น lowercase เสมอ
2. **Merge tracker files** — รวม hashes จากทั้ง 2 ไฟล์เข้าด้วยกัน
3. **เพิ่ม `.lower()` ใน `get_dirs()`** เป็น safety net:
   ```python
   tracker_safe = topic_safe.replace("/", "_").lower()
   ```
4. **Consolidate report/audio/script directories** — ย้ายจาก `NATEHERK/` → `nateherk/`

---

## Issue #2.1: ไฟล์เสียงสร้างเนื้อหาซ้ำในไฟล์เดียวกัน

### อาการ
- nateherk 11/6 v1.wav มีเนื้อหาท่อนเดียวกันซ้ำ 2 ครั้ง

### Root Cause: หลายปัจจัยรวมกัน

1. **Report มี `สรุปภาพรวม` + `สรุปสั้น`** ซ้อนกัน → condense model เห็นเนื้อหาเดียวกัน 2 รอบ
2. **Videos 2-3 มี "Summary unavailable"** → condense model hallucinate เนื้อหาจาก title เฉยๆ (เนื้อหาจึงซ้ำ/คล้าย v1)
3. **`_clean_section_text()` ไม่ตัดส่วน `สรุปสั้น`** ออกก่อนส่งให้ condense model

### Code ที่เป็นต้นเหตุ

**ไฟล์:** `scripts/generate_audio_report.py`

```python
# Lines 155-167: _clean_section_text() ตัดแค่ markdown markers แต่ไม่ตัดส่วนสรุปซ้ำ
def _clean_section_text(text):
    # ไม่มีการตัด "สรุปสั้น" หรือ "เอาไปใช้ยังไง" ออก
```

```python
# Lines 328+: _split_into_video_sections() แบ่งตาม ## Video N: แต่ไม่ skip "Summary unavailable"
for i, (title, text) in enumerate(sections):
    # ← ไม่มี check ว่า text มี "Summary unavailable" → สร้างเสียงจาก error message
```

### Fix
1. **Skip "Summary unavailable" sections** — ไม่สร้างเสียงสำหรับ video ที่ไม่มีสรุป
2. **ตัด `สรุปสั้น` และ `เอาไปใช้ยังไง`** ออกก่อนส่งให้ condense model
3. **เพิ่ม guard** ใน `_condense_video_section()` ให้ return empty ถ้า content สั้นเกินไปหรือเป็น error message

---

## Issue #2.2: สรุปเสียงไม่ครบตามเนื้อหา

### อาการ
- joanna_wiebe 12/6 v3.wav ไม่ครบ — ข้ามบางประเด็น
- ตรวจพบว่าเป็นปัญหาเรื้อรังทุก script ของ report นี้

### Root Cause: Condense Model Prompt จำกัดย่อหน้า

**ไฟล์:** `scripts/generate_audio_report.py`

```python
# Line 185: Prompt สั่ง "4-6 ย่อหน้า" แต่ report มีถึง 7 ประเด็น
"2. เขียนเนื้อหาหลัก 4-6 ย่อหน้า แต่ละย่อหน้าอธิบายประเด็นสำคัญหนึ่งข้อ\n"
```

```python
# Line 216: max_output_tokens จำกัด
max_output_tokens=4096  # ← อาจตัดเนื้อหายาว
```

### Evidence (joanna_wiebe 12/6)

| Video | ประเด็นใน Report | ประเด็นในเสียง | ขาด |
|-------|------------------|----------------|------|
| v1 (Body Language) | 7 | 4 | hair, walking, mirroring |
| v2 (Small Talk) | 6 | ~5 | subtle gaps |
| v3 (8 Hooks) | 6 | 5 | Loop types, Re-hook |
| v4 (First Impression) | 4 | ~4 | (สั้นกว่า พอไหว) |

### Fix
1. **นับ key points จาก report แล้วปรับ paragraph target แบบ dynamic**:
   ```python
   key_points = len(re.findall(r'\*\*\d+\.', section_text))
   para_target = max(key_points, 4)
   ```
2. **เพิ่ม max_output_tokens** จาก 4096 → 8192
3. **เพิ่ม instruction** ใน prompt: "ต้องครอบคลุมทุกประเด็นที่ระบุ ไม่ตัดออก"
4. **(Optional) เพิ่ม post-check** นับประเด็นใน script vs report

---

## Impact Assessment

| ปัญหา | ผลกระทบ | ความรุนแรง |
|-------|---------|------------|
| Vdo ซ้ำข้ามวัน | เสีย API cost ซ้ำ, ส่งเนื้อหาซ้ำผู้ฟัง | 🔴 สูง |
| เสียงสร้างจาก "Summary unavailable" | hallucinated content, เนื้อหาผิด | 🔴 สูง |
| เสียงซ้ำในไฟล์เดียวกัน | ผู้ฟังได้ยินซ้ำ, ไม่มีประโยชน์ | 🟡 กลาง |
| เสียงไม่ครบเนื้อหา | ข้อมูลไม่ครบ, พลาดประเด็นสำคัญ | 🟡 กลาง |

---

## Priority Fix Order

1. 🔴 **Merge tracker + ลบ special case** → แก้ vdo ซ้ำ (Issue #1)
2. 🔴 **Skip "Summary unavailable"** → แก้ hallucinated audio (Issue #2.1 หลัก)
3. 🟡 **ตัด `สรุปสั้น`** → แก้เสียงซ้ำในไฟล์ (Issue #2.1 รอง)
4. 🟡 **Dynamic paragraph target** → แก้เสียงไม่ครบ (Issue #2.2)

---

## Files ที่ต้องแก้ไข

| File | การแก้ไข |
|------|---------|
| `scripts/run_ai_trends_research_enhanced.py` | ลบ special case NATEHERK, เพิ่ม .lower() ใน get_dirs() |
| `scripts/generate_audio_report.py` | Skip "Summary unavailable", ตัด "สรุปสั้น", dynamic paragraphs |
| `ai_trends_reports/content_hashes_nateherk.json` | Merge จาก NATEHERK เข้ามา |
| `ai_trends_reports/content_hashes_NATEHERK.json` | ลบหลัง merge เสร็จ |
| `reports/NATEHERK/` → `reports/nateherk/` | ย้ายไฟล์ |
| `audio/NATEHERK/` → `audio/nateherk/` | ย้ายไฟล์ |
| `audio_scripts/NATEHERK/` → `audio_scripts/nateherk/` | ย้ายไฟล์ |
