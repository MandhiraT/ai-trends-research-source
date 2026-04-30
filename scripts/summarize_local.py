#!/usr/bin/env python3
"""
summarize_local.py — drop-in replacement for the `summarize` CLI.
Providers: vertex (Vertex AI ADC) → qwen → glm → gemini (AI Studio) → gemma

Usage (as library):
    from summarize_local import summarize_video
    result = summarize_video(video_url, prompt_file, language='th')

Usage (as CLI):
    python3 summarize_local.py <video_url> --youtube auto --language th --prompt-file ...
"""

import os
import sys
import json
import argparse
import subprocess
import requests
from typing import Optional

# Load credentials from master file
_CRED_FILE = os.environ.get('CREDENTIALS_FILE', os.path.expanduser('~/.credentials.env'))
if os.path.exists(_CRED_FILE):
    with open(_CRED_FILE) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _, _v = _line.partition('=')
                os.environ.setdefault(_k.strip(), _v.strip())


def _get_youtube_transcript(video_url: str) -> str:
    """Extract transcript from YouTube video using yt-dlp."""
    import re as _re
    try:
        subprocess.run(
            ['yt-dlp', '--skip-download', '--write-auto-sub',
             '--sub-lang', 'en', '--sub-format', 'vtt',
             '--output', '/tmp/yt_transcript', video_url],
            capture_output=True, text=True, timeout=60
        )
        for ext in ['.en.vtt', '.vtt']:
            path = f'/tmp/yt_transcript{ext}'
            if os.path.exists(path):
                with open(path, encoding='utf-8') as f:
                    seen, lines_clean = set(), []
                    for line in f:
                        line = line.strip()
                        if not line or '-->' in line:
                            continue
                        if any(line.startswith(p) for p in ('WEBVTT', 'NOTE', 'Kind:', 'Language:')):
                            continue
                        # Strip word-level timing tags: <00:00:01.520>, <c>, </c>
                        clean = _re.sub(r'<[^>]+>', '', line).strip()
                        if clean and clean not in seen:
                            seen.add(clean)
                            lines_clean.append(clean)
                return ' '.join(lines_clean)[:30000]
    except Exception:
        pass
    return ''


def _call_provider(provider: str, prompt: str, system_prompt: str = '') -> str:
    if provider == 'vertex':
        from google import genai as _genai
        _project  = os.environ.get('VERTEX_PROJECT_ID', '')
        _location = os.environ.get('VERTEX_LOCATION', 'us-central1')
        _model    = os.environ.get('VERTEX_MODEL', 'gemini-2.5-flash')
        if not _project:
            raise ValueError("VERTEX_PROJECT_ID not set")
        _client = _genai.Client(vertexai=True, project=_project, location=_location)
        _contents = []
        if system_prompt:
            _contents.append(f"[System]: {system_prompt}\n\n{prompt}")
        else:
            _contents.append(prompt)
        _response = _client.models.generate_content(
            model=_model,
            contents=_contents,
            config=_genai.types.GenerateContentConfig(
                max_output_tokens=16384, temperature=0.3))
        return _response.text.strip()

    if provider in ('gemini', 'gemma'):
        api_key = os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            raise ValueError("No GEMINI_API_KEY set")
        model = 'gemma-3-4b-it' if provider == 'gemma' else os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
        contents = []
        if system_prompt:
            contents.append({'role': 'user', 'parts': [{'text': system_prompt}]})
            contents.append({'role': 'model', 'parts': [{'text': 'Understood.'}]})
        contents.append({'role': 'user', 'parts': [{'text': prompt}]})
        resp = requests.post(url, json={'contents': contents,
                                        'generationConfig': {'maxOutputTokens': 8192, 'temperature': 0.3}},
                             timeout=60)
        resp.raise_for_status()
        data = resp.json()
        try:
            return data['candidates'][0]['content']['parts'][0]['text'].strip()
        except (KeyError, IndexError):
            raise ValueError(f"No content from gemini: {data}")

    cfg = {
        'qwen': {
            'url': os.environ.get('QWEN_BASE_URL',
                'https://dashscope-intl.aliyuncs.com/compatible-mode/v1') + '/chat/completions',
            'key': os.environ.get('QWEN_API_KEY', ''),
            'model': os.environ.get('QWEN_MODEL', 'qwen3.5-plus'),
        },
        'glm': {
            'url': os.environ.get('GLM_BASE_URL',
                'https://api.z.ai/api/coding/paas/v4') + '/chat/completions',
            'key': os.environ.get('GLM_API_KEY', ''),
            'model': os.environ.get('GLM_MODEL', 'glm-4.7'),
        },
    }
    c = cfg.get(provider, {})
    if not c.get('key'):
        raise ValueError(f"No API key for {provider}")

    messages = []
    if system_prompt:
        messages.append({'role': 'system', 'content': system_prompt})
    messages.append({'role': 'user', 'content': prompt})

    resp = requests.post(
        c['url'],
        headers={'Authorization': f"Bearer {c['key']}", 'Content-Type': 'application/json'},
        json={'model': c['model'], 'messages': messages, 'max_tokens': 8192, 'temperature': 0.3},
        timeout=60
    )
    resp.raise_for_status()
    data = resp.json()
    if 'choices' in data:
        return data['choices'][0]['message']['content'].strip()
    raise ValueError(f"No content from {provider}: {data}")


def summarize_video(
    video_url: str,
    prompt_file: Optional[str] = None,
    language: str = 'th',
    topic: str = '',
) -> str:
    """
    Summarize a YouTube video using AI providers.
    Returns markdown summary string.
    """
    # Get transcript
    transcript = _get_youtube_transcript(video_url)

    # Load system prompt from file if provided
    system_prompt = ''
    if prompt_file and os.path.exists(prompt_file):
        with open(prompt_file, encoding='utf-8') as f:
            system_prompt = f.read().strip()

    if language == 'th':
        if system_prompt:
            # system_prompt (from prompt file) controls structure — just provide video data
            prompt = f"""เขียนคำตอบเป็นภาษาไทยทั้งหมดเท่านั้น ห้ามใช้ภาษาอังกฤษในเนื้อหา

วิดีโอ: {video_url}
หัวข้อ: {topic or 'เทรนด์ AI และเทคโนโลยี'}

{'เนื้อหาจากวิดีโอ:\n' + transcript[:15000] if transcript else 'ไม่มี transcript — สรุปจาก URL และชื่อวิดีโอ โดยใช้ความรู้เกี่ยวกับ ' + (topic or 'AI') + ' ที่มีอยู่'}"""
        else:
            # No prompt file — use default Thai structure
            prompt = f"""คุณต้องเขียนคำตอบเป็นภาษาไทยทั้งหมดเท่านั้น ห้ามใช้ภาษาอังกฤษในเนื้อหาเด็ดขาด

สรุปเนื้อหาวิดีโอ YouTube นี้สำหรับการตลาด:
URL: {video_url}
หัวข้อ: {topic or 'เทรนด์ AI และเทคโนโลยี'}

{'เนื้อหาจากวิดีโอ: ' + transcript[:3000] if transcript else 'ไม่มี transcript — สรุปจาก URL และชื่อวิดีโอ'}

สรุปเป็น markdown ภาษาไทย:
1. **หัวข้อหลัก** — วิดีโอนี้พูดถึงอะไร
2. **ข้อมูลเชิงลึก** — 3-5 ประเด็นที่นำไปใช้ได้จริง
3. **เทรนด์ที่เกี่ยวข้อง** — เทรนด์อะไรที่ถูกพูดถึง
4. **มุมมองสำหรับ Facebook** — นำไปใช้สร้าง content ได้อย่างไร

เขียนเป็นภาษาไทยทั้งหมด กระชับและใช้งานได้จริง"""
    else:
        prompt = f"""Write in {language}.

Summarize this YouTube video content for affiliate/content marketing use.
Video URL: {video_url}
Topic: {topic or 'AI and technology trends'}

{'Transcript excerpt: ' + transcript[:3000] if transcript else 'Note: No transcript available - summarize based on video metadata and URL context.'}

Provide a structured markdown summary with:
1. **Main Topic** — what the video is about
2. **Key Insights** — 3-5 actionable points
3. **Relevant Trends** — what trends are discussed
4. **Content Angle** — how to use this for Facebook content

Keep it concise and practical."""

    # Provider chain: vertex (GCP ADC) → qwen → glm → gemini (AI Studio) → gemma
    primary  = os.environ.get('TRENDS_PRIMARY_PROVIDER',  'vertex')
    fallback = os.environ.get('TRENDS_FALLBACK_PROVIDER', 'qwen')
    seen, providers = set(), []
    for p in [primary, fallback, 'glm', 'gemini', 'gemma']:
        if p not in seen:
            seen.add(p)
            providers.append(p)

    import time as _time
    for provider in providers:
        for attempt in range(3):
            try:
                return _call_provider(provider, prompt, system_prompt)
            except Exception as e:
                msg = str(e)
                if '429' in msg:
                    wait = 60 * (attempt + 1)
                    print(f"[summarize_local] {provider} rate limited, waiting {wait}s...", file=sys.stderr)
                    _time.sleep(wait)
                    continue
                print(f"[summarize_local] {provider} failed: {e}", file=sys.stderr)
                break

    return f"# Summary unavailable\n\nURL: {video_url}\nAll AI providers failed."


def main():
    parser = argparse.ArgumentParser(description='Local AI summarizer (drop-in for summarize CLI)')
    parser.add_argument('url', help='YouTube URL')
    parser.add_argument('--youtube', default='auto')
    parser.add_argument('--language', default='th')
    parser.add_argument('--prompt-file', dest='prompt_file', default=None)
    parser.add_argument('--format', default='md')
    parser.add_argument('--length', default='xl')
    parser.add_argument('--model', default=None)  # ignored — use credentials.env
    parser.add_argument('--markdown-mode', default='llm')
    parser.add_argument('--topic', default='')
    args = parser.parse_args()

    result = summarize_video(
        args.url,
        prompt_file=args.prompt_file,
        language=args.language,
        topic=args.topic,
    )
    print(result)


if __name__ == '__main__':
    main()
