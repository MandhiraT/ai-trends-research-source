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
Upload AI Trends Research reports to GitHub repository (FIXED)
Supports recursive directory copy for all subtopics
"""

import os
import subprocess
import shutil
from datetime import datetime

# Configuration
GITHUB_REPO = "https://github.com/MandhiraT/ai-trends-research.git"
LOCAL_REPO_PATH = GITHUB_TEMP_CLONE
REPORTS_SOURCE = _os.path.join(REPORTS_DIR, 'reports')
DATE_STR = datetime.now().strftime('%Y-%m-%d')

def run_git_command(cmd, cwd):
    """Run git command and handle errors"""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Git error: {result.stderr}")
        return False
    return True

def copy_recursive(src_dir, dest_dir):
    """Recursively copy all files from source to destination"""
    uploaded = []

    for root, dirs, files in os.walk(src_dir):
        # Calculate relative path from source
        rel_path = os.path.relpath(root, src_dir)
        dest_subdir = os.path.join(dest_dir, rel_path)
        os.makedirs(dest_subdir, exist_ok=True)

        for file in files:
            src_file = os.path.join(root, file)
            dest_file = os.path.join(dest_subdir, file)
            shutil.copy2(src_file, dest_file)
            print(f"✅ Copied: {dest_file}")
            uploaded.append(dest_file)

    return uploaded

def upload_reports():
    """Upload all report files to GitHub recursively"""
    # Ensure local repo exists
    if not os.path.exists(LOCAL_REPO_PATH):
        os.makedirs(LOCAL_REPO_PATH)
        subprocess.run(["git", "init"], cwd=LOCAL_REPO_PATH)
        subprocess.run(["git", "remote", "add", "origin", GITHUB_REPO], cwd=LOCAL_REPO_PATH)

    # Pull latest changes
    subprocess.run(["git", "pull", "origin", "master"], cwd=LOCAL_REPO_PATH, capture_output=True)

    # Configure git user
    subprocess.run(["git", "config", "user.email", "mandhira@thequietself.com"], cwd=LOCAL_REPO_PATH)
    subprocess.run(["git", "config", "user.name", "MandhiraT"], cwd=LOCAL_REPO_PATH)

    # Create reports directory structure
    reports_dest = os.path.join(LOCAL_REPO_PATH, "reports")
    os.makedirs(reports_dest, exist_ok=True)

    uploaded_files = []

    # Copy all topic directories RECURSIVELY
    for topic_dir in os.listdir(REPORTS_SOURCE):
        topic_path = os.path.join(REPORTS_SOURCE, topic_dir)
        if os.path.isdir(topic_path):
            # Create topic directory in repo
            dest_topic_dir = os.path.join(reports_dest, topic_dir)

            # Clear destination directory first to ensure fresh upload
            if os.path.exists(dest_topic_dir):
                shutil.rmtree(dest_topic_dir)
            os.makedirs(dest_topic_dir, exist_ok=True)
            
            # Copy all files recursively (including subdirectories)
            uploaded_files.extend(copy_recursive(topic_path, dest_topic_dir))

    # Also copy Joanna Wiebe reports
    joanna_source = _os.path.join(PROJECT_ROOT, 'joanna_wiebe_reports', 'joanna-wiebe')
    if os.path.exists(joanna_source):
        content_marketing_dir = os.path.join(LOCAL_REPO_PATH, "Content Marketing")
        joanna_dest = os.path.join(content_marketing_dir, "Joanna-Wiebe")
        
        # Clear destination first
        if os.path.exists(joanna_dest):
            shutil.rmtree(joanna_dest)
        os.makedirs(os.path.dirname(joanna_dest), exist_ok=True)
        
        uploaded_files.extend(copy_recursive(joanna_source, joanna_dest))

    if len(uploaded_files) == 0:
        print("❌ No reports found")
        return False

    print(f"\n📊 Total files to upload: {len(uploaded_files)}")

    # Git add, commit, push
    if not run_git_command(["git", "add", "."], LOCAL_REPO_PATH):
        return False

    # Check if there are changes to commit
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=LOCAL_REPO_PATH, capture_output=True)
    if result.returncode == 0:
        print("\n⚠️ No changes to commit - files already up to date")
        return True  # Return True since no error, just no changes
    
    commit_msg = f"AI Trends Research Reports - {DATE_STR} (FIXED - Recursive Upload)"
    if not run_git_command(["git", "commit", "-m", commit_msg], LOCAL_REPO_PATH):
        return False

    if not run_git_command(["git", "push", "origin", "master"], LOCAL_REPO_PATH):
        return False

    print(f"\n✅ Successfully uploaded {len(uploaded_files)} file(s) to GitHub")
    return True

if __name__ == "__main__":
    if upload_reports():
        url = "https://github.com/MandhiraT/ai-trends-research/tree/master/reports"
        print(f"\n🔗 GitHub Reports URL: {url}")
    else:
        import sys
        sys.exit(1)
