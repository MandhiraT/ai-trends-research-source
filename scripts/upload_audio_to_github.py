#!/usr/bin/env python3
"""
upload_audio_to_github.py — Push generated WAV audio files to ai-trends-research GitHub repo.

Reads config/audio_topics.json for enabled topics and github_folder_map.
Copies WAV files from ai_trends_reports/audio/{TOPIC}/ to canonical
voice/{folder}/ in the reports repo clone, then commits and pushes.

Usage:
    python3 scripts/upload_audio_to_github.py --date 2026-05-07
    python3 scripts/upload_audio_to_github.py  # defaults to today
"""

import sys
import os
import json
import shutil
import subprocess
from datetime import date as _date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config'))
try:
    from paths import PROJECT_ROOT, AUDIO_DIR, GITHUB_TEMP_CLONE, load_credentials
except ImportError:
    PROJECT_ROOT    = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    AUDIO_DIR       = os.path.join(PROJECT_ROOT, 'ai_trends_reports', 'audio')
    GITHUB_TEMP_CLONE = '/tmp/ai-trends-research'
    def load_credentials(): pass

load_credentials()

AUDIO_CONFIG = os.path.join(PROJECT_ROOT, 'config', 'audio_topics.json')
GITHUB_REPO  = 'https://github.com/MandhiraT/ai-trends-research.git'


def _git(args: list, cwd: str) -> bool:
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0 and r.stderr:
        print(f'  [git] {r.stderr.strip()}')
    return r.returncode == 0


def upload_audio(date_str: str) -> bool:
    with open(AUDIO_CONFIG, encoding='utf-8') as f:
        config = json.load(f)

    enabled   = config.get('enabled_topics', [])
    folder_map = config.get('github_folder_map', {})
    token     = os.environ.get('GITHUB_TOKEN', '')

    if not enabled:
        print('[audio-upload] No enabled topics — nothing to push.')
        return True

    repo = GITHUB_TEMP_CLONE
    if not os.path.isdir(os.path.join(repo, '.git')):
        print(f'[audio-upload] Reports repo not cloned at {repo} — cloning...')
        os.makedirs(repo, exist_ok=True)
        subprocess.run(['git', 'init'], cwd=repo)
        subprocess.run(['git', 'remote', 'add', 'origin', GITHUB_REPO], cwd=repo)

    _git(['git', 'pull', 'origin', 'master'], repo)

    copied = []
    for topic in enabled:
        wav = os.path.join(AUDIO_DIR, topic, f'{date_str}.wav')
        if not os.path.exists(wav):
            print(f'[audio-upload] ⚠️  No WAV for {topic}/{date_str} — skipping')
            continue

        dest_folder = folder_map.get(topic, topic).strip().replace(' ', '_').replace('-', '_').lower()
        dest_dir    = os.path.join(repo, 'voice', dest_folder)
        os.makedirs(dest_dir, exist_ok=True)

        dest = os.path.join(dest_dir, f'{date_str}.wav')
        shutil.copy2(wav, dest)
        size_mb = os.path.getsize(dest) / (1024 * 1024)
        rel_path = os.path.join('voice', dest_folder, f'{date_str}.wav')
        print(f'[audio-upload] ✅ Copied: {rel_path} ({size_mb:.1f} MB)')
        copied.append(rel_path)

    if not copied:
        print('[audio-upload] Nothing to commit.')
        return True

    _git(['git', 'add'] + copied, repo)

    has_changes = subprocess.run(
        ['git', 'diff', '--cached', '--quiet'], cwd=repo
    ).returncode != 0

    if not has_changes:
        print('[audio-upload] No changes to commit (files already up to date).')
        return True

    _git(['git', '-c', 'user.email=mandhira@thequietself.com',
          '-c', 'user.name=MandhiraT',
          'commit', '-m', f'auto: audio reports {date_str}'], repo)

    if token:
        _git(['git', 'remote', 'set-url', 'origin',
              f'https://{token}@github.com/MandhiraT/ai-trends-research.git'], repo)

    ok = _git(['git', 'push', 'origin', 'master'], repo)
    if ok:
        print(f'[audio-upload] ✅ Pushed {len(copied)} file(s) to GitHub')
    else:
        print('[audio-upload] ❌ Push failed')
    return ok


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
