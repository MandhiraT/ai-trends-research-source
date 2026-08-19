#!/usr/bin/env python3
"""Local dashboard for AI Trends Research jobs."""

import argparse
import html
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

# Import search engine from build_report_index
_SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
from voice_filenames import voice_filename, find_voice_files
try:
    from build_report_index import INDEX_DIR, load_jsonl, search_records, build_index_records, write_indexes  # noqa: E402
    _SEARCH_AVAILABLE = True
except ImportError:
    _SEARCH_AVAILABLE = False

try:
    from notify_topic import TOPIC_MAP, load_routing_config, ROUTING_CONFIG_PATH, _load_topic_map
    _NOTIFY_OK = True
except ImportError:
    _NOTIFY_OK = False
    TOPIC_MAP = {}
    ROUTING_CONFIG_PATH = None
    def _load_topic_map(): return {}

try:
    import markdown as _md_lib
    _MD_OK = True
except ImportError:
    _MD_OK = False

# Regular daily-cron reports are named {date}.md. On-demand reports (the
# "speech"/"On Demand" job) are named {date}_{HHMM}_{slug}.md instead, since
# there can be several per calendar day (see build_report_filename() in
# run_ai_trends_research_enhanced.py) -- every "date" validation below must
# accept both, or on-demand reports are structurally invisible to Assets.
DATE_OR_REPORT_STEM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(_[A-Za-z0-9_-]+)?$")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SHARED_UI_DIR = Path.home() / "Desktop" / "Projects" / "shared-ui"

def _ui_ver() -> int:
    try:
        return int(max((SHARED_UI_DIR / f).stat().st_mtime for f in ("theme.css", "sidebar.js")))
    except OSError:
        return 0
CONFIG_FILE = PROJECT_ROOT / "config" / "research_jobs.json"
REPORTS_DIR = PROJECT_ROOT / "ai_trends_reports" / "reports"
DASHBOARD_DIR = PROJECT_ROOT / "ai_trends_reports" / "dashboard"
STATUS_FILE = DASHBOARD_DIR / "job_status.json"
LOGS_DIR = PROJECT_ROOT / "logs" / "dashboard"
RUN_TOPIC = PROJECT_ROOT / "scripts" / "run_ai_trends_with_creds.sh"
RUN_SUBTOPICS = PROJECT_ROOT / "scripts" / "run_claude_code_subtopics_with_creds.sh"
SYNC_CRON = PROJECT_ROOT / "scripts" / "sync_dashboard_cron.py"
AUDIO_CONFIG_PATH = PROJECT_ROOT / "config" / "audio_topics.json"

SOURCE_TYPES = ("topic", "channel", "playlist", "video", "claude_code_subtopic")
DEFAULT_TRANSCRIPT_LANGS = ["en", "th", "all"]
DEFAULT_SOURCE_LANGUAGE = "en"
SCHEDULE_SLOT_START = "05:00"
SCHEDULE_SLOT_END = "23:50"
SCHEDULE_SLOT_STEP_MINUTES = 10
RUN_LOCK = threading.Lock()


def _slug(name: str) -> str:
    """Normalize a topic name to a slug for consistent comparison.
    'AI Agents' → 'ai_agents', 'Claude Code' → 'claude_code', 'NATEHERK' → 'nateherk'
    """
    import re as _re
    return _re.sub(r"[\s\-]+", "_", name.strip()).lower()


def _find_topic_dir(base: Path, raw_name: str, slug_name: str) -> Path | None:
    """Return the first existing subdir matching raw_name, slug_name, or any dir whose slug matches."""
    for candidate in (raw_name, slug_name):
        d = base / candidate
        if d.is_dir():
            return d
    # Fallback: scan for a dir whose slug equals slug_name (handles NATEHERK vs nateherk etc.)
    if base.is_dir():
        for sub in base.iterdir():
            if sub.is_dir() and _slug(sub.name) == slug_name:
                return sub
    return None


def _resolve_report_path(topic: str, date: str) -> tuple[Path | None, str]:
    """Resolve a Dashboard topic/date request to the actual report file.

    Reports can live directly under reports/{topic}/{date}.md or under a nested
    parent, e.g. reports/claude_code/claude_code_design/{date}.md. The old
    fallback picked the first folder that happened to contain the date, which
    could falsely generate NATEHERK when the user clicked claude_code_design.
    Always match by slug before returning a report.
    """
    topic = (topic or "").strip()
    topic_slug = _slug(topic)
    if not topic_slug or not DATE_OR_REPORT_STEM_RE.match(date or ""):
        return None, topic_slug

    for candidate in (
        REPORTS_DIR / topic / f"{date}.md",
        REPORTS_DIR / topic_slug / f"{date}.md",
    ):
        if candidate.exists() and candidate.is_file():
            return candidate, _slug(candidate.parent.name)

    matches: list[Path] = []
    if REPORTS_DIR.exists():
        for candidate in REPORTS_DIR.rglob(f"{date}.md"):
            if not candidate.is_file():
                continue
            rel_parent = candidate.parent.relative_to(REPORTS_DIR).as_posix()
            leaf_slug = _slug(candidate.parent.name)
            rel_slug = _slug(rel_parent.replace("/", "_"))
            if leaf_slug == topic_slug or rel_slug == topic_slug:
                matches.append(candidate)

    if not matches:
        return None, topic_slug

    matches.sort(key=lambda p: (len(p.relative_to(REPORTS_DIR).parts), p.as_posix()))
    return matches[0], _slug(matches[0].parent.name)


def build_full_detail_report_content(
    topic: str, date: str, video_no: int, video_title: str, thai_title: str,
    source_url: str, video_id: str, result_text: str,
) -> str:
    """Build a Full Detail .md file matching the standard ATS report shape
    (# AI Trends Research - ... metadata block, ## Video N:, ### Full
    Summary section) instead of the old ad-hoc "# Full Detail: ..." plain
    header — so Full Detail files look and parse like every other ATS
    report. Uses date[:10] for the Date field since on-demand reports'
    own "date" value is the whole filename stem (date+time+slug+video-id),
    not a plain date.
    """
    generated_at = datetime.now()
    report_date = (date or "")[:10]
    report_time = generated_at.strftime("%H:%M ICT")
    display_title = thai_title or video_title

    return (
        f"# AI Trends Research - {topic}\n\n"
        f"**Date:** {report_date} {report_time}\n"
        f"**Topic:** {topic}\n"
        f"**Mode:** Full Detail (On-Demand Re-summarize)\n"
        f"**Videos Processed:** 1\n"
        f"**Duplicate Prevention:** Content Hash + Date Filtering\n"
        f"**Dashboard Job ID:** {_slug(topic)}\n\n"
        f"---\n\n"
        f"## Video {video_no}: {display_title}\n\n"
        f"**Source:** {source_url}\n"
        f"**Video ID:** {video_id}\n\n"
        f"### 📝 Full Summary (Thai)\n"
        f"{result_text}\n\n"
        f"---\n\n"
        f"Report generated at: {generated_at.isoformat()}\n"
    )


def filter_reports_by_date_range(reports: list, date_from: str | None, date_to: str | None) -> list:
    """Keep only reports whose date falls within [date_from, date_to] (either
    bound optional). Regular reports' filename stem IS the plain date
    (2026-05-14.md), but on-demand reports' stem also carries time/slug/
    video-id (2026-07-18_0807_make-any-topic..._LvuoNlYRs7g.md) — comparing
    the *full* stem against a plain "YYYY-MM-DD" boundary (always what an
    HTML <input type="date"> submits) made any same-day on-demand report
    compare as "greater than" date_to and get silently excluded, since a
    longer string with a shared prefix always sorts after the shorter one.
    Compare only the date prefix instead.
    """
    if not date_from and not date_to:
        return list(reports)
    filtered = []
    for rp in reports:
        date_str = rp.stem[:10]
        if date_from and date_str < date_from:
            continue
        if date_to and date_str > date_to:
            continue
        filtered.append(rp)
    return filtered


# Full Detail (on-demand, re-reads the original transcript instead of the
# already-compressed report) started NATEHERK-only, lifted to every topic
# 2026-07-13 per Mandy's instruction once the NATEHERK trial proved out.
FULL_DETAIL_PROMPT_FILE = PROJECT_ROOT / "prompts" / "thai_summary_prompt_full_detail.txt"

# Topics with automated daily TTS audio already emailed to Mandy — regenerating
# Quick Script here would silently overwrite that day's real audio script.
AUTOMATED_AUDIO_TOPICS = {"nateherk", "joanna_wiebe", "health_food_nutrition", "health_top_to_toe", "boom_bignose", "research_job"}


def _full_detail_path(topic: str, date: str, video_no: int) -> Path | None:
    """Sibling file next to the day's report: {date}-v{N}-full-detail.md."""
    report_path, _ = _resolve_report_path(topic, date)
    if not report_path:
        return None
    return report_path.parent / f"{date}-v{int(video_no)}-full-detail.md"


def _looks_like_no_transcript_failure(text: str) -> bool:
    """Detect cached Full Detail files that are failure stubs, not reports.

    Full Detail generation can fail transiently when YouTube/yt-dlp cannot fetch
    captions.  If we treat that markdown as a valid existing report, later UI
    clicks keep opening the stale failure page even after Thai captions become
    available.  These files should be regenerated, not considered done.
    """
    text = text or ""
    return (
        "# ไม่สามารถสรุปวิดีโอนี้ได้" in text
        or "วิดีโอนี้ไม่มี transcript" in text
        or "No transcript for" in text
    )


def build_file_preview_html(text: str, selected: str, suffix: str) -> str:
    """Inline file-preview fragment used by render_files() (/reports, /logs).

    Markdown reports (.md) render as formatted HTML (headers, bold, lists)
    instead of a raw escaped-text dump, matching view_report()/
    view_full_detail()/render_single_report() elsewhere in this dashboard.
    Non-.md files (e.g. .log) still show as plain text. The file on disk is
    untouched either way — this only changes how it looks when viewed here.
    """
    if _MD_OK and suffix == ".md":
        rendered = _md_lib.markdown(text, extensions=["nl2br", "fenced_code"])
        return (
            f'<section id="file-content"><h2>{h(selected)}</h2>'
            f'<style>#file-content .markdown-body{{line-height:1.7;font-size:15px}}'
            f'#file-content .markdown-body h1{{font-size:1.4em}}'
            f'#file-content .markdown-body h2{{font-size:1.2em;border-bottom:1px solid var(--line);padding-bottom:4px}}'
            f'#file-content .markdown-body h3{{font-size:1.05em}}'
            f'#file-content .markdown-body hr{{border:none;border-top:1px solid var(--line);margin:16px 0}}'
            f'#file-content .markdown-body code{{background:#eef2f7;border-radius:4px;padding:2px 6px;font-size:13px}}'
            f'#file-content .markdown-body pre{{background:#eef2f7;border-radius:6px;padding:12px;overflow-x:auto}}'
            f'#file-content .markdown-body ul,#file-content .markdown-body ol{{padding-left:1.4em}}</style>'
            f'<div class="markdown-body">{rendered}</div></section>'
        )
    return f'<section id="file-content"><h2>{h(selected)}</h2><pre style="white-space:pre-wrap;word-break:break-word">{h(text)}</pre></section>'


def _resolve_relative_file(base: Path, selected: str) -> Path | None:
    """Resolve a user-facing relative file path safely, with case-insensitive dirs.

    Search indexes and old shared links can contain historical folder casing such
    as ``NATEHERK/2026-05-04.md`` while the canonical Linux path is lowercase
    (``nateherk/2026-05-04.md``). Resolve each path segment by slug/casefold so
    legacy links keep opening, without allowing absolute paths or ``..`` escapes.
    """
    decoded = unquote(selected or "").strip().replace("\\", "/")
    parts = [p for p in decoded.split("/") if p]
    if not parts or any(p in {".", ".."} for p in parts):
        return None
    if Path(decoded).is_absolute():
        return None

    base_resolved = base.resolve()
    direct = (base / Path(*parts)).resolve()
    if base_resolved in direct.parents and direct.is_file():
        return direct

    current = base
    for part in parts:
        candidate = current / part
        if candidate.exists():
            current = candidate
            continue
        if not current.is_dir():
            return None
        target_slug = _slug(part)
        match = next(
            (
                child for child in current.iterdir()
                if child.name.casefold() == part.casefold() or _slug(child.name) == target_slug
            ),
            None,
        )
        if not match:
            return None
        current = match

    resolved = current.resolve()
    if base_resolved in resolved.parents and resolved.is_file():
        return resolved
    return None


def _asset_entry_score(entry: dict) -> tuple[int, int]:
    """Score asset entries so canonical slug-folder rows win during dedupe."""
    path = str(entry.get("path", ""))
    first = path.split("/", 1)[0]
    slug = entry.get("topic_folder", "")
    canonical = 1 if first == slug else 0
    generated_count = sum(
        1 for key in ("has_script_file", "has_voice_file", "has_social_file")
        if entry.get(key)
    )
    return canonical, generated_count


def _dedupe_asset_entries(entries: list[dict]) -> list[dict]:
    """Merge duplicate asset JSON rows caused by display-name vs slug folders."""
    merged: dict[tuple[str, str, str], dict] = {}
    order: list[tuple[str, str, str]] = []
    for entry in entries:
        key = (
            entry.get("topic_folder") or _slug(entry.get("topic") or entry.get("topic_raw") or ""),
            entry.get("date", ""),
            entry.get("report_path", ""),
        )
        if key not in merged:
            merged[key] = dict(entry)
            order.append(key)
            continue
        current = merged[key]
        preferred = dict(entry) if _asset_entry_score(entry) > _asset_entry_score(current) else current
        for flag in ("has_script_file", "has_voice_file", "has_social_file"):
            preferred[flag] = bool(current.get(flag) or entry.get(flag))
        preferred["videos"] = max(int(current.get("videos") or 0), int(entry.get("videos") or 0))
        merged[key] = preferred
    return [merged[key] for key in order]


def ensure_dirs():
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def load_jobs():
    ensure_dirs()
    if not CONFIG_FILE.exists():
        return []
    with CONFIG_FILE.open() as f:
        return json.load(f).get("jobs", [])


def save_jobs(jobs):
    ensure_dirs()
    with CONFIG_FILE.open("w") as f:
        json.dump({"jobs": jobs}, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_status():
    ensure_dirs()
    if not STATUS_FILE.exists():
        return {}
    with STATUS_FILE.open() as f:
        return json.load(f)


def save_status(status):
    ensure_dirs()
    with STATUS_FILE.open("w") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_audio_config():
    if not AUDIO_CONFIG_PATH.exists():
        return {"enabled_topics": [], "voice": "Aoede", "language_hint": "th-TH",
                "github_folder_map": {}, "default_voice_profile": "ats_female_narrator",
                "voice_profiles": {}, "automated_voice_topics": {}}
    with AUDIO_CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def save_audio_config(cfg):
    with AUDIO_CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")


def resolve_audio_key(topic_key, local_folder, report_folder, enabled_set):
    """Find which key in enabled_set matches this job, or return best key for new entries."""
    normalized = report_folder.replace("/", "_")
    for candidate in (local_folder, normalized, topic_key):
        if candidate in enabled_set:
            return candidate
    return local_folder


def sync_dashboard_cron():
    """Apply Dashboard daily-cron settings to the user's crontab."""
    result = subprocess.run(
        ["/usr/bin/python3", str(SYNC_CRON), "--apply"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "cron sync failed")
    return result.stdout


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def slugify(value):
    value = value.strip().lower().replace(" ", "_")
    value = re.sub(r"[^a-z0-9_\-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:80] or "research_job"


def job_daily_cron_enabled(job):
    if "daily_cron_enabled" in job:
        return bool(job.get("daily_cron_enabled"))
    return bool((job.get("schedule_time") or "").strip())


def report_date_key(filename, suffix):
    """Return YYYY-MM-DD for both daily and timestamped on-demand report filenames."""
    stem = filename[:-len(suffix)] if suffix and filename.endswith(suffix) else filename
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", stem)
    return match.group(1) if match else stem


def schedule_time_conflicts(jobs, schedule_time, current_job_id=None):
    schedule_time = (schedule_time or "").strip()
    if not schedule_time:
        return []
    return [
        job for job in jobs
        if job.get("id") != current_job_id
        and job.get("enabled", True)
        and job_daily_cron_enabled(job)
        and (job.get("schedule_time") or "").strip() == schedule_time
    ]


def duplicate_schedule_groups(jobs):
    groups = {}
    for job in jobs:
        schedule_time = (job.get("schedule_time") or "").strip()
        if not job.get("enabled", True) or not job_daily_cron_enabled(job) or not schedule_time:
            continue
        groups.setdefault(schedule_time, []).append(job)
    return {time_: group for time_, group in sorted(groups.items()) if len(group) > 1}


def _time_to_minutes(value):
    if not re.fullmatch(r"\d{1,2}:\d{2}", (value or "").strip()):
        return None
    hour, minute = [int(x) for x in value.split(":")]
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def schedule_slot_values():
    """Allowed production daily cron times shown in the job form dropdown."""
    start = _time_to_minutes(SCHEDULE_SLOT_START) or 0
    end = _time_to_minutes(SCHEDULE_SLOT_END) or (23 * 60 + 50)
    slots = []
    for total in range(start, end + 1, SCHEDULE_SLOT_STEP_MINUTES):
        slots.append(f"{total // 60:02d}:{total % 60:02d}")
    return slots


def schedule_slot_options(jobs, current_job_id=None, current_value=""):
    """Render safe schedule options: used slots are disabled except current job's slot."""
    current_value = (current_value or "").strip()
    used_by = {}
    for job in jobs:
        if job.get("id") == current_job_id:
            continue
        slot = (job.get("schedule_time") or "").strip()
        if job.get("enabled", True) and job_daily_cron_enabled(job) and slot:
            used_by.setdefault(slot, []).append(job.get("name") or job.get("id") or slot)

    known_slots = schedule_slot_values()
    if current_value and current_value not in known_slots:
        known_slots = [current_value] + known_slots

    options = ['<option value="">Manual only / no daily cron</option>']
    for slot in known_slots:
        names = used_by.get(slot, [])
        disabled = bool(names)
        label = slot if not names else f"{slot} — used by {', '.join(names[:2])}{'…' if len(names) > 2 else ''}"
        options.append(
            f'<option value="{h(slot)}" {"selected" if slot == current_value else ""} {"disabled" if disabled else ""}>{h(label)}</option>'
        )
    return "".join(options)


RESERVED_REPORT_FOLDERS = {"", "research_job"}


def clean_report_folder(value, fallback):
    parts = []
    for raw in (value or "").replace("\\", "/").split("/"):
        if not raw.strip() or raw.strip() in {".", ".."}:
            continue
        part = slugify(raw)
        if part and part not in {".", ".."}:
            parts.append(part)
    cleaned = "/".join(parts) if parts else slugify(fallback or "research_job")
    return cleaned.lower()


def default_report_folder_for_job(topic, name="", source_url="", job_id=""):
    """User-friendly report folder: derive a safe lowercase folder from topic/name.

    Operators should not need to understand filesystem naming. The dashboard uses
    this when the Report Folder field is blank or accidentally left as a generic
    placeholder like 'research_job'.
    """
    return clean_report_folder("", slugify(topic or name or job_id or source_url or "research_job"))


def normalize_report_folder_for_save(raw_value, topic, name, source_url, job_id, *, is_on_demand=False):
    fallback = default_report_folder_for_job(topic, name, source_url, job_id)
    if is_on_demand and not (raw_value or "").strip():
        return clean_report_folder(f"on_demand/{fallback}", fallback)
    folder = clean_report_folder(raw_value or "", fallback)
    # 'research_job' is the legacy/on-demand reference bucket. For normal jobs it
    # makes reports look like they belong to the reference job and risks overwrite.
    if not is_on_demand and folder in RESERVED_REPORT_FOLDERS:
        folder = fallback
    if is_on_demand and folder == "research_job":
        folder = "on_demand/research_job"
    return folder


def unique_report_folder(folder, jobs, current_job_id=""):
    """Avoid multiple jobs writing the same daily report file path."""
    existing = {
        clean_report_folder(j.get("report_folder") or "", slugify(j.get("topic") or j.get("name") or j.get("id") or "research_job"))
        for j in jobs
        if j.get("id") != current_job_id
    }
    if folder not in existing:
        return folder
    base = folder
    for i in range(2, 1000):
        candidate = f"{base}_{i}"
        if candidate not in existing:
            return candidate
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base}_{timestamp}"


def report_files_for_job(job):
    folder = clean_report_folder(job.get("report_folder") or "", slugify(job.get("topic") or job.get("name") or job.get("id") or "research_job"))
    base = REPORTS_DIR / folder
    if not base.exists():
        return []
    files = [p for p in base.rglob("*.md") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def unique_job_id(base, jobs, current_id=""):
    """Create a stable unique job id for new Dashboard jobs."""
    base_id = slugify(base or "research_job")
    existing_ids = {j.get("id") for j in jobs if j.get("id") and j.get("id") != current_id}
    if base_id not in existing_ids:
        return base_id
    for i in range(2, 1000):
        candidate = f"{base_id}_{i}"
        if candidate not in existing_ids:
            return candidate
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_id}_{timestamp}"


def h(value):
    return html.escape(str(value or ""), quote=True)


def read_text_file(path, limit=40000):
    try:
        text = path.read_text(errors="replace")
    except OSError as exc:
        return f"Could not read file: {exc}"
    return text[-limit:]


def relative_files(base, suffix):
    if not base.exists():
        return []
    files = [p for p in base.rglob(f"*{suffix}") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def build_command(job):
    source_type = job.get("source_type", "topic")
    max_videos = str(max(1, int(job.get("max_videos") or 1)))
    topic = job.get("topic") or job.get("name") or "AI Trends"
    report_folder = clean_report_folder(job.get("report_folder") or "", slugify(topic))

    if source_type == "claude_code_subtopic":
        only = topic.lower().replace("claude code", "").strip() or topic
        cmd = [
            "bash",
            str(RUN_SUBTOPICS),
            "--only",
            only,
            "--max-results",
            max_videos,
            "--total-videos",
            max_videos,
        ]
    else:
        cmd = [
            "bash",
            str(RUN_TOPIC),
            "--topic",
            topic,
            "--report-folder",
            report_folder,
            "--config-job-id",
            job.get("id", ""),
        ]
        if source_type in {"channel", "playlist"} and job.get("source_url"):
            # Some channel/handle fetches return more unique videos than --playlist-end;
            # --count enforces the dashboard's Number of Videos at processing time.
            cmd.extend(["--channel", job["source_url"], "--max-results", max_videos, "--count", max_videos])
        elif source_type == "video" and job.get("source_url"):
            cmd.extend(["--video-url", job["source_url"], "--count", "1"])
        else:
            cmd.extend(["--max-results", max_videos])

        transcript_langs = job.get("transcript_langs")
        if isinstance(transcript_langs, list):
            transcript_langs = ",".join(str(x).strip() for x in transcript_langs if str(x).strip())
        if transcript_langs:
            cmd.extend(["--transcript-langs", str(transcript_langs)])
        if job.get("on_demand", False):
            cmd.append("--on-demand")

    if job.get("detailed", True):
        cmd.append("--detailed")
    return cmd


def run_job(job):
    job_id = job["id"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"{job_id}_{timestamp}.log"

    with RUN_LOCK:
        status = load_status()
        status[job_id] = {
            "state": "running",
            "last_started_at": now_text(),
            "last_finished_at": "",
            "exit_code": None,
            "latest_log": str(log_file),
            "latest_report": "",
        }
        save_status(status)

        cmd = build_command(job)
        with log_file.open("w") as log:
            log.write(f"[{now_text()}] Running: {' '.join(cmd)}\n\n")
            log.flush()
            result = subprocess.run(cmd, cwd=PROJECT_ROOT, stdout=log, stderr=subprocess.STDOUT, text=True)
            log.write(f"\n[{now_text()}] Exit code: {result.returncode}\n")

        latest_report = ""
        reports = report_files_for_job(job)
        if reports:
            latest_report = str(reports[0])

        status = load_status()
        status[job_id] = {
            "state": "success" if result.returncode == 0 else "failed",
            "last_started_at": status.get(job_id, {}).get("last_started_at", ""),
            "last_finished_at": now_text(),
            "exit_code": result.returncode,
            "latest_log": str(log_file),
            "latest_report": latest_report,
        }
        save_status(status)


def start_job(job):
    thread = threading.Thread(target=run_job, args=(job,), daemon=True)
    thread.start()


# Set by do_GET/do_POST per-request when accessed via the unified demo domain
# path prefix (e.g. /ats/...) instead of ATS's own subdomain.
_req_ctx = threading.local()

def _url_prefix() -> str:
    return getattr(_req_ctx, "prefix", "")

def _other_app_links() -> tuple:
    if _url_prefix():
        return "/mjs/", "/faw/"
    return "https://mjs.thequietself.com/", "https://faw.thequietself.com/"

_ICONS = {
    "newspaper": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/></svg>',
    "file-text": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
    "search": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    "box": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>',
    "bell": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>',
    "clock": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
}

def page(title, body):
    p = _url_prefix()
    mjs_href, faw_href = _other_app_links()
    I = _ICONS
    v = _ui_ver()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{h(title)}</title>
  <script>(function(){{try{{var t=localStorage.getItem('sati-ui-theme');if(t)document.documentElement.setAttribute('data-theme',t);}}catch(e){{}}}})();</script>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
  <link rel="stylesheet" href="{p}/shared-ui/theme.css?v={v}">
  <style>
    /* Local names ATS's own CSS below already uses, re-aliased onto the
       shared theme.css tokens (loaded above) instead of hardcoded light
       values — this is what was overriding the shared dark theme. */
    :root {{
      --line:var(--border); --ink:var(--text-primary); --muted:var(--text-secondary); --panel:var(--surface);
      --blue:var(--info); --green:var(--success); --red:var(--danger);
      --accent-soft:var(--accent-subtle);
      --font-shared: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: var(--font-shared); background:var(--bg); color:var(--ink); }}
    a {{ color:var(--accent-text,var(--accent)); }}
    a:visited {{ color:var(--accent-text,var(--accent)); }}
    header {{ background:#111827; color:white; padding:16px 24px; display:flex; align-items:center; justify-content:space-between; gap:16px; border-bottom:2px solid var(--accent); }}
    header a {{ color:white; text-decoration:none; margin-left:14px; }}
    header a:hover {{ color:var(--accent-soft); }}
    main {{ max-width:1180px; margin:0 auto; padding:22px; }}
    h1 {{ font-size:24px; margin:0 0 14px; }}
    h2 {{ font-size:18px; margin:24px 0 10px; }}
    .grid {{ display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:12px; }}
    .metric, section {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px; }}
    .metric strong {{ display:block; font-size:22px; margin-top:4px; }}
    table {{ width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); border-radius:10px; overflow:hidden; }}
    th, td {{ padding:10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; font-size:14px; }}
    th {{ background:var(--surface-hover,#eef2f7); font-size:12px; text-transform:uppercase; color:var(--muted); }}
    tr:last-child td {{ border-bottom:0; }}
    .actions {{ display:flex; gap:8px; flex-wrap:wrap; }}
    button, .button {{ appearance:none; border:1px solid var(--accent); background:var(--accent); color:white; padding:8px 10px; border-radius:6px; text-decoration:none; cursor:pointer; font-size:14px; transition:background .15s,border-color .15s; }}
    button:hover, .button:hover {{ background:var(--accent-hover); border-color:var(--accent-hover); }}
    .button.secondary, button.secondary {{ background:white; color:var(--accent); }}
    .button.secondary:hover, button.secondary:hover {{ background:var(--accent-soft); }}
    button.danger {{ border-color:var(--red); background:var(--red); }}
    input, select, textarea {{ width:100%; padding:9px; border:1px solid var(--line); border-radius:6px; font:inherit; background:var(--panel); color:var(--ink); }}
    input:focus, select:focus, textarea:focus {{ outline:none; border-color:var(--accent); }}
    label {{ display:block; font-size:13px; color:var(--muted); margin:12px 0 5px; }}
    form.inline {{ display:inline; }}
    .form-grid {{ display:grid; grid-template-columns: 1fr 1fr; gap:0 14px; }}
    .muted {{ color:var(--muted); }}
    .pill {{ display:inline-block; border-radius:999px; padding:3px 8px; background:var(--surface-hover,#edf2f7); color:var(--text-secondary,#334155); font-size:12px; }}
    .success {{ color:var(--green); }}
    .failed {{ color:var(--red); }}
    pre {{ white-space:pre-wrap; background:#101828; color:#f8fafc; padding:14px; border-radius:8px; overflow:auto; max-height:560px; }}
    @media (max-width: 760px) {{ .grid, .form-grid {{ grid-template-columns:1fr; }} header {{ display:block; }} header nav {{ margin-top:8px; }} }}
  </style>
</head>
<body class="su-shell">
  <button id="su-hamburger" class="su-hamburger" aria-label="Menu">☰</button>
  <div class="su-backdrop"></div>
  <nav class="su-sidebar">
    <div class="su-sidebar-header">
      <span class="su-logo-tile">⚡</span>
      <span class="su-wordmark">Content Engine</span>
    </div>
    <div class="su-app-switch">
      <a href="{mjs_href}">MJS</a>
      <a href="{faw_href}">FAW</a>
      <a href="{p}/" class="active">ATS</a>
    </div>
    <div class="su-sidebar-nav">
      <div class="su-nav-label">Research</div>
      <a class="su-nav-item" href="{p}/">{I['newspaper']}<span class="su-label">Jobs</span></a>
      <a class="su-nav-item" href="{p}/reports">{I['file-text']}<span class="su-label">Reports</span></a>
      <a class="su-nav-item" href="{p}/search">{I['search']}<span class="su-label">Search</span></a>
      <div class="su-nav-label">Content</div>
      <a class="su-nav-item" href="{p}/assets">{I['box']}<span class="su-label">Assets</span></a>
      <div class="su-nav-label">System</div>
      <a class="su-nav-item" href="{p}/notifications">{I['bell']}<span class="su-label">Notifications</span></a>
      <a class="su-nav-item" href="{p}/logs">{I['file-text']}<span class="su-label">Logs</span></a>
      <a class="su-nav-item" href="{p}/cron">{I['clock']}<span class="su-label">Cron</span></a>
    </div>
    <div class="su-sidebar-footer">
      <div class="su-toggle-row">
        <button class="su-icon-btn" id="su-collapse-toggle" title="Collapse sidebar">⇔</button>
        <div class="su-theme-pill">
          <button data-mode="light">☀</button>
          <button data-mode="dark">☾</button>
        </div>
      </div>
    </div>
  </nav>
  <main>{body}</main>
  <script src="{p}/shared-ui/sidebar.js?v={v}"></script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def _strip_prefix(self):
        _req_ctx.prefix = ""
        _p = urlparse(self.path)
        if _p.path == "/ats" or _p.path.startswith("/ats/"):
            _req_ctx.prefix = "/ats"
            new_path = _p.path[len("/ats"):] or "/"
            self.path = new_path + (("?" + _p.query) if _p.query else "")

    def do_GET(self):
        self._strip_prefix()
        parsed = urlparse(self.path)
        if parsed.path == "/shared-ui/theme.css":
            self.send_static((SHARED_UI_DIR / "theme.css").read_text(), "text/css; charset=utf-8")
        elif parsed.path == "/shared-ui/sidebar.js":
            self.send_static((SHARED_UI_DIR / "sidebar.js").read_text(), "application/javascript; charset=utf-8")
        elif parsed.path == "/":
            self.render_home()
        elif parsed.path == "/job":
            self.render_job_form(parse_qs(parsed.query).get("id", [""])[0])
        elif parsed.path == "/reports":
            self.render_files(REPORTS_DIR, ".md", "Reports")
        elif parsed.path == "/report":
            self.render_single_report()
        elif parsed.path == "/logs":
            self.render_files(LOGS_DIR, ".log", "Dashboard Logs")
        elif parsed.path == "/cron":
            self.render_cron()
        elif parsed.path == "/search":
            self.render_search()
        elif parsed.path == "/api/search":
            self.api_search()
        elif parsed.path == "/api/search/rebuild":
            self.api_search_rebuild()
        elif parsed.path == "/assets":
            self.render_assets()
        elif parsed.path == "/assets/manage":
            self.render_assets_manage()
        elif parsed.path == "/api/assets/videos":
            self.api_assets_videos()
        elif parsed.path == "/api/catalog":
            self.api_catalog()
        elif parsed.path == "/api/assets/generate":
            self.api_assets_generate()
        elif parsed.path == "/api/assets/generate-one":
            self.api_assets_generate_one()
        elif parsed.path == "/api/assets/progress":
            self.api_assets_progress()
        elif parsed.path == "/api/assets/gen-status":
            self.api_assets_gen_status()
        elif parsed.path == "/api/assets/script":
            self.api_assets_script_get()
        elif parsed.path == "/api/assets/voice-status":
            self.api_assets_voice_status()
        elif parsed.path == "/api/audio/serve":
            self.api_audio_serve()
        elif parsed.path == "/api/voice/serve":
            self.api_voice_serve()
        elif parsed.path == "/api/social/view":
            self.api_social_view()
        elif parsed.path == "/notifications":
            self.render_notifications()
        elif parsed.path == "/api/notifications/config":
            self.api_notifications_config_get()
        elif parsed.path == "/api/audio/config":
            self.api_audio_config_get()
        elif parsed.path == "/download/report":
            self.download_report()
        elif parsed.path == "/view/report":
            self.view_report()
        elif parsed.path == "/view/full-detail":
            self.view_full_detail()
        elif parsed.path == "/download/full-detail":
            self.download_full_detail()
        elif parsed.path == "/view/audio":
            self.view_audio()
        else:
            self.send_error(404)

    def do_POST(self):
        self._strip_prefix()
        parsed = urlparse(self.path)
        # Notifications API uses JSON body — handle before form-urlencoded parsing
        if parsed.path in ("/api/notifications/config", "/api/notifications/test", "/api/audio/config"):
            length = int(self.headers.get("content-length", "0"))
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                json_body = json.loads(raw) if raw.strip() else {}
            except Exception:
                json_body = {}
            if parsed.path == "/api/notifications/config":
                self.api_notifications_config_save(json_body)
            elif parsed.path == "/api/audio/config":
                self.api_audio_config_save(json_body)
            else:
                self.api_notifications_test(json_body)
            return
        length = int(self.headers.get("content-length", "0"))
        data = parse_qs(self.rfile.read(length).decode())
        if parsed.path == "/job/save":
            self.save_job(data)
        elif parsed.path == "/job/delete":
            self.delete_job(data)
        elif parsed.path == "/job/run":
            self.run_job_action(data)
        elif parsed.path == "/api/assets/script":
            self.api_assets_script_save(data)
        elif parsed.path == "/api/assets/generate-deep-dive-script":
            self.api_assets_generate_deep_dive_script(data)
        elif parsed.path == "/api/assets/generate-full-detail":
            self.api_assets_generate_full_detail(data)
        elif parsed.path == "/api/assets/generate-voice":
            self.api_assets_generate_voice(data)
        else:
            self.send_error(404)

    def send_html(self, html_text, code=200):
        encoded = html_text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def send_static(self, text, content_type):
        encoded = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(encoded)

    def redirect(self, target="/"):
        if target.startswith("/") and _url_prefix():
            target = _url_prefix() + target
        self.send_response(303)
        self.send_header("Location", target)
        self.end_headers()

    def render_home(self):
        jobs = load_jobs()
        status = load_status()
        rows = []
        for job in jobs:
            st = status.get(job["id"], {})
            state = st.get("state", "not run")
            is_enabled = job.get("enabled", True)
            enabled_badge = '<span style="color:#16a34a;font-weight:600;font-size:12px">● Enabled</span>' if is_enabled else '<span style="color:#dc2626;font-weight:600;font-size:12px">○ Disabled</span>'
            rows.append(f"""<tr>
  <td><strong>{h(job.get('name'))}</strong><br><span class="muted">{h(job.get('id'))}</span></td>
  <td><span class="pill">{h(job.get('source_type'))}</span><br>{h(job.get('topic'))}</td>
  <td>{h(job.get('source_url'))}</td>
  <td>{h(job.get('max_videos'))}</td>
  <td>{h(job.get('report_folder'))}</td>
  <td>{enabled_badge}<br><span class="{h(state)}" style="font-size:12px">{h(state)}</span><br><span class="muted" style="font-size:11px">{h(st.get('last_finished_at') or st.get('last_started_at') or '')}</span></td>
  <td class="actions">
    <a class="button secondary" href="/job?id={quote(job['id'])}">Edit</a>
    {'<form class="inline" method="post" action="/job/run"><input type="hidden" name="id" value="' + h(job['id']) + '"><button type="submit">Run</button></form>' if is_enabled else '<button type="button" class="secondary" disabled title="Job is disabled">Run disabled</button>'}
  </td>
</tr>""")

        duplicate_groups = duplicate_schedule_groups(jobs)
        duplicate_warning = ""
        if duplicate_groups:
            items = []
            for schedule_time, group in duplicate_groups.items():
                names = ", ".join(h(j.get("name") or j.get("id")) for j in group)
                items.append(f"<li><strong>{h(schedule_time)}</strong>: {names}</li>")
            duplicate_warning = f"""<section style="border-color:#f59e0b;background:#fff7ed;color:#78350f">
  <h2 style="color:#78350f">⚠️ Duplicate Daily Cron Times</h2>
  <p class="muted" style="color:#92400e">เวลานี้มีหลาย jobs ที่เปิด Add to Daily Cron อยู่ ระบบยังรันได้ แต่จะเริ่มพร้อมกัน อาจกิน quota/CPU พร้อมกันค่ะ</p>
  <ul>{''.join(items)}</ul>
</section>"""
        enabled = sum(1 for j in jobs if j.get("enabled"))
        running = sum(1 for s in status.values() if s.get("state") == "running")
        body = f"""<h1>Research Jobs</h1>
<div class="grid">
  <div class="metric"><span class="muted">Jobs</span><strong>{len(jobs)}</strong></div>
  <div class="metric"><span class="muted">Enabled</span><strong>{enabled}</strong></div>
  <div class="metric"><span class="muted">Running</span><strong>{running}</strong></div>
  <div class="metric"><span class="muted">Config</span><strong>JSON</strong></div>
</div>
<p><a class="button" href="/job">Add Job</a> <a class="button secondary" href="/reports">View Reports</a></p>
{duplicate_warning}
<table>
  <thead><tr><th>Name</th><th>Source</th><th>URL</th><th>Videos</th><th>Folder</th><th>Status</th><th>Actions</th></tr></thead>
  <tbody>{''.join(rows) if rows else '<tr><td colspan="7">No jobs configured.</td></tr>'}</tbody>
</table>"""
        self.send_html(page("AI Trends Dashboard", body))

    def render_job_form(self, job_id):
        jobs = load_jobs()
        job = next((j for j in jobs if j.get("id") == job_id), {})
        is_new = not job
        options = "".join(
            f'<option value="{h(t)}" {"selected" if job.get("source_type", "topic") == t else ""}>{h(t)}</option>'
            for t in SOURCE_TYPES
        )
        job_id_field = (
            '<input type="hidden" name="id" value="">'
            '<div><label>Job ID</label><div class="muted" style="padding:9px 0">Auto-generated after Save</div></div>'
            if is_new else
            f'<div><label>Job ID</label><input name="id" value="{h(job.get("id"))}" readonly></div>'
        )
        enabled_default = job.get('enabled', True)
        on_demand_default = job.get('on_demand', False)
        include_summary_default = job.get('include_in_daily_summary', True if is_new else False)
        daily_cron_default = job.get('daily_cron_enabled', bool(job.get('schedule_time'))) if not is_new else False
        schedule_options = schedule_slot_options(jobs, current_job_id=job.get('id'), current_value=job.get('schedule_time', ''))
        source_language_default = job.get('source_language', DEFAULT_SOURCE_LANGUAGE)
        transcript_langs_default = job.get('transcript_langs', DEFAULT_TRANSCRIPT_LANGS)
        if isinstance(transcript_langs_default, list):
            transcript_langs_default = ",".join(transcript_langs_default)
        current_report_folder = job.get('report_folder') or ''
        default_folder_preview = default_report_folder_for_job(job.get('topic', ''), job.get('name', ''), job.get('source_url', ''), job.get('id', '')) if not is_new else 'auto from Topic, e.g. VidIQ → vidiq; On Demand → on_demand/vidiq'
        conflicts = schedule_time_conflicts(jobs, job.get('schedule_time'), current_job_id=job.get('id')) if daily_cron_default else []
        conflict_warning = ""
        if conflicts:
            names = ", ".join(h(j.get("name") or j.get("id")) for j in conflicts)
            conflict_warning = f"""<section style="border-color:#f59e0b;background:#fff7ed;color:#78350f">
  <strong style="color:#78350f">⚠️ Schedule Time ซ้ำ</strong>
  <p class="muted" style="color:#92400e">เวลา {h(job.get('schedule_time'))} มี job อื่นเปิด daily cron อยู่แล้ว: {names}</p>
</section>"""
        body = f"""<h1>{'Add Job' if is_new else 'Edit Job'}</h1>
{conflict_warning}
<section>
<form method="post" action="/job/save">
  <div class="form-grid">
    {job_id_field}
    <div><label>Name</label><input name="name" value="{h(job.get('name'))}" required></div>
    <div><label>Source Type</label><select name="source_type">{options}</select></div>
    <div><label>Topic / Search Query</label><input name="topic" id="topic_input" value="{h(job.get('topic'))}" placeholder="เช่น VidIQ หรือ OpenAI Codex" required><div class="muted" style="font-size:12px;margin-top:4px">ระบบใช้ค่านี้เป็นคำค้น/ชื่อหัวข้อในรายงาน ไม่ใช่ชื่อโฟลเดอร์ที่ต้องจำเอง</div></div>
    <div><label>Source URL</label><input name="source_url" value="{h(job.get('source_url'))}" placeholder="Channel, playlist, or single video URL"></div>
    <div><label>Number of Videos</label><input name="max_videos" type="number" min="1" max="50" value="{h(job.get('max_videos', 3))}"></div>
    <div><label>Report Folder <span class="muted">(optional)</span></label><input name="report_folder" id="report_folder" value="{h(current_report_folder)}" placeholder="Auto-generate from Topic"><div class="muted" style="font-size:12px;margin-top:4px">ปล่อยว่างได้ — ระบบจะสร้าง lowercase folder ให้อัตโนมัติ: <code id="folder_preview">{h(default_folder_preview)}</code>. ห้ามใช้ <code>research_job</code> สำหรับ daily jobs เพราะเป็น legacy/reference bucket.</div></div>
    <div><label>Schedule Time <span class="muted">(select a supported slot)</span></label><select name="schedule_time" id="schedule_time">{schedule_options}</select></div>
    <input type="hidden" name="source_language" value="{h(source_language_default)}">
    <input type="hidden" name="transcript_langs" value="{h(transcript_langs_default)}">
  </div>
  <p class="muted">เลือกเวลาจาก dropdown เท่านั้นเพื่อกัน cron format ผิด/เวลาชนกัน ถ้าไม่ต้องการ daily cron ให้เลือก Manual only และปิด Add to Daily Cron</p>
  <label>Notes</label><textarea name="notes" rows="3">{h(job.get('notes'))}</textarea>
  <p>
    <label><input type="checkbox" name="enabled" value="1" {'checked' if enabled_default else ''} style="width:auto"> Job Enabled <span class="muted">(off = keep config but block Run and cron)</span></label>
    <label><input type="checkbox" name="daily_cron_enabled" id="daily_cron_enabled" value="1" {'checked' if daily_cron_default else ''} style="width:auto"> Add to Daily Cron <span class="muted">(Save syncs production cron)</span></label>
    <label><input type="checkbox" name="on_demand" id="on_demand" value="1" {'checked' if on_demand_default else ''} style="width:auto"> On Demand Report <span class="muted">(manual run only; unique readable filename per run; prevents overwrite)</span></label>
    <label><input type="checkbox" name="include_in_daily_summary" id="include_in_daily_summary" value="1" {'checked' if include_summary_default else ''} style="width:auto"> Include in Daily Summary <span class="muted">(ให้ digest ดึง report ของ job นี้ด้วย)</span></label>
    <label><input type="checkbox" name="detailed" value="1" {'checked' if job.get('detailed', True) else ''} style="width:auto"> Detailed Thai summary</label>
  </p>
  <script>
    const dailyCron = document.getElementById('daily_cron_enabled');
    const onDemand = document.getElementById('on_demand');
    const includeSummary = document.getElementById('include_in_daily_summary');
    const scheduleSelect = document.getElementById('schedule_time');
    const topicInput = document.getElementById('topic_input');
    const folderInput = document.getElementById('report_folder');
    const folderPreview = document.getElementById('folder_preview');
    function slugifyFolder(value) {{
      const slug = String(value || '').trim().toLowerCase()
        .replace(/[\\s-]+/g, '_')
        .replace(/[^a-z0-9_\\/]+/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_+|_+$/g, '');
      return slug || 'auto_after_save';
    }}
    function syncFolderPreview() {{
      if (!folderPreview) return;
      const explicit = folderInput && folderInput.value.trim();
      const raw = explicit || (topicInput && topicInput.value) || '';
      let preview = slugifyFolder(raw);
      if (!explicit && onDemand && onDemand.checked) preview = `on_demand/${{preview}}`;
      if (!explicit && preview === 'research_job') preview = 'auto_after_save';
      if (explicit && preview === 'research_job') preview = onDemand && onDemand.checked ? 'on_demand/research_job' : 'auto from Topic (research_job is reserved)';
      folderPreview.textContent = preview;
    }}
    function syncOnDemandMode() {{
      if (!onDemand) return;
      if (onDemand.checked) {{
        if (dailyCron) {{ dailyCron.checked = false; dailyCron.disabled = true; }}
        if (scheduleSelect) {{ scheduleSelect.value = ''; scheduleSelect.disabled = true; }}
        if (includeSummary) {{ includeSummary.checked = false; }}
      }} else {{
        if (dailyCron) dailyCron.disabled = false;
        if (scheduleSelect) scheduleSelect.disabled = false;
      }}
      syncFolderPreview();
      syncScheduleHint();
    }}
    function syncScheduleHint() {{
      if (dailyCron && scheduleSelect && dailyCron.checked && !scheduleSelect.value) {{
        scheduleSelect.setCustomValidity('Please choose a schedule time for daily cron.');
      }} else if (scheduleSelect) {{
        scheduleSelect.setCustomValidity('');
      }}
    }}
    if (dailyCron && scheduleSelect) {{
      dailyCron.addEventListener('change', syncScheduleHint);
      scheduleSelect.addEventListener('change', syncScheduleHint);
      syncScheduleHint();
    }}
    if (topicInput) topicInput.addEventListener('input', syncFolderPreview);
    if (folderInput) folderInput.addEventListener('input', syncFolderPreview);
    if (onDemand) onDemand.addEventListener('change', syncOnDemandMode);
    syncOnDemandMode();
    syncFolderPreview();
  </script>
  <button type="submit">Save</button>
  <a class="button secondary" href="/">Cancel</a>
</form>
</section>
{'' if is_new else f'<form method="post" action="/job/delete" style="margin-top:12px"><input type="hidden" name="id" value="{h(job.get("id"))}"><button class="danger" type="submit">Delete Job</button></form>'}"""
        self.send_html(page("Job", body))

    def render_files(self, base, suffix, title):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        selected = qs.get("file", [""])[0]
        content = ""
        if selected:
            try:
                path = _resolve_relative_file(base, selected)
                if path:
                    text = read_text_file(path)
                    content = build_file_preview_html(text, selected, suffix)
            except OSError:
                content = "<p>Invalid file.</p>"

        is_reports = (base.resolve() == REPORTS_DIR.resolve())
        rows = []
        for path in relative_files(base, suffix):
            rel = path.relative_to(base).as_posix()
            mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            parts = rel.split("/")
            # Use full folder path (all parts except filename) as topic key
            topic = "/".join(parts[:-1]) if len(parts) > 1 else ""
            date_part = report_date_key(parts[-1], suffix) if is_reports else ""
            data_attrs = f' data-topic="{h(topic)}" data-date="{h(date_part)}"' if is_reports else ""
            selected_class = ' class="selected-row"' if rel == selected else ""
            rows.append(f'<tr{data_attrs}{selected_class}><td><a href="{parsed.path}?file={quote(rel)}">{h(rel)}</a></td><td>{h(mtime)}</td></tr>')

        filter_ui = ""
        if is_reports:
            # Build topic list from research_jobs.json report_folder values — canonical source
            jobs = load_jobs()
            job_topics = sorted({
                j.get("report_folder", "").strip()
                for j in jobs
                if j.get("report_folder", "").strip()
            })
            topic_opts = "".join(f'<option value="{h(t)}">{h(t)}</option>' for t in job_topics)
            filter_ui = f"""<div id="report-filters" style="margin-bottom:16px">
  <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px">
    <select id="filter-topic" style="padding:7px 10px;border-radius:6px;border:1px solid #ccc;font-size:14px;min-width:180px">
      <option value="">All Topics</option>
      {topic_opts}
    </select>
    <input id="filter-date" type="date" style="padding:7px 10px;border-radius:6px;border:1px solid #ccc;font-size:14px">
    <select id="filter-month" style="padding:7px 10px;border-radius:6px;border:1px solid #ccc;font-size:14px">
      <option value="">All Months</option>
    </select>
  </div>
  <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
    <button onclick="setQuickDate('today')" id="btn-today" style="padding:5px 14px;border-radius:20px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer;font-size:13px">Today</button>
    <button onclick="setQuickDate('yesterday')" id="btn-yesterday" style="padding:5px 14px;border-radius:20px;border:1px solid var(--border,#ccc);background:var(--surface-hover,#f5f5f5);color:var(--text-primary);cursor:pointer;font-size:13px">Yesterday</button>
    <button onclick="setQuickDate('week')" id="btn-week" style="padding:5px 14px;border-radius:20px;border:1px solid var(--border,#ccc);background:var(--surface-hover,#f5f5f5);color:var(--text-primary);cursor:pointer;font-size:13px">7 Days</button>
    <button onclick="setQuickDate('all')" id="btn-all" style="padding:5px 14px;border-radius:20px;border:1px solid var(--border,#ccc);background:var(--surface-hover,#f5f5f5);color:var(--text-primary);cursor:pointer;font-size:13px">All</button>
    <span id="filter-count" style="color:#888;font-size:13px;margin-left:4px"></span>
  </div>
</div>
<script>
var _quickMode='today';
function fmtDate(d){{return d.toISOString().slice(0,10);}}
function todayStr(){{return fmtDate(new Date());}}
function yesterdayStr(){{var d=new Date();d.setDate(d.getDate()-1);return fmtDate(d);}}
function weekDates(){{
  var dates=[]; var d=new Date();
  for(var i=0;i<7;i++){{dates.push(fmtDate(d));d.setDate(d.getDate()-1);}}
  return dates;
}}
function setActiveBtn(mode){{
  ['today','yesterday','week','all'].forEach(function(m){{
    var b=document.getElementById('btn-'+m);
    if(b){{b.style.background=m===mode?'var(--accent)':'var(--surface-hover,#f5f5f5)';b.style.color=m===mode?'#fff':'var(--text-primary)';b.style.borderColor=m===mode?'var(--accent)':'var(--border,#ccc)';}}
  }});
}}
function setQuickDate(mode){{
  _quickMode=mode;
  setActiveBtn(mode);
  document.getElementById('filter-month').value='';
  if(mode==='today'){{document.getElementById('filter-date').value=todayStr();}}
  else if(mode==='yesterday'){{document.getElementById('filter-date').value=yesterdayStr();}}
  else{{document.getElementById('filter-date').value='';}}
  applyFilters();
}}
function applyFilters(){{
  var topic=(document.getElementById('filter-topic').value||'').toLowerCase();
  var rows=document.querySelectorAll('#file-table tbody tr[data-topic]');
  var shown=0;
  var wdates=_quickMode==='week'?weekDates():null;
  rows.forEach(function(r){{
    var tm=(r.dataset.topic||'').toLowerCase();
    var dt=r.dataset.date||'';
    var topicOk=(!topic||(tm===topic||tm.startsWith(topic+'/')));
    var dateOk=true;
    if(_quickMode==='today'){{dateOk=dt===todayStr();}}
    else if(_quickMode==='yesterday'){{dateOk=dt===yesterdayStr();}}
    else if(_quickMode==='week'){{dateOk=wdates.indexOf(dt)!==-1;}}
    else if(_quickMode==='month'){{
      var mv=document.getElementById('filter-month').value;
      dateOk=mv?dt.startsWith(mv):true;
    }}
    else if(_quickMode==='date'){{
      var dv=document.getElementById('filter-date').value;
      dateOk=dv?dt===dv:true;
    }}
    var ok=topicOk&&dateOk;
    r.style.display=ok?'':'none';
    if(ok)shown++;
  }});
  document.getElementById('filter-count').textContent=shown+' reports';
}}
function buildMonthDropdown(){{
  var months={{}};
  document.querySelectorAll('#file-table tbody tr[data-date]').forEach(function(r){{
    var d=r.dataset.date||'';
    if(d.length>=7){{var m=d.slice(0,7);months[m]=1;}}
  }});
  var sel=document.getElementById('filter-month');
  Object.keys(months).sort().reverse().forEach(function(m){{
    var opt=document.createElement('option');opt.value=m;
    var parts=m.split('-');var yr=parts[0];var mo=parseInt(parts[1]);
    var names=['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    opt.textContent=names[mo]+' '+yr;sel.appendChild(opt);
  }});
}}
document.getElementById('filter-topic').addEventListener('change',applyFilters);
document.getElementById('filter-date').addEventListener('change',function(){{
  if(this.value){{_quickMode='date';setActiveBtn('');document.getElementById('filter-month').value='';}}
  else{{_quickMode='all';setActiveBtn('all');}}
  applyFilters();
}});
document.getElementById('filter-month').addEventListener('change',function(){{
  if(this.value){{_quickMode='month';setActiveBtn('');document.getElementById('filter-date').value='';}}
  else{{_quickMode='all';setActiveBtn('all');}}
  applyFilters();
}});
window.addEventListener('DOMContentLoaded',function(){{buildMonthDropdown();setQuickDate('today');}});
</script>"""

        back_link = f'<p style="margin-bottom:12px"><a href="{parsed.path}">← กลับไปรายการ</a></p>' if content and is_reports else ""
        body = f"""<h1>{h(title)}</h1>
{content}
{back_link}
{filter_ui}
<table id="file-table"><thead><tr><th>File</th><th>Modified</th></tr></thead><tbody>{''.join(rows) if rows else '<tr><td colspan="2">No files found.</td></tr>'}</tbody></table>
<style>#file-table tr.selected-row td{{background:#fffbe6}}</style>"""
        self.send_html(page(title, body))

    def render_single_report(self):
        qs = parse_qs(urlparse(self.path).query)
        selected = qs.get("file", [""])[0]
        if not selected:
            self.send_html(page("Report", '<h1>Report</h1><p class="failed">No file specified.</p>'))
            return
        try:
            path = _resolve_relative_file(REPORTS_DIR, selected)
            if not path:
                self.send_html(page("Report", '<h1>Report</h1><p class="failed">File not found.</p>'))
                return
            text = read_text_file(path)
            # Render as formatted Markdown (headers, bold, lists) instead of a
            # raw escaped-text dump — matches how view_report()/view_full_detail()
            # already display reports elsewhere in this dashboard; the file on
            # disk is untouched, this only changes how it looks when viewed here.
            if _MD_OK:
                rendered = _md_lib.markdown(text, extensions=["nl2br", "fenced_code"])
            else:
                rendered = f"<pre style='white-space:pre-wrap;word-break:break-word'>{h(text)}</pre>"
            body = (
                f'<p><a href="/search">← Back to Search</a></p>'
                f'<h2>{h(selected)}</h2>'
                f'<style>.markdown-body{{line-height:1.7;font-size:15px}}'
                f'.markdown-body h1{{font-size:1.4em}}.markdown-body h2{{font-size:1.2em;border-bottom:1px solid var(--line);padding-bottom:4px}}'
                f'.markdown-body h3{{font-size:1.05em}}.markdown-body hr{{border:none;border-top:1px solid var(--line);margin:16px 0}}'
                f'.markdown-body code{{background:#eef2f7;border-radius:4px;padding:2px 6px;font-size:13px}}'
                f'.markdown-body pre{{background:#eef2f7;border-radius:6px;padding:12px;overflow-x:auto}}'
                f'.markdown-body ul,.markdown-body ol{{padding-left:1.4em}}</style>'
                f'<div class="markdown-body">{rendered}</div>'
            )
            self.send_html(page(selected, body))
        except OSError:
            self.send_html(page("Report", '<h1>Report</h1><p class="failed">Could not read file.</p>'))

    def render_cron(self):
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        cron = result.stdout if result.returncode == 0 else result.stderr
        body = f"""<h1>Production Cron</h1>
<section>
  <p class="muted">Dashboard-managed ATS research cron. Saving a job with Add to Daily Cron syncs these lines.</p>
  <pre>{h(cron)}</pre>
</section>"""
        self.send_html(page("Cron", body))

    def save_job(self, data):
        jobs = load_jobs()
        requested_id = slugify(data.get("id", [""])[0])
        existing = next((j for j in jobs if j.get("id") == requested_id), None) if requested_id else None
        topic = data.get("topic", [""])[0].strip()
        name = data.get("name", [topic])[0].strip() or topic
        source_url = data.get("source_url", [""])[0].strip()
        # For new jobs, Job ID is generated by the system from topic/name/source URL
        # and made unique with a numeric suffix when needed.
        job_id = requested_id if existing else unique_job_id(topic or name or source_url, jobs)
        on_demand = data.get("on_demand", ["0"])[0] == "1"
        report_folder = normalize_report_folder_for_save(
            data.get("report_folder", [""])[0],
            topic,
            name,
            source_url,
            job_id,
            is_on_demand=on_demand,
        )
        if not on_demand:
            report_folder = unique_report_folder(report_folder, jobs, current_job_id=job_id)
        schedule_time = data.get("schedule_time", [""])[0].strip()
        daily_cron_enabled = data.get("daily_cron_enabled", ["0"])[0] == "1"
        include_in_daily_summary = data.get("include_in_daily_summary", ["0"])[0] == "1"
        if on_demand:
            schedule_time = ""
            daily_cron_enabled = False
            include_in_daily_summary = False
        raw_transcript_langs = data.get("transcript_langs", [""])[0].strip()
        if raw_transcript_langs:
            transcript_langs = [x.strip() for x in raw_transcript_langs.split(",") if x.strip()]
        else:
            transcript_langs = existing.get("transcript_langs", DEFAULT_TRANSCRIPT_LANGS) if existing else DEFAULT_TRANSCRIPT_LANGS
        source_language = data.get("source_language", [""])[0].strip()
        if not source_language:
            source_language = existing.get("source_language", DEFAULT_SOURCE_LANGUAGE) if existing else DEFAULT_SOURCE_LANGUAGE
        job = {
            "id": job_id,
            "name": name,
            "enabled": data.get("enabled", ["0"])[0] == "1",
            "source_type": data.get("source_type", ["topic"])[0],
            "topic": topic,
            "source_url": source_url,
            "max_videos": max(1, int(data.get("max_videos", ["3"])[0] or 3)),
            "detailed": data.get("detailed", ["0"])[0] == "1",
            "report_folder": report_folder,
            "schedule_time": schedule_time,
            "daily_cron_enabled": daily_cron_enabled,
            "on_demand": on_demand,
            "include_in_daily_summary": include_in_daily_summary,
            "notes": data.get("notes", [""])[0].strip(),
            "source_language": source_language,
            "transcript_langs": transcript_langs,
        }
        if daily_cron_enabled:
            if not schedule_time:
                self.send_html(page("Schedule required", '<h1>Schedule required</h1><p class="failed">Add to Daily Cron requires choosing a Schedule Time from the dropdown.</p><p><a href="/job">Back</a></p>'), code=400)
                return
            if schedule_time not in schedule_slot_values():
                self.send_html(page("Invalid schedule", f'<h1>Invalid schedule</h1><p class="failed">{h(schedule_time)} is not a supported ATS schedule slot. Please choose from the dropdown.</p><p><a href="/job">Back</a></p>'), code=400)
                return
            conflicts = schedule_time_conflicts(jobs, schedule_time, current_job_id=job_id)
            if conflicts:
                names = ", ".join(h(j.get("name") or j.get("id")) for j in conflicts)
                self.send_html(page("Schedule conflict", f'<h1>Schedule conflict</h1><p class="failed">{h(schedule_time)} is already used by: {names}. Please choose another dropdown time.</p><p><a href="/job">Back</a></p>'), code=400)
                return
        if existing:
            jobs[jobs.index(existing)] = job
        else:
            jobs.append(job)
        save_jobs(jobs)
        try:
            sync_dashboard_cron()
        except Exception as exc:
            self.send_html(page("Cron sync failed", f'<h1>Cron sync failed</h1><p class="failed">{h(exc)}</p><p><a href="/">Back to Jobs</a></p>'), code=500)
            return
        self.redirect("/")

    def delete_job(self, data):
        job_id = data.get("id", [""])[0]
        save_jobs([j for j in load_jobs() if j.get("id") != job_id])
        try:
            sync_dashboard_cron()
        except Exception as exc:
            self.send_html(page("Cron sync failed", f'<h1>Cron sync failed</h1><p class="failed">{h(exc)}</p><p><a href="/">Back to Jobs</a></p>'), code=500)
            return
        self.redirect("/")

    def run_job_action(self, data):
        job_id = data.get("id", [""])[0]
        job = next((j for j in load_jobs() if j.get("id") == job_id), None)
        if job and not job.get("enabled", True):
            status = load_status()
            status[job_id] = {
                "state": "disabled",
                "last_started_at": now_text(),
                "last_finished_at": now_text(),
                "exit_code": None,
                "latest_log": "",
                "latest_report": "",
            }
            save_status(status)
        elif job:
            start_job(job)
        self.redirect("/")

    # ── Search ────────────────────────────────────────────────

    def _search_index_path(self):
        return INDEX_DIR / "reports_index.jsonl"

    def _load_search_index(self):
        path = self._search_index_path()
        if not path.exists():
            return []
        return load_jsonl(str(path))

    def _available_topics(self, records):
        seen = set()
        topics = []
        for r in records:
            t = r.get("topic", "")
            if t and t not in seen:
                seen.add(t)
                topics.append(t)
        return topics

    def _available_tags(self, records):
        seen = set()
        tags = []
        for r in records:
            for t in r.get("tags", []):
                if t and t not in seen:
                    seen.add(t)
                    tags.append(t)
        return sorted(tags)

    def render_search(self):
        records = self._load_search_index()
        total = len(records)
        topics = self._available_topics(records)
        tags = self._available_tags(records)

        topic_options = "".join(f'<option value="{h(t)}">{h(t)}</option>' for t in topics)
        tag_options = "".join(f'<option value="{h(t)}">{h(t)}</option>' for t in tags)

        rebuild_note = ""
        if not _SEARCH_AVAILABLE:
            rebuild_note = '<p class="failed">⚠ Search module not available. Run: <code>pip install -r requirements.txt</code></p>'
        elif total == 0:
            rebuild_note = '<p class="failed">⚠ Index is empty. <a href="/api/search/rebuild" class="button" style="font-size:13px">Rebuild Index</a></p>'

        body = f"""<h1>🔍 Search Reports</h1>
{rebuild_note}
<section>
<p class="muted">{total} video sections indexed · Last rebuild: {datetime.fromtimestamp(self._search_index_path().stat().st_mtime).strftime('%Y-%m-%d %H:%M') if total else 'never'}</p>
<form id="searchForm" onsubmit="return doSearch(event)">
  <div class="form-grid">
    <div style="grid-column:1/-1">
      <label>Search query</label>
      <input id="sq" name="q" placeholder="e.g. claude code, NATEHERK, copywriting, seedance…" autofocus>
    </div>
    <div>
      <label>Topic</label>
      <select id="st" name="topic"><option value="">All topics</option>{topic_options}</select>
    </div>
    <div>
      <label>Tag</label>
      <select id="stag" name="tag"><option value="">All tags</option>{tag_options}</select>
    </div>
  </div>
  <p>
    <button type="submit">Search</button>
    <button type="button" class="secondary" onclick="clearSearch()">Clear</button>
    <a href="/api/search/rebuild" class="button secondary" style="font-size:13px">🔄 Rebuild Index</a>
  </p>
</form>
</section>
<div id="results"></div>
<script>
function doSearch(e){{
  e.preventDefault();
  var q=document.getElementById('sq').value;
  var t=document.getElementById('st').value;
  var tag=document.getElementById('stag').value;
  var params='?q='+encodeURIComponent(q);
  if(t)params+='&topic='+encodeURIComponent(t);
  if(tag)params+='&tag='+encodeURIComponent(tag);
  fetch('/api/search'+params)
    .then(function(r){{return r.json()}})
    .then(function(data){{
      var el=document.getElementById('results');
      if(!data.results||data.results.length===0){{
        el.innerHTML='<p class="muted">No results found.</p>';
        return;
      }}
      var html='<p class="muted">Found '+data.results.length+' result(s)</p><table><thead><tr><th>Date</th><th>Topic</th><th>Video</th><th>Summary</th><th>Tags</th><th>Report</th></tr></thead><tbody>';
      data.results.forEach(function(r){{
        var tags=r.tags.map(function(t){{return'<span class="pill">'+t+'</span>'}}).join(' ');
        var yt=r.source_url?'<a href="'+r.source_url+'" target="_blank" style="font-size:12px">▶ YouTube</a>':'';
        var rpt=r.report_path?'<a href="/report?file='+encodeURIComponent(r.report_path)+'" style="font-size:12px">📄 Report</a>':'';
        html+='<tr><td>'+r.date+'</td><td><span class="pill">'+r.topic+'</span></td>';
        html+='<td><strong>'+r.video_title+'</strong><br><span class="muted" style="font-size:13px">'+r.thai_title+'</span><br>'+yt+'</td>';
        html+='<td style="font-size:13px;max-width:360px">'+r.summary_short+'</td>';
        html+='<td style="font-size:12px">'+tags+'</td>';
        html+='<td>'+rpt+'</td></tr>';
      }});
      html+='</tbody></table>';
      el.innerHTML=html;
    }})
    .catch(function(err){{document.getElementById('results').innerHTML='<p class="failed">Search error: '+err+'</p>'}});
  return false;
}}
function clearSearch(){{
  document.getElementById('sq').value='';
  document.getElementById('st').value='';
  document.getElementById('stag').value='';
  document.getElementById('results').innerHTML='';
}}
</script>"""
        self.send_html(page("Search Reports", body))

    def api_search(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        query = qs.get("q", [""])[0]
        topic = qs.get("topic", [""])[0] or None
        tag = qs.get("tag", [""])[0] or None
        limit = min(50, max(1, int(qs.get("limit", ["20"])[0])))

        records = self._load_search_index()
        if not records:
            self._send_json({"results": [], "total_indexed": 0})
            return

        results = search_records(records, query, topic=topic, tag=tag)
        results = results[:limit]

        # Trim for JSON response
        out = []
        for r in results:
            out.append({
                "date": r.get("date", ""),
                "topic": r.get("topic", ""),
                "video_title": r.get("video_title", ""),
                "thai_title": r.get("thai_title", ""),
                "summary_short": r.get("summary_short", ""),
                "source_url": r.get("source_url", ""),
                "tags": r.get("tags", []),
                "report_path": r.get("report_path", ""),
                "score": r.get("score", 0),
            })

        self._send_json({"results": out, "total_indexed": len(records)})

    def api_search_rebuild(self):
        if not _SEARCH_AVAILABLE:
            self._send_json({"error": "Search module not available"}, code=500)
            return

        def _rebuild():
            records = build_index_records(str(REPORTS_DIR))
            write_indexes(records, str(INDEX_DIR))

        try:
            _rebuild()
            count = len(self._load_search_index())
            self._send_json({"status": "ok", "indexed": count})
        except Exception as exc:
            self._send_json({"error": str(exc)}, code=500)

    def _send_json(self, data, code=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── Content Assets ────────────────────────────────────────

    def _voice_script_paths(self, topic, date, video_no, script_type):
        """Return safe script/output paths for an asset video voice workflow."""
        safe_topic = _slug(topic)
        try:
            vno = int(video_no)
        except (TypeError, ValueError):
            raise ValueError("video must be a number")
        if not safe_topic or not re.match(r"^[A-Za-z0-9_]+$", safe_topic):
            raise ValueError("invalid topic")
        if not DATE_OR_REPORT_STEM_RE.match(date or ""):
            raise ValueError("invalid date")
        if vno < 1 or vno > 99:
            raise ValueError("invalid video number")
        if script_type not in ("full", "deep_dive"):
            raise ValueError("type must be full or deep_dive")

        audio_scripts_base = PROJECT_ROOT / "ai_trends_reports" / "audio_scripts"
        voice_base         = PROJECT_ROOT / "ai_trends_reports" / "voice"
        # Resolve actual folder names on disk (handles NATEHERK vs nateherk, Joanna Wiebe vs joanna_wiebe, etc.)
        scripts_dir = _find_topic_dir(audio_scripts_base, topic, safe_topic)
        actual_scripts_folder = scripts_dir.name if scripts_dir else safe_topic
        voice_dir_found = _find_topic_dir(voice_base, topic, safe_topic)
        actual_voice_folder = voice_dir_found.name if voice_dir_found else safe_topic

        if script_type == "deep_dive":
            script_path = audio_scripts_base / actual_scripts_folder / f"{date}-v{vno}-deep-dive.md"
            voice_path  = voice_base / actual_voice_folder / voice_filename(actual_voice_folder, date, video_no=vno, variant="deep_dive")
        else:
            script_path = audio_scripts_base / actual_scripts_folder / f"{date}-v{vno}.md"
            voice_path  = voice_base / actual_voice_folder / voice_filename(actual_voice_folder, date, video_no=vno)
        return actual_scripts_folder, vno, script_path, voice_path

    def _extract_voice_text(self, content, script_type):
        """Extract spoken script text from saved script markdown."""
        from voice_engine import extract_script_text
        return extract_script_text(content, script_type)

    def api_assets_script_get(self):
        qs = parse_qs(urlparse(self.path).query)
        try:
            topic = qs.get("topic", [""])[0]
            date = qs.get("date", [""])[0]
            video = qs.get("video", ["1"])[0]
            script_type = qs.get("type", ["full"])[0]
            safe_topic, vno, script_path, voice_path = self._voice_script_paths(topic, date, video, script_type)
            exists = script_path.exists()
            content = script_path.read_text(encoding="utf-8") if exists else ""
            self._send_json({
                "topic": safe_topic,
                "date": date,
                "video": vno,
                "type": script_type,
                "exists": exists,
                "path": str(script_path.relative_to(PROJECT_ROOT)),
                "voice_path": str(voice_path.relative_to(PROJECT_ROOT)),
                "content": content,
                "voice_text_chars": len(self._extract_voice_text(content, script_type)),
            })
        except Exception as exc:
            self._send_json({"error": str(exc)}, code=400)

    def api_assets_script_save(self, data):
        try:
            topic = data.get("topic", [""])[0]
            date = data.get("date", [""])[0]
            video = data.get("video", ["1"])[0]
            script_type = data.get("type", ["full"])[0]
            content = data.get("content", [""])[0]
            safe_topic, vno, script_path, voice_path = self._voice_script_paths(topic, date, video, script_type)
            if not content.strip():
                self._send_json({"error": "content is empty"}, code=400)
                return
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(content, encoding="utf-8")
            stale = True
            meta_path = Path(str(voice_path) + ".json")
            if voice_path.exists() and meta_path.exists():
                from voice_engine import is_voice_stale
                stale = is_voice_stale(script_path, meta_path)
            self._send_json({
                "status": "ok",
                "topic": safe_topic,
                "date": date,
                "video": vno,
                "type": script_type,
                "path": str(script_path.relative_to(PROJECT_ROOT)),
                "voice_stale": stale,
            })
        except Exception as exc:
            self._send_json({"error": str(exc)}, code=400)

    def api_assets_voice_status(self):
        qs = parse_qs(urlparse(self.path).query)
        try:
            topic = qs.get("topic", [""])[0]
            date = qs.get("date", [""])[0]
            video = qs.get("video", ["1"])[0]
            result = {"topic": topic, "date": date, "video": int(video), "types": {}}
            for script_type in ("full", "deep_dive"):
                safe_topic, vno, script_path, voice_path = self._voice_script_paths(topic, date, video, script_type)
                meta_path = Path(str(voice_path) + ".json")
                stale = True
                if voice_path.exists() and meta_path.exists() and script_path.exists():
                    from voice_engine import is_voice_stale
                    stale = is_voice_stale(script_path, meta_path)
                result["topic"] = safe_topic
                result["video"] = vno
                result["types"][script_type] = {
                    "script_exists": script_path.exists(),
                    "voice_exists": voice_path.exists(),
                    "voice_stale": stale,
                    "script_path": str(script_path.relative_to(PROJECT_ROOT)),
                    "voice_path": str(voice_path.relative_to(PROJECT_ROOT)),
                    "metadata_path": str(meta_path.relative_to(PROJECT_ROOT)),
                }
            self._send_json(result)
        except Exception as exc:
            self._send_json({"error": str(exc)}, code=400)

    def api_assets_generate_deep_dive_script(self, data):
        """Generate a deep-dive script only; voice remains a separate saved-script step."""
        try:
            from generate_content_assets import (
                AUDIO_SCRIPTS_DIR,
                build_asset_from_report,
                generate_deep_dive_script,
                save_deep_dive_script,
                _get_ai_client,
            )
        except ImportError:
            self._send_json({"error": "Asset module not available"}, code=500)
            return

        try:
            topic = data.get("topic", [""])[0]
            date = data.get("date", [""])[0]
            video = data.get("video", ["1"])[0]
            force = data.get("force", [""])[0] == "1"
            safe_topic, vno, script_path, _voice_path = self._voice_script_paths(topic, date, video, "deep_dive")
            if script_path.exists() and not force:
                self._send_json({
                    "status": "exists",
                    "topic": safe_topic,
                    "date": date,
                    "video": vno,
                    "type": "deep_dive",
                    "path": str(script_path.relative_to(PROJECT_ROOT)),
                    "message": "Deep dive script already exists — open editor or pass force=1 to regenerate",
                })
                return

            report_path, resolved_topic = _resolve_report_path(safe_topic, date)
            if not report_path:
                self._send_json({"error": f"Report not found: {topic}/{date}"}, code=404)
                return

            for creds in (PROJECT_ROOT / "credentials.env", Path.home() / ".credentials.env"):
                if creds.exists():
                    for line in creds.read_text().splitlines():
                        if "=" in line and not line.startswith("#"):
                            k, _, v = line.partition("=")
                            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

            asset = build_asset_from_report(report_path, REPORTS_DIR)
            if not asset:
                self._send_json({"error": "Failed to parse report"}, code=500)
                return
            ai_module = _get_ai_client()
            result = generate_deep_dive_script(asset, vno, ai_module)
            saved_path = save_deep_dive_script(asset, vno, AUDIO_SCRIPTS_DIR)
            self._send_json({
                "status": "ok",
                "topic": safe_topic,
                "date": date,
                "video": vno,
                "type": "deep_dive",
                "path": str(saved_path.relative_to(PROJECT_ROOT)),
                **result,
            })
        except Exception as exc:
            self._send_json({"error": str(exc)}, code=500)

    def api_assets_generate_full_detail(self, data):
        """Generate a Full Detail report for one video — re-reads the original
        transcript (not the already-compressed report) and writes a sibling file.
        Never touches the day's main report."""
        try:
            from generate_content_assets import build_asset_from_report, _find_asset_video
        except ImportError:
            self._send_json({"error": "Asset module not available"}, code=500)
            return

        try:
            topic = data.get("topic", [""])[0]
            date = data.get("date", [""])[0]
            video = data.get("video", ["1"])[0]
            force = data.get("force", [""])[0] == "1"

            safe_topic = _slug(topic)
            try:
                vno = int(video)
            except (TypeError, ValueError):
                self._send_json({"error": "video must be a number"}, code=400)
                return
            if not DATE_OR_REPORT_STEM_RE.match(date or ""):
                self._send_json({"error": "invalid date"}, code=400)
                return

            out_path = _full_detail_path(safe_topic, date, vno)
            if not out_path:
                self._send_json({"error": f"Report not found: {topic}/{date}"}, code=404)
                return
            if out_path.exists() and not force:
                existing_text = out_path.read_text(encoding="utf-8", errors="replace")
                if not _looks_like_no_transcript_failure(existing_text):
                    self._send_json({
                        "status": "exists",
                        "topic": safe_topic,
                        "date": date,
                        "video": vno,
                        "type": "full_detail",
                        "path": str(out_path.relative_to(PROJECT_ROOT)),
                        "message": "Full Detail already exists — pass force=1 to regenerate",
                    })
                    return

            report_path, _ = _resolve_report_path(safe_topic, date)
            if not report_path:
                self._send_json({"error": f"Report not found: {topic}/{date}"}, code=404)
                return
            asset = build_asset_from_report(report_path, REPORTS_DIR)
            if not asset:
                self._send_json({"error": "Failed to parse report"}, code=500)
                return
            video_entry = _find_asset_video(asset, vno)
            if not video_entry:
                self._send_json({"error": f"video {vno} not found in report"}, code=404)
                return
            source_url = video_entry.get("source_url", "")
            if not source_url:
                self._send_json({"error": "selected video has no source URL to re-summarize"}, code=400)
                return

            for creds in (PROJECT_ROOT / "credentials.env", Path.home() / ".credentials.env"):
                if creds.exists():
                    for line in creds.read_text().splitlines():
                        if "=" in line and not line.startswith("#"):
                            k, _, v = line.partition("=")
                            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

            import summarize_local
            result_text = summarize_local.summarize_video(
                source_url,
                prompt_file=str(FULL_DETAIL_PROMPT_FILE),
                language="th",
                topic=asset.get("topic", topic),
                transcript_langs=["th", "th-orig", "en", "all"],
                transcript_char_limit=120000,
                max_output_tokens=32768,
            )
            if _looks_like_no_transcript_failure(result_text):
                self._send_json({
                    "error": "selected video transcript could not be downloaded; not writing a failed Full Detail report",
                    "status": "transcript_missing",
                    "topic": safe_topic,
                    "date": date,
                    "video": vno,
                }, code=502)
                return

            content = build_full_detail_report_content(
                topic=asset.get("topic", topic),
                date=date,
                video_no=vno,
                video_title=video_entry.get("video_title", ""),
                thai_title=video_entry.get("thai_title", ""),
                source_url=source_url,
                video_id=video_entry.get("video_id", ""),
                result_text=result_text,
            )
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")

            self._send_json({
                "status": "ok",
                "topic": safe_topic,
                "date": date,
                "video": vno,
                "type": "full_detail",
                "path": str(out_path.relative_to(PROJECT_ROOT)),
            })
        except Exception as exc:
            self._send_json({"error": str(exc)}, code=500)

    def api_assets_generate_voice(self, data):
        """Generate voice only from an existing saved script. Never creates a script."""
        try:
            topic = data.get("topic", [""])[0]
            date = data.get("date", [""])[0]
            video = data.get("video", ["1"])[0]
            script_type = data.get("type", ["full"])[0]
            dry_run = data.get("dry_run", [""])[0] == "1"
            safe_topic, vno, script_path, voice_path = self._voice_script_paths(topic, date, video, script_type)
            for creds in (PROJECT_ROOT / "credentials.env", Path.home() / ".credentials.env"):
                if creds.exists():
                    for line in creds.read_text().splitlines():
                        if "=" in line and not line.startswith("#"):
                            k, _, v = line.partition("=")
                            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            if not script_path.exists():
                self._send_json({"error": "Script missing — generate script first", "script_path": str(script_path.relative_to(PROJECT_ROOT))}, code=400)
                return
            content = script_path.read_text(encoding="utf-8")
            voice_text = self._extract_voice_text(content, script_type)
            if len(voice_text) < 20:
                self._send_json({"error": "Saved script has no usable voice text"}, code=400)
                return
            from dataclasses import asdict
            from voice_engine import generate_voice_from_text
            meta = generate_voice_from_text(
                voice_text,
                voice_path,
                script_path=script_path,
                raw_script_text=content,
                dry_run=dry_run,
            )
            self._send_json({
                "status": "dry_run" if dry_run else "ok",
                "topic": safe_topic,
                "date": date,
                "video": vno,
                "type": script_type,
                "voice_path": str(voice_path.relative_to(PROJECT_ROOT)),
                "metadata": asdict(meta),
            })
        except Exception as exc:
            self._send_json({"error": str(exc)}, code=500)

    def render_assets(self):
        # Import asset generator
        try:
            from generate_content_assets import ASSETS_DIR, AUDIO_SCRIPTS_DIR, SOCIAL_DIR, find_reports, build_asset_from_report
            _assets_available = True
        except ImportError:
            _assets_available = False
            ASSETS_DIR = Path("")

        if not _assets_available:
            self.send_html(page("Assets", '<h1>Content Assets</h1><p class="failed">Asset module not available.</p>'))
            return

        # Collect existing assets
        assets_dir = ASSETS_DIR
        audio_base    = PROJECT_ROOT / "ai_trends_reports" / "audio"
        voice_base    = PROJECT_ROOT / "ai_trends_reports" / "voice"
        scripts_base  = AUDIO_SCRIPTS_DIR
        social_base   = SOCIAL_DIR
        existing = []
        if assets_dir.exists():
            for p in sorted(assets_dir.rglob("*.json")):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    topic = data.get("topic", "?")
                    date = data.get("date", "?")
                    # Use folder name (slug) for API calls, not display name
                    raw_name = p.parent.name if p.parent != assets_dir else topic
                    topic_folder = _slug(raw_name)
                    n = data.get("total_videos", 0)
                    has_social_json = any(v.get("social_posts") for v in data.get("videos", []))
                    # Check actual files on disk (try raw name and slug)
                    scripts_dir = _find_topic_dir(scripts_base, raw_name, topic_folder)
                    audio_dir   = _find_topic_dir(audio_base, raw_name, topic_folder)
                    social_dir  = _find_topic_dir(social_base, raw_name, topic_folder)
                    has_script_file = bool(scripts_dir and list(scripts_dir.glob(f"{date}-v*.md")))
                    has_voice_file  = bool(audio_dir and find_voice_files(audio_dir, topic_folder, date))
                    has_social_file = bool(social_dir and (social_dir / f"{date}.json").exists())
                    # Aggregate counts for manage-page status badges
                    n_full_s = len([f for f in scripts_dir.glob(f"{date}-v*.md") if "-deep-dive" not in f.name]) if scripts_dir else 0
                    n_dd_s   = len(list(scripts_dir.glob(f"{date}-v*-deep-dive.md"))) if scripts_dir else 0
                    v_dir_voice = _find_topic_dir(voice_base, raw_name, topic_folder)
                    all_vf   = find_voice_files(v_dir_voice, topic_folder, date) if v_dir_voice else []
                    n_full_v = len([f for f in all_vf if "deep-dive" not in f.stem])
                    n_dd_v   = len([f for f in all_vf if "deep-dive" in f.stem])
                    existing.append({
                        "topic": topic, "topic_folder": topic_folder, "topic_raw": raw_name,
                        "date": date, "videos": n,
                        "report_path": data.get("report_path", ""),
                        "has_script_file": has_script_file,
                        "has_voice_file":  has_voice_file,
                        "has_social_file": has_social_file or has_social_json,
                        "path": str(p.relative_to(assets_dir)),
                        "n_full_scripts": n_full_s,
                        "n_dd_scripts":   n_dd_s,
                        "n_full_voices":  n_full_v,
                        "n_dd_voices":    n_dd_v,
                    })
                except (json.JSONDecodeError, OSError):
                    pass
        existing = _dedupe_asset_entries(existing)
        # Sort by actual date recency (not directory-traversal order) before capping
        # the list below — rglob() yields entries alphabetically by topic folder first,
        # so an uncapped-by-date slice silently drops topics whose folder name sorts
        # early (e.g. "ai_viral_niche") once total asset count exceeds the display cap.
        existing.sort(key=lambda a: a["date"])

        # Collect available topics
        topics = sorted(set(str(p.parent.name) for p in REPORTS_DIR.rglob("*.md") if p.is_file()))

        topic_options = "".join(f'<option value="{h(t)}">{h(t)}</option>' for t in topics)

        today_str = datetime.now().strftime("%Y-%m-%d")

        generating_now = DashboardHandler._generating_set
        any_generating = bool(generating_now)
        status_store   = DashboardHandler._status_store
        now_ts         = time.time()

        def cnt_badge(icon, count, total, title):
            if total > 0 and count == total:
                cls = "cnt-badge cnt-green"
            elif count > 0:
                cls = "cnt-badge cnt-partial"
            else:
                cls = "cnt-badge cnt-gray"
            label = f"{count}/{total}" if total != 1 else ("✓" if count else "—")
            return f'<span class="{cls}" title="{title}">{icon}&thinsp;{label}</span>'

        rows = ""
        any_recently_done = False
        for a in reversed(existing[-100:]):
            safe_topic  = h(a["topic"])
            safe_folder = h(a["topic_folder"])
            safe_raw    = h(a["topic_raw"])
            safe_date   = h(a["date"])
            n_tot       = max(a["videos"], 1)
            is_generating = (a["topic_folder"], a["date"]) in generating_now
            _se = status_store.get((a["topic_folder"], a["date"]))
            recently_done = bool(_se and _se[0] == "done" and now_ts - _se[1] < 30)
            if recently_done:
                any_recently_done = True

            b_asset  = '<span class="cnt-badge cnt-green" title="Asset JSON ✓">📄&thinsp;✓</span>'
            b_script = cnt_badge("📝", a["n_full_scripts"], n_tot, f"Full audio scripts: {a['n_full_scripts']}/{n_tot}")
            b_dd     = cnt_badge("📖", a["n_dd_scripts"],   n_tot, f"Deep-dive scripts: {a['n_dd_scripts']}/{n_tot}")
            b_voice  = cnt_badge("🎙️", a["n_full_voices"],  n_tot, f"Full voices: {a['n_full_voices']}/{n_tot}")
            b_dd_v   = cnt_badge("🎧", a["n_dd_voices"],    n_tot, f"Deep-dive voices: {a['n_dd_voices']}/{n_tot}")
            b_social_cls = "cnt-badge cnt-green" if a["has_social_file"] else "cnt-badge cnt-gray"
            b_social_onclick = f' onclick="viewSocial(\'{safe_raw}\',\'{safe_date}\')" style="cursor:pointer"' if a["has_social_file"] else ""
            b_social = f'<span class="{b_social_cls}" title="{"Social posts ✓ — click to view" if a["has_social_file"] else "Social not generated"}"{b_social_onclick}>📱&thinsp;{"✓" if a["has_social_file"] else "—"}</span>'

            rows += f'<tr data-topic="{safe_folder}" data-date="{safe_date}" id="row-{safe_folder}-{safe_date}">'
            rows += f'<td>{safe_date}</td>'
            rows += f'<td><span class="pill">{safe_topic}</span></td>'
            rows += f'<td style="text-align:center">{a["videos"]}</td>'
            rows += f'<td style="white-space:nowrap;font-size:13px">{b_asset} {b_script} {b_dd} {b_voice} {b_dd_v} {b_social}</td>'
            rows += f'<td><a class="btn-sm" href="/assets/manage?topic={safe_folder}&date={safe_date}" title="Manage scripts and voice per video">🎛️ Manage</a> <a class="btn-sm" href="http://localhost:8080/ats-sources?topic={safe_folder}&date={safe_date}" target="_blank" title="Open in FAW Draft Import" style="background:#17a2b8;color:#fff;text-decoration:none;padding:3px 8px;border-radius:4px;font-size:11px;">FAW→</a></td>'
            rows += f'<td class="muted" style="font-size:12px">{h(a["path"])}</td>'
            rows += f'<td id="gentd-{safe_folder}-{safe_date}" style="white-space:nowrap">'
            if is_generating:
                rows += f'<span style="color:#6366f1;font-size:13px">⏳ กำลังสร้าง...</span>'
            elif recently_done:
                rows += f'<span style="color:#16a34a;font-size:13px">✅ เสร็จแล้ว</span>'
            else:
                rows += f'<button class="btn-sm" onclick="generateOne(\'{safe_folder}\',\'{safe_date}\',\'asset\')" title="Asset JSON only">📄</button> '
                rows += f'<button class="btn-sm" onclick="generateOne(\'{safe_folder}\',\'{safe_date}\',\'audio\')" title="Generate audio scripts for all videos">🔊</button> '
                rows += f'<button class="btn-sm" onclick="generateOne(\'{safe_folder}\',\'{safe_date}\',\'social\')" title="Social posts">📱</button> '
                rows += f'<button class="btn-sm" onclick="generateOne(\'{safe_folder}\',\'{safe_date}\',\'all\')" title="Audio + Social">🚀</button>'
            rows += f'</td></tr>'

        if any_generating:
            auto_refresh = '<meta http-equiv="refresh" content="8">'
        elif any_recently_done:
            auto_refresh = '<meta http-equiv="refresh" content="12">'
        else:
            auto_refresh = ''

        body = f"""{auto_refresh}<h1>📦 Content Assets</h1>
<section>
<p class="muted">{len(existing)} asset files · Generate audio scripts and social posts from reports</p>
</section>
<section>
<h2>Batch Generate</h2>
<form id="assetForm" onsubmit="return generateAssets(event)">
  <div class="form-grid">
    <div>
      <label>Topic</label>
      <select id="at" name="topic"><option value="">All topics</option>{topic_options}</select>
    </div>
    <div>
      <label>Generate</label>
      <select id="am" name="mode">
        <option value="asset">Asset JSON only (no AI cost)</option>
        <option value="audio">Asset + Audio Scripts (uses AI)</option>
        <option value="social">Asset + Social Posts (uses AI)</option>
        <option value="all">Asset + Audio + Social (uses AI)</option>
      </select>
    </div>
    <div>
      <label>Date from</label>
      <input type="date" id="adf" name="date_from" value="">
    </div>
    <div>
      <label>Date to</label>
      <input type="date" id="adt" name="date_to" value="">
    </div>
  </div>
  <div style="margin-top:4px;margin-bottom:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
    <label style="font-size:13px"><input type="checkbox" id="askip" checked> Skip already generated</label>
    <span class="muted" style="font-size:12px">|</span>
    <button type="button" class="secondary" style="font-size:12px" onclick="document.getElementById('adf').value='{today_str}';document.getElementById('adt').value='{today_str}';filterTable()">Today</button>
    <button type="button" class="secondary" style="font-size:12px" onclick="setLast7()">Last 7 days</button>
    <button type="button" class="secondary" style="font-size:12px" onclick="document.getElementById('adf').value='';document.getElementById('adt').value='';filterTable()">All dates</button>
  </div>
  <p><button type="submit" id="genBtn">Generate</button> <span id="assetStatus" class="muted"></span></p>
  <div id="progressBar" style="display:none;margin-bottom:12px">
    <div style="background:#e2e8f0;border-radius:6px;overflow:hidden;height:20px">
      <div id="progressFill" style="background:linear-gradient(90deg,#6366f1,#8b5cf6);height:100%;width:0%;transition:width 0.3s"></div>
    </div>
    <p id="progressText" class="muted" style="font-size:13px;margin-top:4px"></p>
  </div>
</form>
</section>
<section>
<h2>Existing Assets <span id="assetCount" class="muted" style="font-size:14px"></span></h2>
<p class="muted" style="font-size:13px">Status: 📄=Asset JSON · 📝=Audio script (click to edit) · 🎙️=Voice WAV (click to download) · 📱=Social posts (click to view) — green=ready, gray=not yet generated</p>
<p class="muted" style="font-size:13px">Gen: 📄=JSON only · 🔊=+Audio script · 📱=+Social · 🚀=+All | Script/Voice: 📝=Edit full · 📖=Generate deep dive script · 📚=Edit deep dive · 🎙️/🎧=Generate voice from saved script</p>
<table><thead><tr><th>Date</th><th>Topic</th><th>Videos</th><th>Status</th><th>Manage</th><th>Path</th><th>Gen</th></tr></thead>
<tbody>{rows if rows else '<tr><td colspan="7">No assets yet. Generate some above.</td></tr>'}</tbody></table>
</section>
<div id="socialModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:1000;overflow-y:auto">
  <div style="background:var(--surface,#fff);max-width:680px;margin:40px auto;border-radius:10px;padding:24px;position:relative;color:var(--text-primary)">
    <button onclick="closeSocialModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;font-size:22px;cursor:pointer;color:#5f6c80">✕</button>
    <h2 id="socialModalTitle" style="margin:0 0 16px;font-size:18px"></h2>
    <div id="socialModalBody" style="white-space:pre-wrap;font-size:14px;line-height:1.7;color:#172033"></div>
  </div>
</div>
<style>
.btn-sm{{
  padding:6px 10px;font-size:20px;border:1px solid var(--border,#d1d5db);border-radius:6px;
  background:var(--surface-hover,#f9fafb);color:var(--text-primary);cursor:pointer;line-height:1.2;
}}
.btn-sm:hover{{background:var(--accent-subtle,#e0e7ff);border-color:var(--accent)}}
.btn-sm:disabled{{opacity:0.4;cursor:default}}
.badge{{
  display:inline-flex;align-items:center;justify-content:center;
  width:32px;height:32px;border-radius:8px;font-size:16px;
  border:1px solid transparent;
}}
.badge-green{{background:#dcfce7;border-color:#86efac;cursor:pointer}}
.badge-green:hover{{background:#bbf7d0}}
.badge-gray{{background:#f3f4f6;border-color:#d1d5db;opacity:0.55;cursor:default}}
.cnt-badge{{
  display:inline-flex;align-items:center;padding:2px 6px;border-radius:4px;
  font-size:12px;border:1px solid transparent;white-space:nowrap;
}}
.cnt-green{{background:#dcfce7;border-color:#86efac;color:#166534}}
.cnt-partial{{background:#fef9c3;border-color:#fde047;color:#713f12}}
.cnt-gray{{background:#f3f4f6;border-color:#d1d5db;color:#9ca3af}}
</style>
<script>
function setLast7(){{
  var today=new Date();
  var from=new Date(today);
  from.setDate(from.getDate()-6);
  document.getElementById('adf').value=from.toISOString().slice(0,10);
  document.getElementById('adt').value=today.toISOString().slice(0,10);
  filterTable();
}}

function _modeLabel(m){{
  return{{'asset':'JSON only','audio':'+Audio (AI)','social':'+Social (AI)','all':'+Audio+Social (AI)'}}[m]||m;
}}

function _confirmIfAI(mode,topic,dateFrom,dateTo){{
  if(mode==='asset') return true;
  var scope=topic?('"'+topic+'"'):('all topics');
  var range='';
  if(dateFrom&&dateTo) range=' from '+dateFrom+' to '+dateTo;
  else if(dateFrom) range=' from '+dateFrom;
  else if(dateTo) range=' until '+dateTo;
  return confirm('Generate '+_modeLabel(mode)+' for '+scope+range+'?\\nThis uses AI and may take a few minutes.');
}}

/* ── Filter Existing Assets table by topic + date range ── */
function filterTable(){{
  var topic=document.getElementById('at').value;
  var dateFrom=document.getElementById('adf').value;
  var dateTo=document.getElementById('adt').value;
  var rows=document.querySelectorAll('tbody tr[data-date]');
  var shown=0;
  rows.forEach(function(row){{
    var match=true;
    if(topic && row.dataset.topic.toLowerCase()!==topic.toLowerCase()) match=false;
    if(dateFrom && row.dataset.date<dateFrom) match=false;
    if(dateTo && row.dataset.date>dateTo) match=false;
    row.style.display=match?'':'none';
    if(match) shown++;
  }});
  var counter=document.getElementById('assetCount');
  if(counter) counter.textContent=shown;
}}

function generateAssets(e){{
  e.preventDefault();
  var topic=document.getElementById('at').value;
  var mode=document.getElementById('am').value;
  var dateFrom=document.getElementById('adf').value;
  var dateTo=document.getElementById('adt').value;
  var skipExisting=document.getElementById('askip').checked;
  if(!_confirmIfAI(mode,topic,dateFrom,dateTo)) return false;

  var st=document.getElementById('assetStatus');
  var pb=document.getElementById('progressBar');
  var pf=document.getElementById('progressFill');
  var pt=document.getElementById('progressText');
  var btn=document.getElementById('genBtn');
  btn.disabled=true;
  st.textContent='Starting...';
  pb.style.display='block';
  pf.style.width='0%';
  pt.textContent='Preparing...';

  var params='?mode='+mode;
  if(topic) params+='&topic='+encodeURIComponent(topic);
  if(dateFrom) params+='&date_from='+encodeURIComponent(dateFrom);
  if(dateTo) params+='&date_to='+encodeURIComponent(dateTo);
  if(skipExisting) params+='&skip_existing=1';

  // Poll progress while generating
  var progressTimer=setInterval(function(){{
    fetch('/api/assets/progress').then(function(r){{return r.json()}}).then(function(d){{
      if(d.total>0){{
        var pct=Math.round((d.current/d.total)*100);
        pf.style.width=pct+'%';
        pt.textContent=d.current+'/'+d.total+' reports — '+d.status;
      }}
    }}).catch(function(){{}});
  }},2000);

  fetch('/api/assets/generate'+params)
    .then(function(r){{return r.json()}})
    .then(function(data){{
      clearInterval(progressTimer);
      btn.disabled=false;
      if(data.error){{
        st.textContent='Error: '+data.error;
        pb.style.display='none';
        return;
      }}
      pf.style.width='100%';
      var skipped=data.skipped||0;
      pt.textContent='Done!';
      st.textContent='✅ '+data.generated+' generated, '+data.total_videos+' videos'+(skipped?' ('+skipped+' skipped)':'');
      setTimeout(function(){{location.reload();}},2000);
    }})
    .catch(function(err){{
      clearInterval(progressTimer);
      btn.disabled=false;
      st.textContent='Error: '+err;
      pb.style.display='none';
    }});
  return false;
}}

function downloadVoice(topic,date){{
  window.location.href='/api/audio/serve?topic='+encodeURIComponent(topic)+'&date='+encodeURIComponent(date);
}}

function viewSocial(topic,date){{
  fetch('/api/social/view?topic='+encodeURIComponent(topic)+'&date='+encodeURIComponent(date))
    .then(function(r){{return r.json()}})
    .then(function(data){{
      if(data.error){{alert('Error: '+data.error);return;}}
      var title=document.getElementById('socialModalTitle');
      var body=document.getElementById('socialModalBody');
      title.textContent='📱 Social Posts — '+topic+' '+date;
      var html='';
      Object.entries(data.posts||{{}}).forEach(function([key,v]){{
        html+='<strong>'+v.video_title+'</strong>\\n';
        var s=v.social||{{}};
        if(s.raw) html+=s.raw+'\\n';
        else Object.entries(s).forEach(function([k2,txt]){{html+=txt+'\\n\\n';}});
        html+='\\n---\\n\\n';
      }});
      body.textContent=html.trim();
      document.getElementById('socialModal').style.display='block';
    }})
    .catch(function(err){{alert('Error: '+err);}});
}}

function closeSocialModal(){{
  document.getElementById('socialModal').style.display='none';
}}

function _genLsKey(topic,date){{return 'ats_gen_'+topic+'_'+date;}}

function _lockGenRow(topic,date,label){{
  var gentd=document.getElementById('gentd-'+topic+'-'+date);
  if(gentd) gentd.innerHTML='<span style="color:#6366f1;font-size:13px">⏳ '+label+'...</span>';
}}

function _setGenRowDone(topic,date,lsKey){{
  try{{localStorage.setItem(lsKey,JSON.stringify({{topic:topic,date:date,ts:Date.now(),status:'done'}}));}}catch(e){{try{{localStorage.removeItem(lsKey);}}catch(e2){{}}}}
  var gentd=document.getElementById('gentd-'+topic+'-'+date);
  if(gentd) gentd.innerHTML='<span style="color:#16a34a;font-size:13px">✅ เสร็จแล้ว — โหลดใหม่...</span>';
  setTimeout(function(){{location.reload();}},3000);
}}

function _pollUntilDone(topic,date,lsKey){{
  var poll=setInterval(function(){{
    fetch('/api/assets/gen-status?topic='+encodeURIComponent(topic)+'&date='+encodeURIComponent(date))
      .then(function(r){{return r.json()}})
      .then(function(d){{
        if(d.status==='done'){{clearInterval(poll);_setGenRowDone(topic,date,lsKey);}}
        else if(d.status==='error'){{
          clearInterval(poll);
          try{{localStorage.removeItem(lsKey);}}catch(e){{}}
          var errMsg=(d.error)?('Error: '+d.error):'Generation failed. Check server logs.';
          alert(errMsg);
          location.reload();
        }}
      }})
      .catch(function(){{}});
  }},5000);
}}

function generateOne(topic,date,mode){{
  if(!_confirmIfAI(mode,topic,date,date)) return;
  var lsKey=_genLsKey(topic,date);
  _lockGenRow(topic,date,'กำลังสร้าง '+_modeLabel(mode));
  try{{localStorage.setItem(lsKey,JSON.stringify({{topic:topic,date:date,mode:mode,ts:Date.now()}}));}}catch(e){{}}
  var params='?mode='+mode+'&topic='+encodeURIComponent(topic)+'&date='+encodeURIComponent(date);
  fetch('/api/assets/generate-one'+params)
    .then(function(r){{return r.json()}})
    .then(function(data){{
      if(data.error){{
        try{{localStorage.removeItem(lsKey);}}catch(e){{}}
        alert('Error: '+data.error);
        location.reload();
        return;
      }}
      if(data.status==='started'){{
        // AI generation running in background — poll gen-status every 5s
        _lockGenRow(topic,date,'กำลังสร้าง AI...');
        _pollUntilDone(topic,date,lsKey);
        return;
      }}
      _setGenRowDone(topic,date,lsKey);
    }})
    .catch(function(err){{
      try{{localStorage.removeItem(lsKey);}}catch(e){{}}
      alert('Error: '+err);
      location.reload();
    }});
}}

document.addEventListener('DOMContentLoaded',function(){{
  document.getElementById('at').addEventListener('change',filterTable);
  document.getElementById('adf').addEventListener('change',filterTable);
  document.getElementById('adt').addEventListener('change',filterTable);
  filterTable();
  var keys=[];
  for(var i=0;i<localStorage.length;i++){{var k=localStorage.key(i);if(k&&k.startsWith('ats_gen_'))keys.push(k);}}
  keys.forEach(function(lsKey){{
    var val;try{{val=JSON.parse(localStorage.getItem(lsKey));}}catch(e){{try{{localStorage.removeItem(lsKey);}}catch(e2){{}}return;}}
    if(!val||!val.topic||!val.date){{try{{localStorage.removeItem(lsKey);}}catch(e){{}}return;}}
    if(Date.now()-val.ts>600000){{try{{localStorage.removeItem(lsKey);}}catch(e){{}}return;}}
    if(val.status==='done'){{
      var gtd=document.getElementById('gentd-'+val.topic+'-'+val.date);
      if(gtd) gtd.innerHTML='<span style="color:#16a34a;font-size:13px">✅ เสร็จแล้ว</span>';
      setTimeout(function(){{try{{localStorage.removeItem(lsKey);}}catch(e){{}} location.reload();}},8000);
      return;
    }}
    fetch('/api/assets/gen-status?topic='+encodeURIComponent(val.topic)+'&date='+encodeURIComponent(val.date))
      .then(function(r){{return r.json()}})
      .then(function(data){{
        if(data.status==='generating'){{
          _lockGenRow(val.topic,val.date,'กำลังสร้าง');
        }}else if(data.status==='done'){{
          var gtd2=document.getElementById('gentd-'+val.topic+'-'+val.date);
          if(gtd2) gtd2.innerHTML='<span style="color:#16a34a;font-size:13px">✅ เสร็จแล้ว</span>';
          setTimeout(function(){{try{{localStorage.removeItem(lsKey);}}catch(e){{}} location.reload();}},8000);
        }}else{{
          try{{localStorage.removeItem(lsKey);}}catch(e){{}}
        }}
      }})
      .catch(function(){{try{{localStorage.removeItem(lsKey);}}catch(e){{}}  }});
  }});
}});
</script>"""
        self.send_html(page("Content Assets", body))

    # ── Progress tracking for batch generation ──────────────
    _gen_progress = {"current": 0, "total": 0, "status": "idle"}
    _generating_set: set = set()  # (topic_raw, date) while api_assets_generate_one runs
    _status_store: dict = {}      # (topic_slug, date) → ("generating"|"done"|"error", timestamp)
    _gen_results: dict = {}       # (topic_slug, date) → result dict from completed background job

    def api_assets_progress(self):
        self._send_json(self._gen_progress)

    def api_assets_gen_status(self):
        qs = parse_qs(urlparse(self.path).query)
        topic = qs.get("topic", [""])[0].strip()
        date  = qs.get("date",  [""])[0].strip()
        video = qs.get("video", [""])[0].strip()
        # Per-video jobs use date-vN key; full-report jobs use plain date
        date_key = f"{date}-v{int(video)}" if video and video.isdigit() else date
        now = time.time()
        # purge stale entries (>600s = 10 min, covers longest generation job)
        stale = [k for k, v in DashboardHandler._status_store.items() if now - v[1] > 600]
        for k in stale:
            DashboardHandler._status_store.pop(k, None)
            DashboardHandler._gen_results.pop(k, None)
        entry = DashboardHandler._status_store.get((topic, date_key))
        if entry and now - entry[1] <= 600:
            result = DashboardHandler._gen_results.get((topic, date_key), {})
            self._send_json({"status": entry[0], "topic": topic, "date": date, **result})
        else:
            self._send_json({"status": "unknown", "topic": topic, "date": date})

    def _set_progress(self, current, total, status):
        self._gen_progress = {"current": current, "total": total, "status": status}

    def _generate_single_report(self, report_path, mode, ai_module):
        """Generate assets for a single report. Returns (asset_dict, generated_bool)."""
        try:
            from generate_content_assets import (
                ASSETS_DIR, AUDIO_SCRIPTS_DIR, SOCIAL_DIR,
                build_asset_from_report, save_asset,
                generate_audio_scripts, generate_social_posts,
                save_audio_scripts, save_social_posts,
                enable_content_use,
            )
        except ImportError:
            return None, False

        with_audio = mode in ("audio", "all")
        with_social = mode in ("social", "all")

        asset = build_asset_from_report(report_path, REPORTS_DIR)
        if not asset:
            return None, False

        enable_content_use(asset, audio=with_audio, social=with_social)

        if with_audio:
            generate_audio_scripts(asset, ai_module)
            save_audio_scripts(asset, AUDIO_SCRIPTS_DIR)
        if with_social:
            generate_social_posts(asset, ai_module)
            save_social_posts(asset, SOCIAL_DIR)

        save_asset(asset, ASSETS_DIR)
        return asset, True

    def api_assets_generate(self):
        try:
            from generate_content_assets import (
                ASSETS_DIR, AUDIO_SCRIPTS_DIR, SOCIAL_DIR,
                find_reports, build_asset_from_report, save_asset,
                generate_audio_scripts, generate_social_posts,
                save_audio_scripts, save_social_posts, _get_ai_client,
                enable_content_use,
            )
        except ImportError:
            self._send_json({"error": "Asset module not available"}, code=500)
            return

        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        topic = qs.get("topic", [""])[0] or None
        mode = qs.get("mode", ["asset"])[0]
        date_from = qs.get("date_from", [""])[0] or None
        date_to = qs.get("date_to", [""])[0] or None
        skip_existing = qs.get("skip_existing", [""])[0] == "1"

        with_audio = mode in ("audio", "all")
        with_social = mode in ("social", "all")

        reports = find_reports(topic, REPORTS_DIR)
        if not reports:
            self._send_json({"error": "No reports found", "generated": 0, "total_videos": 0})
            return

        reports = filter_reports_by_date_range(reports, date_from, date_to)

        if not reports:
            self._send_json({"error": "No reports in date range", "generated": 0, "total_videos": 0})
            return

        # Load credentials for AI
        if with_audio or with_social:
            for creds in (PROJECT_ROOT / "credentials.env", Path.home() / ".credentials.env"):
                if creds.exists():
                    for line in creds.read_text().splitlines():
                        if "=" in line and not line.startswith("#"):
                            k, _, v = line.partition("=")
                            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

        ai_module = _get_ai_client() if (with_audio or with_social) else None

        # Check existing assets if skip_existing
        existing_keys = set()
        if skip_existing:
            if ASSETS_DIR.exists():
                for p in ASSETS_DIR.rglob("*.json"):
                    try:
                        data = json.loads(p.read_text(encoding="utf-8"))
                        # Normalize: use folder name (slug) not display name
                        topic_slug = _slug(p.parent.name if p.parent != ASSETS_DIR else data.get("topic", ""))
                        key = (topic_slug, data.get("date", ""))
                        if mode == "asset":
                            existing_keys.add(("asset", key))
                        if mode in ("audio", "all"):
                            has_a = any(v.get("audio_script_full") for v in data.get("videos", []))
                            if has_a:
                                existing_keys.add(("audio", key))
                        if mode in ("social", "all"):
                            has_s = any(v.get("social_posts") for v in data.get("videos", []))
                            if has_s:
                                existing_keys.add(("social", key))
                    except (json.JSONDecodeError, OSError):
                        pass

        batch = reports[-30:]  # Limit to latest 30 per batch
        total_batch = len(batch)
        generated = 0
        skipped = 0
        total_videos = 0
        self._set_progress(0, total_batch, "Starting...")

        for i, report_path in enumerate(batch):
            date_str = report_path.stem
            # Determine topic from parent folder — normalize to slug
            topic_name = _slug(report_path.parent.name)

            # Check skip
            if skip_existing:
                key = (topic_name, date_str)
                should_skip = False
                if mode == "asset" and ("asset", key) in existing_keys:
                    should_skip = True
                elif mode == "audio" and ("asset", key) in existing_keys and ("audio", key) in existing_keys:
                    should_skip = True
                elif mode == "social" and ("asset", key) in existing_keys and ("social", key) in existing_keys:
                    should_skip = True
                elif mode == "all" and ("asset", key) in existing_keys and ("audio", key) in existing_keys and ("social", key) in existing_keys:
                    should_skip = True
                if should_skip:
                    skipped += 1
                    self._set_progress(i + 1, total_batch, f"Skipped {date_str}")
                    continue

            self._set_progress(i + 1, total_batch, f"Processing {topic_name}/{date_str}")

            asset = build_asset_from_report(report_path, REPORTS_DIR)
            if not asset:
                continue
            total_videos += asset.get("total_videos", 0)

            enable_content_use(asset, audio=with_audio, social=with_social)

            if with_audio:
                generate_audio_scripts(asset, ai_module)
                save_audio_scripts(asset, AUDIO_SCRIPTS_DIR)
            if with_social:
                generate_social_posts(asset, ai_module)
                save_social_posts(asset, SOCIAL_DIR)

            save_asset(asset, ASSETS_DIR)
            generated += 1

        self._set_progress(total_batch, total_batch, "Done")
        self._send_json({
            "generated": generated,
            "skipped": skipped,
            "total_videos": total_videos,
            "with_audio": with_audio,
            "with_social": with_social,
        })

    def api_assets_generate_one(self):
        """Generate asset for a single report by topic + date."""
        try:
            from generate_content_assets import (
                ASSETS_DIR, AUDIO_SCRIPTS_DIR, SOCIAL_DIR,
                find_reports, build_asset_from_report, save_asset,
                generate_audio_scripts, generate_social_posts,
                save_audio_scripts, save_social_posts, _get_ai_client,
                enable_content_use,
            )
        except ImportError:
            self._send_json({"error": "Asset module not available"}, code=500)
            return

        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        topic = qs.get("topic", [""])[0] or None
        date = qs.get("date", [""])[0] or None
        mode = qs.get("mode", ["asset"])[0]
        video_param = qs.get("video", [""])[0].strip()  # optional: single video number
        single_video = None
        if video_param:
            try:
                single_video = int(video_param)
            except ValueError:
                self._send_json({"error": "video must be a number"}, code=400)
                return

        if not topic or not date:
            self._send_json({"error": "Both topic and date required"}, code=400)
            return

        # Find the specific report by normalized topic slug. Supports nested topics
        # such as reports/claude_code/claude_code_design/{date}.md and refuses to
        # silently fall back to an unrelated topic.
        report_path, topic_folder = _resolve_report_path(topic, date)
        if not report_path:
            self._send_json({"error": f"Report not found: {topic}/{date}"}, code=404)
            return

        with_audio = mode in ("audio", "all")
        with_social = mode in ("social", "all")

        # Load credentials for AI
        if with_audio or with_social:
            for creds in (PROJECT_ROOT / "credentials.env", Path.home() / ".credentials.env"):
                if creds.exists():
                    for line in creds.read_text().splitlines():
                        if "=" in line and not line.startswith("#"):
                            k, _, v = line.partition("=")
                            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

        topic_slug = _slug(topic_folder or topic)
        # Per-video jobs use a distinct status key so they don't collide with full-report jobs
        date_key = f"{date}-v{single_video}" if single_video else date
        status_key = (topic_slug, date_key)
        gen_key = (topic_slug, date_key)

        # AI modes (audio/social) take minutes — run in background thread so Cloudflare
        # tunnel doesn't time out (30s default). Return "started" immediately; JS polls
        # gen-status every 5s until "done" or "error".
        if with_audio or with_social:
            ai_module = _get_ai_client()

            DashboardHandler._status_store[status_key] = ("generating", time.time())
            DashboardHandler._generating_set.add(gen_key)

            def _bg_generate(
                _report_path=report_path,
                _with_audio=with_audio,
                _with_social=with_social,
                _ai_module=ai_module,
                _status_key=status_key,
                _gen_key=gen_key,
                _single_video=single_video,
            ):
                try:
                    from generate_content_assets import (
                        ASSETS_DIR, AUDIO_SCRIPTS_DIR, SOCIAL_DIR,
                        build_asset_from_report, save_asset,
                        generate_audio_scripts, generate_social_posts,
                        save_audio_scripts, save_social_posts,
                        enable_content_use,
                    )
                    asset = build_asset_from_report(_report_path, REPORTS_DIR)
                    if not asset:
                        raise RuntimeError("Failed to parse report")

                    if _single_video:
                        # Enable only the requested video; leave others disabled
                        for v in asset.get("videos", []):
                            cu = v.setdefault("content_use", {})
                            if int(v.get("video_no", 0)) == _single_video:
                                if _with_audio:
                                    cu["audio_full"] = True
                                    cu["audio_short"] = True
                                if _with_social:
                                    cu["social_post"] = True
                            else:
                                cu["audio_full"] = False
                                cu["audio_short"] = False
                                cu["social_post"] = False
                    else:
                        enable_content_use(asset, audio=_with_audio, social=_with_social)

                    audio_paths = []
                    social_paths = []
                    audio_n = 0
                    social_n = 0
                    if _with_audio:
                        r = generate_audio_scripts(asset, _ai_module)
                        audio_n = r.get("audio_scripts_generated", 0)
                        audio_paths = save_audio_scripts(asset, AUDIO_SCRIPTS_DIR)
                    if _with_social:
                        r = generate_social_posts(asset, _ai_module)
                        social_n = r.get("social_posts_generated", 0)
                        social_paths = save_social_posts(asset, SOCIAL_DIR)

                    save_asset(asset, ASSETS_DIR)
                    DashboardHandler._gen_results[_status_key] = {
                        "audio_scripts_generated": audio_n,
                        "social_posts_generated": social_n,
                        "audio_paths": [str(p.relative_to(PROJECT_ROOT)) for p in audio_paths],
                        "social_paths": [str(p.relative_to(PROJECT_ROOT)) for p in social_paths],
                    }
                    DashboardHandler._status_store[_status_key] = ("done", time.time())
                except Exception as exc:
                    DashboardHandler._gen_results[_status_key] = {"error": str(exc)}
                    DashboardHandler._status_store[_status_key] = ("error", time.time())
                finally:
                    DashboardHandler._generating_set.discard(_gen_key)

            import threading as _threading
            _threading.Thread(target=_bg_generate, daemon=True).start()
            self._send_json({"status": "started", "topic": topic_slug, "date": date})
            return

        # Asset-only mode is fast — run synchronously as before
        DashboardHandler._status_store[status_key] = ("generating", time.time())
        DashboardHandler._generating_set.add(gen_key)
        try:
            from generate_content_assets import (
                ASSETS_DIR, build_asset_from_report, save_asset, enable_content_use,
            )
            asset = build_asset_from_report(report_path, REPORTS_DIR)
            if not asset:
                DashboardHandler._status_store[status_key] = ("error", time.time())
                self._send_json({"error": "Failed to parse report"}, code=500)
                return

            enable_content_use(asset)
            asset_path = save_asset(asset, ASSETS_DIR)
            DashboardHandler._status_store[status_key] = ("done", time.time())
        except Exception as exc:
            DashboardHandler._status_store[status_key] = ("error", time.time())
            self._send_json({"error": str(exc)}, code=500)
            return
        finally:
            DashboardHandler._generating_set.discard(gen_key)

        self._send_json({
            "generated": 1,
            "total_videos": asset.get("total_videos", 0),
            "with_audio": False,
            "with_social": False,
            "topic": topic_slug,
            "date": date,
            "report_path": str(report_path.relative_to(REPORTS_DIR)),
            "asset_path": str(asset_path.relative_to(PROJECT_ROOT)),
            "audio_scripts_generated": 0,
            "audio_paths": [],
            "social_posts_generated": 0,
            "social_paths": [],
        })


    def api_audio_serve(self):
        """Serve a WAV file for browser download. Optional video=N (1-based) selects specific file."""
        qs = parse_qs(urlparse(self.path).query)
        topic = qs.get("topic", [""])[0].strip()
        date  = qs.get("date",  [""])[0].strip()
        video = qs.get("video", [""])[0].strip()
        if not topic or not DATE_OR_REPORT_STEM_RE.match(date):
            self.send_error(400)
            return

        audio_base = PROJECT_ROOT / "ai_trends_reports" / "audio"
        topic_dir  = _find_topic_dir(audio_base, topic, _slug(topic))
        if not topic_dir:
            self.send_error(404)
            return

        candidates = find_voice_files(topic_dir, topic, date)
        if not candidates:
            self.send_error(404)
            return

        if video and video.isdigit():
            idx = int(video) - 1
            wav_path = candidates[idx] if 0 <= idx < len(candidates) else candidates[0]
        else:
            wav_path = candidates[0]
        data = wav_path.read_bytes()
        fname = wav_path.name
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
        self.end_headers()
        self.wfile.write(data)

    def api_voice_serve(self):
        """Serve a voice WAV file from voice/ directory (per-video, canonical naming)."""
        qs = parse_qs(urlparse(self.path).query)
        topic = qs.get("topic", [""])[0].strip()
        date  = qs.get("date",  [""])[0].strip()
        video = qs.get("video", [""])[0].strip()
        vtype = qs.get("type",  ["full"])[0].strip()
        if not topic or not DATE_OR_REPORT_STEM_RE.match(date) or not video or not video.isdigit():
            self.send_error(400)
            return
        if vtype not in ("full", "deep_dive"):
            self.send_error(400)
            return

        voice_base = PROJECT_ROOT / "ai_trends_reports" / "voice"
        topic_slug = _slug(topic)
        voice_dir  = _find_topic_dir(voice_base, topic, topic_slug)
        if not voice_dir:
            self.send_error(404)
            return

        fname = voice_filename(voice_dir.name, date, video_no=int(video), variant=vtype)
        wav_path = voice_dir / fname
        if not wav_path.exists():
            self.send_error(404)
            return

        data = wav_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
        self.end_headers()
        self.wfile.write(data)

    def api_social_view(self):
        """Return social posts JSON for a topic+date."""
        qs = parse_qs(urlparse(self.path).query)
        topic = qs.get("topic", [""])[0].strip()
        date  = qs.get("date",  [""])[0].strip()
        if not topic or not DATE_OR_REPORT_STEM_RE.match(date):
            self._send_json({"error": "Invalid topic or date"}, code=400)
            return

        social_base = PROJECT_ROOT / "ai_trends_reports" / "social"
        topic_dir   = _find_topic_dir(social_base, topic, _slug(topic))
        if not topic_dir:
            self._send_json({"error": "Social posts not found"}, code=404)
            return

        social_file = topic_dir / f"{date}.json"
        if not social_file.exists():
            self._send_json({"error": "No social posts for this date"}, code=404)
            return

        try:
            posts = json.loads(social_file.read_text(encoding="utf-8"))
            self._send_json({"posts": posts})
        except Exception as exc:
            self._send_json({"error": str(exc)}, code=500)

    def download_report(self):
        """Serve a Markdown report file as a download attachment."""
        qs = parse_qs(urlparse(self.path).query)
        topic = qs.get("topic", [""])[0].strip()
        date  = qs.get("date",  [""])[0].strip()
        if not topic or not DATE_OR_REPORT_STEM_RE.match(date):
            self.send_error(400)
            return

        report_path, _ = _resolve_report_path(topic, date)
        if not report_path:
            self.send_error(404)
            return

        try:
            data = report_path.read_bytes()
        except OSError:
            self.send_error(404)
            return

        fname = f"{_slug(topic)}-{date}.md"
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def view_report(self):
        """Render a Markdown report as HTML for in-browser reading (mobile-friendly)."""
        qs = parse_qs(urlparse(self.path).query)
        topic = qs.get("topic", [""])[0].strip()
        date  = qs.get("date",  [""])[0].strip()
        if not topic or not DATE_OR_REPORT_STEM_RE.match(date):
            self.send_error(400)
            return

        report_path, _ = _resolve_report_path(topic, date)
        if not report_path:
            self.send_error(404)
            return

        try:
            text = report_path.read_text(encoding="utf-8")
        except OSError:
            self.send_error(404)
            return

        if _MD_OK:
            body_html = _md_lib.markdown(text, extensions=["nl2br", "fenced_code"])
        else:
            body_html = f"<pre style='white-space:pre-wrap;word-break:break-word'>{h(text)}</pre>"

        title = h(f"{topic} — {date}")
        html_page = f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  body{{max-width:820px;margin:0 auto;padding:16px 18px;font-family:-apple-system,Arial,sans-serif;font-size:16px;line-height:1.7;color:#1a202c;background:#fff}}
  h1,h2,h3{{color:#111827;line-height:1.3}}
  h1{{font-size:1.5em}} h2{{font-size:1.25em;border-bottom:1px solid #e5e7eb;padding-bottom:4px}} h3{{font-size:1.1em}}
  a{{color:#1d4ed8}} pre,code{{background:#f3f4f6;border-radius:4px;padding:2px 6px;font-size:14px;word-break:break-word;white-space:pre-wrap}}
  pre{{padding:12px;overflow-x:auto}}
  .nav{{margin-bottom:16px;font-size:14px;color:#6b7280}}
</style>
</head>
<body>
<p class="nav">📄 {title} &nbsp;·&nbsp; <a href="/download/report?topic={quote(topic)}&date={quote(date)}">⬇ Download .md</a></p>
{body_html}
</body>
</html>"""
        data = html_page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def download_full_detail(self):
        """Serve a Full Detail Markdown file as a download attachment."""
        qs = parse_qs(urlparse(self.path).query)
        topic = qs.get("topic", [""])[0].strip()
        date  = qs.get("date",  [""])[0].strip()
        video = qs.get("video", ["1"])[0].strip()
        if not topic or not DATE_OR_REPORT_STEM_RE.match(date) or not video.isdigit():
            self.send_error(400)
            return

        full_detail_path = _full_detail_path(topic, date, int(video))
        if not full_detail_path or not full_detail_path.exists():
            self.send_error(404)
            return

        try:
            data = full_detail_path.read_bytes()
        except OSError:
            self.send_error(404)
            return

        fname = f"{_slug(topic)}-{date}-v{video}-full-detail.md"
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def view_full_detail(self):
        """Render a Full Detail file as HTML for in-browser reading."""
        qs = parse_qs(urlparse(self.path).query)
        topic = qs.get("topic", [""])[0].strip()
        date  = qs.get("date",  [""])[0].strip()
        video = qs.get("video", ["1"])[0].strip()
        if not topic or not DATE_OR_REPORT_STEM_RE.match(date) or not video.isdigit():
            self.send_error(400)
            return

        full_detail_path = _full_detail_path(topic, date, int(video))
        if not full_detail_path or not full_detail_path.exists():
            self.send_error(404)
            return

        try:
            text = full_detail_path.read_text(encoding="utf-8")
        except OSError:
            self.send_error(404)
            return

        if _MD_OK:
            body_html = _md_lib.markdown(text, extensions=["nl2br", "fenced_code"])
        else:
            body_html = f"<pre style='white-space:pre-wrap;word-break:break-word'>{h(text)}</pre>"

        title = h(f"{topic} — {date} — Full Detail v{video}")
        html_page = f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  body{{max-width:820px;margin:0 auto;padding:16px 18px;font-family:-apple-system,Arial,sans-serif;font-size:16px;line-height:1.7;color:#1a202c;background:#fff}}
  h1,h2,h3{{color:#111827;line-height:1.3}}
  h1{{font-size:1.5em}} h2{{font-size:1.25em;border-bottom:1px solid #e5e7eb;padding-bottom:4px}} h3{{font-size:1.1em}}
  a{{color:#1d4ed8}} pre,code{{background:#f3f4f6;border-radius:4px;padding:2px 6px;font-size:14px;word-break:break-word;white-space:pre-wrap}}
  pre{{padding:12px;overflow-x:auto}}
  .nav{{margin-bottom:16px;font-size:14px;color:#6b7280}}
</style>
</head>
<body>
<p class="nav">🔎 {title} &nbsp;·&nbsp; <a href="/download/full-detail?topic={quote(topic)}&date={quote(date)}&video={quote(video)}">⬇ Download .md</a></p>
{body_html}
</body>
</html>"""
        data = html_page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def view_audio(self):
        """List all audio files for a topic+date with inline players and download links."""
        qs = parse_qs(urlparse(self.path).query)
        topic = qs.get("topic", [""])[0].strip()
        date  = qs.get("date",  [""])[0].strip()
        if not topic or not DATE_OR_REPORT_STEM_RE.match(date):
            self.send_error(400)
            return

        audio_base = PROJECT_ROOT / "ai_trends_reports" / "audio"
        topic_dir  = _find_topic_dir(audio_base, topic, _slug(topic))
        files = find_voice_files(topic_dir, topic, date) if topic_dir else []

        title = h(f"Audio — {topic} · {date}")
        if not files:
            items_html = "<p>ไม่พบไฟล์เสียงสำหรับวันนี้</p>"
        else:
            items = []
            for i, f in enumerate(files, 1):
                serve_url = f"/api/audio/serve?topic={quote(topic)}&date={quote(date)}&video={i}"
                items.append(f"""<div class="track">
  <p class="label">Video {i} — {h(f.name)}</p>
  <audio controls style="width:100%;margin-bottom:6px"><source src="{serve_url}" type="audio/wav"></audio>
  <a class="dl" href="{serve_url}">⬇ Download {h(f.name)}</a>
</div>""")
            items_html = "\n".join(items)

        html_page = f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  body{{max-width:720px;margin:0 auto;padding:16px 18px;font-family:-apple-system,Arial,sans-serif;font-size:16px;line-height:1.6;color:#1a202c;background:#fff}}
  h1{{font-size:1.3em;color:#111827;margin-bottom:16px}}
  .track{{background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px;margin-bottom:14px}}
  .label{{margin:0 0 8px;font-weight:600;font-size:14px;color:#374151}}
  .dl{{font-size:13px;color:#1d4ed8;text-decoration:none}}
  .nav{{margin-bottom:16px;font-size:14px;color:#6b7280}}
</style>
</head>
<body>
<p class="nav">🎧 {title}</p>
<h1>Audio Reports — {h(topic)} · {h(date)}</h1>
{items_html}
</body>
</html>"""
        data = html_page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def api_assets_videos(self):
        """Return per-video status JSON for a topic+date."""
        qs = parse_qs(urlparse(self.path).query)
        topic = qs.get("topic", [""])[0].strip()
        date  = qs.get("date",  [""])[0].strip()
        if not topic or not DATE_OR_REPORT_STEM_RE.match(date):
            self._send_json({"error": "topic and date required"}, code=400)
            return

        try:
            from generate_content_assets import ASSETS_DIR, AUDIO_SCRIPTS_DIR
        except ImportError:
            self._send_json({"error": "Asset module not available"}, code=500)
            return

        assets_dir = ASSETS_DIR
        topic_slug = _slug(topic)
        asset_dir = _find_topic_dir(assets_dir, topic, topic_slug)
        if not asset_dir:
            self._send_json({"error": "Asset folder not found"}, code=404)
            return

        asset_file = asset_dir / f"{date}.json"
        if not asset_file.exists():
            self._send_json({"error": "Asset JSON not found"}, code=404)
            return

        try:
            asset_data = json.loads(asset_file.read_text(encoding="utf-8"))
        except Exception as exc:
            self._send_json({"error": str(exc)}, code=500)
            return

        scripts_base = AUDIO_SCRIPTS_DIR
        voice_base   = PROJECT_ROOT / "ai_trends_reports" / "voice"
        scripts_dir  = _find_topic_dir(scripts_base, topic, topic_slug)
        voice_dir    = _find_topic_dir(voice_base, topic, topic_slug)

        videos_out = []
        for v in asset_data.get("videos", []):
            vno = v.get("video_no", 1)
            full_script_path  = (scripts_dir / f"{date}-v{vno}.md") if scripts_dir else None
            dd_script_path    = (scripts_dir / f"{date}-v{vno}-deep-dive.md") if scripts_dir else None
            from voice_filenames import voice_filename as _vf
            full_voice_name  = _vf(voice_dir.name if voice_dir else topic_slug, date, video_no=vno, variant="full")
            dd_voice_name    = _vf(voice_dir.name if voice_dir else topic_slug, date, video_no=vno, variant="deep_dive")
            full_voice_path  = (voice_dir / full_voice_name) if voice_dir else None
            dd_voice_path    = (voice_dir / dd_voice_name)   if voice_dir else None

            videos_out.append({
                "video_no":   vno,
                "title":      v.get("title", ""),
                "source_url": v.get("source_url", ""),
                "full_script":      {"exists": bool(full_script_path and full_script_path.exists())},
                "deep_dive_script": {"exists": bool(dd_script_path and dd_script_path.exists())},
                "full_voice":       {"exists": bool(full_voice_path and full_voice_path.exists())},
                "deep_dive_voice":  {"exists": bool(dd_voice_path and dd_voice_path.exists())},
            })

        self._send_json({
            "topic":        topic_slug,
            "date":         date,
            "total_videos": asset_data.get("total_videos", len(videos_out)),
            "videos":       videos_out,
        })

    def api_catalog(self):
        """Read-only catalog API for FAW bridge / external consumers.

        GET /api/catalog                    → list topics + date counts
        GET /api/catalog?topic=X            → list dates for topic
        GET /api/catalog?topic=X&date=Y     → full video detail for topic/date

        Returns FAW-ready metadata: video_id, source_url, summary_short,
        tags, keywords, content_use, social_posts. Never mutates data.
        """
        qs = parse_qs(urlparse(self.path).query)
        topic = qs.get("topic", [""])[0].strip()
        date_val = qs.get("date", [""])[0].strip()

        try:
            from generate_content_assets import ASSETS_DIR
        except ImportError:
            self._send_json({"error": "Asset module not available"}, code=500)
            return

        assets_dir = ASSETS_DIR

        # Mode 1: no topic → list all topics
        if not topic:
            topics = []
            if assets_dir.exists():
                for d in sorted(assets_dir.iterdir()):
                    if not d.is_dir():
                        continue
                    jsons = [f for f in d.iterdir() if f.suffix == ".json"]
                    if jsons:
                        topics.append({
                            "topic": d.name,
                            "date_count": len(jsons),
                            "latest_date": max(f.stem for f in jsons),
                        })
            self._send_json({"topics": topics})
            return

        topic_slug = _slug(topic)
        asset_dir = _find_topic_dir(assets_dir, topic, topic_slug)
        if not asset_dir:
            self._send_json({"error": f"Topic '{topic}' not found"}, code=404)
            return

        # Mode 2: topic only → list dates
        if not date_val:
            dates = sorted(
                (f.stem for f in asset_dir.iterdir() if f.suffix == ".json"),
                reverse=True,
            )
            self._send_json({"topic": asset_dir.name, "dates": dates})
            return

        # Mode 3: topic + date → full video detail
        asset_file = asset_dir / f"{date_val}.json"
        if not asset_file.exists():
            self._send_json({"error": f"No asset for {asset_dir.name}/{date_val}"}, code=404)
            return

        try:
            asset = json.loads(asset_file.read_text(encoding="utf-8"))
        except Exception as exc:
            self._send_json({"error": str(exc)}, code=500)
            return

        videos = []
        for v in asset.get("videos", []):
            use = v.get("content_use") or {}
            social = v.get("social_posts") or {}
            videos.append({
                "video_no": v.get("video_no", 0),
                "video_id": v.get("video_id", ""),
                "video_title": v.get("video_title", ""),
                "thai_title": v.get("thai_title", ""),
                "source_url": v.get("source_url", ""),
                "summary_short": v.get("summary_short", ""),
                "keywords": v.get("keywords", []),
                "tags": v.get("tags", []),
                "content_use": use,
                "social_facebook": social.get("facebook", ""),
                "social_hashtags": social.get("hashtags", []),
                "faw_ready": bool(use.get("social_post") or use.get("sonar_storytelling")),
            })

        self._send_json({
            "topic": asset_dir.name,
            "date": date_val,
            "report_path": asset.get("report_path", ""),
            "total_videos": asset.get("total_videos", len(videos)),
            "videos": videos,
        })

    def render_assets_manage(self):
        """Server-rendered manage page — per-video cards with script + voice actions."""
        qs = parse_qs(urlparse(self.path).query)
        topic = qs.get("topic", [""])[0].strip()
        date  = qs.get("date",  [""])[0].strip()

        if not topic or not DATE_OR_REPORT_STEM_RE.match(date):
            self.send_html(page("Manage", '<p class="failed">topic and date required</p>'))
            return

        try:
            from generate_content_assets import ASSETS_DIR, AUDIO_SCRIPTS_DIR
        except ImportError:
            self.send_html(page("Manage", '<p class="failed">Asset module not available</p>'))
            return

        topic_slug = _slug(topic)
        assets_dir = ASSETS_DIR
        asset_dir  = _find_topic_dir(assets_dir, topic, topic_slug)
        asset_file = (asset_dir / f"{date}.json") if asset_dir else None

        if not asset_file or not asset_file.exists():
            self.send_html(page("Manage", f'<p class="failed">No asset JSON for {h(topic)} / {h(date)}. Generate asset first.</p><p><a href="/assets">← Back to Assets</a></p>'))
            return

        try:
            asset_data = json.loads(asset_file.read_text(encoding="utf-8"))
        except Exception as exc:
            self.send_html(page("Manage", f'<p class="failed">Error reading asset: {h(str(exc))}</p>'))
            return

        scripts_base = AUDIO_SCRIPTS_DIR
        voice_base   = PROJECT_ROOT / "ai_trends_reports" / "voice"
        scripts_dir  = _find_topic_dir(scripts_base, topic, topic_slug)
        voice_dir    = _find_topic_dir(voice_base, topic, topic_slug)

        from voice_filenames import voice_filename as _vf

        display_topic = h(asset_data.get("topic", topic))
        safe_topic    = h(topic_slug)
        safe_date     = h(date)
        total_videos  = asset_data.get("total_videos", 0)
        full_detail_enabled = True
        is_automated_audio_topic = topic_slug in AUTOMATED_AUDIO_TOPICS

        # Build per-video card data
        card_data = []
        for v in asset_data.get("videos", []):
            vno = v.get("video_no", 1)
            full_script_path = (scripts_dir / f"{date}-v{vno}.md") if scripts_dir else None
            dd_script_path   = (scripts_dir / f"{date}-v{vno}-deep-dive.md") if scripts_dir else None
            vdir_name = voice_dir.name if voice_dir else topic_slug
            full_voice_path  = (voice_dir / _vf(vdir_name, date, video_no=vno, variant="full"))  if voice_dir else None
            dd_voice_path    = (voice_dir / _vf(vdir_name, date, video_no=vno, variant="deep_dive")) if voice_dir else None
            full_detail_file = _full_detail_path(topic_slug, date, vno) if full_detail_enabled else None

            card_data.append({
                "vno":          vno,
                "title":        h(v.get("title", f"Video {vno}")),
                "source_url":   h(v.get("source_url", "")),
                "has_full_s":   bool(full_script_path and full_script_path.exists()),
                "has_dd_s":     bool(dd_script_path and dd_script_path.exists()),
                "has_full_v":   bool(full_voice_path and full_voice_path.exists()),
                "has_dd_v":     bool(dd_voice_path and dd_voice_path.exists()),
                "has_full_detail": bool(full_detail_file and full_detail_file.exists()),
            })

        # Build video cards HTML
        cards_html = ""
        for c in card_data:
            vno       = c["vno"]
            has_fs    = c["has_full_s"]
            has_dds   = c["has_dd_s"]
            has_fv    = c["has_full_v"]
            has_ddv   = c["has_dd_v"]
            has_fd    = c["has_full_detail"]

            def _dot(ok):
                return '<span style="color:#16a34a">●</span>' if ok else '<span style="color:#d1d5db">●</span>'

            src_link = f' <a href="{c["source_url"]}" target="_blank" rel="noopener" style="font-size:12px;color:#6366f1">↗</a>' if c["source_url"] else ""
            full_voice_download = (
                f"<a class='btn-sm' href='/api/voice/serve?topic={safe_topic}&date={safe_date}&video={vno}&type=full' "
                "download title='Download Quick Script voice WAV'>⬇️ Voice</a>"
                if has_fv else ""
            )
            dd_voice_download = (
                f"<a class='btn-sm' href='/api/voice/serve?topic={safe_topic}&date={safe_date}&video={vno}&type=deep_dive' "
                "download title='Download Long Narration voice WAV'>⬇️ Narration Voice</a>"
                if has_ddv else ""
            )

            fd_gen_option = (
                f'<option value="full_detail">Full Detail — from transcript{" (regenerate)" if has_fd else ""}</option>'
                if full_detail_enabled else ""
            )
            fd_view_option = (
                f'<option value="full_detail"{"" if has_fd else " disabled"}>Full Detail{"" if has_fd else " (not generated)"}</option>'
                if full_detail_enabled else ""
            )
            fd_dot = f' &nbsp;{_dot(has_fd)} Full Detail' if full_detail_enabled else ""

            cards_html += f'''<div class="vcard" id="vcard-{vno}">
<div class="vcard-header">
  <span class="vcard-num">Video {vno}</span>
  <span class="vcard-title">{c["title"]}{src_link}</span>
  <span class="vcard-dots">{_dot(has_fs)} Quick Script &nbsp;{_dot(has_dds)} Long Narration &nbsp;{_dot(has_fv)} Voice &nbsp;{_dot(has_ddv)} Narration Voice{fd_dot}</span>
</div>
<div class="vcard-actions">
  <select class="btn-sm" id="gentype-{vno}" title="Choose what to generate">
    <option value="full">Quick Script (~400w, from report)</option>
    <option value="deep_dive">Long Narration (~10min, from report)</option>
    {fd_gen_option}
  </select>
  <button class="btn-sm" onclick="genSelected('{safe_topic}','{safe_date}',{vno})" title="Generate the selected type via AI">🤖 Generate</button>
  <select class="btn-sm" id="viewtype-{vno}" title="Choose what to view">
    <option value="full"{' disabled' if not has_fs else ''}>Quick Script{'' if has_fs else ' (not generated)'}</option>
    <option value="deep_dive"{' disabled' if not has_dds else ''}>Long Narration{'' if has_dds else ' (not generated)'}</option>
    {fd_view_option}
  </select>
  <button class="btn-sm" onclick="viewSelected('{safe_topic}','{safe_date}',{vno})" title="Open the selected type">📄 View</button>
  <button class="btn-sm{'' if has_fs else ' disabled-btn'}" onclick="genVoice('{safe_topic}','{safe_date}',{vno},'full')" title="Generate voice from saved Quick Script" {'disabled' if not has_fs else ''}>🎙️ Voice</button>
  <button class="btn-sm{'' if has_dds else ' disabled-btn'}" onclick="genVoice('{safe_topic}','{safe_date}',{vno},'deep_dive')" title="Generate voice from saved Long Narration" {'disabled' if not has_dds else ''}>🎧 Narration Voice</button>
  {full_voice_download}
  {dd_voice_download}
  <span id="vstatus-{vno}" class="muted" style="font-size:12px"></span>
</div>
</div>'''

        # Build script editor section
        editor_html = f'''<section id="manageEditor" style="display:none;border:2px solid #6366f1;margin-top:24px">
  <h2>🎙️ Script Editor <span id="manageMeta" class="muted" style="font-size:14px"></span></h2>
  <p class="muted" style="font-size:13px">Voice generation uses the saved script below only. Edit then Save before generating voice.</p>
  <input type="hidden" id="meTopic"><input type="hidden" id="meDate"><input type="hidden" id="meVideo"><input type="hidden" id="meType">
  <textarea id="meContent" style="width:100%;min-height:360px;font-family:ui-monospace,monospace;font-size:13px"></textarea>
  <p>
    <button type="button" onclick="saveManageScript()">💾 Save Script</button>
    <button type="button" class="secondary" onclick="genVoiceFromEditor()">🎙️ Generate Voice from Saved Script</button>
    <button type="button" class="secondary" onclick="document.getElementById('manageEditor').style.display='none'">Close</button>
    <span id="meStatus" class="muted"></span>
  </p>
</section>'''

        # Bulk voice section
        checkboxes_html = "".join(
            f'<label style="display:block;margin:4px 0"><input type="checkbox" class="bv-check" data-vno="{c["vno"]}" data-type="full"> Video {c["vno"]} — {c["title"]}</label>'
            for c in card_data
        )
        bulk_html = f'''<section style="margin-top:24px">
  <h2>Bulk Voice Generation</h2>
  <p class="muted" style="font-size:13px">Select videos to generate full voice for. Requires saved script per video. Runs sequentially.</p>
  {checkboxes_html}
  <p style="margin-top:8px">
    <button type="button" id="bulkVoiceBtn" onclick="runBulkVoice()" disabled>🎙️ Generate Voice for Selected</button>
    <span id="bulkStatus" class="muted" style="font-size:13px"></span>
  </p>
</section>'''

        # Regen All Scripts button
        regen_html = f'''<section style="margin-top:16px">
  <button type="button" class="secondary" onclick="regenAllScripts('{safe_topic}','{safe_date}')">🔄 Regen All Scripts</button>
  <span class="muted" style="font-size:12px"> — regenerates full audio scripts for all {total_videos} video(s) using AI</span>
  <span id="regenStatus" style="margin-left:12px;font-size:13px;color:#6366f1"></span>
</section>'''

        # Inline JS for manage page
        js = f'''<script>
var _manageTopic='{safe_topic}', _manageDate='{safe_date}';
var _isAutomatedAudioTopic={json.dumps(is_automated_audio_topic)};

function genSelected(topic,date,video){{
  var type=document.getElementById('gentype-'+video).value;
  if(type==='full') genScriptVideo(topic,date,video);
  else if(type==='deep_dive') genDeepDive(topic,date,video);
  else if(type==='full_detail') genFullDetail(topic,date,video);
}}

function viewSelected(topic,date,video){{
  var type=document.getElementById('viewtype-'+video).value;
  if(type==='full_detail'){{
    window.open('/view/full-detail?topic='+encodeURIComponent(topic)+'&date='+encodeURIComponent(date)+'&video='+encodeURIComponent(video),'_blank');
  }} else {{
    openManageScript(topic,date,video,type);
  }}
}}

function genFullDetail(topic,date,video){{
  var vstatus=document.getElementById('vstatus-'+video);
  if(!confirm('Generate FULL DETAIL for v'+video+'?\\nRe-reads the original video transcript (not the report) — takes longer than Quick Script.')) return;
  if(vstatus) vstatus.textContent='⏳ Generating Full Detail (may take 1-2 min)...';
  var body=new URLSearchParams({{topic:topic,date:date,video:video}});
  fetch('/api/assets/generate-full-detail',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:body}})
    .then(function(r){{return r.json()}})
    .then(function(data){{
      if(data.error){{if(vstatus) vstatus.textContent='Error: '+data.error;alert('Error: '+data.error);return;}}
      if(data.status==='exists'){{
        if(!confirm('Full Detail already exists for v'+video+'. Regenerate and overwrite?')){{
          if(vstatus) vstatus.textContent='';
          return;
        }}
        var body2=new URLSearchParams({{topic:topic,date:date,video:video,force:'1'}});
        if(vstatus) vstatus.textContent='⏳ Regenerating Full Detail...';
        fetch('/api/assets/generate-full-detail',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:body2}})
          .then(function(r2){{return r2.json()}})
          .then(function(d2){{
            if(d2.error){{if(vstatus) vstatus.textContent='Error: '+d2.error;alert('Error: '+d2.error);return;}}
            if(vstatus) vstatus.textContent='✅ Full Detail ready';
            setTimeout(function(){{location.reload();}},1500);
          }})
          .catch(function(err){{if(vstatus) vstatus.textContent='Error: '+err;}});
        return;
      }}
      if(vstatus) vstatus.textContent='✅ Full Detail ready';
      setTimeout(function(){{location.reload();}},1500);
    }})
    .catch(function(err){{if(vstatus) vstatus.textContent='Error: '+err;alert('Error: '+err);}});
}}

function openManageScript(topic,date,video,type){{
  var st=document.getElementById('meStatus');
  st.textContent='Loading...';
  fetch('/api/assets/script?topic='+encodeURIComponent(topic)+'&date='+encodeURIComponent(date)+'&video='+encodeURIComponent(video)+'&type='+encodeURIComponent(type))
    .then(function(r){{return r.json()}})
    .then(function(data){{
      if(data.error){{alert('Error: '+data.error);return;}}
      document.getElementById('meTopic').value=data.topic;
      document.getElementById('meDate').value=data.date;
      document.getElementById('meVideo').value=data.video;
      document.getElementById('meType').value=data.type;
      document.getElementById('meContent').value=data.content||'';
      document.getElementById('manageMeta').textContent=data.topic+' / '+data.date+' / v'+data.video+' / '+data.type+' — '+(data.exists?'saved':'missing');
      document.getElementById('manageEditor').style.display='block';
      document.getElementById('manageEditor').scrollIntoView({{behavior:'smooth'}});
      st.textContent=data.exists?'Loaded · '+data.voice_text_chars+' chars':'Script missing — paste content and Save';
    }})
    .catch(function(err){{alert('Error: '+err);}});
}}

function saveManageScript(){{
  var topic=document.getElementById('meTopic').value;
  var date=document.getElementById('meDate').value;
  var video=document.getElementById('meVideo').value;
  var type=document.getElementById('meType').value;
  var content=document.getElementById('meContent').value;
  var st=document.getElementById('meStatus');
  st.textContent='Saving...';
  var body=new URLSearchParams({{topic:topic,date:date,video:video,type:type,content:content}});
  fetch('/api/assets/script',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:body}})
    .then(function(r){{return r.json()}})
    .then(function(data){{
      if(data.error){{st.textContent='Error: '+data.error;return;}}
      st.textContent='✅ Saved';
      setTimeout(function(){{location.reload();}},1200);
    }})
    .catch(function(err){{st.textContent='Error: '+err;}});
}}

function genVoice(topic,date,video,type){{
  var vstatus=document.getElementById('vstatus-'+video);
  if(vstatus) vstatus.textContent='Generating...';
  if(!confirm('Generate '+type+' voice for v'+video+' from SAVED script?\\nThis uses Gemini TTS.')) return;
  var body=new URLSearchParams({{topic:topic,date:date,video:video,type:type}});
  fetch('/api/assets/generate-voice',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:body}})
    .then(function(r){{return r.json()}})
    .then(function(data){{
      if(data.error){{if(vstatus) vstatus.textContent='Error: '+data.error;alert('Error: '+data.error);return;}}
      if(vstatus) vstatus.textContent='✅ Done';
      setTimeout(function(){{location.reload();}},1500);
    }})
    .catch(function(err){{if(vstatus) vstatus.textContent='Error: '+err;alert('Error: '+err);}});
}}

function genVoiceFromEditor(){{
  var topic=document.getElementById('meTopic').value;
  var date=document.getElementById('meDate').value;
  var video=document.getElementById('meVideo').value;
  var type=document.getElementById('meType').value;
  genVoice(topic,date,video,type);
}}

function genScriptVideo(topic,date,video){{
  var vstatus=document.getElementById('vstatus-'+video);
  var warnMsg='Generate Quick Script for Video '+video+' via AI?\\nใช้เวลาประมาณ 1 นาที';
  if(_isAutomatedAudioTopic) warnMsg+='\\n\\n⚠️ This topic has automated daily audio already emailed — regenerating here will OVERWRITE today\\'s automated script file.';
  if(!confirm(warnMsg)) return;
  if(vstatus) vstatus.textContent='⏳ กำลังส่งคำสั่ง...';
  var params='?mode=audio&topic='+encodeURIComponent(topic)+'&date='+encodeURIComponent(date)+'&video='+encodeURIComponent(video);
  fetch('/api/assets/generate-one'+params)
    .then(function(r){{return r.json()}})
    .then(function(data){{
      if(data.error){{if(vstatus) vstatus.textContent='Error: '+data.error;alert('Error: '+data.error);return;}}
      if(data.status==='started'){{
        if(vstatus) vstatus.textContent='⏳ กำลังสร้าง script...';
        var poll=setInterval(function(){{
          fetch('/api/assets/gen-status?topic='+encodeURIComponent(topic)+'&date='+encodeURIComponent(date)+'&video='+encodeURIComponent(video))
            .then(function(r){{return r.json()}})
            .then(function(d){{
              if(d.status==='done'){{
                clearInterval(poll);
                if(vstatus) vstatus.textContent='✅ Script พร้อมแล้ว — opening...';
                openManageScript(topic,date,video,'full');
                setTimeout(function(){{location.reload();}},3000);
              }}else if(d.status==='error'){{
                clearInterval(poll);
                var errMsg=d.error||'Generation failed';
                if(vstatus) vstatus.textContent='❌ '+errMsg;
                alert('Error: '+errMsg);
              }}
            }})
            .catch(function(){{}});
        }},5000);
        return;
      }}
      if(vstatus) vstatus.textContent='✅ Script พร้อมแล้ว';
      openManageScript(topic,date,video,'full');
      setTimeout(function(){{location.reload();}},3000);
    }})
    .catch(function(err){{if(vstatus) vstatus.textContent='Error: '+err;alert('Error: '+err);}});
}}

function genDeepDive(topic,date,video){{
  var vstatus=document.getElementById('vstatus-'+video);
  if(!confirm('Generate DEEP DIVE SCRIPT for v'+video+'?\\nThis uses AI (script only, no voice).')) return;
  if(vstatus) vstatus.textContent='Generating deep-dive...';
  var body=new URLSearchParams({{topic:topic,date:date,video:video}});
  fetch('/api/assets/generate-deep-dive-script',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:body}})
    .then(function(r){{return r.json()}})
    .then(function(data){{
      if(data.error){{if(vstatus) vstatus.textContent='Error: '+data.error;alert('Error: '+data.error);return;}}
      if(vstatus) vstatus.textContent='✅ Script ready — opening editor';
      openManageScript(topic,date,video,'deep_dive');
      setTimeout(function(){{location.reload();}},3000);
    }})
    .catch(function(err){{if(vstatus) vstatus.textContent='Error: '+err;alert('Error: '+err);}});
}}

function generateDeepDiveScript(topic,date,video){{
  // Backward-compatible alias for older dashboard tests/buttons: Generate deep dive script.
  return genDeepDive(topic,date,video);
}}

function regenAllScripts(topic,date){{
  if(!confirm('Regenerate ALL full audio scripts for '+topic+' '+date+'?\\nThis uses AI and overwrites existing scripts.')) return;
  var regenBtn=document.querySelector('button[onclick*="regenAllScripts"]');
  var regenSt=document.getElementById('regenStatus');
  if(regenBtn) regenBtn.disabled=true;
  if(regenSt) regenSt.textContent='⏳ กำลังส่งคำสั่ง...';
  var params='?mode=audio&topic='+encodeURIComponent(topic)+'&date='+encodeURIComponent(date);
  fetch('/api/assets/generate-one'+params)
    .then(function(r){{return r.json()}})
    .then(function(data){{
      if(data.error){{
        if(regenBtn) regenBtn.disabled=false;
        if(regenSt) regenSt.textContent='';
        alert('Error: '+data.error);
        return;
      }}
      if(data.status==='started'){{
        if(regenSt) regenSt.textContent='⏳ กำลังสร้าง script ด้วย AI... (อาจใช้เวลาหลายนาที)';
        var poll=setInterval(function(){{
          fetch('/api/assets/gen-status?topic='+encodeURIComponent(topic)+'&date='+encodeURIComponent(date))
            .then(function(r){{return r.json()}})
            .then(function(d){{
              if(d.status==='done'){{
                clearInterval(poll);
                if(regenBtn) regenBtn.disabled=false;
                if(regenSt) regenSt.textContent='';
                alert('✅ Scripts regenerated: '+(d.audio_scripts_generated||0)+' script(s)');
                location.reload();
              }}else if(d.status==='error'){{
                clearInterval(poll);
                if(regenBtn) regenBtn.disabled=false;
                if(regenSt) regenSt.textContent='';
                alert('Error: '+(d.error||'Generation failed'));
                location.reload();
              }}
            }})
            .catch(function(){{}});
        }},5000);
        return;
      }}
      if(regenBtn) regenBtn.disabled=false;
      if(regenSt) regenSt.textContent='';
      alert('✅ Scripts regenerated: '+data.audio_scripts_generated+' script(s)');
      location.reload();
    }})
    .catch(function(err){{
      if(regenBtn) regenBtn.disabled=false;
      if(regenSt) regenSt.textContent='';
      alert('Error: '+err);
    }});
}}

/* Bulk voice */
document.addEventListener('DOMContentLoaded',function(){{
  var checks=document.querySelectorAll('.bv-check');
  var btn=document.getElementById('bulkVoiceBtn');
  checks.forEach(function(cb){{cb.addEventListener('change',function(){{
    var any=Array.from(checks).some(function(c){{return c.checked;}});
    btn.disabled=!any;
  }})}});
}});

function runBulkVoice(){{
  var checks=Array.from(document.querySelectorAll('.bv-check:checked'));
  if(!checks.length) return;
  var names=checks.map(function(c){{return 'v'+c.dataset.vno;}}).join(', ');
  if(!confirm('Generate full voice for: '+names+'?\\nRuns sequentially. This uses Gemini TTS.')) return;
  var st=document.getElementById('bulkStatus');
  var btn=document.getElementById('bulkVoiceBtn');
  btn.disabled=true;
  var queue=checks.slice();
  function next(){{
    if(!queue.length){{st.textContent='✅ All done';setTimeout(function(){{location.reload();}},1500);return;}}
    var cb=queue.shift();
    var vno=cb.dataset.vno;
    st.textContent='Generating v'+vno+'...';
    var body=new URLSearchParams({{topic:_manageTopic,date:_manageDate,video:vno,type:'full'}});
    fetch('/api/assets/generate-voice',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:body}})
      .then(function(r){{return r.json()}})
      .then(function(data){{
        if(data.error){{st.textContent='Error on v'+vno+': '+data.error;btn.disabled=false;return;}}
        next();
      }})
      .catch(function(err){{st.textContent='Error: '+err;btn.disabled=false;}});
  }}
  next();
}}
</script>'''

        body = f'''<div style="display:flex;align-items:baseline;gap:16px;margin-bottom:8px">
  <h1>🎛️ Manage: {display_topic} / {safe_date}</h1>
  <a href="/assets" style="font-size:14px;color:#6366f1">← Back to Assets</a>
</div>
<p class="muted">{total_videos} video(s) · Status: ● green=exists &nbsp; ● gray=missing</p>
{regen_html}
<section style="margin-top:16px">
  <h2>Videos</h2>
  {cards_html}
</section>
{editor_html}
{bulk_html}
<style>
.vcard{{border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px;margin-bottom:12px;background:#fafafa}}
.vcard-header{{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:8px}}
.vcard-num{{font-weight:600;font-size:15px;color:#6366f1}}
.vcard-title{{font-size:14px;flex:1}}
.vcard-dots{{font-size:12px;color:#6b7280;white-space:nowrap}}
.vcard-actions{{display:flex;gap:6px;flex-wrap:wrap;align-items:center}}
.disabled-btn{{opacity:0.4;cursor:default}}
</style>
{js}'''

        self.send_html(page(f"Manage — {topic_slug}/{date}", body))


    # ── Notifications ──────────────────────────────────────────────────────

    def render_notifications(self):
        if not _NOTIFY_OK:
            self.send_html(page("Notifications", "<p>notify_topic module not available.</p>"))
            return

        defaults, topics_cfg = load_routing_config()
        live_topic_map = _load_topic_map()  # fresh read — picks up newly added jobs
        audio_cfg = load_audio_config()
        audio_enabled_set = set(audio_cfg.get("enabled_topics", []))

        # Build enabled-status lookup from research_jobs.json
        job_enabled = {j.get("id"): j.get("enabled", True) for j in load_jobs()}

        rows_html = []
        email_count = 0
        tg_count = 0
        audio_count = 0
        for topic_key, (display_name, local_folder, report_folder) in live_topic_map.items():
            cfg = {
                "email_enabled": False,
                "telegram_enabled": False,
                "recipient_emails": [],
                "telegram_chat_ids": [],
            }
            cfg.update(defaults)
            cfg.update(topics_cfg.get(topic_key, {}))

            if cfg["email_enabled"]:
                email_count += 1
            if cfg["telegram_enabled"]:
                tg_count += 1

            emails_str   = ", ".join(cfg.get("recipient_emails", []))
            chat_ids_str = ", ".join(str(c) for c in cfg.get("telegram_chat_ids", []))
            email_chk    = "checked" if cfg["email_enabled"] else ""
            tg_chk       = "checked" if cfg["telegram_enabled"] else ""
            job_en = job_enabled.get(topic_key, True)
            job_badge = '<span style="color:#16a34a;font-size:11px;font-weight:600">● Job ON</span>' if job_en else '<span style="color:#dc2626;font-size:11px;font-weight:600">○ Job OFF</span>'

            audio_key     = resolve_audio_key(topic_key, local_folder, report_folder, audio_enabled_set)
            audio_enabled = audio_key in audio_enabled_set
            if audio_enabled:
                audio_count += 1
            audio_chk = "checked" if audio_enabled else ""

            rows_html.append(f"""<tr data-key="{h(topic_key)}">
  <td>{job_badge}<br><strong>{h(display_name)}</strong><br><span class="muted" style="font-size:12px">{h(topic_key)}</span></td>
  <td style="text-align:center"><input type="checkbox" class="email-chk" {email_chk} data-key="{h(topic_key)}"></td>
  <td><input class="email-input" type="text" value="{h(emails_str)}" placeholder="email1@x.com, email2@x.com" data-key="{h(topic_key)}" style="font-size:13px"></td>
  <td style="text-align:center"><input type="checkbox" class="tg-chk" {tg_chk} data-key="{h(topic_key)}"></td>
  <td><input class="tg-input" type="text" value="{h(chat_ids_str)}" placeholder="1043709932" data-key="{h(topic_key)}" style="font-size:13px"></td>
  <td style="text-align:center"><input type="checkbox" class="audio-chk" {audio_chk} data-key="{h(topic_key)}" data-audio-key="{h(audio_key)}" data-report-folder="{h(report_folder)}"></td>
  <td><button class="secondary" style="font-size:12px;padding:5px 10px" onclick="testSend('{h(topic_key)}')">▶ Test</button></td>
</tr>""")

        table_rows = "\n".join(rows_html)
        total = len(live_topic_map)

        body = f"""<h1>🔔 Notification Routing</h1>
<div class="grid" style="grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:16px">
  <div class="metric"><span class="muted">Topics</span><strong>{total}</strong></div>
  <div class="metric"><span class="muted">Email Active</span><strong>{email_count}</strong></div>
  <div class="metric"><span class="muted">Telegram Active</span><strong>{tg_count}</strong></div>
  <div class="metric"><span class="muted">🎧 Audio Active</span><strong>{audio_count}</strong></div>
</div>
<section style="margin-bottom:16px">
  <p class="muted" style="margin:0 0 12px;font-size:14px">กำหนดได้ว่าแต่ละ topic จะส่ง email / Telegram DM / สร้างไฟล์เสียงอัตโนมัติ
  บันทึกใน <code>config/notification_routing.json</code> และ <code>config/audio_topics.json</code></p>
  <button onclick="saveAll()">💾 Save All Changes</button>
  <span id="saveStatus" style="margin-left:12px;font-size:13px"></span>
</section>
<table id="notifTable">
  <thead><tr>
    <th>Topic</th>
    <th style="text-align:center">📧 Email</th>
    <th>Recipient Emails (comma-separated)</th>
    <th style="text-align:center">💬 Telegram</th>
    <th>Chat IDs (comma-separated)</th>
    <th style="text-align:center">🎧 Audio</th>
    <th>Test</th>
  </tr></thead>
  <tbody>{table_rows}</tbody>
</table>
<div id="testResult" style="margin-top:16px;display:none">
  <section>
    <h2 style="margin-top:0">Test Result</h2>
    <pre id="testOutput" style="max-height:300px"></pre>
  </section>
</div>
<script>
function collectConfig() {{
  var cfg = {{ defaults: {{ email_enabled: false, telegram_enabled: false, notification_mode: "per_topic", recipient_emails: [], telegram_chat_ids: [] }}, topics: {{}} }};
  document.querySelectorAll('#notifTable tbody tr').forEach(function(row) {{
    var key = row.dataset.key;
    var emailEnabled = row.querySelector('.email-chk').checked;
    var tgEnabled = row.querySelector('.tg-chk').checked;
    var emailsRaw = row.querySelector('.email-input').value.trim();
    var chatIdsRaw = row.querySelector('.tg-input').value.trim();
    var emails = emailsRaw ? emailsRaw.split(',').map(function(s){{return s.trim();}}).filter(Boolean) : [];
    var chatIds = chatIdsRaw ? chatIdsRaw.split(',').map(function(s){{return s.trim();}}).filter(Boolean) : [];
    if (emailEnabled || tgEnabled || emails.length || chatIds.length) {{
      cfg.topics[key] = {{ email_enabled: emailEnabled, telegram_enabled: tgEnabled, recipient_emails: emails, telegram_chat_ids: chatIds, notification_mode: "per_topic" }};
    }}
  }});
  return cfg;
}}
function collectAudioConfig() {{
  var topics = {{}};
  document.querySelectorAll('#notifTable .audio-chk').forEach(function(chk) {{
    var jobKey = chk.dataset.key;
    var audioKey = chk.dataset.audioKey;
    var reportFolder = chk.dataset.reportFolder;
    topics[jobKey] = {{ enabled: chk.checked, audio_key: audioKey, report_folder: reportFolder }};
  }});
  return {{ topics: topics }};
}}
function saveAll() {{
  var st = document.getElementById('saveStatus');
  st.textContent = 'Saving…';
  Promise.all([
    fetch('/api/notifications/config', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(collectConfig())
    }}).then(function(r){{return r.json();}}),
    fetch('/api/audio/config', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(collectAudioConfig())
    }}).then(function(r){{return r.json();}})
  ]).then(function(results) {{
    var d1 = results[0]; var d2 = results[1];
    var ok = d1.ok && d2.ok;
    st.textContent = ok ? '✅ Saved' : ('❌ ' + (d1.error || d2.error || 'error'));
    setTimeout(function(){{st.textContent='';}}, 3000);
  }}).catch(function(e){{st.textContent='❌ ' + e;}});
}}
function testSend(topicKey) {{
  var panel = document.getElementById('testResult');
  var out = document.getElementById('testOutput');
  panel.style.display = 'block';
  out.textContent = 'Sending test for ' + topicKey + '…';
  fetch('/api/notifications/test', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{ topic_key: topicKey, dry_run: false }})
  }}).then(function(r){{return r.json();}})
  .then(function(d){{
    out.textContent = (d.stdout || '') + (d.stderr ? ('\\nSTDERR:\\n' + d.stderr) : '');
  }}).catch(function(e){{out.textContent = 'Error: ' + e;}});
}}
</script>"""
        self.send_html(page("Notifications", body))

    def api_notifications_config_get(self):
        if not _NOTIFY_OK:
            self._send_json({"error": "notify_topic not available"}, code=500)
            return
        try:
            defaults, topics = load_routing_config()
            self._send_json({"defaults": defaults, "topics": topics})
        except Exception as e:
            self._send_json({"error": str(e)}, code=500)

    def api_notifications_config_save(self, json_body):
        if not _NOTIFY_OK or ROUTING_CONFIG_PATH is None:
            self._send_json({"error": "notify_topic not available"}, code=500)
            return
        try:
            # Validate minimal structure
            if "defaults" not in json_body or "topics" not in json_body:
                self._send_json({"error": "missing defaults or topics key"}, code=400)
                return
            with open(str(ROUTING_CONFIG_PATH), "w", encoding="utf-8") as f:
                json.dump(json_body, f, ensure_ascii=False, indent=2)
            self._send_json({"ok": True})
        except Exception as e:
            self._send_json({"error": str(e)}, code=500)

    def api_audio_config_get(self):
        try:
            cfg = load_audio_config()
            self._send_json({"ok": True, "enabled_topics": cfg.get("enabled_topics", [])})
        except Exception as e:
            self._send_json({"error": str(e)}, code=500)

    def api_audio_config_save(self, json_body):
        # json_body = {"topics": {"job_id": {"enabled": bool, "audio_key": str, "report_folder": str}}}
        try:
            topics_state = json_body.get("topics", {})
            cfg = load_audio_config()
            enabled_list  = cfg.setdefault("enabled_topics", [])
            folder_map    = cfg.setdefault("github_folder_map", {})
            voice_topics  = cfg.setdefault("automated_voice_topics", {})

            for _job_id, state in topics_state.items():
                enabled       = bool(state.get("enabled", False))
                audio_key     = (state.get("audio_key") or "").strip()
                report_folder = (state.get("report_folder") or audio_key).strip()
                if not audio_key:
                    continue
                if enabled:
                    if audio_key not in enabled_list:
                        enabled_list.append(audio_key)
                    folder_map.setdefault(audio_key, report_folder)
                    voice_topics.setdefault(audio_key, {
                        "enabled": True,
                        "script_type": "full",
                        "voice_type": "full",
                        "per_video": True,
                        "publish": True,
                        "github_folder": audio_key,
                        "voice_profile": "ats_female_narrator",
                    })
                else:
                    if audio_key in enabled_list:
                        enabled_list.remove(audio_key)

            save_audio_config(cfg)
            self._send_json({"ok": True})
        except Exception as e:
            self._send_json({"error": str(e)}, code=500)

    def api_notifications_test(self, json_body):
        topic_key = (json_body.get("topic_key") or "").strip()
        date_str  = json_body.get("date") or datetime.now().strftime("%Y-%m-%d")
        dry_run   = bool(json_body.get("dry_run", False))
        if not topic_key:
            self._send_json({"error": "topic_key required"}, code=400)
            return
        script = PROJECT_ROOT / "scripts" / "notify_topic.py"
        if not script.exists():
            self._send_json({"error": "notify_topic.py not found"}, code=500)
            return
        cmd = [sys.executable, str(script), "--topic", topic_key, "--date", date_str]
        if dry_run:
            cmd.append("--dry-run")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                                    cwd=str(PROJECT_ROOT))
            self._send_json({
                "ok": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            })
        except subprocess.TimeoutExpired:
            self._send_json({"error": "timeout (60s)"}, code=500)
        except Exception as e:
            self._send_json({"error": str(e)}, code=500)


def main():
    parser = argparse.ArgumentParser(description="AI Trends local dashboard")
    parser.add_argument("--host", default=os.environ.get("AI_TRENDS_DASHBOARD_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AI_TRENDS_DASHBOARD_PORT", "8092")))
    args = parser.parse_args()
    ensure_dirs()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"AI Trends Dashboard running at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
