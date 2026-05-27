#!/usr/bin/env python3

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "config"))
try:
    from paths import PROJECT_ROOT, REPORTS_DIR, AUDIO_DIR
except ImportError:
    PROJECT_ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
    REPORTS_DIR = _os.path.join(PROJECT_ROOT, "ai_trends_reports", "reports")
    AUDIO_DIR   = _os.path.join(PROJECT_ROOT, "ai_trends_reports", "audio")

"""
AI Trends Daily Summary — Thai status report with Telegram notification.
Checks actual report files for today, counts videos, builds status message,
and sends to Telegram via Bot API.
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path
from voice_filenames import find_voice_files

GITHUB_BASE = "https://github.com/MandhiraT/ai-trends-research/blob/master/reports"

TOPICS = [
    ("AI Agents",          "ai_agents",              "ai_agents"),
    ("Claude Code",        "claude_code",             "claude_code"),
    ("AI Viral Niche",     "ai_viral_niche",          "ai_viral_niche"),
    ("NATEHERK",           "NATEHERK",                "NATEHERK"),
    ("Joanna Wiebe",       "joanna_wiebe",            "joanna_wiebe"),
    ("Jacksons AI",        "jacksons_ai",             "jacksons_ai"),
    ("Make Money Matt",    "make_money_matt",         "make_money_matt"),
    ("Miss Luna Vega",     "miss_luna_vega",          "miss_luna_vega"),
    ("CC Obsidian",        "claude_code_obsidian",       "claude_code/claude_code_obsidian"),
    ("CC NotebookLM",      "claude_code_notebooklm",     "claude_code/claude_code_notebooklm"),
    ("CC Design",          "claude_code_design",         "claude_code/claude_code_design"),
    ("CC Skills",          "claude_code_skills",         "claude_code/claude_code_skills"),
    ("CC Remotion Video",  "claude_code_remotion_video", "claude_code/claude_code_remotion_video"),
    ("CC Video",           "claude_code_video",          "claude_code/claude_code_video"),
    ("CC Seedance",        "claude_code_seedance",       "claude_code/claude_code_seedance"),
    ("CC Higgsfield",      "claude_code_higgsfield",     "claude_code/claude_code_higgsfield"),
    ("CC Shopify",         "claude_code_shopify",        "claude_code/claude_code_shopify"),
    ("CC Hyperframe",      "claude_code_hyperframe",     "claude_code/claude_code_hyperframe"),
    ("Finance — THE MONEY COACH", "finance_money_coach", "finance_money_coach"),
    ("Finance — Money Buffalo", "finance_money_buffalo", "finance_money_buffalo"),
    ("Finance — A-Academy", "finance_a_academy", "finance_a_academy"),
    ("Finance — The Financial Diet", "finance_financial_diet", "finance_financial_diet"),
    ("Finance — Humphrey Yang", "finance_humphrey_yang", "finance_humphrey_yang"),
    ("Boom BigNose",      "boom_bignose",           "boom_bignose"),
    ("Health — อาหารบำรุงสุขภาพ", "health/health_food_nutrition", "health/health_food_nutrition"),
    ("Health — Top to Toe", "health/top_to_toe", "health/top_to_toe"),
]


def count_videos_in_report(report_path):
    """Count ## Video N: headers in a report file."""
    try:
        content = open(report_path, encoding='utf-8').read()
        return content.count('## Video ')
    except Exception:
        return 0


def build_status(date_str):
    # REPORTS_DIR = .../ai_trends_reports — reports are one level deeper in /reports/
    reports_base = os.path.join(REPORTS_DIR, "reports")

    lines = []
    total_videos = 0
    found = 0
    not_found = []

    for label, folder, github_path in TOPICS:
        if folder.startswith("claude_code_"):
            report_file = os.path.join(reports_base, "claude_code", folder, f"{date_str}.md")
        else:
            report_file = os.path.join(reports_base, folder, f"{date_str}.md")

        if os.path.exists(report_file):
            n = count_videos_in_report(report_file)
            total_videos += n
            found += 1
            video_txt = f"{n} video{'s' if n != 1 else ''}" if n else "no new videos"
            url = f"{GITHUB_BASE}/{github_path}/{date_str}.md"
            lines.append(f"✅ {label} — {video_txt}\n   {url}")
        else:
            not_found.append(label)
            lines.append(f"⏭️ {label} — no new content")

    return lines, total_videos, found, not_found


AUDIO_CONFIG = _os.path.join(PROJECT_ROOT, 'config', 'audio_topics.json')
GITHUB_AUDIO_BASE = "https://github.com/MandhiraT/ai-trends-research/tree/master/voice"


def _slug(value):
    return str(value).strip().replace(' ', '_').replace('-', '_').lower()


def build_audio_status(date_str):
    """Check which enabled audio topics have WAV file(s) for date_str.

    Daily automation can produce either the legacy whole-day file
    ``YYYY-MM-DD.wav`` or per-video files like ``YYYY-MM-DD-v1.wav``.
    Treat any ``date*.wav`` file as a valid audio output and link to the
    canonical lowercase output repo folder: ``voice/{topic_slug}/``.
    """
    try:
        with open(AUDIO_CONFIG, encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception:
        return []

    enabled    = cfg.get('enabled_topics', [])
    folder_map = cfg.get('github_folder_map', {})
    results = []
    for topic in enabled:
        topic_audio_dir = _os.path.join(AUDIO_DIR, topic)
        wav_files = [str(p) for p in find_voice_files(Path(topic_audio_dir), topic, date_str)]

        gh_folder = _slug(folder_map.get(topic, topic))
        if wav_files:
            size_mb = sum(_os.path.getsize(wav) for wav in wav_files) / (1024 * 1024)
            url = f"{GITHUB_AUDIO_BASE}/{gh_folder}"
            results.append(('ok', topic, gh_folder, size_mb, url))
        else:
            results.append(('missing', topic, gh_folder, 0, ''))
    return results


def get_telegram_creds():
    """Load bot token from Sati's Telegram channel config."""
    try:
        env_path = os.path.expanduser("~/.claude/channels/telegram/.env")
        bot_token = ""
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    bot_token = line.split("=", 1)[1].strip()
                    break
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "1043709932")
        return bot_token, chat_id
    except Exception:
        return "", ""


def send_telegram(text, bot_token, chat_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def generate_daily_summary():
    date_str = datetime.now().strftime('%Y-%m-%d')
    time_str = datetime.now().strftime('%H:%M ICT')

    lines, total_videos, found, not_found = build_status(date_str)

    # Plain text for stdout / log
    report_lines = [
        f"# AI Trends Research Status — {date_str}",
        f"Generated: {time_str}",
        f"Topics with new content: {found}/{len(TOPICS)} | Total videos: {total_videos}",
        "",
    ] + lines + [
        "",
        f"Full reports: https://github.com/MandhiraT/ai-trends-research/tree/master/reports",
    ]
    return "\n".join(report_lines), date_str, time_str, lines, total_videos, found


def build_telegram_message(date_str, time_str, lines, total_videos, found, audio_status=None):
    msg = (
        f"📊 <b>AI Trends Research — {date_str}</b>\n"
        f"เวลา: {time_str}\n"
        f"Topics: {found}/{len(TOPICS)} | Videos: {total_videos} รายการ\n\n"
    )
    for line in lines:
        # Shorten for Telegram — show only label + video count (first line)
        first = line.split('\n')[0]
        url_line = line.split('\n')[1].strip() if '\n' in line else ''
        if '✅' in first:
            label_part = first.replace('✅ ', '')
            msg += f"✅ {label_part}\n"
            if url_line:
                msg += f"   <a href='{url_line}'>{url_line.split('/')[-1]}</a>\n"
        else:
            msg += f"{first}\n"

    msg += f"\n🔗 <a href='https://github.com/MandhiraT/ai-trends-research/tree/master/reports'>ดูรายงานทั้งหมด</a>"

    # Audio status section
    if audio_status:
        msg += "\n\n🎧 <b>Audio Reports</b>\n"
        for status, topic, gh_folder, size_mb, url in audio_status:
            if status == 'ok':
                msg += f"✅ {gh_folder} — {size_mb:.1f} MB\n"
                msg += f"   <a href='{url}'>voice/{gh_folder}</a>\n"
            else:
                msg += f"❌ {gh_folder} — ไม่พบไฟล์เสียง\n"

    return msg


if __name__ == "__main__":
    summary, date_str, time_str, lines, total_videos, found = generate_daily_summary()
    print(summary)

    audio_status = build_audio_status(date_str)
    if audio_status:
        print("\nAudio status:")
        for status, topic, gh_folder, size_mb, url in audio_status:
            icon = "✅" if status == "ok" else "❌"
            print(f"  {icon} {topic} ({gh_folder}) — {size_mb:.1f} MB" if status == "ok" else f"  {icon} {topic} — missing")

    # Send Telegram notification
    bot_token, chat_id = get_telegram_creds()
    if bot_token and chat_id:
        try:
            msg = build_telegram_message(date_str, time_str, lines, total_videos, found, audio_status)
            send_telegram(msg, bot_token, chat_id)
            print(f"✅ Telegram notification sent to {chat_id}")
        except Exception as e:
            print(f"⚠️  Telegram notification failed: {e}")
    else:
        print("⚠️  Telegram credentials not found — skipping notification")
