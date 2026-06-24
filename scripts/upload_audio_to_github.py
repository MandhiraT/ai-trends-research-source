#!/usr/bin/env python3
"""
upload_audio_to_github.py — Push generated WAV audio files to ai-trends-research GitHub repo.

Hardening changes:
- always clone a fresh output-repo checkout for each upload run
- do not rely on a stale /tmp clone carrying old auth or broken git objects
- keep the existing per-date copy/publish behavior, but make the checkout self-healing
"""

import sys
import os
import json
import shutil
from datetime import date as _date
from pathlib import Path
from voice_filenames import find_voice_files

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config'))
try:
    from paths import PROJECT_ROOT, AUDIO_DIR, GITHUB_TEMP_CLONE, load_credentials
except ImportError:
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    AUDIO_DIR = os.path.join(PROJECT_ROOT, 'ai_trends_reports', 'audio')
    GITHUB_TEMP_CLONE = os.path.expanduser('~/.cache/ai-trends-research/github-output-repo')
    def load_credentials():
        return None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from github_output_repo import GitRepoError, prepare_fresh_checkout, stage_paths, commit_and_push

load_credentials()

AUDIO_CONFIG = os.path.join(PROJECT_ROOT, 'config', 'audio_topics.json')
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, 'ai_trends_reports', 'audio_scripts')
GITHUB_REPO = 'https://github.com/MandhiraT/ai-trends-research.git'


def _remove_matching_files(directory: str, *patterns: str) -> None:
    path = Path(directory)
    if not path.exists():
        return
    for pattern in patterns:
        for candidate in path.glob(pattern):
            if candidate.is_file():
                candidate.unlink()


def upload_audio(date_str: str) -> bool:
    with open(AUDIO_CONFIG, encoding='utf-8') as f:
        config = json.load(f)

    enabled = config.get('enabled_topics', [])
    folder_map = config.get('github_folder_map', {})
    token = os.environ.get('GITHUB_TOKEN', '')

    if not enabled:
        print('[audio-upload] No enabled topics — nothing to push.')
        return True

    repo = prepare_fresh_checkout(GITHUB_REPO, GITHUB_TEMP_CLONE, token=token)

    import glob as _glob

    copied = []
    touched_dirs = set()
    for topic in enabled:
        topic_audio_dir = os.path.join(AUDIO_DIR, topic)
        wav_files = [str(p) for p in find_voice_files(Path(topic_audio_dir), topic, date_str)]
        if not wav_files:
            print(f'[audio-upload] ⚠️  No WAV for {topic}/{date_str} — skipping')
            continue

        dest_folder = folder_map.get(topic, topic).strip().replace(' ', '_').replace('-', '_').lower()
        dest_dir = os.path.join(repo, 'voice', dest_folder)
        os.makedirs(dest_dir, exist_ok=True)
        _remove_matching_files(dest_dir, f'{date_str}.wav', f'{date_str}-*.wav')
        touched_dirs.add(os.path.join('voice', dest_folder))

        for wav in wav_files:
            fname = os.path.basename(wav)
            dest = os.path.join(dest_dir, fname)
            shutil.copy2(wav, dest)
            size_mb = os.path.getsize(dest) / (1024 * 1024)
            rel_path = os.path.join('voice', dest_folder, fname)
            print(f'[audio-upload] ✅ Copied: {rel_path} ({size_mb:.1f} MB)')
            copied.append(rel_path)

    for topic in enabled:
        topic_scripts_dir = os.path.join(SCRIPTS_DIR, topic)
        script_files = _glob.glob(os.path.join(topic_scripts_dir, f'{date_str}-v*.md'))
        if not script_files:
            continue

        dest_folder = folder_map.get(topic, topic).strip().replace(' ', '_').replace('-', '_').lower()
        dest_scripts_dir = os.path.join(repo, 'audio_scripts', dest_folder)
        os.makedirs(dest_scripts_dir, exist_ok=True)
        _remove_matching_files(dest_scripts_dir, f'{date_str}.md', f'{date_str}-*.md')
        touched_dirs.add(os.path.join('audio_scripts', dest_folder))

        for src in script_files:
            fname = os.path.basename(src)
            dest = os.path.join(dest_scripts_dir, fname)
            shutil.copy2(src, dest)
            rel_path = os.path.join('audio_scripts', dest_folder, fname)
            print(f'[audio-upload] 📄 Copied: {rel_path}')
            copied.append(rel_path)

    if not copied:
        print('[audio-upload] Nothing to commit.')
        return True

    try:
        stage_paths(repo, sorted(touched_dirs))
        changed = commit_and_push(repo, f'auto: audio reports {date_str}', token=token)
    except GitRepoError as exc:
        print(f'[audio-upload] ❌ {exc}')
        return False

    if not changed:
        print('[audio-upload] No changes to commit (files already up to date).')
        return True

    print(f'[audio-upload] ✅ Pushed {len(copied)} file(s) to GitHub')
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=str(_date.today()))
    args = parser.parse_args()

    print(f'[audio-upload] Uploading audio for date={args.date}')
    ok = upload_audio(args.date)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
