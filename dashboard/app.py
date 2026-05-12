#!/usr/bin/env python3
"""Local dashboard for AI Trends Research jobs."""

import argparse
import html
import json
import os
import re
import subprocess
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / "config" / "research_jobs.json"
REPORTS_DIR = PROJECT_ROOT / "ai_trends_reports" / "reports"
DASHBOARD_DIR = PROJECT_ROOT / "ai_trends_reports" / "dashboard"
STATUS_FILE = DASHBOARD_DIR / "job_status.json"
LOGS_DIR = PROJECT_ROOT / "logs" / "dashboard"
RUN_TOPIC = PROJECT_ROOT / "scripts" / "run_ai_trends_with_creds.sh"
RUN_SUBTOPICS = PROJECT_ROOT / "scripts" / "run_claude_code_subtopics_with_creds.sh"

SOURCE_TYPES = ("topic", "channel", "playlist", "video", "claude_code_subtopic")
RUN_LOCK = threading.Lock()


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


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def slugify(value):
    value = value.strip().lower().replace(" ", "_")
    value = re.sub(r"[^a-z0-9_\-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:80] or "research_job"


def clean_report_folder(value, fallback):
    parts = []
    for raw in value.replace("\\", "/").split("/"):
        part = slugify(raw)
        if part and part not in {".", ".."}:
            parts.append(part)
    return "/".join(parts) if parts else fallback


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
    return files[:30]


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
            cmd.extend(["--channel", job["source_url"], "--max-results", max_videos])
        elif source_type == "video" and job.get("source_url"):
            cmd.extend(["--video-url", job["source_url"], "--count", "1"])
        else:
            cmd.extend(["--max-results", max_videos])

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
        reports = relative_files(REPORTS_DIR, ".md")
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


def page(title, body):
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{h(title)}</title>
  <style>
    :root {{ color-scheme: light; --line:#d8dee8; --ink:#172033; --muted:#5f6c80; --bg:#f6f8fb; --panel:#fff; --blue:#0d63ce; --green:#0b7a42; --red:#b42318; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: Arial, sans-serif; background:var(--bg); color:var(--ink); }}
    header {{ background:#111827; color:white; padding:16px 24px; display:flex; align-items:center; justify-content:space-between; gap:16px; }}
    header a {{ color:white; text-decoration:none; margin-left:14px; }}
    main {{ max-width:1180px; margin:0 auto; padding:22px; }}
    h1 {{ font-size:24px; margin:0 0 14px; }}
    h2 {{ font-size:18px; margin:24px 0 10px; }}
    .grid {{ display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:12px; }}
    .metric, section {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; }}
    .metric strong {{ display:block; font-size:22px; margin-top:4px; }}
    table {{ width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
    th, td {{ padding:10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; font-size:14px; }}
    th {{ background:#eef2f7; font-size:12px; text-transform:uppercase; color:var(--muted); }}
    tr:last-child td {{ border-bottom:0; }}
    .actions {{ display:flex; gap:8px; flex-wrap:wrap; }}
    button, .button {{ appearance:none; border:1px solid var(--blue); background:var(--blue); color:white; padding:8px 10px; border-radius:6px; text-decoration:none; cursor:pointer; font-size:14px; }}
    .button.secondary, button.secondary {{ background:white; color:var(--blue); }}
    button.danger {{ border-color:var(--red); background:var(--red); }}
    input, select, textarea {{ width:100%; padding:9px; border:1px solid var(--line); border-radius:6px; font:inherit; }}
    label {{ display:block; font-size:13px; color:var(--muted); margin:12px 0 5px; }}
    form.inline {{ display:inline; }}
    .form-grid {{ display:grid; grid-template-columns: 1fr 1fr; gap:0 14px; }}
    .muted {{ color:var(--muted); }}
    .pill {{ display:inline-block; border-radius:999px; padding:3px 8px; background:#edf2f7; color:#334155; font-size:12px; }}
    .success {{ color:var(--green); }}
    .failed {{ color:var(--red); }}
    pre {{ white-space:pre-wrap; background:#101828; color:#f8fafc; padding:14px; border-radius:8px; overflow:auto; max-height:560px; }}
    @media (max-width: 760px) {{ .grid, .form-grid {{ grid-template-columns:1fr; }} header {{ display:block; }} header nav {{ margin-top:8px; }} }}
  </style>
</head>
<body>
  <header>
    <strong>AI Trends Dashboard</strong>
    <nav><a href="/">Jobs</a><a href="/reports">Reports</a><a href="/logs">Logs</a><a href="/cron">Cron</a></nav>
  </header>
  <main>{body}</main>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.render_home()
        elif parsed.path == "/job":
            self.render_job_form(parse_qs(parsed.query).get("id", [""])[0])
        elif parsed.path == "/reports":
            self.render_files(REPORTS_DIR, ".md", "Reports")
        elif parsed.path == "/logs":
            self.render_files(LOGS_DIR, ".log", "Dashboard Logs")
        elif parsed.path == "/cron":
            self.render_cron()
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("content-length", "0"))
        data = parse_qs(self.rfile.read(length).decode())
        if parsed.path == "/job/save":
            self.save_job(data)
        elif parsed.path == "/job/delete":
            self.delete_job(data)
        elif parsed.path == "/job/run":
            self.run_job_action(data)
        else:
            self.send_error(404)

    def send_html(self, html_text, code=200):
        encoded = html_text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def redirect(self, target="/"):
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
            rows.append(f"""<tr>
  <td><strong>{h(job.get('name'))}</strong><br><span class="muted">{h(job.get('id'))}</span></td>
  <td><span class="pill">{h(job.get('source_type'))}</span><br>{h(job.get('topic'))}</td>
  <td>{h(job.get('source_url'))}</td>
  <td>{h(job.get('max_videos'))}</td>
  <td>{h(job.get('report_folder'))}</td>
  <td><span class="{h(state)}">{h(state)}</span><br><span class="muted">{h(st.get('last_finished_at') or st.get('last_started_at'))}</span></td>
  <td class="actions">
    <a class="button secondary" href="/job?id={quote(job['id'])}">Edit</a>
    <form class="inline" method="post" action="/job/run"><input type="hidden" name="id" value="{h(job['id'])}"><button type="submit">Run</button></form>
  </td>
</tr>""")

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
        body = f"""<h1>{'Add Job' if is_new else 'Edit Job'}</h1>
<section>
<form method="post" action="/job/save">
  <div class="form-grid">
    <div><label>Job ID</label><input name="id" value="{h(job.get('id'))}" {'readonly' if not is_new else ''} required></div>
    <div><label>Name</label><input name="name" value="{h(job.get('name'))}" required></div>
    <div><label>Source Type</label><select name="source_type">{options}</select></div>
    <div><label>Topic</label><input name="topic" value="{h(job.get('topic'))}" required></div>
    <div><label>Source URL</label><input name="source_url" value="{h(job.get('source_url'))}" placeholder="Channel, playlist, or video URL"></div>
    <div><label>Number of Videos</label><input name="max_videos" type="number" min="1" max="50" value="{h(job.get('max_videos', 3))}"></div>
    <div><label>Report Folder</label><input name="report_folder" value="{h(job.get('report_folder'))}" placeholder="folder or parent/folder"></div>
    <div><label>Schedule Time</label><input name="schedule_time" value="{h(job.get('schedule_time'))}" placeholder="07:35"></div>
  </div>
  <label>Notes</label><textarea name="notes" rows="3">{h(job.get('notes'))}</textarea>
  <p>
    <label><input type="checkbox" name="enabled" value="1" {'checked' if job.get('enabled', True) else ''} style="width:auto"> Enabled</label>
    <label><input type="checkbox" name="detailed" value="1" {'checked' if job.get('detailed', True) else ''} style="width:auto"> Detailed Thai summary</label>
    <label><input type="checkbox" name="include_in_daily_summary" value="1" {'checked' if job.get('include_in_daily_summary', True) else ''} style="width:auto"> Include in daily summary</label>
  </p>
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
                path = (base / unquote(selected)).resolve()
                if base.resolve() in path.parents and path.is_file():
                    content = f"<h2>{h(selected)}</h2><pre>{h(read_text_file(path))}</pre>"
            except OSError:
                content = "<p>Invalid file.</p>"

        rows = []
        for path in relative_files(base, suffix):
            rel = path.relative_to(base).as_posix()
            mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            rows.append(f'<tr><td><a href="{parsed.path}?file={quote(rel)}">{h(rel)}</a></td><td>{h(mtime)}</td><td>{h(path)}</td></tr>')
        body = f"""<h1>{h(title)}</h1>
<table><thead><tr><th>File</th><th>Modified</th><th>Path</th></tr></thead><tbody>{''.join(rows) if rows else '<tr><td colspan="3">No files found.</td></tr>'}</tbody></table>
{content}"""
        self.send_html(page(title, body))

    def render_cron(self):
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        cron = result.stdout if result.returncode == 0 else result.stderr
        body = f"""<h1>Production Cron</h1>
<section>
  <p class="muted">Read-only view. The dashboard does not edit production cron.</p>
  <pre>{h(cron)}</pre>
</section>"""
        self.send_html(page("Cron", body))

    def save_job(self, data):
        jobs = load_jobs()
        job_id = slugify(data.get("id", [""])[0])
        existing = next((j for j in jobs if j.get("id") == job_id), None)
        topic = data.get("topic", [""])[0].strip()
        report_folder = clean_report_folder(data.get("report_folder", [""])[0], slugify(topic))
        job = {
            "id": job_id,
            "name": data.get("name", [topic])[0].strip(),
            "enabled": data.get("enabled", ["0"])[0] == "1",
            "source_type": data.get("source_type", ["topic"])[0],
            "topic": topic,
            "source_url": data.get("source_url", [""])[0].strip(),
            "max_videos": max(1, int(data.get("max_videos", ["3"])[0] or 3)),
            "detailed": data.get("detailed", ["0"])[0] == "1",
            "report_folder": report_folder,
            "schedule_time": data.get("schedule_time", [""])[0].strip(),
            "include_in_daily_summary": data.get("include_in_daily_summary", ["0"])[0] == "1",
            "notes": data.get("notes", [""])[0].strip(),
        }
        if existing:
            jobs[jobs.index(existing)] = job
        else:
            jobs.append(job)
        save_jobs(jobs)
        self.redirect("/")

    def delete_job(self, data):
        job_id = data.get("id", [""])[0]
        save_jobs([j for j in load_jobs() if j.get("id") != job_id])
        self.redirect("/")

    def run_job_action(self, data):
        job_id = data.get("id", [""])[0]
        job = next((j for j in load_jobs() if j.get("id") == job_id), None)
        if job:
            start_job(job)
        self.redirect("/")


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
