# ATS Notification System — Design Document

> **สถานะ:** Design (ยังไม่ implement)
> **วันที่:** 2026-05-27
> **อ้างอิง:** `docs/NOTIFICATION-SYSTEM-ANALYSIS.md` (analysis เบื้องต้น)
> **แผน implementation:** `docs/NOTIFICATION-SYSTEM-IMPLEMENTATION-PLAN.md`

---

## 1. สรุปผู้บริหาร (Executive Summary)

ระบบ ATS (AI Trends Research Source) ทำงานทุกวันโดยดึงวิดีโอ YouTube → สรุปเป็น Thai markdown → ส่งขึ้น GitHub → แจ้งเตือนผ่าน Telegram digest รวมทุก topic

ปัจจุบันข้อจำกัดคือ: มีแค่ Telegram digest รวมทุก topic ส่งพร้อมกัน ไม่สามารถกำหนดได้ว่า "topic นี้ให้ส่งให้ใคร" หรือ "ส่งทางอีเมล์"

**เป้าหมายของระบบใหม่:**
- ส่ง **email notification** พร้อมสรุปและลิ้งค์ download ไปยังอีเมล์ที่กำหนด per-topic
- ส่ง **Telegram DM** per-topic ไปยัง chat_id ที่ระบุ
- จัดการผ่าน **JSON config ไฟล์เดียว** — แก้ไขได้ง่าย ขยาย Dashboard UI ได้ในอนาคต
- **Additive เท่านั้น** — ไม่กระทบ Telegram daily digest ที่มีอยู่

---

## 2. Architecture Overview

### 2.1 Data Flow

```
run_daily_summary_cron.sh
├── Step 1: upload_reports_to_github_fixed.py   (MD reports → GitHub)
├── Step 2: generate_audio_report.py            (TTS WAV generation)
├── Step 3: upload_audio_to_github.py           (WAV → GitHub)
├── Step 4: notify_topic.py --all               ← NEW (per-topic notifications)
│           │
│           ├── load config/notification_routing.json
│           ├── for each topic:
│           │   ├── find today's report file
│           │   ├── extract summary (800 chars)
│           │   ├── build GitHub download URLs (.md + .wav)
│           │   ├── if email_enabled → send via Brevo SMTP
│           │   └── if telegram_enabled → POST to Bot API sendMessage
│           └── log: success/fail per topic, never abort pipeline
└── Step 5: ai_trends_daily_summary_thai.py     (existing Telegram digest — unchanged)
```

### 2.2 Component Map

| Component | ไฟล์ | บทบาท |
|-----------|------|--------|
| Routing config | `config/notification_routing.json` | กำหนด topic → channel mapping |
| Notification script | `scripts/notify_topic.py` | ส่ง email + Telegram DM |
| Email template | `scripts/templates/email_report.html.j2` | Jinja2 HTML email template |
| Pipeline hook | `scripts/run_daily_summary_cron.sh` | เรียก notify_topic.py ก่อน digest |
| Credentials | `~/.credentials.env` | SMTP + Telegram token |

---

## 3. Config Schema: `config/notification_routing.json`

### 3.1 Schema Definition

```json
{
  "defaults": {
    "email_enabled": false,
    "telegram_enabled": false,
    "notification_mode": "per_topic",
    "recipient_emails": [],
    "telegram_chat_ids": []
  },
  "topics": {
    "{topic_id}": {
      "email_enabled": true | false,
      "telegram_enabled": true | false,
      "recipient_emails": ["email1@example.com", "email2@example.com"],
      "telegram_chat_ids": ["1043709932", "987654321"],
      "notification_mode": "per_topic" | "digest_only"
    }
  }
}
```

### 3.2 Field Definitions

| Field | Type | ระดับ | คำอธิบาย |
|-------|------|-------|----------|
| `email_enabled` | boolean | defaults + topic | เปิด/ปิดการส่งอีเมล์สำหรับ topic นี้ |
| `telegram_enabled` | boolean | defaults + topic | เปิด/ปิดการส่ง Telegram DM สำหรับ topic นี้ |
| `recipient_emails` | string[] | defaults + topic | รายการอีเมล์ที่จะส่ง (หลายคนได้) |
| `telegram_chat_ids` | string[] | defaults + topic | รายการ chat_id ที่จะส่ง DM (หลายคนได้) |
| `notification_mode` | enum | defaults + topic | `per_topic` = ส่งแยกต่าง topic; `digest_only` = ข้ามการส่งรายบุคคล |

**Override logic:** ค่าใน `topics.{id}` override ค่าใน `defaults` — ถ้า topic ไม่ระบุ field ใด ให้ใช้ค่า defaults

### 3.3 ตัวอย่าง Config (3 topics)

```json
{
  "defaults": {
    "email_enabled": false,
    "telegram_enabled": false,
    "notification_mode": "per_topic",
    "recipient_emails": [],
    "telegram_chat_ids": []
  },
  "topics": {
    "nateherk": {
      "email_enabled": true,
      "recipient_emails": ["owllulla@gmail.com"],
      "telegram_enabled": true,
      "telegram_chat_ids": ["1043709932"],
      "notification_mode": "per_topic"
    },
    "ai_agents": {
      "email_enabled": true,
      "recipient_emails": ["owllulla@gmail.com", "team@example.com"],
      "telegram_enabled": false,
      "notification_mode": "per_topic"
    },
    "finance_money_coach": {
      "email_enabled": false,
      "telegram_enabled": true,
      "telegram_chat_ids": ["1043709932"],
      "notification_mode": "per_topic"
    }
  }
}
```

**Topic IDs** ตรงกับ `id` field ใน `config/research_jobs.json`:
`ai_agents`, `claude_code`, `ai_viral_niche`, `nateherk`, `joanna_wiebe`,
`jacksons_ai`, `make_money_matt`, `miss_luna_vega`, `claude_code_seedance`,
`claude_code_higgsfield`, `claude_code_shopify`, `finance_money_coach`,
`finance_money_buffalo`, `finance_a_academy`, `finance_financial_diet`,
`finance_humphrey_yang`, `boom_big_nose`

---

## 4. Script Design: `scripts/notify_topic.py`

### 4.1 ความรับผิดชอบของ Script

1. รับ arguments: `--topic {id}` หรือ `--all`, `--date {YYYY-MM-DD}` (default: today), `--dry-run`
2. โหลด `config/notification_routing.json`
3. สำหรับแต่ละ topic ที่กำหนด:
   a. หา report file วันนี้ (ใช้ logic เดียวกับ `ai_trends_daily_summary_thai.py`)
   b. Extract summary จาก report (800 chars แรก หรือส่วน intro)
   c. สร้าง download URLs (md + wav ถ้ามี)
   d. ส่ง email ถ้า `email_enabled=true`
   e. ส่ง Telegram DM ถ้า `telegram_enabled=true`
4. Log ผลทุก topic — ไม่ abort ถ้า 1 topic fail
5. `--dry-run`: แสดงว่าจะส่งอะไร ไปไหน โดยไม่ส่งจริง

### 4.2 CLI Interface

```bash
# ส่งทุก topic ที่เปิด notification ไว้
python3 scripts/notify_topic.py --all --date 2026-05-27

# ส่งเฉพาะ topic เดียว (สำหรับ test)
python3 scripts/notify_topic.py --topic nateherk --date 2026-05-27

# Dry-run — แสดงว่าจะส่งอะไร ไม่ส่งจริง
python3 scripts/notify_topic.py --all --dry-run

# ส่งเฉพาะ email (ข้าม Telegram)
python3 scripts/notify_topic.py --topic nateherk --email-only
```

### 4.3 Report Summary Extraction Logic

```
1. เปิด report file: ai_trends_reports/reports/{folder}/{date}.md
2. ถ้าไม่มีไฟล์: log "no report today" → skip topic
3. อ่าน 2 บรรทัดแรก (title + date line) → หัวเรื่อง
4. ดึงเนื้อหาก่อน "## Video 1:" (~800 chars) → intro summary
5. นับจำนวน "## Video " headers → video count
6. สรุป: "{N} วิดีโอ · {date}"
```

### 4.4 Download URL Construction

**Markdown report:**
```
Base: https://github.com/MandhiraT/ai-trends-research/blob/master/reports/{github_path}/{date}.md
Download (raw): https://raw.githubusercontent.com/MandhiraT/ai-trends-research/master/reports/{github_path}/{date}.md
```

`github_path` มาจาก tuple ที่ 3 ใน TOPICS list ใน `ai_trends_daily_summary_thai.py`
เช่น `NATEHERK` → `"NATEHERK"`, `CC Obsidian` → `"claude_code/claude_code_obsidian"`

**Voice WAV file:**
```
Base: https://github.com/MandhiraT/ai-trends-research/tree/master/voice/{voice_folder}/
Raw: https://raw.githubusercontent.com/MandhiraT/ai-trends-research/master/voice/{voice_folder}/{date}-v1.wav
```

`voice_folder` มาจาก `config/audio_topics.json::github_folder_map`
เช่น `NATEHERK` → `"nateherk"`, `joanna_wiebe` → `"joanna_wiebe"`

**ถ้าไม่มี voice file** (topic ไม่ได้เปิด audio): แสดงลิ้งค์ไปที่ voice folder แทน และ note ว่า "ยังไม่มี audio วันนี้"

---

## 5. Email Notification Design

### 5.1 Email Format

| ส่วน | รายละเอียด |
|------|-----------|
| Transport | Brevo SMTP: `smtp-relay.brevo.com:587` (STARTTLS) |
| Format | `multipart/alternative` — HTML part + plain text fallback |
| Template engine | Jinja2 (`.j2` template file) |
| Template path | `scripts/templates/email_report.html.j2` |
| Sender | `ATS Research <noreply@thequietself.com>` |
| Encoding | UTF-8 (Thai text support) |

### 5.2 Email Subject Line Template

```
[ATS] {topic_name} — {video_count} วิดีโอใหม่ · {date_thai}
```

ตัวอย่าง:
```
[ATS] NATEHERK — 3 วิดีโอใหม่ · 27 พ.ค. 2569
[ATS] AI Agents — 5 วิดีโอใหม่ · 27 พ.ค. 2569
```

### 5.3 Email Template Structure (HTML)

```
┌────────────────────────────────────────────────┐
│  HEADER                                        │
│  ATS Daily Research · {date}                   │
│  Topic: {topic_name}                           │
├────────────────────────────────────────────────┤
│  SUMMARY BLOCK                                 │
│  {video_count} วิดีโอใหม่วันนี้               │
│  {intro_summary_text}  (≤800 chars)            │
├────────────────────────────────────────────────┤
│  DOWNLOAD LINKS BLOCK                          │
│  📄 [ดาวน์โหลด Report (.md)]  → raw GitHub URL │
│  🎧 [ฟัง Audio (.wav)]        → GitHub tree URL │
│       (ถ้าไม่มี audio: ซ่อน section นี้)       │
├────────────────────────────────────────────────┤
│  FOOTER                                        │
│  AI Trends Research System · MandhiraT          │
│  Unsubscribe: แก้ไขไฟล์ config โดยตรง          │
└────────────────────────────────────────────────┘
```

### 5.4 Jinja2 Template Variables

| Variable | Type | ค่าที่ส่งเข้า template |
|----------|------|----------------------|
| `topic_name` | str | "NATEHERK", "AI Agents" ฯลฯ |
| `date_str` | str | "2026-05-27" |
| `date_thai` | str | "27 พ.ค. 2569" |
| `video_count` | int | จำนวน ## Video headers |
| `intro_summary` | str | 800 chars แรกของ report |
| `md_github_url` | str | GitHub blob URL สำหรับดู |
| `md_raw_url` | str | raw.githubusercontent.com สำหรับ download |
| `wav_url` | str | GitHub tree URL สำหรับ audio (None ถ้าไม่มี) |
| `wav_raw_url` | str | raw URL สำหรับ download WAV โดยตรง (None ถ้าไม่มี) |

### 5.5 Credential Sourcing (SMTP)

จาก `~/.credentials.env` (load ด้วย `config/paths.py::load_credentials()`):

```python
BREVO_SMTP_HOST     = credentials["BREVO_SMTP_HOST"]      # smtp-relay.brevo.com
BREVO_SMTP_PORT     = int(credentials["BREVO_SMTP_PORT"]) # 587
BREVO_SMTP_USERNAME = credentials["BREVO_SMTP_USERNAME"]  # a5da26001@smtp-brevo.com
BREVO_SMTP_PASSWORD = credentials["BREVO_SMTP_PASSWORD"]  # xsmtpsib-...
```

Sender email: `GIT_USER_EMAIL` (`mandhira@thequietself.com`) หรือกำหนดใน config

---

## 6. Telegram DM Design

### 6.1 Bot Token Sourcing

ใช้ bot token เดียวกับ `ai_trends_daily_summary_thai.py`:

```python
env_path = os.path.expanduser("~/.claude/channels/telegram/.env")
# TELEGRAM_BOT_TOKEN=8710044916:AAETX4x...
```

> **หมายเหตุ:** ATS ใช้ bot token เดียวกับ Hermes Channels — แต่ไม่มี conflict เพราะ ATS ใช้ผ่าน direct API calls ไม่ใช่ผ่าน Channels plugin. อย่าเปิด `enabledPlugins.telegram=true` ใน Claude sessions ขณะที่ ATS cron ทำงาน (ดู memory: `feedback_telegram_plugin_conflict.md`)

### 6.2 sendMessage Parameters

```python
requests.post(
    f"https://api.telegram.org/bot{bot_token}/sendMessage",
    json={
        "chat_id": chat_id,          # จาก telegram_chat_ids array ใน config
        "text": message_text,        # Thai HTML-formatted message
        "parse_mode": "HTML",        # เหมือน daily digest ที่ใช้อยู่
        "disable_web_page_preview": True
    },
    timeout=30
)
```

### 6.3 Telegram Message Format

```
📊 <b>{topic_name}</b> · {date}

{video_count} วิดีโอใหม่

{intro_summary_short}  (≤400 chars)

📄 <a href="{md_github_url}">ดู Report</a>
📥 <a href="{md_raw_url}">Download .md</a>
{wav line ถ้ามี: 🎧 <a href="{wav_url}">Download .wav</a>}

—
ATS Research System
```

### 6.4 Multi-recipient Loop

```python
for chat_id in topic_config["telegram_chat_ids"]:
    result = send_telegram_dm(bot_token, chat_id, message)
    log(f"Telegram → {chat_id}: {'ok' if result else 'failed'}")
```

---

## 7. Error Handling & Pipeline Safety

### 7.1 Isolation Principle

`notify_topic.py` จะ **ไม่ abort pipeline** ในทุกกรณี:

```bash
# ใน run_daily_summary_cron.sh:
python3 "$SCRIPTS_DIR/notify_topic.py" --all --date "$(date +%Y-%m-%d)" || true
```

### 7.2 Error Handling Per Component

| กรณี | การจัดการ |
|------|----------|
| ไม่มี report วันนี้ | log "no report" → skip topic → ไม่ส่ง |
| SMTP connection fail | log error → skip email → ดำเนินการต่อ |
| Telegram API error | log error + response → skip DM → ดำเนินการต่อ |
| config topic ไม่พบ | ใช้ `defaults` values |
| voice file ไม่มี | ส่งแค่ MD link, ไม่ส่ง WAV section |
| notification_routing.json ไม่มี | log warning → skip ทั้ง script → exit 0 |

### 7.3 Logging

```
[2026-05-27 09:00:01] notify_topic: nateherk → email owllulla@gmail.com OK
[2026-05-27 09:00:02] notify_topic: nateherk → telegram 1043709932 OK
[2026-05-27 09:00:03] notify_topic: ai_agents → email owllulla@gmail.com OK
[2026-05-27 09:00:04] notify_topic: joanna_wiebe → skipped (email_enabled=false, telegram_enabled=false)
```

---

## 8. Security Considerations

| เรื่อง | แนวทาง |
|--------|--------|
| SMTP credentials | อยู่ใน `~/.credentials.env` (ไม่ commit) — เหมือน pattern เดิม |
| Telegram bot token | อยู่ใน `~/.claude/channels/telegram/.env` (ไม่ commit) |
| Email addresses | อยู่ใน `config/notification_routing.json` — ไม่มี secrets ใน config |
| Content ใน email | สรุปเนื้อหาสาธารณะจาก YouTube — ไม่มีข้อมูลส่วนตัวหรือ credentials |
| WAV attachment | ไม่แนบไฟล์โดยตรง — ใช้ download links เท่านั้น (ไฟล์ 10–30MB เกิน SMTP limit) |

---

## 9. Prerequisites ก่อน Implementation

| รายการ | สถานะ | หมายเหตุ |
|--------|--------|---------|
| Brevo SMTP credentials | ✅ ยืนยันแล้ว | `~/.credentials.env` มีครบ 4 keys |
| Telegram bot token | ✅ ยืนยันแล้ว | `~/.claude/channels/telegram/.env` |
| `config/research_jobs.json` topic IDs | ✅ ยืนยันแล้ว | ใช้เป็น key ใน notification_routing.json |
| GitHub voice URL pattern | ✅ ยืนยันแล้ว | `voice/{folder}/` จาก `audio_topics.json` |
| Jinja2 installed | ✅ ยืนยันแล้ว | มีในระบบ |
| `config/notification_routing.json` | ❌ ต้องสร้าง | Phase 1 |
| `scripts/notify_topic.py` | ❌ ต้องเขียน | Phase 1 |
| `scripts/templates/email_report.html.j2` | ❌ ต้องเขียน | Phase 1 |
| Dashboard UI tab | ❌ ต้องออกแบบ | Phase 2 |

---

## 10. ไฟล์ที่ต้องสร้าง/แก้ไข

| ไฟล์ | Action | Phase |
|------|--------|-------|
| `config/notification_routing.json` | สร้างใหม่ | 1 |
| `scripts/notify_topic.py` | สร้างใหม่ | 1 |
| `scripts/templates/email_report.html.j2` | สร้างใหม่ | 1 |
| `scripts/run_daily_summary_cron.sh` | เพิ่ม 1 บรรทัด (step 4) | 1 |
| `dashboard/app.py` | เพิ่ม tab "Notifications" | 2 |

---

*Document เสร็จสมบูรณ์ · สร้าง 2026-05-27 · Implementation plan: `docs/NOTIFICATION-SYSTEM-IMPLEMENTATION-PLAN.md`*
