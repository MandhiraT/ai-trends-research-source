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
import json
import os
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

def get_dirs(topic):
    """Get topic-specific directories"""
    topic_safe = sanitize_topic(topic)
    return {
        "reports": f"{BASE_REPORTS_DIR}/reports/{topic_safe}",
        "archive": f"{BASE_REPORTS_DIR}/reports_archive/{topic_safe}",
        "tracker": f"{BASE_REPORTS_DIR}/last_processed_{topic_safe}.json",
        "hash_tracker": f"{BASE_REPORTS_DIR}/content_hashes_{topic_safe}.json"
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

def process_video_with_summarize(video_url, topic, video_title="Unknown", detailed=False):
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
        import importlib.util, sys as _sys
        _spec = importlib.util.spec_from_file_location(
            "summarize_local",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "summarize_local.py")
        )
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _summary_text = _mod.summarize_video(video_url, prompt_file=prompt_file, language="th", topic=topic)
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
    args = parser.parse_args()

    topic = args.topic
    dirs = get_dirs(topic)

    # Create directories
    os.makedirs(dirs["reports"], exist_ok=True)
    os.makedirs(dirs["archive"], exist_ok=True)

    print(f"=== AI Trends Researcher - Enhanced ===")
    print(f"Topic: {topic}")
    print(f"Mode: {'Channel' if args.channel else 'Topic Search'}")
    if args.use_date_filter:
        print(f"Date Filter: Today only")

    # Get videos
    if args.channel:
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
        video_url = f"https://youtube.com/watch?v={video_id}"
        
        print(f"Processing: {video_title}")
        
        # Process video using summarize skill
        video_data = process_video_with_summarize(video_url, topic, video_title, args.detailed)
        
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
    report_date = datetime.now().strftime('%Y-%m-%d')
    report_time = datetime.now().strftime('%H:%M ICT')
    
    report_content = f"""# AI Trends Research - {topic}

**Date:** {report_date} {report_time}
**Topic:** {topic}
**Mode:** {'Channel (Today Only)' if args.channel and args.use_date_filter else 'Channel' if args.channel else 'Topic Search'}
**Videos Processed:** {len(all_video_data)}
**Duplicate Prevention:** Content Hash + Date Filtering

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
    report_file = f"{dirs['reports']}/{report_date}.md"
    
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
