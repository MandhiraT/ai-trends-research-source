#!/usr/bin/env python3
"""
generate_audio_report.py — Generate spoken-word audio from daily AI trends reports.

Two-step pipeline:
  1. Condense full MD report → ~400-word Thai audio script (Gemini 2.5 Flash text)
  2. Convert script → WAV audio (Gemini 2.5 Flash TTS)

Output: ai_trends_reports/audio/{topic}/YYYY-MM-DD.wav

Usage:
    python3 scripts/generate_audio_report.py --topic ai_agents
    python3 scripts/generate_audio_report.py --all-enabled --date 2026-05-07
    python3 scripts/generate_audio_report.py --topic ai_agents --dry-run
"""

import sys
import os
import json
import wave
import base64
import struct
import argparse
from datetime import date as _date

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

AUDIO_CONFIG_FILE    = os.path.join(PROJECT_ROOT, 'config', 'audio_topics.json')
AUDIO_PROMPT_FILE    = os.path.join(PROMPTS_DIR, 'audio_script_prompt.txt')
TTS_MODEL            = 'gemini-2.5-flash-preview-tts'
CONDENSE_MODEL       = 'gemini-2.5-flash'
DEFAULT_VOICE        = 'Aoede'
SAMPLE_RATE          = 24000   # Hz — Gemini TTS native PCM rate
SAMPLE_WIDTH         = 2       # bytes (16-bit)
CHANNELS             = 1       # mono


def _load_audio_config() -> dict:
    if os.path.exists(AUDIO_CONFIG_FILE):
        with open(AUDIO_CONFIG_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {'enabled_topics': [], 'voice': DEFAULT_VOICE}


def _find_report(topic_key: str, date_str: str) -> str | None:
    """Return path to {topic_key}/YYYY-MM-DD.md, or None if not found."""
    # Direct topic folder
    direct = os.path.join(REPORTS_DIR, 'reports', topic_key, f'{date_str}.md')
    if os.path.exists(direct):
        return direct
    # Claude Code subtopics live under reports/claude_code/{topic_key}/
    nested = os.path.join(REPORTS_DIR, 'reports', 'claude_code', topic_key, f'{date_str}.md')
    if os.path.exists(nested):
        return nested
    return None


def _condense_to_script(report_text: str, topic_name: str, date_str: str) -> str:
    """Use Gemini text generation to condense report to spoken Thai audio script."""
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
    full_prompt = prompt + report_text[:15000]  # guard against very large reports

    project  = os.environ.get('VERTEX_PROJECT_ID', '')
    location = os.environ.get('VERTEX_LOCATION', 'us-central1')
    if not project:
        raise EnvironmentError('VERTEX_PROJECT_ID not set')

    from google import genai as _genai
    client = _genai.Client(vertexai=True, project=project, location=location)
    response = client.models.generate_content(
        model=CONDENSE_MODEL,
        contents=full_prompt,
        config=_genai.types.GenerateContentConfig(max_output_tokens=2048, temperature=0.4),
    )
    return response.text.strip()


def _text_to_wav(text: str, output_path: str, voice: str = DEFAULT_VOICE) -> None:
    """Call Gemini TTS and save audio as WAV."""
    project  = os.environ.get('VERTEX_PROJECT_ID', '')
    location = os.environ.get('VERTEX_LOCATION', 'us-central1')
    if not project:
        raise EnvironmentError('VERTEX_PROJECT_ID not set')

    from google import genai as _genai
    from google.genai.types import (
        GenerateContentConfig,
        SpeechConfig,
        VoiceConfig,
        PrebuiltVoiceConfig,
    )

    client = _genai.Client(vertexai=True, project=project, location=location)
    response = client.models.generate_content(
        model=TTS_MODEL,
        contents=text,
        config=GenerateContentConfig(
            response_modalities=['AUDIO'],
            speech_config=SpeechConfig(
                voice_config=VoiceConfig(
                    prebuilt_voice_config=PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )

    audio_b64 = response.candidates[0].content.parts[0].inline_data.data
    audio_bytes = base64.b64decode(audio_b64)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with wave.open(output_path, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_bytes)


def generate_for_topic(topic_key: str, date_str: str, voice: str = DEFAULT_VOICE,
                       dry_run: bool = False, force: bool = False) -> bool:
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

    topic_display = topic_key.replace('_', ' ').title()
    print(f'  [audio] 📝 Condensing report: {topic_key}/{date_str} ({len(report_text)} chars)...')

    try:
        script = _condense_to_script(report_text, topic_display, date_str)
        print(f'  [audio] ✅ Audio script ready ({len(script)} chars, ~{len(script.split())//2} words)')
    except Exception as e:
        print(f'  [audio] ❌ Condense failed: {e}')
        return False

    if dry_run:
        print(f'  [audio] 🔍 DRY RUN — script preview:')
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
    parser.add_argument('--dry-run',     action='store_true',
                        help='Condense report only — no TTS, no file written')
    parser.add_argument('--force',       action='store_true',
                        help='Regenerate even if WAV already exists')
    args = parser.parse_args()

    config = _load_audio_config()
    voice  = args.voice or config.get('voice', DEFAULT_VOICE)

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

    print(f'[audio] Generating audio reports for {len(topics)} topic(s), date={args.date}, voice={voice}')
    success, failed = 0, 0
    for topic in topics:
        ok = generate_for_topic(topic, args.date, voice=voice,
                                dry_run=args.dry_run, force=args.force)
        if ok:
            success += 1
        else:
            failed += 1

    print(f'\n[audio] Done — {success} succeeded, {failed} failed')
    if failed:
        sys.exit(2)


if __name__ == '__main__':
    main()
