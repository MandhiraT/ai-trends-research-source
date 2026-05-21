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


def _slug(name: str) -> str:
    """Normalize display topic names to stable folder slugs.

    Examples: "AI Agents" → "ai_agents", "Joanna Wiebe" → "joanna_wiebe",
    "NATEHERK" → "nateherk". Keep this module self-contained because the
    Dashboard imports these save helpers directly.
    """
    return re.sub(r"[\s\-]+", "_", str(name or "").strip()).lower()


# Topics that get full audio + social by default
PRIORITY_TOPICS = {"NATEHERK", "joanna_wiebe"}

# Thai audio script prompt — tone: คนที่เพิ่งดูมาแล้วอยากบอกเล่าสิ่งที่ได้เรียนรู้,
# ยกคำพูดผู้พูด, เปิดด้วย hook, ไม่มี AI filler/คำสนิทสนมเกินไป
AUDIO_SCRIPT_PROMPT = """เขียนเป็นภาษาไทยทั้งหมด

คุณเพิ่งดูคลิปนี้มา แล้วอยากบอกเล่าสิ่งที่ได้เรียนรู้ให้คนฟังเข้าใจแบบเห็นภาพ โดยไม่ต้องไปดูเอง

กติกา:
- เล่าแบบคนที่เพิ่งดูมาแล้วอยากบอกเล่าสิ่งที่ได้เรียนรู้ — ไม่เป็นทางการเกิน แต่ไม่ใช่แบบเพื่อนสนิทเม้าท์กัน
- เปิดด้วย hook ที่ดึงความสนใจทันที เช่น ข้อความที่ขัดแย้งกับสิ่งที่คนทั่วไปคิด, คำถามที่กระตุ้นความอยากรู้, หรือข้อเท็จจริงที่น่าตกใจจากคลิป — ห้ามเริ่มด้วย "คลิปนี้", คำทักทาย หรือการแนะนำตัว
- ยกคำพูดจริงของผู้พูดในคลิปมาด้วย เช่น "...เขาพูดไว้ชัดๆ ว่า..." หรือ "...คำที่เขาใช้คือ..."
- เล่าเหมือนมีความรู้สึกกับเนื้อหา เช่น "จริงด้วย", "ตรงนี้น่าสนใจมาก", "คิดได้แบบนี้ก็ดีเหมือนกัน"
- ห้ามใช้คำสนิทสนมเกินไป เช่น "แก", "เว้ย", "แกๆ", "คิดดูดิ", "โห", "โคตร", "เจ๋ง", "อ่ะ" หรือคำอุทานแบบวัยรุ่น
- ห้ามใช้คำเติมแบบ AI: "แน่นอน!", "รับรองว่า", "นี่คือสรุป", "เริ่มกันเลย", "พร้อมแล้วใช่ไหม"
- ห้ามใช้ 'ผม' หรือ 'ครับ' เพราะผู้บรรยายเป็นผู้หญิง — ใช้ 'ฉัน' หรือ 'ดิฉัน' แทน 'ผม' และ 'ค่ะ' แทน 'ครับ'
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

DEEP_DIVE_SCRIPT_PROMPT = """เขียนเป็นภาษาไทยทั้งหมด

เป้าหมาย: เขียนสคริปต์เสียงแบบ Deep Dive ให้คนฟังเข้าใจเนื้อหาจากวิดีโอ/รายงานนี้ได้ครบ โดยไม่ต้องกลับไปดูต้นฉบับ

โครงสร้างที่ต้องมีในเนื้อหา:
1. Hook & Promise — เปิดด้วย pain/problem หรือ insight ที่ทำให้อยากฟังต่อ และบอกว่าคนฟังจะได้อะไร
2. Core Problem — อธิบายความเข้าใจผิด ปัญหา หรือบริบทหลักที่คลิปกำลังตอบ
3. Deep Dive — เดินตามทุกประเด็นสำคัญจากรายงานตามลำดับ อธิบายว่าแต่ละประเด็นหมายถึงอะไร มีตัวอย่างอะไร ทำไมจึงสำคัญ และควรเอาไปใช้ยังไง
4. Master Insights — ร้อย insight สำคัญให้เห็นภาพใหญ่
5. How-to Blueprint — สรุปเป็นขั้นตอนนำไปใช้จริง โดยยึดจากรายงาน
6. Outro — ปิดด้วยความคิดที่จำง่ายและชวนเอาไปทดลองใช้

กติกาเสียง/รูปแบบ:
- Natural spoken Thai เหมือน host พอดแคสต์ที่เล่าให้ฟังอย่างเข้าใจจริง
- ใช้ภาษาพูดที่อบอุ่น ชัดเจน เป็นผู้ใหญ่ ไม่แข็งแบบรายงาน และไม่สนิทเกิน
- ยกตัวอย่าง คน บริษัท framework หรือคำพูดสำคัญจากรายงานให้ครบเท่าที่มี
- ห้ามใช้ bullet, numbered list, markdown, heading หรือ table ในคำตอบสุดท้าย ให้เป็น plain text สำหรับ TTS เท่านั้น
- บรรทัดแรกต้องเป็น hook เท่านั้น: เริ่มด้วยคำถาม/ความขัดแย้ง/ข้อเท็จจริงที่น่าสนใจจากเนื้อหา ห้ามขึ้นต้นด้วยคำทักทาย
- ห้ามเริ่มด้วย "คลิปนี้", "สวัสดี", "วันนี้", "ในตอนนี้", "เราจะมา", คำทักทาย หรือการแนะนำตัว
- ห้ามใช้คำเติมแบบ AI: "แน่นอน!", "รับรองว่า", "นี่คือสรุป", "เริ่มกันเลย", "พร้อมแล้วใช่ไหม"
- ห้ามใช้ 'ผม' หรือ 'ครับ' เพราะผู้บรรยายเป็นผู้หญิง — ใช้ 'ฉัน' หรือ 'ดิฉัน' แทน 'ผม' และ 'ค่ะ' แทน 'ครับ'
- เป้าหมายความยาว: 8–12 นาทีถ้าเนื้อหาในรายงานมากพอ แต่ห้ามเติมน้ำเกินข้อมูลต้นฉบับ

หัวข้อวิดีโอ: {video_title}

เนื้อหาจาก report:
{section_text}

Deep Dive audio script:"""


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

    # Use summarize_local provider chain (Vertex → Gemini) if available
    if module and hasattr(module, '_call_provider'):
        for provider in ('vertex', 'gemini'):
            try:
                result = module._call_provider(provider, prompt)
                if result:
                    return result
            except Exception:
                continue

    # Direct Gemini API fallback
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        return ""
    try:
        import urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        data = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=120)
        result = json.loads(resp.read().decode())
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
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

        is_priority = topic.replace(' ', '_').lower() in {t.replace(' ', '_').lower() for t in PRIORITY_TOPICS}

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


def enable_content_use(asset: dict, *, audio: bool = False, social: bool = False) -> dict:
    """Enable generation flags for explicit/manual requests.

    PRIORITY_TOPICS controls default automation policy only. When a user clicks
    +Audio/+Social/+All in the Dashboard or runs the CLI with --with-audio/
    --with-social, the selected report should generate for any topic.
    """
    for video in asset.get("videos", []):
        content_use = video.setdefault("content_use", {})
        if audio:
            content_use["audio_full"] = True
            content_use["audio_short"] = True
        if social:
            content_use["social_post"] = True
    return asset


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
            video["audio_script_full"] = _fix_gender(result.strip())
            generated += 1
            time.sleep(2)  # Rate limit

        # Short script (~150 words)
        prompt = AUDIO_SCRIPT_PROMPT.format(
            target_words=150,
            section_text=section_text[:2000],
        )
        result = _call_ai(prompt, module)
        if result:
            video["audio_script_short"] = _fix_gender(result.strip())
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


def _find_asset_video(asset: dict, video_no: int) -> dict | None:
    """Return a video dict by 1-based report video number."""
    for video in asset.get("videos", []):
        try:
            if int(video.get("video_no", 0)) == int(video_no):
                return video
        except (TypeError, ValueError):
            continue
    return None


def _deep_dive_needs_quality_retry(text: str) -> bool:
    """Return True when a generated deep-dive script violates critical voice rules."""
    first_line = next((line.strip() for line in (text or "").splitlines() if line.strip()), "")
    forbidden_openings = (
        "สวัสดี", "คลิปนี้", "วันนี้", "ในตอนนี้", "เราจะมา",
        "แน่นอน", "นี่คือสรุป", "เริ่มกันเลย", "พร้อมแล้วใช่ไหม",
    )
    return first_line.startswith(forbidden_openings)


def _quality_retry_prompt(original_prompt: str, bad_result: str) -> str:
    """Build a correction prompt that preserves content but fixes forbidden openings."""
    return f"""งานก่อนหน้านี้ยังผิดกติกาสำคัญ: ห้ามขึ้นต้นด้วยคำทักทาย ห้ามขึ้นต้นด้วย "คลิปนี้", "วันนี้", "เราจะมา" หรือการแนะนำตัว

ให้เขียนสคริปต์ใหม่ทั้งหมด โดยบรรทัดแรกต้องเป็น hook จากเนื้อหาเท่านั้น เช่น คำถาม ข้อขัดแย้ง หรือข้อเท็จจริงที่น่าสนใจ ห้ามมี markdown/bullet/heading

ผลลัพธ์ก่อนหน้าที่ต้องแก้:
{bad_result[:2000]}

คำสั่งต้นฉบับ:
{original_prompt}"""


def _fix_gender(text: str) -> str:
    """Replace masculine Thai particles with female equivalents as a safety net.

    Prompt rules are the primary guard; this catches any slipthrough.
    """
    text = text.replace("ครับ", "ค่ะ")
    text = text.replace("ผม", "ฉัน")
    return text


def generate_deep_dive_script(asset: dict, video_no: int, module=None) -> dict:
    """Generate one deep-dive audio script for a selected video.

    Deep-dive generation is intentionally per-video and script-only. It writes
    text into the asset dict; callers then save the reviewable script file and
    voice generation remains a separate saved-script step.
    """
    video = _find_asset_video(asset, video_no)
    if not video:
        raise ValueError(f"video {video_no} not found in asset")
    if video.get("audio_script_deep_dive"):
        return {"deep_dive_scripts_generated": 0, "reason": "already exists", "quality_retry_count": 0}

    section_text = video.get("section_text", "")
    if not section_text or len(section_text) < 200:
        raise ValueError("selected video has no usable report section")

    prompt = DEEP_DIVE_SCRIPT_PROMPT.format(
        video_title=video.get("video_title") or video.get("thai_title") or "",
        section_text=section_text[:12000],
    )
    result = _call_ai(prompt, module)
    retry_count = 0
    if result and _deep_dive_needs_quality_retry(result):
        retry_count = 1
        retry_result = _call_ai(_quality_retry_prompt(prompt, result), module)
        if retry_result:
            result = retry_result
    if not result:
        raise RuntimeError("AI did not return a deep-dive script")

    video["audio_script_deep_dive"] = _fix_gender(result.strip())
    return {"deep_dive_scripts_generated": 1, "quality_retry_count": retry_count}


def save_asset(asset: dict, output_dir: Path) -> Path:
    """Save asset JSON to output directory."""
    topic = asset.get("topic", "unknown")
    date = asset.get("date", "unknown")
    out_path = output_dir / _slug(topic) / f"{date}.json"
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

        out_path = output_dir / _slug(topic) / f"{date}-v{video.get('video_no', 0)}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines), encoding="utf-8")
        paths.append(out_path)

    return paths


def save_deep_dive_script(asset: dict, video_no: int, output_dir: Path) -> Path:
    """Save one generated deep-dive script as a separate reviewable markdown file."""
    topic = asset.get("topic", "unknown")
    date = asset.get("date", "unknown")
    video = _find_asset_video(asset, video_no)
    if not video:
        raise ValueError(f"video {video_no} not found in asset")
    script = (video.get("audio_script_deep_dive") or "").strip()
    if not script:
        raise ValueError("selected video has no deep-dive script to save")

    lines = [
        f"# Deep Dive Audio Script: {video.get('thai_title', video.get('video_title', ''))}",
        f"Date: {date}",
        f"Topic: {topic}",
        f"Video: {video.get('video_title', '')}",
        f"Source: {video.get('source_url', '')}",
        "",
        "## Deep Dive Script",
        "",
        script,
        "",
    ]
    out_path = output_dir / _slug(topic) / f"{date}-v{int(video_no)}-deep-dive.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


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

    out_path = output_dir / _slug(topic) / f"{date}.json"
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

    enable_content_use(asset, audio=with_audio, social=with_social)

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
    """Find report files, optionally filtered by topic slug/display name.

    Supports nested topics such as reports/claude_code/claude_code_design/*.md.
    Matching is by normalized slug, not substring, so selecting one topic cannot
    accidentally return another topic's reports.
    """
    if topic:
        topic_slug = _slug(topic)
        direct_dirs = [reports_root / topic, reports_root / topic_slug]
        for topic_dir in direct_dirs:
            if topic_dir.exists() and topic_dir.is_dir():
                return sorted(
                    p for p in topic_dir.rglob("*.md")
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", p.stem)
                )

        matches: list[Path] = []
        if reports_root.exists():
            for p in reports_root.rglob("*.md"):
                if not p.is_file() or not re.match(r"^\d{4}-\d{2}-\d{2}$", p.stem):
                    continue
                rel_parent = p.parent.relative_to(reports_root).as_posix()
                leaf_slug = _slug(p.parent.name)
                rel_slug = _slug(rel_parent.replace("/", "_"))
                if leaf_slug == topic_slug or rel_slug == topic_slug:
                    matches.append(p)
        return sorted(matches)

    return sorted(
        p for p in reports_root.rglob("*.md")
        if p.is_file() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.stem)
    )


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
