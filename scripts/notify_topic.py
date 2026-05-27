#!/usr/bin/env python3
"""
ATS per-topic notification sender.
Sends email (Brevo SMTP) and/or Telegram DM for configured topics.

Usage:
  python3 scripts/notify_topic.py --all --date 2026-05-27
  python3 scripts/notify_topic.py --topic NATEHERK --dry-run
  python3 scripts/notify_topic.py --topic ai_agents --email-only
  python3 scripts/notify_topic.py --all --telegram-only
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config"))

from paths import PROJECT_ROOT, REPORTS_DIR, AUDIO_DIR, load_credentials

import argparse
import json
import smtplib
import re
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import urlencode

try:
    from jinja2 import Environment, FileSystemLoader
    _JINJA_OK = True
except ImportError:
    _JINJA_OK = False

import requests

# ── Paths ──────────────────────────────────────────────────────────────────
ROUTING_CONFIG_PATH = Path(PROJECT_ROOT) / "config" / "notification_routing.json"
AUDIO_CONFIG_PATH   = Path(PROJECT_ROOT) / "config" / "audio_topics.json"
TEMPLATES_DIR       = Path(__file__).parent / "templates"
REPORTS_BASE        = Path(REPORTS_DIR) / "reports"

# ── Dashboard download base (Cloudflare Tunnel → localhost:8092) ─────────────
DASHBOARD_HOST = "https://ai-trends.thequietself.com"

# ── Topic map: key → (display_name, local_folder, github_path) ─────────────
# Key = local_folder (matches TOPICS tuple[1] in ai_trends_daily_summary_thai.py)
TOPIC_MAP = {
    "ai_agents":                ("AI Agents",                     "ai_agents",                "ai_agents"),
    "claude_code":              ("Claude Code",                   "claude_code",              "claude_code"),
    "ai_viral_niche":           ("AI Viral Niche",                "ai_viral_niche",           "ai_viral_niche"),
    "NATEHERK":                 ("NATEHERK",                      "NATEHERK",                 "NATEHERK"),
    "joanna_wiebe":             ("Joanna Wiebe",                  "joanna_wiebe",             "joanna_wiebe"),
    "jacksons_ai":              ("Jacksons AI",                   "jacksons_ai",              "jacksons_ai"),
    "make_money_matt":          ("Make Money Matt",               "make_money_matt",          "make_money_matt"),
    "miss_luna_vega":           ("Miss Luna Vega",                "miss_luna_vega",           "miss_luna_vega"),
    "claude_code_obsidian":     ("CC Obsidian",                   "claude_code_obsidian",     "claude_code/claude_code_obsidian"),
    "claude_code_notebooklm":   ("CC NotebookLM",                 "claude_code_notebooklm",   "claude_code/claude_code_notebooklm"),
    "claude_code_design":       ("CC Design",                     "claude_code_design",       "claude_code/claude_code_design"),
    "claude_code_skills":       ("CC Skills",                     "claude_code_skills",       "claude_code/claude_code_skills"),
    "claude_code_remotion_video":("CC Remotion Video",            "claude_code_remotion_video","claude_code/claude_code_remotion_video"),
    "claude_code_video":        ("CC Video",                      "claude_code_video",        "claude_code/claude_code_video"),
    "claude_code_seedance":     ("CC Seedance",                   "claude_code_seedance",     "claude_code/claude_code_seedance"),
    "claude_code_higgsfield":   ("CC Higgsfield",                 "claude_code_higgsfield",   "claude_code/claude_code_higgsfield"),
    "claude_code_shopify":      ("CC Shopify",                    "claude_code_shopify",      "claude_code/claude_code_shopify"),
    "claude_code_hyperframe":   ("CC Hyperframe",                 "claude_code_hyperframe",   "claude_code/claude_code_hyperframe"),
    "finance_money_coach":      ("Finance — THE MONEY COACH",     "finance_money_coach",      "finance_money_coach"),
    "finance_money_buffalo":    ("Finance — Money Buffalo",       "finance_money_buffalo",    "finance_money_buffalo"),
    "finance_a_academy":        ("Finance — A-Academy",           "finance_a_academy",        "finance_a_academy"),
    "finance_financial_diet":   ("Finance — The Financial Diet",  "finance_financial_diet",   "finance_financial_diet"),
    "finance_humphrey_yang":    ("Finance — Humphrey Yang",       "finance_humphrey_yang",    "finance_humphrey_yang"),
    "boom_bignose":             ("Boom BigNose",                  "boom_bignose",             "boom_bignose"),
}

THAI_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
               "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def thai_date(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.day} {THAI_MONTHS[dt.month - 1]} {dt.year + 543}"
    except Exception:
        return date_str


# ── Config helpers ──────────────────────────────────────────────────────────

def load_routing_config():
    """Return (defaults_dict, topics_dict). Empty dicts on any error."""
    try:
        with open(ROUTING_CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("defaults", {}), cfg.get("topics", {})
    except FileNotFoundError:
        return {}, {}
    except Exception as e:
        logging.warning(f"notify_topic: routing config load failed: {e}")
        return {}, {}


def get_topic_config(topic_key, defaults, topics):
    """Merge topic config with defaults. Always returns a full config dict."""
    base = {
        "email_enabled": False,
        "telegram_enabled": False,
        "recipient_emails": [],
        "telegram_chat_ids": [],
        "notification_mode": "per_topic",
    }
    base.update(defaults)
    base.update(topics.get(topic_key, {}))
    return base


# ── Report helpers ──────────────────────────────────────────────────────────

def find_report_file(local_folder, date_str):
    """Return Path to report .md if it exists, else None."""
    if local_folder.startswith("claude_code_"):
        path = REPORTS_BASE / "claude_code" / local_folder / f"{date_str}.md"
    else:
        path = REPORTS_BASE / local_folder / f"{date_str}.md"
    return path if path.exists() else None


def extract_summary(report_path, max_chars=800):
    """Return (intro_text, video_count) from a report file."""
    try:
        content = Path(report_path).read_text(encoding="utf-8")
    except Exception:
        return "", 0
    video_count = content.count("## Video ")
    # Everything before the first "## Video" header
    split = re.split(r"\n## Video ", content, maxsplit=1)
    intro = split[0].strip()
    if len(intro) > max_chars:
        intro = intro[:max_chars].rsplit(" ", 1)[0] + "…"
    return intro, video_count


# ── URL builders ────────────────────────────────────────────────────────────

def build_urls(topic_key, local_folder, github_path, date_str):
    """Return (md_download_url, wav_download_url_or_None).

    Both URLs point to the ATS dashboard (ai-trends.thequietself.com) so they
    work regardless of GitHub repo visibility and always trigger a file download.
    """
    md_download = (
        f"{DASHBOARD_HOST}/download/report?"
        + urlencode({"topic": local_folder, "date": date_str})
    )
    wav_download = None
    try:
        with open(AUDIO_CONFIG_PATH, encoding="utf-8") as f:
            audio_cfg = json.load(f)
        enabled = audio_cfg.get("enabled_topics", [])
        if local_folder in enabled or topic_key in enabled:
            wav_download = (
                f"{DASHBOARD_HOST}/api/voice/serve?"
                + urlencode({"topic": local_folder, "date": date_str, "video": "1"})
            )
    except Exception as e:
        logging.warning(f"notify_topic: could not load audio config: {e}")
    return md_download, wav_download


# ── Email ───────────────────────────────────────────────────────────────────

def render_html_email(vars_dict):
    if not _JINJA_OK:
        return None
    try:
        env  = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
        tmpl = env.get_template("email_report.html.j2")
        return tmpl.render(**vars_dict)
    except Exception as e:
        logging.warning(f"notify_topic: HTML template render failed: {e}")
        return None


def render_plain_email(vars_dict):
    lines = [
        f"[ATS] {vars_dict['topic_name']} — {vars_dict['video_count']} วิดีโอใหม่ · {vars_dict['date_thai']}",
        "",
        vars_dict["intro_summary"],
        "",
        f"📄 Download Report (.md): {vars_dict['md_download_url']}",
    ]
    if vars_dict.get("wav_download_url"):
        lines.append(f"🎧 Download Audio (.wav): {vars_dict['wav_download_url']}")
    lines += ["", "—", "AI Trends Research System"]
    return "\n".join(lines)


def _load_home_credentials():
    """Also load ~/.credentials.env (contains Brevo keys not in project credentials.env)."""
    home_creds = os.path.expanduser("~/.credentials.env")
    if os.path.exists(home_creds):
        with open(home_creds) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())


def send_email(recipients, subject, html_body, text_body, dry_run=False):
    """Send via Brevo SMTP. Returns True on success."""
    if dry_run:
        print(f"    [DRY-RUN] Email → {recipients}")
        print(f"    Subject: {subject}")
        return True
    try:
        load_credentials()
        _load_home_credentials()
        host = os.environ.get("BREVO_SMTP_HOST", "smtp-relay.brevo.com")
        port = int(os.environ.get("BREVO_SMTP_PORT", "587"))
        user = os.environ.get("BREVO_SMTP_USERNAME", "")
        pwd  = os.environ.get("BREVO_SMTP_PASSWORD", "")
        from_addr = os.environ.get("GIT_USER_EMAIL", "noreply@thequietself.com")
        if not user or not pwd:
            logging.error("notify_topic: SMTP credentials missing")
            return False
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"ATS Research <{from_addr}>"
        msg["To"]      = ", ".join(recipients)
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP(host, port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(user, pwd)
            smtp.sendmail(from_addr, recipients, msg.as_string())
        logging.info(f"notify_topic: email sent to {recipients}")
        return True
    except Exception as e:
        logging.error(f"notify_topic: email error: {e}")
        return False


# ── Telegram ────────────────────────────────────────────────────────────────

def get_telegram_token():
    env_path = os.path.expanduser("~/.claude/channels/telegram/.env")
    try:
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def build_telegram_text(vars_dict):
    topic        = vars_dict["topic_name"]
    date         = vars_dict["date_thai"]
    count        = vars_dict["video_count"]
    intro        = vars_dict["intro_summary"]
    md_download  = vars_dict["md_download_url"]
    wav_download = vars_dict.get("wav_download_url")

    if len(intro) > 400:
        intro = intro[:400].rsplit(" ", 1)[0] + "…"

    lines = [
        f"📊 <b>{topic}</b> · {date}",
        "",
        f"{count} วิดีโอใหม่",
        "",
        intro,
        "",
        f'📄 <a href="{md_download}">Download Report (.md)</a>',
    ]
    if wav_download:
        lines.append(f'🎧 <a href="{wav_download}">Download Audio (.wav)</a>')
    lines += ["", "—", "ATS Research System"]
    return "\n".join(lines)


def send_telegram_dms(bot_token, chat_ids, text, dry_run=False):
    """Send DM to each chat_id. Returns list of (chat_id, success)."""
    results = []
    for chat_id in chat_ids:
        if dry_run:
            print(f"    [DRY-RUN] Telegram DM → {chat_id}")
            results.append((chat_id, True))
            continue
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=30,
            )
            ok = resp.status_code == 200 and resp.json().get("ok", False)
            if not ok:
                logging.warning(f"notify_topic: Telegram {chat_id} error: {resp.text[:200]}")
            results.append((chat_id, ok))
        except Exception as e:
            logging.error(f"notify_topic: Telegram {chat_id} exception: {e}")
            results.append((chat_id, False))
    return results


# ── Core orchestrator ───────────────────────────────────────────────────────

def notify_topic(topic_key, date_str, dry_run=False, email_only=False, telegram_only=False):
    """Notify for one topic. Returns True if at least one channel succeeded."""
    if topic_key not in TOPIC_MAP:
        logging.warning(f"notify_topic: unknown topic key '{topic_key}'")
        return False

    defaults, topics_cfg = load_routing_config()
    cfg = get_topic_config(topic_key, defaults, topics_cfg)

    if cfg.get("notification_mode") == "digest_only":
        print(f"  ⏭  {topic_key}: digest_only, skipping per-topic")
        return False

    do_email    = cfg["email_enabled"] and not telegram_only
    do_telegram = cfg["telegram_enabled"] and not email_only

    if not do_email and not do_telegram:
        print(f"  ⏭  {topic_key}: all channels disabled")
        return False

    display_name, local_folder, github_path = TOPIC_MAP[topic_key]
    report_path = find_report_file(local_folder, date_str)
    if report_path is None:
        print(f"  ⏭  {topic_key}: no report for {date_str}")
        return False

    intro, video_count = extract_summary(report_path)
    md_download, wav_download = build_urls(topic_key, local_folder, github_path, date_str)

    vars_dict = {
        "topic_name":     display_name,
        "date_str":       date_str,
        "date_thai":      thai_date(date_str),
        "video_count":    video_count,
        "intro_summary":  intro,
        "md_download_url":  md_download,
        "wav_download_url": wav_download,
    }

    sent = False

    if do_email and cfg["recipient_emails"]:
        subject   = f"[ATS] {display_name} — {video_count} วิดีโอใหม่ · {thai_date(date_str)}"
        html_body = render_html_email(vars_dict)
        text_body = render_plain_email(vars_dict)
        ok = send_email(cfg["recipient_emails"], subject, html_body, text_body, dry_run=dry_run)
        tag = "(dry-run)" if dry_run else "sent"
        print(f"  {'✉️ ' if ok else '❌'} email → {cfg['recipient_emails']}: {tag if ok else 'failed'}")
        if ok:
            sent = True

    if do_telegram and cfg["telegram_chat_ids"]:
        bot_token = get_telegram_token()
        if not bot_token:
            print(f"  ❌  telegram: bot token not found")
        else:
            tg_text = build_telegram_text(vars_dict)
            results = send_telegram_dms(bot_token, cfg["telegram_chat_ids"], tg_text, dry_run=dry_run)
            for chat_id, ok in results:
                tag = "(dry-run)" if dry_run else "sent"
                print(f"  {'📨' if ok else '❌'} telegram → {chat_id}: {tag if ok else 'failed'}")
                if ok:
                    sent = True

    return sent


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="ATS per-topic notification sender")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--all", action="store_true", help="Notify all configured topics")
    grp.add_argument("--topic", metavar="KEY", help="Notify one topic key (e.g. NATEHERK)")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                        help="Report date YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print planned actions without sending")
    parser.add_argument("--email-only", action="store_true",
                        help="Skip Telegram, send email only")
    parser.add_argument("--telegram-only", action="store_true",
                        help="Skip email, send Telegram DMs only")
    args = parser.parse_args()

    date_str = args.date
    keys = [args.topic] if args.topic else list(TOPIC_MAP.keys())

    if args.dry_run:
        print(f"[DRY-RUN] notify_topic for date={date_str}, topics={len(keys)}")

    total_sent = 0
    for key in keys:
        print(f"\n→ {key}")
        try:
            ok = notify_topic(key, date_str,
                              dry_run=args.dry_run,
                              email_only=args.email_only,
                              telegram_only=args.telegram_only)
            if ok:
                total_sent += 1
        except Exception as e:
            logging.error(f"notify_topic: unexpected error for {key}: {e}")

    print(f"\n✅ Done — {total_sent}/{len(keys)} topics notified")


if __name__ == "__main__":
    main()
