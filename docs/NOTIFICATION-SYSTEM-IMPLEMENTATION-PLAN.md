# ATS Notification System — Implementation Plan

> **สถานะ:** Plan (ยังไม่ implement)
> **วันที่:** 2026-05-27
> **Design document:** `docs/NOTIFICATION-SYSTEM-DESIGN.md`
> **Analysis document:** `docs/NOTIFICATION-SYSTEM-ANALYSIS.md`

---

## Phase 1: Core Notification Script + Config

**เป้าหมาย:** ส่ง email + Telegram DM ได้จริง ผ่าน CLI เพียงอย่างเดียว ไม่มี Dashboard UI

**ขอบเขต Phase 1:**
- สร้าง `config/notification_routing.json` (config ไฟล์ + initial config สำหรับ Mandy)
- เขียน `scripts/notify_topic.py` (notification script หลัก)
- สร้าง `scripts/templates/email_report.html.j2` (Jinja2 HTML email template)
- เพิ่ม 1 บรรทัดใน `scripts/run_daily_summary_cron.sh` เพื่อเรียก notify_topic.py

**ไม่รวมใน Phase 1:**
- Dashboard UI
- Auto-subscribe / unsubscribe logic
- Email analytics / open tracking
- Webhook triggers

---

### Phase 1 — Checklist

#### 1.1 Config File

- [ ] สร้าง `config/notification_routing.json` โดยใช้ schema จาก Design doc Section 3
- [ ] เพิ่ม initial config สำหรับ nateherk (email + Telegram) เป็น example
- [ ] Validate JSON: ไม่มี syntax errors, ครบทุก required fields
- [ ] เพิ่ม `notification_routing.json` เข้า `.gitignore` (ป้องกัน email address leak)

#### 1.2 Notification Script

- [ ] สร้าง `scripts/notify_topic.py` พร้อม argparse: `--all`, `--topic`, `--date`, `--dry-run`, `--email-only`, `--telegram-only`
- [ ] implement `load_routing_config()` — โหลด JSON + merge defaults
- [ ] implement `find_report_file(topic_id, date)` — หา .md ตาม research_jobs.json folder map
- [ ] implement `extract_summary(report_path)` — ดึง title + intro text ≤800 chars
- [ ] implement `build_download_urls(topic_id, date)` — MD + WAV GitHub URLs
- [ ] implement `send_email(to_list, subject, html_body, text_body)` — Brevo SMTP via smtplib
- [ ] implement `send_telegram_dm(bot_token, chat_id, text)` — Bot API sendMessage
- [ ] implement `render_email_template(vars)` — Jinja2 render เป็น HTML + plain text
- [ ] ทุก function: catch exception → log → return False (ไม่ raise)
- [ ] `--dry-run` mode: print ทุก action แต่ไม่ส่งจริง

#### 1.3 Email Template

- [ ] สร้าง `scripts/templates/` directory
- [ ] สร้าง `scripts/templates/email_report.html.j2` — responsive HTML email (inline CSS)
- [ ] Template มีครบ: header block, summary block, download links block, footer block
- [ ] รองรับ `wav_url=None` → ซ่อน audio section อัตโนมัติ (Jinja2 `{% if wav_url %}`)
- [ ] Encoding UTF-8 สำหรับ Thai text
- [ ] มี plain text fallback template (`.txt.j2`)

#### 1.4 Pipeline Integration

- [ ] เพิ่ม Step 4 ใน `scripts/run_daily_summary_cron.sh`:
  ```bash
  python3 "$SCRIPTS_DIR/notify_topic.py" --all --date "$(date +%Y-%m-%d)" || true
  ```
- [ ] วางหลัง Step 3 (audio push) และก่อน Step 5 (Telegram digest)
- [ ] ตรวจสอบว่า `set -e` ไม่ kill pipeline เมื่อ notify_topic.py fail (เพราะ `|| true`)

---

## Phase 2: Dashboard UI — Notification Config Tab

**เป้าหมาย:** จัดการ notification routing ผ่าน Dashboard web UI แทนการ edit JSON ด้วยมือ

**ขอบเขต Phase 2:**
- เพิ่ม tab "Notifications" ใน `dashboard/app.py`
- แสดง table ของ topics ทั้งหมด พร้อม email/Telegram toggle
- แก้ไข recipient emails และ chat IDs ได้จาก UI
- ปุ่ม "Test Send" — ส่ง test notification ไปยัง 1 recipient

**ไม่รวมใน Phase 2:**
- User self-service subscribe/unsubscribe
- Email template editor ใน Dashboard
- Notification history log viewer

---

### Phase 2 — Checklist

#### 2.1 Dashboard Route

- [ ] เพิ่ม `GET /notifications` — แสดง Notifications config page
- [ ] เพิ่ม `GET /api/notifications/config` — return notification_routing.json เป็น JSON
- [ ] เพิ่ม `POST /api/notifications/config` — รับ updated config + เขียน JSON file
- [ ] เพิ่ม `POST /api/notifications/test` — ส่ง test notification ไปยัง topic + recipient

#### 2.2 Notifications Page UI

- [ ] Table แสดงทุก topic จาก research_jobs.json
- [ ] Column: Topic Name | Email Enabled (toggle) | Email Recipients | Telegram Enabled (toggle) | Telegram Chat IDs | Actions
- [ ] Click toggle → call `/api/notifications/config` PATCH
- [ ] Click "Edit" row → inline edit สำหรับ emails/chat_ids
- [ ] "Test Send" button per row → call `/api/notifications/test`
- [ ] แสดง result ของ test (success/fail) inline

---

## Test Strategy

### ทดสอบ Phase 1 โดยไม่ส่งจริง (Dry-run)

```bash
cd /home/mandhira/Desktop/Projects/ai-trends-research-source

# 1. Dry-run ทุก topic — ดูว่า detect ไฟล์และ build URLs ถูกต้อง
python3 scripts/notify_topic.py --all --dry-run

# 2. Dry-run topic เดียว
python3 scripts/notify_topic.py --topic nateherk --dry-run

# 3. ตรวจสอบ JSON config valid
python3 -c "import json; json.load(open('config/notification_routing.json')); print('JSON OK')"

# 4. ตรวจสอบ template render ไม่ crash
python3 -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('scripts/templates'))
tmpl = env.get_template('email_report.html.j2')
print(tmpl.render(topic_name='NATEHERK', date_str='2026-05-27', video_count=3,
    intro_summary='test', md_github_url='http://x', md_raw_url='http://x', wav_url=None))[:200]
"
```

### ทดสอบ Real Send (topic เดียว ก่อน rollout)

```bash
# ส่ง email จริงไปที่ test recipient
python3 scripts/notify_topic.py --topic nateherk --email-only

# ส่ง Telegram DM จริง
python3 scripts/notify_topic.py --topic nateherk --telegram-only

# ส่งทั้ง email + Telegram สำหรับ 1 topic
python3 scripts/notify_topic.py --topic nateherk --date 2026-05-27
```

### Regression Test (ตรวจสอบ daily digest ยังทำงานปกติ)

```bash
# ตรวจสอบว่า ai_trends_daily_summary_thai.py ยังทำงานได้หลัง เพิ่ม Step 4
python3 -m py_compile scripts/ai_trends_daily_summary_thai.py && echo "OK"
python3 -m py_compile scripts/notify_topic.py && echo "OK"
bash -n scripts/run_daily_summary_cron.sh && echo "Shell syntax OK"
```

---

## Rollout Order

```
[Phase 1]
1. สร้าง config/notification_routing.json (เริ่มจาก all topics disabled)
2. เขียน scripts/notify_topic.py
3. สร้าง scripts/templates/email_report.html.j2
4. รัน dry-run ทุก topic — verify output
5. เปิด nateherk เป็น topic แรก (email + Telegram)
6. รัน real send สำหรับ nateherk → ยืนยัน email inbox + Telegram DM
7. เพิ่ม Step 4 ใน run_daily_summary_cron.sh
8. รอ cron รันวันถัดไป → verify notification มาถึงจริง

[Phase 2]
9. ออกแบบ Dashboard Notifications tab UI (ขอ approval ก่อน)
10. Implement routes + UI
11. Test toggle + test send จาก Dashboard
```

---

## Risk Mitigation

| ความเสี่ยง | แนวทางป้องกัน |
|-----------|-------------|
| Telegram bot conflict กับ Hermes | ใช้ direct API calls เหมือน ai_trends_daily_summary_thai.py (ไม่ใช่ Channels plugin) |
| Email ติด spam | ตั้ง subject ชัดเจน `[ATS]` prefix, ใช้ Brevo domain (SPF/DKIM ตั้งโดย Brevo) |
| WAV link 404 (ยังไม่ upload) | notify_topic.py รันหลัง upload_audio_to_github.py — ลำดับใน cron script ถูกต้องแล้ว |
| Pipeline abort จาก notify_topic crash | `|| true` ใน run_daily_summary_cron.sh ป้องกัน |
| Email address ใน config leak | เพิ่ม notification_routing.json ใน `.gitignore` |

---

*Implementation plan เสร็จสมบูรณ์ · สร้าง 2026-05-27*
