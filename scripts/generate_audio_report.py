#!/usr/bin/env python3
"""
generate_audio_report.py — Generate spoken-word audio from daily AI trends reports.

Two-step pipeline:
  1. Condense full MD report → ~400-word Thai audio script (Gemini 2.5 Flash text)
  2. Convert script → WAV audio (Gemini 2.5 Flash TTS)

Per-video mode (--per-video):
  - Splits MD on '## Video N:' headers
  - Condenses + TTS each video section separately (~150 words each)
  - Concatenates all WAV segments into one output file
  - Produces more complete coverage vs. whole-file 400-word summary

Output: ai_trends_reports/audio/{topic}/YYYY-MM-DD.wav

Usage:
    python3 scripts/generate_audio_report.py --topic ai_agents
    python3 scripts/generate_audio_report.py --topic NATEHERK --date 2026-05-07 --per-video
    python3 scripts/generate_audio_report.py --all-enabled --date 2026-05-07
    python3 scripts/generate_audio_report.py --topic ai_agents --dry-run
"""

import sys
import os
import re
import json
import argparse
import tempfile
import time
from datetime import date as _date

from voice_engine import (
    DEFAULT_VOICE,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    CHANNELS,
    concat_wavs,
    load_voice_profile,
    text_to_wav,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config'))
try:
    from paths import PROJECT_ROOT, REPORTS_DIR, AUDIO_DIR, PROMPTS_DIR, load_credentials
except ImportError:
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    REPORTS_DIR  = os.path.join(PROJECT_ROOT, 'ai_trends_reports')
    AUDIO_DIR    = os.path.join(PROJECT_ROOT, 'ai_trends_reports', 'audio')
    PROMPTS_DIR  = os.path.join(PROJECT_ROOT, 'prompts')
    def load_credentials(): pass

load_credentials()

AUDIO_CONFIG_FILE = os.path.join(PROJECT_ROOT, 'config', 'audio_topics.json')
AUDIO_PROMPT_FILE = os.path.join(PROMPTS_DIR, 'audio_script_prompt.txt')
SCRIPTS_DIR       = os.path.join(PROJECT_ROOT, 'ai_trends_reports', 'audio_scripts')
TTS_MODEL         = 'gemini-2.5-flash-preview-tts'
CONDENSE_MODEL    = 'gemini-2.5-flash'
DEFAULT_VOICE     = 'Aoede'
SAMPLE_RATE       = 24000   # Hz — Gemini TTS native PCM rate
SAMPLE_WIDTH      = 2       # bytes (16-bit)
CHANNELS          = 1       # mono


def _load_audio_config() -> dict:
    if os.path.exists(AUDIO_CONFIG_FILE):
        with open(AUDIO_CONFIG_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {'enabled_topics': [], 'voice': DEFAULT_VOICE}


def _find_report(topic_key: str, date_str: str) -> str | None:
    """Return path to {topic_key}/YYYY-MM-DD.md, or None if not found."""
    direct = os.path.join(REPORTS_DIR, 'reports', topic_key, f'{date_str}.md')
    if os.path.exists(direct):
        return direct
    # Claude Code subtopics live under reports/claude_code/{topic_key}/
    nested = os.path.join(REPORTS_DIR, 'reports', 'claude_code', topic_key, f'{date_str}.md')
    if os.path.exists(nested):
        return nested
    return None


def _split_into_video_sections(report_text: str) -> list[tuple[str, str]]:
    """
    Split MD report into (video_title, section_text) tuples on '## Video N:' headers.
    Falls back to [(None, full_text)] if no video headers found.
    """
    pattern = re.compile(r'^## Video \d+:\s*(.+)$', re.MULTILINE)
    matches = list(pattern.finditer(report_text))
    if not matches:
        return [(None, report_text)]

    sections = []
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.start()
        end   = matches[i + 1].start() if i + 1 < len(matches) else len(report_text)
        sections.append((title, report_text[start:end]))
    return sections


def _condense_to_script(report_text: str, topic_name: str, date_str: str) -> str:
    """Condense full report → ~400-word Thai audio script (whole-file mode)."""
    prompt_template = ''
    if os.path.exists(AUDIO_PROMPT_FILE):
        with open(AUDIO_PROMPT_FILE, encoding='utf-8') as f:
            prompt_template = f.read()
    else:
        prompt_template = (
            "สรุปรายงานต่อไปนี้เป็นบทพูด (audio script) ภาษาไทย ความยาวประมาณ 400 คำ "
            "เริ่มด้วย 'สวัสดีค่ะ วันนี้มาสรุปรายงาน {TOPIC_NAME} ประจำวันที่ {DATE} ค่ะ' "
            "ปิดด้วย 'ดูรายงานฉบับเต็มได้ที่ GitHub ค่ะ ขอบคุณที่ฟังนะคะ' "
            "ส่งคืนเฉพาะบทพูด plain text ไม่มี markdown\n\n---\nรายงาน:\n"
        )

    prompt = prompt_template.replace('{TOPIC_NAME}', topic_name).replace('{DATE}', date_str)
    full_prompt = prompt + report_text[:15000]

    return _call_condense_model(full_prompt)


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


def _condense_video_section(section_text: str, video_title: str, date_str: str,
                            is_first: bool, is_last: bool) -> str:
    """Condense one video section → ~350-word Thai spoken segment."""
    if is_first:
        opening = f"สวัสดีค่ะ วันนี้วันที่ {date_str} มาฟังสรุปวิดีโอเด่นๆ กันค่ะ เริ่มที่วิดีโอแรก เรื่อง {video_title} ค่ะ"
    else:
        opening = f"วิดีโอถัดมา เรื่อง {video_title} ค่ะ"

    closing = "สำหรับรายละเอียดเพิ่มเติม ดูรายงานฉบับเต็มได้ที่ GitHub ค่ะ ขอบคุณที่ฟังนะคะ" if is_last else ""

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
    if closing:
        prompt += f"8. ปิดท้ายด้วย: {closing}\n"
    prompt += "\nส่งคืนเฉพาะบทพูด ไม่ต้องอธิบาย ไม่ต้องใส่หัวข้อ ไม่ต้องบอกจำนวนคำ\n\n---\nเนื้อหาวิดีโอ:\n"
    prompt += _clean_section_text(section_text)[:15000]

    return _call_condense_model(prompt)


def _call_condense_model(prompt: str) -> str:
    """Call Gemini text model to condense content. Retries on 429 with backoff."""
    project  = os.environ.get('VERTEX_PROJECT_ID', '')
    location = os.environ.get('VERTEX_LOCATION', 'us-central1')
    if not project:
        raise EnvironmentError('VERTEX_PROJECT_ID not set')

    from google import genai as _genai
    client = _genai.Client(vertexai=True, project=project, location=location)

    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=CONDENSE_MODEL,
                contents=prompt,
                config=_genai.types.GenerateContentConfig(max_output_tokens=4096, temperature=0.7),
            )
            return response.text.strip()
        except Exception as e:
            if '429' in str(e) and attempt < 3:
                wait = 30 * (2 ** attempt)  # 30s, 60s, 120s
                print(f'  [audio]     ⏳ Rate limited — waiting {wait}s before retry {attempt+1}/3...')
                time.sleep(wait)
            else:
                raise


def _text_to_wav(text: str, output_path: str, voice: str = DEFAULT_VOICE) -> None:
    """Compatibility wrapper: use unified ATS voice engine for Gemini TTS."""
    text_to_wav(text, output_path, voice=voice)


def _concat_wavs(wav_paths: list[str], output_path: str) -> None:
    """Compatibility wrapper: use unified ATS voice engine WAV concat."""
    concat_wavs(wav_paths, output_path)


def generate_for_topic(topic_key: str, date_str: str, voice: str = DEFAULT_VOICE,
                       dry_run: bool = False, force: bool = False,
                       per_video: bool = False) -> bool:
    """
    Run the full condense → TTS pipeline for one topic.
    Returns True on success, False on skip/error.
    """
    output_path = os.path.join(AUDIO_DIR, topic_key, f'{date_str}.wav')

    if os.path.exists(output_path) and not force:
        print(f'  [audio] ⏭️  {topic_key}/{date_str}.wav already exists — skipping')
        return True

    report_path = _find_report(topic_key, date_str)
    if not report_path:
        print(f'  [audio] ⚠️  Report not found: {topic_key}/{date_str}.md')
        return False

    with open(report_path, encoding='utf-8') as f:
        report_text = f.read()

    if len(report_text.strip()) < 100:
        print(f'  [audio] ⚠️  Report too short, skipping {topic_key}/{date_str}')
        return False

    if per_video:
        return _generate_per_video(topic_key, date_str, report_text, output_path,
                                   voice=voice, dry_run=dry_run)

    # ── Whole-file mode ────────────────────────────────────────────────────────
    topic_display = topic_key.replace('_', ' ').title()
    print(f'  [audio] 📝 Condensing report: {topic_key}/{date_str} ({len(report_text)} chars)...')

    try:
        script = _condense_to_script(report_text, topic_display, date_str)
        print(f'  [audio] ✅ Script ready ({len(script)} chars, ~{len(script.split())//2} words)')
    except Exception as e:
        print(f'  [audio] ❌ Condense failed: {e}')
        return False

    if dry_run:
        print('  [audio] 🔍 DRY RUN — script preview:')
        print('  ' + script[:300].replace('\n', '\n  ') + '...')
        return True

    print(f'  [audio] 🎙️  Generating TTS audio (voice={voice})...')
    try:
        _text_to_wav(script, output_path, voice=voice)
        size_kb = os.path.getsize(output_path) // 1024
        print(f'  [audio] ✅ Saved: {output_path} ({size_kb} KB)')
        return True
    except Exception as e:
        print(f'  [audio] ❌ TTS failed: {e}')
        return False


def _save_combined_script(topic_key: str, date_str: str,
                          scripts: list[tuple[str, str]]) -> str | None:
    """Save all per-video scripts as one combined ATS script file. Returns path or None."""
    scripts_dir = os.path.join(SCRIPTS_DIR, topic_key)
    os.makedirs(scripts_dir, exist_ok=True)
    script_path = os.path.join(scripts_dir, f'{date_str}-v1.md')

    topic_display = topic_key.replace('_', ' ').title()
    header = (
        f"# Audio Script: {topic_display} — {date_str}\n"
        f"Date: {date_str}\n"
        f"Topic: {topic_display}\n"
        f"เวอร์ชัน: auto-generated\n\n"
        f"## Full Script\n\n"
    )
    body = "\n\n".join(script for _, script in scripts)

    try:
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(header + body + "\n")
        print(f'  [audio] 📄 Script saved: {script_path}')
        return script_path
    except Exception as e:
        print(f'  [audio] ⚠️  Script save failed: {e}')
        return None


def _generate_per_video(topic_key: str, date_str: str, report_text: str,
                        output_path: str, voice: str, dry_run: bool) -> bool:
    """Per-video mode: split → condense each section → TTS each → concatenate."""
    sections = _split_into_video_sections(report_text)
    print(f'  [audio] 📹 Per-video mode: {len(sections)} section(s) found')

    seg_paths = []
    all_scripts: list[tuple[str, str]] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, (title, text) in enumerate(sections):
            is_first = (i == 0)
            is_last  = (i == len(sections) - 1)
            label    = title or f'section_{i+1}'
            short    = label[:50]

            if i > 0:
                time.sleep(8)  # brief pause between sections to avoid quota bursts

            print(f'  [audio]   [{i+1}/{len(sections)}] 📝 Condensing: "{short}"...')
            try:
                script = _condense_video_section(text, label, date_str, is_first, is_last)
                # Retry once if output is too short — model sometimes under-generates
                if len(script) < 500:
                    print(f'  [audio]   [{i+1}/{len(sections)}] ⚠️  Script too short ({len(script)} chars) — retrying...')
                    time.sleep(10)
                    script2 = _condense_video_section(text, label, date_str, is_first, is_last)
                    if len(script2) > len(script):
                        script = script2
                print(f'  [audio]   [{i+1}/{len(sections)}] ✅ Script: {len(script)} chars')
                all_scripts.append((label, script))
            except Exception as e:
                print(f'  [audio]   [{i+1}/{len(sections)}] ❌ Condense failed: {e}')
                return False

            if dry_run:
                print(f'  [audio]   [{i+1}/{len(sections)}] 🔍 Preview:')
                print('  ' + script[:200].replace('\n', '\n  ') + '...')
                continue

            seg_path = os.path.join(tmpdir, f'seg_{i:02d}.wav')
            print(f'  [audio]   [{i+1}/{len(sections)}] 🎙️  TTS (voice={voice})...')
            try:
                _text_to_wav(script, seg_path, voice=voice)
                size_kb = os.path.getsize(seg_path) // 1024
                print(f'  [audio]   [{i+1}/{len(sections)}] ✅ Segment: {size_kb} KB')
                seg_paths.append(seg_path)
            except Exception as e:
                print(f'  [audio]   [{i+1}/{len(sections)}] ❌ TTS failed: {e}')
                return False

        if dry_run:
            return True

        if not seg_paths:
            print('  [audio] ❌ No segments generated')
            return False

        print(f'  [audio] 🔗 Concatenating {len(seg_paths)} segment(s)...')
        try:
            _concat_wavs(seg_paths, output_path)
            size_kb = os.path.getsize(output_path) // 1024
            print(f'  [audio] ✅ Saved: {output_path} ({size_kb} KB)')
        except Exception as e:
            print(f'  [audio] ❌ Concat failed: {e}')
            return False

    if all_scripts:
        _save_combined_script(topic_key, date_str, all_scripts)
    return True


def main():
    parser = argparse.ArgumentParser(description='Generate audio reports from AI Trends MD files')
    parser.add_argument('--topic',       type=str,  default=None,
                        help='Single topic key (folder name in ai_trends_reports/reports/)')
    parser.add_argument('--all-enabled', action='store_true',
                        help='Generate for all topics listed in config/audio_topics.json')
    parser.add_argument('--date',        type=str,  default=str(_date.today()),
                        help='Report date (YYYY-MM-DD). Default: today')
    parser.add_argument('--voice',       type=str,  default=None,
                        help='Gemini TTS voice name. Default: from config or Aoede')
    parser.add_argument('--per-video',   action='store_true',
                        help='Split report by video sections, condense + TTS each separately')
    parser.add_argument('--dry-run',     action='store_true',
                        help='Condense only — no TTS, no file written')
    parser.add_argument('--force',       action='store_true',
                        help='Regenerate even if WAV already exists')
    args = parser.parse_args()

    config = _load_audio_config()
    profile = load_voice_profile(config.get('default_voice_profile'), voice_override=config.get('voice'))
    voice  = args.voice or profile.get('voice', DEFAULT_VOICE)

    topics = []
    if args.topic:
        topics = [args.topic]
    elif args.all_enabled:
        topics = config.get('enabled_topics', [])
        if not topics:
            print('[audio] No topics enabled in config/audio_topics.json — nothing to do.')
            sys.exit(0)
    else:
        parser.print_help()
        sys.exit(1)

    mode = 'per-video' if args.per_video else 'whole-file'
    print(f'[audio] Generating audio for {len(topics)} topic(s), date={args.date}, voice={voice}, mode={mode}')
    success, failed = 0, 0
    for topic in topics:
        ok = generate_for_topic(topic, args.date, voice=voice,
                                dry_run=args.dry_run, force=args.force,
                                per_video=args.per_video)
        if ok:
            success += 1
        else:
            failed += 1

    print(f'\n[audio] Done — {success} succeeded, {failed} failed')
    if failed:
        sys.exit(2)


if __name__ == '__main__':
    main()
