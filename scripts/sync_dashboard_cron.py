#!/usr/bin/env python3
"""Sync ATS Dashboard jobs from config/research_jobs.json into user crontab.

This owns only ATS research-generation lines (run_ai_trends_with_creds.sh and
run_claude_code_subtopics_with_creds.sh). Existing daily summary/upload cron
lines are preserved.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / "config" / "research_jobs.json"
RUN_TOPIC = PROJECT_ROOT / "scripts" / "run_ai_trends_with_creds.sh"
RUN_SUBTOPICS = PROJECT_ROOT / "scripts" / "run_claude_code_subtopics_with_creds.sh"
LOGS_DIR = PROJECT_ROOT / "logs"
MANAGED_PATTERNS = (str(RUN_TOPIC), str(RUN_SUBTOPICS))


def slugify(value: str) -> str:
    value = (value or "").strip().lower().replace(" ", "_").replace("-", "_")
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_") or "research_job"


def cron_prefix(time_text: str) -> str:
    if not re.fullmatch(r"\d{1,2}:\d{2}", (time_text or "").strip()):
        raise ValueError(f"Invalid schedule_time {time_text!r}; expected HH:MM")
    hour, minute = [int(x) for x in time_text.split(":")]
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid schedule_time {time_text!r}; expected HH:MM")
    return f"{minute} {hour} * * *"


def quote_cmd(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(p)) for p in parts)


def load_jobs() -> list[dict]:
    data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    jobs = data.get("jobs", []) if isinstance(data, dict) else data
    if not isinstance(jobs, list):
        raise ValueError("research_jobs.json must contain a jobs list")
    return jobs


def daily_cron_enabled(job: dict) -> bool:
    # Backward compatibility: existing production jobs predate this field, and a
    # schedule_time meant “daily job”. New Dashboard saves write the explicit field.
    if "daily_cron_enabled" in job:
        return bool(job.get("daily_cron_enabled"))
    return bool((job.get("schedule_time") or "").strip())


def transcript_arg(job: dict) -> str:
    langs = job.get("transcript_langs")
    if isinstance(langs, list):
        return ",".join(str(x).strip() for x in langs if str(x).strip())
    return str(langs or "").strip()


def topic_job_command(job: dict) -> list[str]:
    source_type = job.get("source_type", "topic")
    max_videos = str(max(1, int(job.get("max_videos") or 1)))
    topic = job.get("topic") or job.get("name") or "AI Trends"
    report_folder = job.get("report_folder") or slugify(topic)
    cmd = [
        str(RUN_TOPIC),
        "--topic", topic,
        "--report-folder", report_folder,
        "--config-job-id", job.get("id", ""),
    ]
    if source_type in {"channel", "playlist"} and job.get("source_url"):
        # yt-dlp channel date filtering can return more than --playlist-end on some
        # channel/handle URLs. Pass --count too so the configured max_videos is
        # enforced at processing time, not only at fetch time.
        cmd.extend(["--channel", job["source_url"], "--max-results", max_videos, "--count", max_videos])
    elif source_type == "video" and job.get("source_url"):
        cmd.extend(["--video-url", job["source_url"], "--count", "1"])
    else:
        cmd.extend(["--max-results", max_videos])
    langs = transcript_arg(job)
    if langs:
        cmd.extend(["--transcript-langs", langs])
    if job.get("detailed", True):
        cmd.append("--detailed")
    return cmd


def subtopic_filter(job: dict) -> str:
    topic = (job.get("topic") or job.get("name") or "").strip().lower()
    topic = topic.replace("_", " ").replace("-", " ")
    topic = topic.replace("claude code", "").strip()
    return re.sub(r"\s+", " ", topic) or slugify(job.get("id", ""))


def generate_lines(jobs: list[dict]) -> list[str]:
    lines: list[str] = []
    subtopic_groups: dict[tuple[str, str, bool], list[dict]] = defaultdict(list)

    for job in jobs:
        if not job.get("enabled", True):
            continue
        if not daily_cron_enabled(job):
            continue
        schedule = (job.get("schedule_time") or "").strip()
        if not schedule:
            continue
        if job.get("source_type") == "claude_code_subtopic":
            subtopic_groups[(schedule, transcript_arg(job), bool(job.get("detailed", True)))].append(job)
            continue
        prefix = cron_prefix(schedule)
        log_name = f"{slugify(str(job.get('id') or job.get('topic') or job.get('name') or 'research_job'))}.log"
        cmd = quote_cmd(topic_job_command(job))
        lines.append(f"{prefix} {cmd} >> {shlex.quote(str(LOGS_DIR / log_name))} 2>&1")

    for (schedule, langs, detailed), group in sorted(subtopic_groups.items()):
        prefix = cron_prefix(schedule)
        filters = ",".join(subtopic_filter(j) for j in group)
        max_results = max(max(1, int(j.get("max_videos") or 1)) for j in group)
        total_videos = sum(max(1, int(j.get("max_videos") or 1)) for j in group)
        cmd = [
            str(RUN_SUBTOPICS),
            "--only", filters,
            "--max-results", str(max_results),
            "--total-videos", str(total_videos),
        ]
        if langs:
            cmd.extend(["--transcript-langs", langs])
        if detailed:
            cmd.append("--detailed")
        log_name = f"claude_code_subtopics_{schedule.replace(':', '')}.log"
        lines.append(f"{prefix} {quote_cmd(cmd)} >> {shlex.quote(str(LOGS_DIR / log_name))} 2>&1")

    return sorted(lines, key=lambda line: tuple(int(x) for x in line.split()[:2][::-1]))


def current_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout


def remove_old_managed_lines(cron_text: str) -> list[str]:
    kept = []
    for line in cron_text.splitlines():
        if any(pattern in line for pattern in MANAGED_PATTERNS):
            continue
        kept.append(line)
    return kept


def sync(apply: bool) -> tuple[str, str, Path]:
    jobs = load_jobs()
    generated = generate_lines(jobs)
    existing = current_crontab()
    kept = remove_old_managed_lines(existing)
    # Trim trailing blank lines but preserve comments/other cron entries.
    while kept and not kept[-1].strip():
        kept.pop()
    new_lines = kept + ([""] if kept and generated else []) + generated
    new_text = "\n".join(new_lines).rstrip() + "\n"
    backup = Path("/tmp") / f"ats_crontab_before_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    backup.write_text(existing, encoding="utf-8")
    if apply:
        proc = subprocess.run(["crontab", "-"], input=new_text, text=True, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or "crontab update failed")
    return existing, new_text, backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync ATS Dashboard daily cron jobs")
    parser.add_argument("--apply", action="store_true", help="write the generated crontab")
    parser.add_argument("--print", action="store_true", help="print generated crontab")
    args = parser.parse_args()
    old, new, backup = sync(apply=args.apply)
    if args.print or not args.apply:
        print(new, end="")
    print(f"\n[ats-cron-sync] backup={backup}", flush=True)
    print(f"[ats-cron-sync] apply={args.apply} old_lines={len(old.splitlines())} new_lines={len(new.splitlines())}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
