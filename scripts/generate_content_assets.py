#!/usr/bin/env python3
"""Generate content asset JSON files from ATS reports.

Each report becomes a structured asset JSON with:
- Per-video metadata (keywords, tags, thai title, summary)
- Audio script placeholders (full + short) — generated separately with AI
- Social post placeholders (FB, Threads, X) — generated separately with AI
- Content use flags per video

Usage:
  # Generate assets for a specific report
  python3 scripts/generate_content_assets.py --report ai_trends_reports/reports/NATEHERK/2026-05-14.md

  # Generate assets for all reports in a topic
  python3 scripts/generate_content_assets.py --topic NATEHERK

  # Generate assets for all reports
  python3 scripts/generate_content_assets.py --all

  # Generate assets + audio scripts using AI
  python3 scripts/generate_content_assets.py --topic NATEHERK --with-audio

  # Generate assets + social posts using AI
  python3 scripts/generate_content_assets.py --topic NATEHERK --with-social

  # Generate everything
  python3 scripts/generate_content_assets.py --topic NATEHERK --with-audio --with-social
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

# Allow imports from scripts dir
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_report_index import (  # noqa: E402
    INDEX_DIR,
    REPORTS_ROOT,
    PROJECT_ROOT as INDEX_PROJECT_ROOT,
    _extract_meta,
    _split_video_sections,
    _extract_thai_title,
    _extract_summary_short,
    _extract_keywords,
    _UNAVAILABLE_MARKERS,
)

ASSETS_DIR = Path(__file__).resolve().parents[1] / "ai_trends_reports" / "assets"
AUDIO_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "ai_trends_reports" / "audio_scripts"
SOCIAL_DIR = Path(__file__).resolve().parents[1] / "ai_trends_reports" / "social"

# Topics that get full audio + social by default
PRIORITY_TOPICS = {"NATEHERK", "joanna_wiebe"}

# Thai audio script prompt — tone: ดูมาแล้วมาเล่าให้ฟัง, ยกคำพูดผู้พูด, ไม่มี AI filler
AUDIO_SCRIPT_PROMPT = """เขียนเป็นภาษาไทยทั้งหมด

คุณเพิ่งดูคลิปนี้มา แล้วอยากเล่าให้คนฟังเข้าใจเนื้อหาแบบเห็นภาพ โดยไม่ต้องไปดูเอง

กติกา:
- เล่าแบบเพื่อนเล่าให้เพื่อนฟัง ไม่ใช่ผู้อ่านข่าว
- ยกคำพูดจริงของผู้พูดในคลิปมาด้วย เช่น "...เขาพูดไว้ชัดๆ ว่า..." หรือ "...คำที่เขาใช้คือ..."
- เล่าเหมือนมีความรู้สึกกับเนื้อหา เช่น "จริงด้วย", "ตรงนี้น่าสนใจมาก", "คิดได้แบบนี้ก็ดีเหมือนกัน"
- ห้ามใช้คำเติมแบบ AI: "แน่นอน!", "รับรองว่า", "นี่คือสรุป", "เริ่มกันเลย", "พร้อมแล้วใช่ไหม"
- ห้ามเริ่มด้วยการทักทายหรือแนะนำตัว เข้าเรื่องทันที
- เขียนเป็น script พูดได้จริง ไม่ใช่บทความอ่าน
- ความยาว: ประมาณ {target_words} คำ
- ปิดท้ายด้วยความคิดเห็นสั้นๆ 1-2 ประโยค แบบเห็นด้วยหรือไม่เห็นด้วยก็ได้

เนื้อหาจาก report:
{section_text}

Audio script:"""

SOCIAL_PROMPT = """เขียนเป็นภาษาไทยทั้งหมด

สร้าง social media posts จากเนื้อหานี้ โทนเหมือนคนที่ดูคลิปมาแล้วเล่าให้เพื่อนฟัง

กติกา:
- เขียนแบบคนจริง ไม่ใช่ AI
- ห้ามใช้คำแบบ AI: "แน่นอน!", "รับรองว่า", "น่าสังเกตว่า", "สิ่งที่น่าสนใจคือ"
- ห้ามเริ่มด้วยคำทักทาย AI
- ยกคำพูดสำคัญจากคลิปมาด้วยได้
- แต่ละ post ต้อง stand alone ได้

เนื้อหาจาก report:
{section_text}

สร้าง:
1. Facebook page post (hook + body + CTA, 3-6 ย่อหน้า)
2. Threads post (1-3 โพสต์สั้น, แต่ละอันไม่เกิน 200 ตัวอักษร)
3. X/Twitter thread (3-5 tweets, แต่ละอันไม่เกิน 280 ตัวอักษร)
4. Short caption (1-2 ประโยค + hashtags)

ตอบเป็น JSON:
{{"facebook": "ข้อความ post", "threads": ["post1", "post2"], "x_thread": ["tweet1", "tweet2", "tweet3"], "short_caption": "caption #hashtag1 #hashtag2", "hashtags": ["#tag1", "#tag2"]}}"""


def _get_ai_client():
    """Get AI client for generation. Uses summarize_local.py's provider chain."""
    try:
        # Try importing the summarization function from summarize_local
        summarize_path = Path(__file__).resolve().parents[1] / "scripts" / "summarize_local.py"
        if summarize_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("summarize_local", summarize_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    except Exception:
        pass
    return None


def _call_ai(prompt: str, module=None) -> str:
    """Call AI with prompt, using available provider chain."""
    if module and hasattr(module, 'generate_text'):
        return module.generate_text(prompt)

    # Fallback: try direct API calls
    # Try Vertex AI first, then others
    providers = []

    # Try Gemini API key
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        providers.append(("gemini", gemini_key))

    if not providers:
        return ""

    for provider_name, key in providers:
        try:
            if provider_name == "gemini":
                import urllib.request
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
                data = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                resp = urllib.request.urlopen(req, timeout=120)
                result = json.loads(resp.read().decode())
                return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            continue

    return ""


def build_asset_from_report(report_path: Path, reports_root: Path) -> dict[str, Any] | None:
    """Build a content asset dict from a single report file."""
    text = report_path.read_text(encoding="utf-8")
    date = _extract_meta(text, "Date") or report_path.stem
    date = date.split()[0]
    topic = _extract_meta(text, "Topic") or report_path.parent.name.replace("_", " ")

    sections = _split_video_sections(text)
    if not sections:
        return None

    videos = []
    for video_no, video_title, section in sections:
        # Skip unavailable
        if any(marker.lower() in section.lower() for marker in _UNAVAILABLE_MARKERS):
            continue

        source_url = _extract_meta(section, "Source")
        video_id = _extract_meta(section, "Video ID")
        thai_title = _extract_thai_title(section, video_title)
        summary_short = _extract_summary_short(section)
        keywords, keywords_normalized, tags = _extract_keywords(topic, video_title, thai_title, summary_short)

        is_priority = topic.upper() in {t.upper() for t in PRIORITY_TOPICS}

        videos.append({
            "video_no": video_no,
            "video_title": video_title,
            "thai_title": thai_title,
            "source_url": source_url,
            "video_id": video_id,
            "summary_short": summary_short,
            "keywords": keywords,
            "keywords_normalized": keywords_normalized,
            "tags": tags,
            "section_text": section,
            "content_use": {
                "audio_full": is_priority,
                "audio_short": is_priority,
                "social_post": is_priority,
                "sonar_storytelling": is_priority,
            },
            "audio_script_full": "",
            "audio_script_short": "",
            "social_posts": {},
        })

    if not videos:
        return None

    try:
        rel_path = report_path.relative_to(reports_root).as_posix()
    except ValueError:
        rel_path = report_path.name

    return {
        "date": date,
        "topic": topic,
        "report_path": rel_path,
        "total_videos": len(videos),
        "videos": videos,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def generate_audio_scripts(asset: dict, module=None) -> dict:
    """Generate audio scripts for videos with content_use.audio_full=True."""
    generated = 0
    for video in asset.get("videos", []):
        if not video.get("content_use", {}).get("audio_full"):
            continue
        if video.get("audio_script_full"):
            continue

        section_text = video.get("section_text", "")
        if not section_text or len(section_text) < 200:
            continue

        # Full script (~400 words)
        prompt = AUDIO_SCRIPT_PROMPT.format(
            target_words=400,
            section_text=section_text[:4000],
        )
        result = _call_ai(prompt, module)
        if result:
            video["audio_script_full"] = result.strip()
            generated += 1
            time.sleep(2)  # Rate limit

        # Short script (~150 words)
        prompt = AUDIO_SCRIPT_PROMPT.format(
            target_words=150,
            section_text=section_text[:2000],
        )
        result = _call_ai(prompt, module)
        if result:
            video["audio_script_short"] = result.strip()
            time.sleep(2)

    return {"audio_scripts_generated": generated}


def generate_social_posts(asset: dict, module=None) -> dict:
    """Generate social posts for videos with content_use.social_post=True."""
    generated = 0
    for video in asset.get("videos", []):
        if not video.get("content_use", {}).get("social_post"):
            continue
        if video.get("social_posts"):
            continue

        section_text = video.get("section_text", "")
        if not section_text or len(section_text) < 200:
            continue

        prompt = SOCIAL_PROMPT.format(section_text=section_text[:3000])
        result = _call_ai(prompt, module)
        if result:
            # Try to parse as JSON
            try:
                # Extract JSON from response
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    posts = json.loads(json_match.group())
                    video["social_posts"] = posts
                    generated += 1
            except json.JSONDecodeError:
                # Store raw result
                video["social_posts"] = {"raw": result.strip()}
                generated += 1
            time.sleep(2)

    return {"social_posts_generated": generated}


def save_asset(asset: dict, output_dir: Path) -> Path:
    """Save asset JSON to output directory."""
    topic = asset.get("topic", "unknown")
    date = asset.get("date", "unknown")
    out_path = output_dir / topic / f"{date}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove section_text from saved JSON (too large, exists in report)
    save_data = json.loads(json.dumps(asset))
    for video in save_data.get("videos", []):
        video.pop("section_text", None)

    out_path.write_text(json.dumps(save_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def save_audio_scripts(asset: dict, output_dir: Path) -> list[Path]:
    """Save audio scripts as markdown files."""
    paths = []
    topic = asset.get("topic", "unknown")
    date = asset.get("date", "unknown")

    for video in asset.get("videos", []):
        if not video.get("audio_script_full") and not video.get("audio_script_short"):
            continue

        lines = [
            f"# Audio Script: {video.get('thai_title', video.get('video_title', ''))}",
            f"Date: {date}",
            f"Topic: {topic}",
            f"Video: {video.get('video_title', '')}",
            f"Source: {video.get('source_url', '')}",
            "",
        ]

        if video.get("audio_script_full"):
            lines.extend(["## Full Script", "", video["audio_script_full"], ""])

        if video.get("audio_script_short"):
            lines.extend(["## Short Script", "", video["audio_script_short"], ""])

        out_path = output_dir / topic / f"{date}-v{video.get('video_no', 0)}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines), encoding="utf-8")
        paths.append(out_path)

    return paths


def save_social_posts(asset: dict, output_dir: Path) -> Path | None:
    """Save social posts as JSON."""
    topic = asset.get("topic", "unknown")
    date = asset.get("date", "unknown")
    posts = {}

    for video in asset.get("videos", []):
        if not video.get("social_posts"):
            continue
        key = f"v{video.get('video_no', 0)}-{video.get('video_id', 'unknown')}"
        posts[key] = {
            "video_title": video.get("video_title", ""),
            "thai_title": video.get("thai_title", ""),
            "social": video["social_posts"],
        }

    if not posts:
        return None

    out_path = output_dir / topic / f"{date}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def process_report(report_path: Path, reports_root: Path,
                   with_audio: bool = False, with_social: bool = False) -> dict:
    """Process a single report: build asset, optionally generate audio/social, save."""
    asset = build_asset_from_report(report_path, reports_root)
    if not asset:
        return {"status": "skipped", "report": str(report_path), "reason": "no summarized videos"}

    ai_module = _get_ai_client() if (with_audio or with_social) else None

    audio_result = {}
    if with_audio:
        audio_result = generate_audio_scripts(asset, ai_module)
        save_audio_scripts(asset, AUDIO_SCRIPTS_DIR)

    social_result = {}
    if with_social:
        social_result = generate_social_posts(asset, ai_module)
        save_social_posts(asset, SOCIAL_DIR)

    asset_path = save_asset(asset, ASSETS_DIR)

    return {
        "status": "ok",
        "report": str(report_path),
        "asset": str(asset_path),
        "videos": asset["total_videos"],
        **audio_result,
        **social_result,
    }


def find_reports(topic: str | None = None, reports_root: Path = REPORTS_ROOT) -> list[Path]:
    """Find report files, optionally filtered by topic."""
    if topic:
        topic_dir = reports_root / topic
        if topic_dir.exists():
            return sorted(topic_dir.rglob("*.md"))
        # Try lowercase/slug variants
        for d in reports_root.iterdir():
            if d.is_dir() and topic.lower() in d.name.lower():
                return sorted(d.rglob("*.md"))
        return []

    return sorted(reports_root.rglob("*.md"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate content assets from ATS reports")
    parser.add_argument("--report", help="Path to a specific report .md file")
    parser.add_argument("--topic", help="Generate assets for all reports in a topic")
    parser.add_argument("--all", action="store_true", help="Generate assets for all reports")
    parser.add_argument("--with-audio", action="store_true", help="Generate audio scripts (uses AI, has cost)")
    parser.add_argument("--with-social", action="store_true", help="Generate social posts (uses AI, has cost)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without writing")
    parser.add_argument("--assets-dir", default=str(ASSETS_DIR), help="Output directory for assets")
    args = parser.parse_args()

    if not any([args.report, args.topic, args.all]):
        parser.error("Specify --report, --topic, or --all")

    reports_root = REPORTS_ROOT

    # Collect report files
    if args.report:
        report_files = [Path(args.report)]
    elif args.topic:
        report_files = find_reports(args.topic, reports_root)
        if not report_files:
            print(f"No reports found for topic: {args.topic}")
            sys.exit(1)
    else:
        report_files = find_reports(None, reports_root)

    # Filter out non-report files
    report_files = [p for p in report_files if p.is_file() and p.suffix == ".md"
                    and not any(part.startswith(".") for part in p.parts)]
    print(f"Found {len(report_files)} report(s)")

    if args.dry_run:
        for p in report_files:
            asset = build_asset_from_report(p, reports_root)
            if asset:
                print(f"  {p.name}: {asset['total_videos']} videos, topic={asset['topic']}")
            else:
                print(f"  {p.name}: skipped (no summarized videos)")
        return

    # Load credentials for AI generation
    if args.with_audio or args.with_social:
        creds_path = Path(__file__).resolve().parents[1] / "credentials.env"
        if creds_path.exists():
            for line in creds_path.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

    results = []
    for report_path in report_files:
        result = process_report(report_path, reports_root,
                                with_audio=args.with_audio,
                                with_social=args.with_social)
        results.append(result)
        status = result.get("status", "unknown")
        videos = result.get("videos", 0)
        asset_path = result.get("asset", "")
        print(f"  {report_path.name}: {status} ({videos} videos) → {asset_path}")

    ok_count = sum(1 for r in results if r.get("status") == "ok")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    audio_gen = sum(r.get("audio_scripts_generated", 0) for r in results)
    social_gen = sum(r.get("social_posts_generated", 0) for r in results)

    print(f"\nDone: {ok_count} assets created, {skipped} skipped")
    if args.with_audio:
        print(f"  Audio scripts generated: {audio_gen}")
    if args.with_social:
        print(f"  Social posts generated: {social_gen}")
    print(f"Output: {args.assets_dir}")


if __name__ == "__main__":
    main()
