# Audio TTS Feature — Implementation Design

> Branch: `feature/audio-tts-reports`  
> Status: Ready to implement  
> Model: Vertex AI `gemini-2.5-flash-preview-tts`

---

## Overview

Generate a spoken-word audio summary of each day's AI trends research report for selected topics/channels. Audio is generated using **Vertex AI Gemini 2.5 Flash TTS** — the same Google Cloud project already used by `summarize_local.py`.

**User controls which topics get audio via `config/audio_topics.json` — initially empty.**

---

## How It Works (Two-Step Pipeline)

Full detailed reports are 2000–3000+ words — too long for direct TTS. The pipeline condenses first, then speaks:

```
ai_trends_reports/reports/{topic}/YYYY-MM-DD.md  (full report, 2000-3000 words)
           │
           │  Step 1: Gemini 2.5 Flash (text)
           │  Condense to ~400-word spoken Thai script
           ▼
       audio_script.txt  (~400 words, natural Thai speech)
           │
           │  Step 2: Gemini 2.5 Flash TTS (audio)
           │  TTS → WAV PCM 24kHz
           ▼
ai_trends_reports/audio/{topic}/YYYY-MM-DD.wav
```

**2-3 minutes listening time** per topic report.

---

## New Files

| File | Purpose |
|------|---------|
| `scripts/generate_audio_report.py` | Main TTS script — condense + TTS per topic |
| `config/audio_topics.json` | Which topics have audio enabled (user configures) |
| `prompts/audio_script_prompt.txt` | Prompt for condensing report to spoken script |
| `docs/AUDIO_TTS_FEATURE.md` | This document |

## Modified Files

| File | Change |
|------|--------|
| `config/paths.py` | Add `AUDIO_DIR` constant |
| `scripts/run_daily_summary_cron.sh` | Add audio generation step after daily summary |

---

## Audio Output Storage

```
ai_trends_reports/
└── audio/
    ├── ai_agents/
    │   ├── 2026-05-07.wav
    │   └── 2026-05-08.wav
    ├── NATEHERK/
    │   └── 2026-05-07.wav
    └── {topic_key}/
        └── YYYY-MM-DD.wav
```

WAV format: PCM 16-bit, 24kHz mono (Gemini TTS native format).

---

## Topic Config (`config/audio_topics.json`)

```json
{
  "enabled_topics": [
    "ai_agents",
    "NATEHERK"
  ],
  "voice": "Aoede",
  "language_hint": "th-TH"
}
```

**`enabled_topics`** — list of topic folder names from `ai_trends_reports/reports/`.  
**`voice`** — Gemini TTS voice name (see Voice Options below).  
**`language_hint`** — language code for TTS pronunciation guidance.

> File starts empty: `{"enabled_topics": [], "voice": "Aoede", "language_hint": "th-TH"}`  
> User adds topic keys to enable audio for those topics.

### Voice Options (Gemini 2.5 Flash TTS)

| Voice | Character | Good for |
|-------|-----------|----------|
| `Aoede` | Warm, clear female | Neutral reports |
| `Kore` | Firm, confident female | News-style delivery |
| `Charon` | Deep, calm male | Formal tone |
| `Fenrir` | Energetic male | Engaging summaries |
| `Puck` | Light, friendly | Conversational |

---

## Condensing Prompt (`prompts/audio_script_prompt.txt`)

```
คุณคือนักเขียนบทพอดแคสต์ภาษาไทย

จงสรุปรายงาน AI Trends Research ด้านล่างให้เป็นบทพูด (audio script) ภาษาไทย ความยาวประมาณ 400 คำ (ฟังแล้วใช้เวลาประมาณ 2-3 นาที)

ข้อกำหนด:
- เขียนเป็นภาษาพูดที่เป็นธรรมชาติ ไม่เป็นทางการเกินไป
- เริ่มต้นด้วย: "สวัสดีค่ะ วันนี้มาสรุปรายงาน {TOPIC_NAME} ประจำวันที่ {DATE} ค่ะ"
- ครอบคลุมประเด็นสำคัญที่สุดจากแต่ละวิดีโอในรายงาน
- ปิดท้ายด้วย: "สำหรับรายละเอียดเพิ่มเติม ดูรายงานฉบับเต็มได้ที่ GitHub ค่ะ ขอบคุณที่ฟังนะคะ"
- ไม่มี markdown ไม่มี bullet points — เป็น plain text ที่อ่านออกเสียงได้เลย
- ไม่มีอักขระพิเศษที่ฟังดูแปลก เช่น ** [] ## ---
- ใช้ "ค่ะ" ลงท้ายประโยคหลักเป็นส่วนใหญ่

ส่งคืนเฉพาะบทพูด ไม่ต้องอธิบาย ไม่ต้องใส่หัวข้อ
```

---

## Vertex AI TTS API Integration

Uses the **same `google-genai` client** already used in `summarize_local.py` (Vertex AI ADC — no new credentials needed).

```python
from google import genai
from google.genai.types import (
    GenerateContentConfig,
    SpeechConfig,
    VoiceConfig,
    PrebuiltVoiceConfig,
)

project  = os.environ.get('VERTEX_PROJECT_ID')
location = os.environ.get('VERTEX_LOCATION', 'us-central1')

client = genai.Client(vertexai=True, project=project, location=location)

# Step 1: Condense report to audio script (text model)
script_response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=condense_prompt + report_text,
    config=GenerateContentConfig(max_output_tokens=2048, temperature=0.3),
)
audio_script = script_response.text.strip()

# Step 2: TTS from audio script
tts_response = client.models.generate_content(
    model='gemini-2.5-flash-preview-tts',
    contents=audio_script,
    config=GenerateContentConfig(
        response_modalities=['AUDIO'],
        speech_config=SpeechConfig(
            voice_config=VoiceConfig(
                prebuilt_voice_config=PrebuiltVoiceConfig(voice_name='Aoede')
            )
        ),
    ),
)

# Decode and save
import base64, struct, wave
audio_b64 = tts_response.candidates[0].content.parts[0].inline_data.data
audio_bytes = base64.b64decode(audio_b64)

# Save as WAV (PCM 16-bit 24kHz mono)
with wave.open(output_path, 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(24000)
    wf.writeframes(audio_bytes)
```

---

## Script CLI (`scripts/generate_audio_report.py`)

```bash
# Generate audio for a specific topic and date
python3 scripts/generate_audio_report.py \
    --topic ai_agents \
    --date 2026-05-07

# Generate for all enabled topics (reads config/audio_topics.json)
python3 scripts/generate_audio_report.py \
    --date 2026-05-07 \
    --all-enabled

# Use today's date automatically
python3 scripts/generate_audio_report.py --all-enabled

# Override voice
python3 scripts/generate_audio_report.py --topic NATEHERK --voice Kore

# Dry run (condense only, no TTS — fast check)
python3 scripts/generate_audio_report.py --topic ai_agents --dry-run
```

**Exit codes:** 0 = success, 1 = report not found, 2 = API error.

---

## Cron Integration

Add to `scripts/run_daily_summary_cron.sh` after the daily summary step:

```bash
# Generate audio reports for enabled topics (reads config/audio_topics.json)
echo "[$(date)] Running audio report generation..."
python3 "$SCRIPT_DIR/generate_audio_report.py" --all-enabled --date "$(date +%Y-%m-%d)"
```

Audio runs **after** reports are generated (already in cron order: reports → summary → audio).

---

## Error Handling

| Scenario | Behavior |
|----------|---------|
| Report MD not found for date | Skip with warning, exit 1 |
| Report too short (< 100 chars) | Skip with warning |
| TTS API error | Log error, skip topic (don't fail entire run) |
| WAV already exists | Skip (idempotent — won't regenerate) |
| `enabled_topics` empty | Exit 0 silently |
| `VERTEX_PROJECT_ID` not set | Exit 2 with clear error message |

---

## Implementation Steps (in order)

1. **`config/paths.py`** — add `AUDIO_DIR = os.path.join(REPORTS_DIR, 'audio')` + `os.makedirs(AUDIO_DIR)`
2. **`config/audio_topics.json`** — create with empty `enabled_topics`
3. **`prompts/audio_script_prompt.txt`** — create condensing prompt
4. **`scripts/generate_audio_report.py`** — full script (see below)
5. **`scripts/run_daily_summary_cron.sh`** — add audio generation call
6. Test: `python3 scripts/generate_audio_report.py --topic ai_agents --dry-run`
7. Enable first topic: add `"ai_agents"` to `config/audio_topics.json`
8. Full test: `python3 scripts/generate_audio_report.py --topic ai_agents`

---

## Dependencies

No new pip packages needed beyond what already exists:

| Package | Already installed? | Used for |
|---------|-------------------|---------|
| `google-genai` | ✅ (used by summarize_local.py) | Vertex AI client |
| `wave` | ✅ (Python stdlib) | WAV file writing |
| `base64` | ✅ (Python stdlib) | Decode TTS audio bytes |

---

## Notes

- **WAV file size:** ~3MB per 3-minute audio at 24kHz PCM16. Acceptable for local storage.
- **GitHub upload:** Not included in v1 — audio stays local. Can add `--upload` flag later.
- **Telegram delivery:** Can add a Telegram step to send the WAV file after generation — scope for v2.
- **Voice language:** Gemini TTS is multilingual. `Aoede` voice handles Thai naturally without explicit language_hint in API call, but the `language_hint` field in config is kept for future use.
- **Re-run safety:** Script checks for existing WAV before generating — safe to re-run.
