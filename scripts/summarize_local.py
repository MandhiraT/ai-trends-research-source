#!/usr/bin/env python3
"""
summarize_local.py — drop-in replacement for the `summarize` CLI.
Uses Qwen (primary) / GLM (fallback) / Gemini (last resort) directly.

Usage (as library):
    from summarize_local import summarize_video
    result = summarize_video(video_url, prompt_file, language='th')

Usage (as CLI, same interface as `summarize` CLI):
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
    try:
        result = subprocess.run(
            ['yt-dlp', '--skip-download', '--write-auto-sub',
             '--sub-lang', 'en', '--sub-format', 'vtt',
             '--output', '/tmp/yt_transcript', video_url],
            capture_output=True, text=True, timeout=60
        )
        # Try reading the generated vtt file
        for ext in ['.en.vtt', '.vtt']:
            path = f'/tmp/yt_transcript{ext}'
            if os.path.exists(path):
                with open(path) as f:
                    lines = [l.strip() for l in f if l.strip()
                             and not l.startswith('WEBVTT')
                             and '-->' not in l
                             and not l.startswith('NOTE')]
                return ' '.join(lines)[:6000]
    except Exception:
        pass
    return ''


def _call_provider(provider: str, prompt: str, system_prompt: str = '') -> str:
    if provider == 'gemini':
        api_key = os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            raise ValueError("No GEMINI_API_KEY set")
        model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
        contents = []
        if system_prompt:
            contents.append({'role': 'user', 'parts': [{'text': system_prompt}]})
            contents.append({'role': 'model', 'parts': [{'text': 'Understood.'}]})
        contents.append({'role': 'user', 'parts': [{'text': prompt}]})
        resp = requests.post(url, json={'contents': contents,
                                        'generationConfig': {'maxOutputTokens': 4096, 'temperature': 0.3}},
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
        json={'model': c['model'], 'messages': messages, 'max_tokens': 4096, 'temperature': 0.3},
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

    lang_instruction = 'Write in Thai language (ภาษาไทย).' if language == 'th' else f'Write in {language}.'

    prompt = f"""{lang_instruction}

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

    # Try providers with fallback (Gemini always last resort)
    primary  = os.environ.get('TRENDS_PRIMARY_PROVIDER',  'qwen')
    fallback = os.environ.get('TRENDS_FALLBACK_PROVIDER', 'glm')
    providers = [p for p in [primary, fallback, 'gemini'] if p not in [primary, fallback][1:] or p == 'gemini']
    # Deduplicate while preserving order
    seen, providers = set(), []
    for p in [primary, fallback, 'gemini']:
        if p not in seen:
            seen.add(p)
            providers.append(p)

    for provider in providers:
        try:
            return _call_provider(provider, prompt, system_prompt)
        except Exception as e:
            print(f"[summarize_local] {provider} failed: {e}", file=sys.stderr)
            continue

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
