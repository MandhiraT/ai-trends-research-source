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
Claude Code Subtopics Research - Enhanced Version
Research specific Claude Code subtopics and generate Thai summaries
With improved search and reduced duplicate filtering for trending topics
"""

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone

WORKSPACE = PROJECT_ROOT
BASE_REPORTS_DIR = f"{WORKSPACE}/ai_trends_reports/reports/claude_code"

def sanitize_topic(topic):
    """Convert topic to safe folder name"""
    return topic.lower().replace(" ", "_").replace("/", "_").replace("\\", "_").replace("-", "_")[:50]

def get_dirs(subtopic):
    """Get subtopic-specific directories"""
    subtopic_safe = sanitize_topic(subtopic)
    return {
        "reports": f"{BASE_REPORTS_DIR}/{subtopic_safe}",
        "tracker": f"{BASE_REPORTS_DIR}/last_processed_{subtopic_safe}.json",
        "hash_tracker": f"{BASE_REPORTS_DIR}/content_hashes_{subtopic_safe}.json"
    }

def search_videos_by_topic(topic, max_results=5):
    """Search YouTube by topic with enhanced queries"""
    print(f"Searching YouTube for: {topic}")
    
    # For trending topics, use broader search
    if "design" in topic.lower() or "skills" in topic.lower():
        # Use multiple search variations for trending topics
        queries = [
            f"ytsearch{max_results}:{topic}",
            f"ytsearch{max_results}:claude design",
            f"ytsearch{max_results}:claude code ui",
            f"ytsearch{max_results}:claude skills"
        ]
        
        all_videos = []
        seen_ids = set()
        
        for query in queries:
            cmd = ["yt-dlp", "--flat-playlist", "--dump-json", query]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            video = json.loads(line)
                            video_id = video.get("id", "")
                            if video_id and video_id not in seen_ids:
                                all_videos.append(video)
                                seen_ids.add(video_id)
                                if len(all_videos) >= max_results:
                                    break
                except json.JSONDecodeError:
                    continue
            
            if len(all_videos) >= max_results:
                break
        
        return all_videos[:max_results]
    else:
        # Normal search for other topics
        query = f"ytsearch{max_results}:{topic}"
        cmd = ["yt-dlp", "--flat-playlist", "--dump-json", query]
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
    prompt_file = THAI_SUMMARY_PROMPT_DETAILED if detailed else THAI_SUMMARY_PROMPT
    print(f"Processing with summarize: {video_title}")
    print(f"  → Using {'detailed' if detailed else 'standard'} prompt")

    try:
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "summarize_local",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "summarize_local.py")
        )
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        summary_text = _mod.summarize_video(video_url, prompt_file=prompt_file,
                                             language="th", topic=topic)
        result = type('R', (), {'returncode': 0, 'stdout': summary_text, 'stderr': ''})()
    except Exception as _e:
        result = type('R', (), {'returncode': 1, 'stdout': '', 'stderr': str(_e)})()

    if result.returncode != 0:
        print(f"Summarize error: {result.stderr}")
        return {
            'video_id': '',
            'title': video_title,
            'topic': topic,
            'transcript_length': 0,
            'raw_summary': f"❌ Summarize failed: {result.stderr}"
        }
    
    summary_text = result.stdout
    
    import re
    video_id_match = re.search(r'[?&]v=([^&]+)', video_url)
    video_id = video_id_match.group(1) if video_id_match else ''
    
    return {
        "video_id": video_id,
        "title": video_title,
        "topic": topic,
        "transcript_length": len(summary_text),
        "raw_summary": summary_text
    }

def main():
    parser = argparse.ArgumentParser(description="Claude Code Subtopics Research - Enhanced")
    parser.add_argument("--max-results", type=int, default=3, help="Max videos per subtopic (default: 3)")
    parser.add_argument("--total-videos", type=int, default=8, help="Total videos across all subtopics (default: 8)")
    parser.add_argument("--detailed", action="store_true", help="Use detailed Thai prompt for comprehensive summaries")
    parser.add_argument("--only", type=str, default="", help="Comma-separated subtopic name filter (partial match, e.g. 'remotion,video')")
    args = parser.parse_args()

    all_subtopics = [
        "claude code obsidian",
        "claude code notebooklm",
        "claude code design",
        "claude code skills",
        "claude code remotion video",
        "claude code video"
    ]

    if args.only:
        filters = [f.strip().lower() for f in args.only.split(",") if f.strip()]
        subtopics = [s for s in all_subtopics if any(f in s.lower() for f in filters)]
    else:
        subtopics = all_subtopics

    print(f"=== Claude Code Subtopics Research - Enhanced ===")
    print(f"Subtopics: {len(subtopics)}")
    print(f"Max results per subtopic: {args.max_results}")
    print(f"Total videos target: {args.total_videos}")

    all_video_data = []
    total_processed = 0
    
    for subtopic in subtopics:
        if total_processed >= args.total_videos:
            break
            
        dirs = get_dirs(subtopic)
        os.makedirs(dirs["reports"], exist_ok=True)
        
        print(f"\n--- Processing: {subtopic} ---")
        
        # Get videos for this subtopic
        videos = search_videos_by_topic(subtopic, args.max_results)
        if not videos:
            print(f"No videos found for: {subtopic}")
            continue
        
        # For trending topics (design/skills), reduce duplicate filtering
        should_filter_duplicates = "design" not in subtopic.lower() and "skills" not in subtopic.lower()
        
        existing_hashes = load_content_hashes(dirs["hash_tracker"]) if should_filter_duplicates else set()
        new_hashes = set()
        unique_videos = []
        
        # Filter duplicates only for non-trending topics
        for video in videos:
            if isinstance(video, dict):
                video_id = video.get("id", "")
                title = video.get("title", "")
                description = video.get("description", "") or ""
                duration = video.get("duration", 0)
                
                if video_id and title:
                    if should_filter_duplicates:
                        content_hash = create_content_hash(title, description, duration)
                        if content_hash not in existing_hashes:
                            unique_videos.append(video)
                            new_hashes.add(content_hash)
                            print(f"✅ New content: {title[:50]}...")
                        else:
                            print(f"❌ Duplicate content skipped: {title[:50]}...")
                    else:
                        # For trending topics, accept all content
                        unique_videos.append(video)
                        print(f"✅ Trending content: {title[:50]}...")
        
        if not unique_videos:
            print(f"No unique videos for: {subtopic}")
            continue
        
        # Process videos (respect total limit)
        videos_to_process = unique_videos[:min(len(unique_videos), args.total_videos - total_processed)]
        
        for video in videos_to_process:
            if total_processed >= args.total_videos:
                break
                
            video_id = video.get("id")
            video_title = video.get("title", "Unknown")
            video_url = f"https://youtube.com/watch?v={video_id}"
            
            print(f"Processing: {video_title}")
            
            video_data = process_video_with_summarize(video_url, subtopic, video_title, detailed=args.detailed)
            video_data['subtopic'] = subtopic
            
            if video_data:
                all_video_data.append(video_data)
                total_processed += 1
                print(f"✅ Processed: {video_title}")
            else:
                print(f"❌ Failed to process: {video_title}")
        
        # Update trackers (only for non-trending topics)
        if should_filter_duplicates and new_hashes:
            all_hashes = existing_hashes.union(new_hashes)
            save_content_hashes(dirs["hash_tracker"], all_hashes)
            print(f"Updated content hashes tracker with {len(new_hashes)} new hashes")
    
    if not all_video_data:
        print("No videos processed successfully")
        return
    
    # Generate reports by subtopic
    report_date = datetime.now().strftime('%Y-%m-%d')
    
    for subtopic in subtopics:
        subtopic_videos = [v for v in all_video_data if v.get('subtopic') == subtopic]
        if not subtopic_videos:
            continue
            
        dirs = get_dirs(subtopic)
        report_content = f"""# Claude Code - {subtopic.title()}

**Date:** {report_date}
**Topic:** {subtopic}
**Videos Processed:** {len(subtopic_videos)}

---

"""
        
        for i, video_data in enumerate(subtopic_videos, 1):
            report_content += f"""## Video {i}: {video_data['title']}

**Source:** {video_data.get('source_url', f"https://youtube.com/watch?v={video_data['video_id']}")}
**Video ID:** {video_data['video_id']}

### 📝 Full Summary (Thai)
{video_data['raw_summary']}

---

"""
        
        report_content += f"""Report generated at: {datetime.now(timezone.utc).isoformat()}
"""
        
        report_file = f"{dirs['reports']}/{report_date}.md"
        with open(report_file, "w") as f:
            f.write(report_content)
        
        print(f"📊 Report saved: {report_file}")
    
    print(f"\n✅ Successfully processed {len(all_video_data)} videos across {len(set(v.get('subtopic') for v in all_video_data))} subtopics")
    print(f"📁 Reports location: {BASE_REPORTS_DIR}/")

if __name__ == "__main__":
    import hashlib
    main()
