#!/usr/bin/env python3

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "config"))
try:
    from paths import PROJECT_ROOT, CREDENTIALS_FILE, REPORTS_DIR, PROMPTS_DIR, GITHUB_TEMP_CLONE, THAI_SUMMARY_PROMPT, THAI_SUMMARY_PROMPT_DETAILED
except ImportError:
    PROJECT_ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
    CREDENTIALS_FILE = _os.path.join(PROJECT_ROOT, "credentials.env")
    REPORTS_DIR = _os.path.join(PROJECT_ROOT, "ai_trends_reports")
    PROMPTS_DIR = _os.path.join(PROJECT_ROOT, "prompts")
    GITHUB_TEMP_CLONE = GITHUB_TEMP_CLONE
    THAI_SUMMARY_PROMPT = _os.path.join(PROMPTS_DIR, "thai_summary_prompt.txt")
    THAI_SUMMARY_PROMPT_DETAILED = _os.path.join(PROMPTS_DIR, "thai_summary_prompt_detailed.txt")

"""
AI Trends Researcher - Enhanced Version
Daily research of AI trends from YouTube with duplicate prevention
Features:
- Content Hash Tracking (prevents duplicate content)
- Timestamp Filtering (for channels only)
- Video ID Fallback
"""

import argparse
import glob
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

WORKSPACE = PROJECT_ROOT
BASE_REPORTS_DIR = f"{WORKSPACE}/ai_trends_reports"

def sanitize_topic(topic):
    """Convert topic to safe folder name"""
    # Special case: Keep NATEHERK uppercase
    if topic.upper() == "NATEHERK":
        return "NATEHERK"
    return topic.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")[:50]

def sanitize_report_folder(folder):
    """Return a safe relative report folder path."""
    parts = []
    for raw_part in folder.replace("\\", "/").split("/"):
        part = raw_part.strip().lower().replace(" ", "_")
        part = re.sub(r"[^a-z0-9_\-]", "_", part)
        part = re.sub(r"_+", "_", part).strip("_")
        if part and part not in {".", ".."}:
            parts.append(part[:80])
    return "/".join(parts)


FILLER_TITLE_WORDS = {
    "a", "an", "and", "are", "at", "by", "for", "from", "full", "how", "in",
    "is", "of", "official", "on", "part", "the", "this", "to", "video", "with",
}


def compact_title_slug(title, max_words=6, max_chars=55):
    """Build a compact, human-readable slug from content title."""
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", title or "").strip().lower()
    words = []
    for word in normalized.split():
        if word in FILLER_TITLE_WORDS:
            continue
        words.append(word)
        if len(words) >= max_words:
            break
    if not words:
        words = ["untitled"]
    slug = "-".join(words)
    return slug[:max_chars].strip("-") or "untitled"


def build_report_filename(report_date, generated_at, on_demand, all_video_data, topic):
    """Return report filename. Daily jobs stay date-only; on-demand jobs are unique per run."""
    if not on_demand:
        return f"{report_date}.md"

    run_time = generated_at.strftime("%H%M")
    if len(all_video_data) == 1:
        video = all_video_data[0]
        title_slug = compact_title_slug(video.get("title", ""))
        video_id = re.sub(r"[^A-Za-z0-9_-]", "", video.get("video_id", ""))[:20]
        suffix = f"{title_slug}_{video_id}" if video_id else title_slug
    else:
        topic_slug = compact_title_slug(topic, max_words=4, max_chars=35)
        suffix = f"{topic_slug}-{len(all_video_data)}-videos"

    return f"{report_date}_{run_time}_{suffix}.md"

def get_dirs(topic, report_folder=None):
    """Get topic-specific directories"""
    topic_safe = sanitize_report_folder(report_folder) if report_folder else sanitize_topic(topic)
    tracker_safe = topic_safe.replace("/", "_")
    return {
        "reports": f"{BASE_REPORTS_DIR}/reports/{topic_safe}",
        "archive": f"{BASE_REPORTS_DIR}/reports_archive/{topic_safe}",
        "tracker": f"{BASE_REPORTS_DIR}/last_processed_{tracker_safe}.json",
        "hash_tracker": f"{BASE_REPORTS_DIR}/content_hashes_{tracker_safe}.json"
    }

def search_videos_by_topic(topic, max_results=5):
    """Search YouTube by topic"""
    print(f"Searching YouTube for: {topic}")
    query = f"ytsearch{max_results}:{topic}"
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-json",
        query
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        print(f"yt-dlp error: {result.stderr}")
        return []
    try:
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                videos.append(json.loads(line))
        return videos
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Raw output: {result.stdout[:200]}...")
        return []

def get_videos_from_channel_with_date(channel_url, max_results=5):
    """Get list of videos from specific channel with today's date filter"""
    print(f"Fetching videos from channel: {channel_url} (today only)")
    # Get today's date in YYYYMMDD format
    today = datetime.now().strftime('%Y%m%d')
    cmd = [
        "yt-dlp",
        "--dateafter", today,
        "--playlist-end", str(max_results),
        "--flat-playlist",
        "--dump-json",
        channel_url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        print(f"yt-dlp error: {result.stderr}")
        # Fallback: get without date filter but limit results
        print("Falling back to no date filter...")
        cmd_fallback = [
            "yt-dlp",
            "--playlist-end", str(max_results),
            "--flat-playlist",
            "--dump-json",
            channel_url
        ]
        result = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if result.returncode != 0 or not result.stdout.strip():
            print(f"yt-dlp fallback error: {result.stderr}")
            return []
    
    try:
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                videos.append(json.loads(line))
        return videos
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Raw output: {result.stdout[:200]}...")
        return []

def get_video_from_url(video_url):
    """Create a single-video metadata item from a specific YouTube URL."""
    print(f"Using specific video URL: {video_url}")
    video_id = ""
    match = re.search(r"[?&]v=([^&]+)", video_url)
    if match:
        video_id = match.group(1)
    elif "youtu.be/" in video_url:
        video_id = video_url.rstrip("/").split("/")[-1].split("?")[0]

    cmd = ["yt-dlp", "--dump-json", "--skip-download", video_url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip():
        try:
            data = json.loads(result.stdout.strip().split("\n")[0])
            return [{
                "id": data.get("id") or video_id,
                "title": data.get("title") or video_url,
                "description": data.get("description") or "",
                "duration": data.get("duration") or 0,
                "webpage_url": data.get("webpage_url") or video_url,
            }]
        except json.JSONDecodeError as e:
            print(f"Video metadata JSON decode error: {e}")

    if not video_id:
        print(f"Could not extract video id from URL: {video_url}")
        return []

    print(f"Falling back to URL-derived video id: {video_id}")
    return [{
        "id": video_id,
        "title": video_url,
        "description": "",
        "duration": 0,
        "webpage_url": video_url,
    }]

def load_content_hashes(hash_file):
    """Load content hashes from file"""
    if os.path.exists(hash_file):
        with open(hash_file) as f:
            return set(json.load(f))
    return set()

def save_content_hashes(hash_file, hashes):
    """Save content hashes to file"""
    with open(hash_file, "w") as f:
        json.dump(list(hashes), f, indent=2)

def create_content_hash(title, description="", duration=0):
    """Create hash from video metadata to detect duplicates"""
    content_string = f"{title}|{description}|{duration}"
    return hashlib.md5(content_string.encode()).hexdigest()

def parse_transcript_langs(value):
    """Parse comma-separated transcript language preference.

    Returns None when unset so summarize_local can use its safe default. Always
    appends `all` as the final fallback for production resilience.
    """
    if not value:
        return None
    langs = []
    for raw in str(value).split(','):
        lang = raw.strip().lower()
        if lang and lang not in langs:
            langs.append(lang)
    if not langs:
        return None
    if 'all' not in langs:
        langs.append('all')
    return langs


def process_video_with_summarize(video_url, topic, video_title="Unknown", detailed=False, transcript_langs=None):
    """Process single video using summarize skill"""
    print(f"Processing with summarize: {video_title}")
    
    # Select prompt file based on detail level
    if detailed:
        prompt_file = THAI_SUMMARY_PROMPT_DETAILED
        print(f"  → Using detailed prompt for comprehensive summary")
    else:
        prompt_file = THAI_SUMMARY_PROMPT
        print(f"  → Using standard prompt")
    
    # Use summarize_local.py — AI provider (Qwen/GLM) instead of summarize CLI
    try:
        _spec = importlib.util.spec_from_file_location(
            "summarize_local",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "summarize_local.py")
        )
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _summary_text = _mod.summarize_video(
            video_url,
            prompt_file=prompt_file,
            language="th",
            topic=topic,
            transcript_langs=transcript_langs,
        )
        result = type('R', (), {'returncode': 0, 'stdout': _summary_text, 'stderr': ''})()
    except Exception as _e:
        print(f"summarize_local error: {_e}")
        result = type('R', (), {'returncode': 1, 'stdout': '', 'stderr': str(_e)})()

    if result.returncode != 0:
        print(f"Summarize error: {result.stderr}")
        return {
            'video_id': '',
            'title': video_title,
            'topic': topic,
            'transcript_length': 0,
            'ai_tools': [],
            'insights': [],
            'relevance_score': 0,
            'relevance_reason': 'Summarize failed',
            'error': result.stderr,
            'source_url': video_url
        }
    
    # Parse the summarize output to extract structured data
    summary_text = result.stdout
    
    # Extract video ID from URL
    import re
    video_id_match = re.search(r'[?&]v=([^&]+)', video_url)
    video_id = video_id_match.group(1) if video_id_match else ''
    
    # Count approximate length
    transcript_length = len(summary_text)
    
    # Set relevance score based on content quality
    relevance_score = 4 if len(summary_text) > 500 else 2
    relevance_reason = "High-quality summary from summarize CLI" if relevance_score == 4 else "Brief summary"
    
    return {
        "video_id": video_id,
        "title": video_title,
        "topic": topic,
        "transcript_length": transcript_length,
        "ai_tools": [],
        "insights": [],
        "relevance_score": relevance_score,
        "relevance_reason": relevance_reason,
        "source_url": video_url,
        "raw_summary": summary_text
    }

def main():
    parser = argparse.ArgumentParser(description="AI Trends Researcher - Enhanced Version")
    parser.add_argument("--topic", required=True, help="Research topic (e.g., 'AI agents', 'machine learning')")
    parser.add_argument("--channel", help="YouTube channel URL (optional, default: search by topic)")
    parser.add_argument("--max-results", type=int, default=20, help="Max videos to fetch (default: 20)")
    parser.add_argument("--count", type=int, default=None, help="Number of new videos to process (default: all new videos)")
    parser.add_argument("--use-date-filter", action="store_true", help="Use date filter for channels (today only)")
    parser.add_argument("--detailed", action="store_true", help="Use detailed prompt for more comprehensive summary")
    parser.add_argument("--video-url", help="Specific YouTube video URL to summarize")
    parser.add_argument("--report-folder", help="Optional report folder under ai_trends_reports/reports")
    parser.add_argument("--config-job-id", help="Optional dashboard job id to include in report metadata")
    parser.add_argument("--on-demand", action="store_true", help="Use unique, readable per-run report filenames")
    parser.add_argument(
        "--transcript-langs",
        help="Comma-separated caption language preference, e.g. en,th,all or th,en,all",
    )
    args = parser.parse_args()

    topic = args.topic
    transcript_langs = parse_transcript_langs(args.transcript_langs)
    dirs = get_dirs(topic, args.report_folder)

    # Create directories
    os.makedirs(dirs["reports"], exist_ok=True)
    os.makedirs(dirs["archive"], exist_ok=True)

    print(f"=== AI Trends Researcher - Enhanced ===")
    print(f"Topic: {topic}")
    print(f"Mode: {'Specific Video' if args.video_url else 'Channel' if args.channel else 'Topic Search'}")
    if args.use_date_filter:
        print(f"Date Filter: Today only")

    # Get videos
    if args.video_url:
        videos = get_video_from_url(args.video_url)
    elif args.channel:
        if args.use_date_filter:
            videos = get_videos_from_channel_with_date(args.channel, args.max_results)
        else:
            videos = get_videos_from_channel_with_date(args.channel, args.max_results)
    else:
        videos = search_videos_by_topic(topic, args.max_results)

    if not videos:
        print("No videos found")
        return

    # Load existing content hashes
    existing_hashes = load_content_hashes(dirs["hash_tracker"])
    print(f"Loaded {len(existing_hashes)} existing content hashes")

    # Filter out duplicates based on content hash
    unique_videos = []
    new_hashes = set()
    
    for video in videos:
        if isinstance(video, dict):
            video_id = video.get("id", "")
            title = video.get("title", "")
            description = video.get("description", "") or ""
            duration = video.get("duration", 0)
            
            if video_id and title:
                content_hash = create_content_hash(title, description, duration)
                
                if content_hash not in existing_hashes:
                    unique_videos.append(video)
                    new_hashes.add(content_hash)
                    print(f"✅ New content: {title[:50]}...")
                else:
                    print(f"❌ Duplicate content skipped: {title[:50]}...")
            else:
                print(f"⚠️ Skipping video with missing data")
        else:
            print(f"Unexpected video format: {type(video)}")

    if not unique_videos:
        print("No new unique videos found")
        return

    # Process videos - process all new videos by default
    videos_to_process = unique_videos[:args.count] if args.count else unique_videos
    print(f"Found {len(unique_videos)} unique videos, processing {len(videos_to_process)} (limit: {args.count if args.count else 'all'})")
    
    all_video_data = []
    
    for video in videos_to_process:
        video_id = video.get("id")
        video_title = video.get("title", "Unknown")
        video_url = video.get("webpage_url") or f"https://youtube.com/watch?v={video_id}"
        
        print(f"Processing: {video_title}")
        
        # Process video using summarize skill
        video_data = process_video_with_summarize(
            video_url,
            topic,
            video_title,
            args.detailed,
            transcript_langs=transcript_langs,
        )
        
        if video_data:
            all_video_data.append(video_data)
            print(f"✅ Processed: {video_title}")
        else:
            print(f"❌ Failed to process: {video_title}")
        time.sleep(15)  # avoid Gemini free-tier 429 rate limit
    
    if not all_video_data:
        print("Failed to process any video")
        return
    
    # Generate combined report
    generated_at = datetime.now()
    report_date = generated_at.strftime('%Y-%m-%d')
    report_time = generated_at.strftime('%H:%M ICT')
    
    report_content = f"""# AI Trends Research - {topic}

**Date:** {report_date} {report_time}
**Topic:** {topic}
**Mode:** {'Specific Video' if args.video_url else 'Channel (Today Only)' if args.channel and args.use_date_filter else 'Channel' if args.channel else 'Topic Search'}
**Videos Processed:** {len(all_video_data)}
**Duplicate Prevention:** Content Hash + Date Filtering
**Dashboard Job ID:** {args.config_job_id or 'N/A'}

---

"""
    
    for i, video_data in enumerate(all_video_data, 1):
        if 'raw_summary' in video_data and video_data['raw_summary']:
            report_content += f"""## Video {i}: {video_data['title']}

**Source:** {video_data.get('source_url', 'Unknown')}
**Video ID:** {video_data['video_id']}

### 📝 Full Summary (Thai)
{video_data['raw_summary']}

---

"""
        else:
            report_content += f"""## Video {i}: {video_data['title']}

**Source:** {video_data.get('source_url', 'Unknown')}
**Video ID:** {video_data['video_id']}

### 📌 Key Tools Mentioned
- No specific AI tools identified

### 💡 Key Insights
- No clear insights extracted

### 🎯 Relevance to AI Automation
- Score: {video_data['relevance_score']}/5
- Reason: {video_data['relevance_reason']}

### 📊 Processing Info
- Transcript length: {video_data['transcript_length']:,} characters

---

"""
    
    report_content += f"""Report generated at: {datetime.now(timezone.utc).isoformat()}
"""
    
    # Save report
    report_filename = build_report_filename(report_date, generated_at, args.on_demand, all_video_data, topic)
    report_file = f"{dirs['reports']}/{report_filename}"
    
    with open(report_file, "w") as f:
        f.write(report_content)
    
    # Update trackers
    if videos_to_process:
        last_video = videos_to_process[-1]
        with open(dirs["tracker"], "w") as f:
            json.dump({
                "last_video_id": last_video.get("id"),
                "last_title": last_video.get("title", "Unknown"),
                "last_processed_at": datetime.now(timezone.utc).isoformat(),
                "count_processed": len(videos_to_process)
            }, f, indent=2)
    
    # Update content hashes
    all_hashes = existing_hashes.union(new_hashes)
    save_content_hashes(dirs["hash_tracker"], all_hashes)
    print(f"Updated content hashes tracker with {len(new_hashes)} new hashes")

    # Report back
    print(f"\n✅ Processed {len(all_video_data)} unique video(s) successfully")
    print(f"📊 Report location: {report_file}")
    print(f"🔁 Tracker: {dirs['tracker']}")
    print(f"🔑 Hash Tracker: {dirs['hash_tracker']}")

if __name__ == "__main__":
    main()
