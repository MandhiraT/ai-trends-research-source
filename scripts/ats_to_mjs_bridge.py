#!/usr/bin/env python3
"""
ATS → MJS Bridge

Selects ATS research reports, generates structured Video Briefs via Claude,
and seeds MJS projects. All steps require manual confirmation — no auto-generation.

Commands:
  list-candidates  List available ATS report files
  create-brief     Extract a Video Brief from a selected report
  create-project   Seed an MJS project from an existing brief

Run from the ai-trends-research-source repo root.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import click

REPORTS_ROOT = Path(__file__).parent.parent / "ai_trends_reports" / "reports"
BRIEFS_ROOT = Path(__file__).parent.parent / "ai_trends_reports" / "mjs_briefs"
INFERENCE_TS = Path.home() / ".claude" / "PAI" / "Tools" / "Inference.ts"
MJS_CLI = Path.home() / ".local" / "bin" / "mjs"


def _default_tool_path(tool_name: str) -> Path:
    """Return Mandy's standard per-user install path for CLI tools."""
    if tool_name == "bun":
        return Path.home() / ".bun" / "bin" / "bun"
    return Path.home() / ".local" / "bin" / tool_name


def _resolve_tool(tool_name: str, env_var: str | None = None) -> str:
    """Resolve a CLI even when dashboard services run with a minimal PATH."""
    env_value = os.environ.get(env_var or "") if env_var else None
    candidates = [env_value, shutil.which(tool_name), str(_default_tool_path(tool_name))]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return tool_name


def _tool_env() -> dict[str, str]:
    """Env for child tools: keep service env, but add user CLI dirs to PATH.

    MJS dashboard user services may start without ~/.bun/bin or ~/.local/bin in
    PATH.  Inference.ts is launched by Bun and then spawns `claude`, so both
    directories must be present for the full chain to work.
    """
    env = os.environ.copy()
    extra_paths = [
        str(Path.home() / ".bun" / "bin"),
        str(Path.home() / ".local" / "bin"),
    ]
    existing_path = env.get("PATH", "")
    env["PATH"] = os.pathsep.join([*extra_paths, existing_path]) if existing_path else os.pathsep.join(extra_paths)
    return env

_BRIEF_SYSTEM_PROMPT = """\
You are a video content strategist. Extract a structured Video Brief from the given ATS research report.
Respond ONLY with valid JSON matching the schema exactly — no prose, no markdown, no code blocks.

Required fields:
{
  "source_title": "the exact video or report title from the report",
  "working_title": "compelling Thai-language YouTube title (under 60 chars)",
  "thesis": "core argument or insight in one Thai sentence",
  "hook": "opening hook line in Thai — the first 3-5 seconds of the video",
  "audience": "target Thai audience description",
  "content_angle": "specific unique angle that differentiates this video",
  "emotional_angle": "emotional journey — what viewer feels from start to end",
  "key_points": ["point 1 in Thai", "point 2 in Thai", "point 3 in Thai"],
  "visual_metaphor": "central visual metaphor or recurring image for the video",
  "voice_tone": "tone of voice (e.g. สงบ/ตรงไปตรงมา/อบอุ่น/ท้าทาย)",
  "cta": "call to action at the end of the video in Thai",
  "mjs_brand": "thequietself",
  "mjs_style": "v6",
  "ratio": "16:9",
  "duration": "short",
  "language": "Thai",
  "pipeline_mode": "manual"
}

Rules:
- Extract from the report's actual content — do not hallucinate topics
- key_points: exactly 3-5 bullet points, each under 100 chars
- working_title: compelling, Thai YouTube-optimized
- thesis: one sentence that captures the single most important insight
- Respond ONLY with the JSON object. No surrounding text.
"""


@click.group()
def cli() -> None:
    """ATS → MJS Bridge — source selection and brief generation."""


@cli.command(name="list-candidates")
@click.option("--date", "filter_date", default=None, help="Filter by date (YYYY-MM-DD)")
@click.option("--folder", "filter_folder", default=None, help="Filter by report folder name")
def list_candidates(filter_date: str | None, filter_folder: str | None) -> None:
    """List ATS reports available for brief creation."""
    if not REPORTS_ROOT.exists():
        click.echo(f"[error] Reports root not found: {REPORTS_ROOT}", err=True)
        sys.exit(1)

    found = False
    folders = sorted(
        [f for f in REPORTS_ROOT.iterdir() if f.is_dir() and not f.name.startswith("_")]
    )

    for folder_path in folders:
        folder_name = folder_path.name
        # preserve lowercase — never change case
        if filter_folder and folder_name != filter_folder.lower():
            continue

        report_files = sorted(folder_path.glob("*.md"))
        if filter_date:
            report_files = [r for r in report_files if r.stem == filter_date]

        for report_path in report_files:
            date_str = report_path.stem
            title = _extract_title(report_path)
            title_preview = title[:80] + ("..." if len(title) > 80 else "")
            click.echo(f"{folder_name:<35} {date_str}  {title_preview}")
            found = True

    if not found:
        click.echo("No reports found matching the given filters.")


@cli.command(name="create-brief")
@click.option("--report-folder", required=True, help="Report folder name (e.g. make_money_matt)")
@click.option("--date", "report_date", required=True, help="Report date (YYYY-MM-DD)")
@click.option("--video-num", default=1, show_default=True,
              help="Which video from the report to use (1-indexed)")
def create_brief(report_folder: str, report_date: str, video_num: int) -> None:
    """Extract a Video Brief from a specific ATS report using Claude."""
    # preserve lowercase (ISC-13)
    folder_name = report_folder.lower()
    report_path = REPORTS_ROOT / folder_name / f"{report_date}.md"

    if not report_path.exists():
        click.echo(f"[error] Report not found: {report_path}", err=True)
        sys.exit(1)

    report_text = report_path.read_text(encoding="utf-8")

    # Extract the specific video section if multiple
    video_section = _extract_video_section(report_text, video_num)

    click.echo(f"Extracting brief from: {report_path.relative_to(REPORTS_ROOT.parent.parent)}")
    click.echo("Calling Claude via PAI Inference...")

    bun_bin = _resolve_tool("bun", "BUN_BIN")
    result = subprocess.run(
        [
            bun_bin, str(INFERENCE_TS),
            "--level", "standard",
            "--json",
            "--timeout", "90000",
            _BRIEF_SYSTEM_PROMPT,
            video_section,
        ],
        capture_output=True, text=True, check=False,
        timeout=120,
        env=_tool_env(),
    )

    if result.returncode != 0 or not result.stdout.strip():
        click.echo(f"[error] Inference failed:\n{result.stderr}", err=True)
        sys.exit(1)

    # Parse the JSON output from Inference.ts
    raw_output = result.stdout.strip()
    try:
        brief_fields = _parse_inference_output(raw_output)
    except (json.JSONDecodeError, ValueError) as e:
        click.echo(f"[error] Failed to parse brief JSON: {e}\nRaw:\n{raw_output[:500]}", err=True)
        sys.exit(1)

    brief_id = f"brief_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    source_report_path = f"ai_trends_reports/reports/{folder_name}/{report_date}.md"

    brief = {
        "brief_id": brief_id,
        "source_report_path": source_report_path,
        "source_report_date": report_date,
        "source_report_folder": folder_name,
        "source_title": brief_fields.get("source_title", ""),
        "selected_by": "mandy",
        "selected_at": now_iso,
        "working_title": brief_fields.get("working_title", ""),
        "thesis": brief_fields.get("thesis", ""),
        "hook": brief_fields.get("hook", ""),
        "audience": brief_fields.get("audience", ""),
        "content_angle": brief_fields.get("content_angle", ""),
        "emotional_angle": brief_fields.get("emotional_angle", ""),
        "key_points": brief_fields.get("key_points", []),
        "visual_metaphor": brief_fields.get("visual_metaphor", ""),
        "voice_tone": brief_fields.get("voice_tone", ""),
        "cta": brief_fields.get("cta", ""),
        "mjs_brand": brief_fields.get("mjs_brand", "thequietself"),
        "mjs_style": brief_fields.get("mjs_style", "v6"),
        "ratio": brief_fields.get("ratio", "16:9"),
        "duration": brief_fields.get("duration", "short"),
        "language": brief_fields.get("language", "Thai"),
        "pipeline_mode": brief_fields.get("pipeline_mode", "manual"),
        "traceability": {
            "generated_at": now_iso,
            "source_report": source_report_path,
            "video_num": video_num,
            "extraction_model": "claude-sonnet",
        },
    }

    # Write brief JSON (ISC-7, ISC-8, ISC-9, ISC-10)
    brief_dir = BRIEFS_ROOT / folder_name / report_date
    brief_dir.mkdir(parents=True, exist_ok=True)
    brief_path = brief_dir / f"{brief_id}.json"
    brief_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")

    click.echo(f"\n[ok] Brief created: {brief_path.relative_to(BRIEFS_ROOT.parent.parent)}")
    click.echo(f"     brief_id: {brief_id}")
    click.echo(f"     title:    {brief['working_title']}")
    click.echo(f"\nNext: python3 scripts/ats_to_mjs_bridge.py create-project --brief-id {brief_id}")


@cli.command(name="create-project")
@click.option("--brief-id", required=True, help="Brief ID from create-brief")
def create_project(brief_id: str) -> None:
    """Seed an MJS project from an existing Video Brief."""
    brief_path = _find_brief(brief_id)
    if not brief_path:
        click.echo(f"[error] Brief not found: {brief_id}", err=True)
        sys.exit(1)

    click.echo(f"Found brief: {brief_path.relative_to(BRIEFS_ROOT.parent.parent)}")

    mjs_bin = _resolve_tool("mjs", "MJS_BIN")
    result = subprocess.run(
        [mjs_bin, "import-brief", str(brief_path)],
        capture_output=False, text=True, check=False,
        env=_tool_env(),
    )

    if result.returncode != 0:
        click.echo(f"[error] mjs import-brief failed (exit {result.returncode})", err=True)
        sys.exit(1)


# ── helpers ───────────────────────────────────────────────────────────────────

def _extract_title(report_path: Path) -> str:
    """Extract the first video title from a report file."""
    try:
        for line in report_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("## Video"):
                # "## Video 1: The Title Here"
                parts = stripped.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()
    except Exception:
        pass
    return report_path.stem


def _extract_video_section(report_text: str, video_num: int) -> str:
    """Extract a specific video section from the report, or the full report."""
    lines = report_text.splitlines()
    sections: list[tuple[int, int]] = []
    current_start = None

    for i, line in enumerate(lines):
        if line.strip().startswith(f"## Video "):
            if current_start is not None:
                sections.append((current_start, i))
            current_start = i

    if current_start is not None:
        sections.append((current_start, len(lines)))

    if sections and 1 <= video_num <= len(sections):
        start, end = sections[video_num - 1]
        section = "\n".join(lines[start:end])
        # Include the report header (first ~15 lines) as context
        header = "\n".join(lines[:15])
        return f"{header}\n\n---\n\n{section}"

    # Fallback: return full report (truncated to ~4000 chars for context)
    return report_text[:4000]


def _parse_inference_output(raw: str) -> dict:
    """Parse JSON from Inference.ts output, which may wrap in a result structure."""
    # Inference.ts --json returns the parsed JSON directly in stdout
    # Try parsing as-is first
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to find JSON object in the output
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(raw[start:end])
        else:
            raise

    # If wrapped in {"success": true, "parsed": {...}}
    if isinstance(data, dict) and "parsed" in data:
        return data["parsed"]
    return data


def _find_brief(brief_id: str) -> Path | None:
    """Search for a brief JSON file by brief_id."""
    if not BRIEFS_ROOT.exists():
        return None
    for match in BRIEFS_ROOT.rglob(f"{brief_id}.json"):
        return match
    return None


if __name__ == "__main__":
    cli()
