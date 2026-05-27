# ATS Notification System — Research & Analysis

> **สถานะ:** Analysis (ยังไม่ implement)  
> **วันที่:** 2026-05-27  
> **ผู้เขียน:** มะลิ (Hermes Agent)  
> **เป้าหมาย:** วิเคราะห์ความเป็นไปได้และแนวทางการสร้างระบบแจ้งเตือน ATS ผ่านอีเมล + Telegram DM แบบ per-topic configurable

---

## 1. สิ่งที่พี่ Mandy ต้องการ

1. **ส่งอีเมลแจ้งเตือน** สรุป report แต่ละ topic ไปยังอีเมล์ที่กำหนด
2. **ส่ง Telegram DM** แจ้งเตือนได้ด้วย (นอกเหนือจาก Telegram summary ปัจจุบัน)
3. **จัดการ per-topic routing** — กำหนดได้ว่า topic นี้ส่งเมล์ไหน, DM ไหน
4. **แนบลิ้งค์ download** `.md` report และ `.wav` voice file ในอีเมล์

---

## 2. สถานะปัจจุบัน (Current State)

### 2.1 การแจ้งเตือนปัจจุบัน

| ช่องทาง | สถานะ | รายละเอียด |
|---------|--------|-----------|
| Telegram daily summary | ✅ ทำงาน | `ai_trends_daily_summary_thai.py` ส่งสรุปรวมทุก topic ไปยัง chat_id `1043709932` |
| Email | ❌ ไม่มี | ยังไม่เคยส่งอีเมล์จาก ATS |
| Per-topic DM | ❌ ไม่มี | มีแค่สรุปรวมทุก topic ในข้อความเดียว |
| Download links | ⚠️ มีใน Telegram | มี GitHub links ใน Telegram summary แต่ยังไม่มีในอีเมล์ |

### 2.2 โครงสร้าง Daily Pipeline ปัจจุบัน

```
05:00–08:35 ICT  →  Research jobs รันทีละ topic (crontab)
08:55 ICT        →  run_daily_summary_cron.sh
                    ├── 1. upload_reports_to_github_fixed.py
                    ├── 2. generate_audio_report.py --all-enabled --per-video
                    ├── 3. upload_audio_to_github.py
                    └── 4. ai_trends_daily_summary_thai.py  ← ส่ง Telegram
```

### 2.3 ทรัพยากรที่มีอยู่แล้ว

#### Email Infrastructure
| ทรัพยากร | รายละเอียด |
|----------|-----------|
| **Brevo SMTP** | `smtp-relay.brevo.com:587` — มี username/password ใน `~/.credentials.env` |
| **Python smtplib** | ใช้ได้กับ `/usr/bin/python3` (3.13) |
| **Python email.mime** | สร้าง HTML + multipart email ได้ |
| **jinja2** | มีในระบบ — ใช้ทำ email template ได้ |
| **Listmonk** | มี credentials แต่ service ไม่ทำงาน (403) — อาจเป็นตัวเลือกอนาคต |

#### Telegram Infrastructure
| ทรัพยากร | รายละเอียด |
|----------|-----------|
| **Bot Token** | มีใน `~/.claude/channels/telegram/.env` |
| **Chat ID** | `1043709932` (พี่ Mandy) |
| **Bot API** | ใช้ `requests.post()` → `sendMessage` พร้อม HTML parse mode |

#### Report & Asset Files
| ประเภท | Path | ตัวอย่าง |
|--------|------|---------|
| Markdown report | `ai_trends_reports/reports/{topic}/{date}.md` | `reports/NATEHERK/2026-05-27.md` |
| Voice WAV | `ai_trends_reports/audio/{topic}/{date}*.wav` | `audio/NATEHERK/2026-05-27-v1.wav` |
| Asset JSON | `ai_trends_reports/assets/{topic}/{date}.json` | |
| Audio script | `ai_trends_reports/audio_scripts/{topic}/{date}-v1.md` | |
| Social | `ai_trends_reports/social/{topic}/{date}.json` | |

#### GitHub Output Repo Links
| ประเภท | URL Pattern |
|--------|------------|
| Report MD | `https://github.com/MandhiraT/ai-trends-research/blob/master/reports/{topic}/{date}.md` |
| Voice WAV | `https://github.com/MandhiraT/ai-trends-research/tree/master/voice/{topic}/` |
| Raw MD download | `https://raw.githubusercontent.com/MandhiraT/ai-trends-research/master/reports/{topic}/{date}.md` |
| Raw WAV download | `https://raw.githubusercontent.com/MandhiraT/ai-trends-research/master/voice/{topic}/{file}.wav` |

### 2.4 Topic ทั้งหมด (24 topics)

```
AI Agents, Claude Code, AI Viral Niche, NATEHERK, Joanna Wiebe,
Jacksons AI, Make Money Matt, Miss Luna Vega,
CC Obsidian, CC NotebookLM, CC Design, CC Skills,
CC Remotion Video, CC Video, CC Seedance, CC Higgsfield,
CC Shopify, CC Hyperframe,
Finance — Money Coach, Finance — Money Buffalo, Finance — A-Academy,
Finance — Financial Diet, Finance — Humphrey Yang, Boom BigNose
```

---

## 3. การวิเคราะห์ทางเลือก (Options Analysis)

### 3.1 Email Sending Approach

| ทางเลือก | ข้อดี | ข้อเสีย | ความเหมาะสม |
|----------|-------|---------|-------------|
| **A. Brevo SMTP + smtplib** | มี account แล้ว, ส่งได้ทันที, ฟรี tier 300 email/วัน | ต้องจัดการ template เอง | ⭐⭐⭐ **แนะนำ** |
| B. Brevo API (REST) | มี template engine, analytics | ต้องเขียน API integration, ซับซ้อนกว่า | ⭐⭐ |
| C. Listmonk | mailing list management, subscriber self-service | service ไม่ทำงาน ต้อง setup Docker, overkill สำหรับ notification | ⭐ |
| D. SendGrid/SES | enterprise grade | ต้องสมัครใหม่, เพิ่ม dependency | ⭐ |

### 3.2 Notification Content Strategy

| ทางเลือก | รายละเอียด |
|----------|-----------|
| **A. Per-topic email** | ส่ง 1 email = 1 topic (เมื่อมี content ใหม่) → ละเอียด แต่อาจหลายเมล์ |
| **B. Digest email** | ส่ง 1 email รวมทุก topic → กระชับ แต่ยาว |
| **C. Both (configurable)** | เลือก per-topic หรือ digest ตาม config → **ยืดหยุ่นที่สุด** ⭐ |

### 3.3 Per-topic Routing Data Store

| ทางเลือก | ข้อดี | ข้อเสีย |
|----------|-------|---------|
| **A. JSON config file** | ง่าย อ่าน/เขียนง่าย ใช้ได้ทั้ง script + dashboard | ต้อง manual edit หรือสร้าง UI |
| B. SQLite table | query ยืดหยุ่น | เพิ่ม complexity ไม่จำเป็น |
| C. Dashboard UI only | user-friendly ที่สุด | ต้องรอ dashboard implement |

**แนะนำ:** เริ่มจาก JSON config → ตามด้วย Dashboard UI ใน phase หน้า

### 3.4 Telegram DM Per-topic

| ทางเลือก | รายละเอียด |
|----------|-----------|
| **A. ส่งแยกกลุ่ม chat** | ส่ง topic summary ไป chat_id ต่างคน (Bot API sendMessage) |
| B. ส่ง channel post | ส่งเป็น channel message → เห็นเฉพาะสมาชิก |
| C. ใช้ Hermes cron job | ใช้ Hermes `send_message` API → ต้อง agent ทำงาน |

**แนะนำ:** A — ใช้ Bot API `sendMessage` โดยตรง (เหมือนที่ทำอยู่แล้ว) แต่เพิ่ม per-topic routing

---

## 4. Constraints & Considerations

### 4.1 ข้อจำกัด

| เรื่อง | รายละเอียด |
|--------|-----------|
| **Brevo free tier** | 300 emails/วัน — เพียงพอ (24 topics × 1 email = 24/วัน สูงสุด) |
| **Telegram rate limit** | Bot API ส่งได้ ~30 msg/sec — ไม่มีปัญหา |
| **Email size** | ไม่ควรแนบ .wav โดยตรง (ไฟล์ใหญ่ 10-30MB) → ใช้ download link |
| **GitHub raw links** | Private repo จะใช้ raw link ไม่ได้ → ต้องใช้ public repo URL หรือ generate temporary link |
| **Spam** | ต้องตั้ง sender name/subject ชัดเจน ไม่ให้ติด spam filter |

### 4.2 GitHub Repo Visibility

```
https://github.com/MandhiraT/ai-trends-research → private repo (2026-05-27)
→ raw.githubusercontent.com links ไม่สามารถใช้ได้โดยไม่ login GitHub
→ ต้องใช้ dashboard download endpoint แทน (ดู section 4.4)
```

### 4.4 ตัวเลือก Download สำหรับ Private Repo

> **สถานะ:** วิเคราะห์แล้ว, ใช้ Option 3 (Dashboard + Cloudflare Tunnel)  
> **วันที่อัปเดต:** 2026-05-27

เมื่อ repo เป็น private, raw.githubusercontent.com links จะ 403 สำหรับ user ที่ไม่มี access
ต้องเลือก solution ที่ external user (ไม่มี GitHub account) สามารถ download ได้

#### Option 1: ส่งไฟล์แนบโดยตรงใน Telegram Bot
| | |
|---|---|
| **วิธีการ** | ใช้ Telegram Bot API `sendDocument` แนบไฟล์โดยตรงใน notification message |
| **ข้อดี** | ไม่ต้องใช้ URL, ทำงานได้ทันที, download ง่ายที่สุดสำหรับ Telegram user |
| **ข้อเสีย** | ใช้ได้แค่ Telegram เท่านั้น — email ยังต้องใช้ link, WAV ใหญ่ (10-30MB) อาจช้า |
| **เหมาะสม** | ถ้า recipient ใช้ Telegram เป็นหลัก |

#### Option 2: GitHub API Pre-signed Download URL
| | |
|---|---|
| **วิธีการ** | ATS server ใช้ GITHUB_TOKEN เรียก GitHub Contents API → ได้ download_url ชั่วคราว |
| **ข้อดี** | ทำงานได้ทั้ง private repo + ส่งได้ทั้ง email และ Telegram |
| **ข้อเสีย** | URL มี token embed อยู่ (security risk ถ้าส่งต่อ), URL อาจหมดอายุ, ต้องจัดการ token scope |
| **เหมาะสม** | ถ้าต้องการ private GitHub + ไม่มี server |

#### Option 3: ATS Dashboard + Cloudflare Tunnel ⭐ แนะนำ
| | |
|---|---|
| **วิธีการ** | เพิ่ม `/download/report` endpoint ใน dashboard → เปิด external access ผ่าน Cloudflare Tunnel |
| **URL** | `https://ai-trends.thequietself.com/download/report?topic=X&date=Y` |
| **ข้อดี** | ไม่ expose token, URL คงที่, ทำงานได้ทั้ง email + Telegram, ไม่ขึ้นกับ GitHub visibility |
| **ข้อเสีย** | Dashboard + Tunnel ต้อง active ตลอด (ลดได้ด้วย systemd service) |
| **สถานะ** | Cloudflare Tunnel configured: `ai-trends.thequietself.com → localhost:8092` ✅ |
| **เหมาะสม** | **ทางเลือกที่ดีที่สุดสำหรับระยะยาว** |

### 4.3 ประเด็นด้านความปลอดภัย

| เรื่อง | แนวทาง |
|--------|--------|
| SMTP credentials | เก็บใน `~/.credentials.env` (เหมือนเดิม) |
| Telegram bot token | เก็บใน `~/.claude/channels/telegram/.env` (เหมือนเดิม) |
| Email addresses | เก็บใน notification config JSON ภายในเครื่อง |
| ไม่ส่ง secret | อีเมล์จะมีแค่ summary + download links ไม่มี API keys |

---

## 5. สรุปแนวทางที่แนะนำ

| องค์ประกอบ | ทางเลือกที่แนะนำ | เหตุผล |
|------------|-------------------|--------|
| Email transport | Brevo SMTP + `smtplib` | มีอยู่แล้ว ส่งได้ทันที |
| Email format | HTML + plain text (multipart) | สวยงาม + fallback |
| Email template | Jinja2 HTML template | ยืดหยุ่น แก้ไขง่าย |
| Telegram | Bot API `sendMessage` (เหมือนเดิม) | ไม่ต้องเพิ่ม dependency |
| Config store | JSON file (`config/notification_routing.json`) | ง่าย อ่านได้ทั้ง script + dashboard |
| Content mode | Per-topic email + digest option | ยืดหยุ่นที่สุด |
| Download links | Dashboard URLs via Cloudflare Tunnel | private repo safe, ไม่ขึ้น GitHub visibility |
| Integration point | เพิ่มเข้าใน `run_daily_summary_cron.sh` | หลัง upload + audio generation |

---

## 6. อนาคต: ระบบ User Subscription (ยังไม่ implement)

> **สถานะ:** วิเคราะห์เบื้องต้น — ยังไม่ implement  
> **วันที่:** 2026-05-27  
> **ขอบเขต:** Analysis เท่านั้น ไม่มี code ใน section นี้

### 6.1 Vision

ในอนาคต ต้องการเปิดให้ external user สามารถ **subscribe** รับรายงาน ATS ได้ด้วยตัวเอง โดยเลือก topic ที่สนใจ และกำหนดช่องทางรับ (email / Telegram) ได้อิสระ

### 6.2 สิ่งที่ User จะทำได้

| ความสามารถ | รายละเอียด |
|-----------|-----------|
| **เลือก topic** | User เลือกได้ว่าจะรับ AI Agents, NATEHERK, Finance ฯลฯ (multi-select) |
| **รับ summary** | ได้รับ Markdown summary รายงานแต่ละ topic ที่เลือก |
| **รับ audio** | ได้รับลิ้งค์ download .wav audio สำหรับ topic ที่มี audio enabled |
| **เลือกช่องทาง** | Email, Telegram DM, หรือทั้งสอง |
| **จัดการ subscription** | แก้ไข/ยกเลิก topic ที่ subscribe ได้ผ่าน self-service portal |

### 6.3 สิ่งที่ต้องสร้างเพิ่ม (ภาพรวม)

| Component | รายละเอียด |
|-----------|-----------|
| **Subscriber registry** | เก็บข้อมูล subscriber (email/Telegram ID + topics เลือก) |
| **Subscription UI** | หน้าสมัคร + จัดการ topic (อาจเป็น public page ที่ dashboard) |
| **Routing integration** | `notify_topic.py` อ่าน subscriber list + ส่งให้ตามที่เลือก |
| **Authentication** | Verify email หรือ Telegram bot start command |
| **Unsubscribe flow** | ลิ้งค์ยกเลิก subscribe ในทุก notification |

### 6.4 ข้อพิจารณา

- **Privacy**: เก็บข้อมูล email/Telegram ID ต้องมีนโยบายชัดเจน
- **Scale**: ถ้ามี subscriber มาก อาจต้องพิจารณา queue แทนส่งตรง
- **Content access**: ถ้า repo private, subscriber ต้องใช้ dashboard URL (ดู Option 3 section 4.4)
- **Prerequisite**: ต้องมี dashboard + tunnel stable ก่อน (ทำแล้วใน Option 3)

---

## 7. ไฟล์ที่เกี่ยวข้อง

| ไฟล์ | บทบาท |
|------|--------|
| `scripts/ai_trends_daily_summary_thai.py` | สร้าง summary + ส่ง Telegram (จะ extend) |
| `scripts/run_daily_summary_cron.sh` | Orchestration (จะเพิ่ม notification step) |
| `config/research_jobs.json` | Topic/job definitions (อ้างอิง) |
| `config/audio_topics.json` | Audio config (อ้างอิง topic list) |
| `~/.credentials.env` | SMTP + Telegram credentials |
| `dashboard/app.py` | Dashboard UI (จะเพิ่ม notification config tab) |

---

| `scripts/notify_topic.py` | สร้าง + ส่ง per-topic notification (implemented) |

---

*เอกสารต่อไป: `docs/NOTIFICATION-SYSTEM-DESIGN.md` — รายละเอียดการออกแบบและแผน implementation*
