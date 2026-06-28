#!/usr/bin/env python3
"""
upload_audio_to_github.py — Push generated WAV/script files to ai-trends-research GitHub repo.

Uses GitHub Git Data API — no local git clone required.
Only uploads files that don't already exist on GitHub.
"""

import sys
import os
import json
from datetime import date as _date
from pathlib import Path
from voice_filenames import find_voice_files
import glob as _glob

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config'))
try:
    from paths import PROJECT_ROOT, AUDIO_DIR, load_credentials
except ImportError:
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    AUDIO_DIR = os.path.join(PROJECT_ROOT, 'ai_trends_reports', 'audio')
    def load_credentials():
        return None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from github_api_upload import upload_files, ApiError

load_credentials()

AUDIO_CONFIG = os.path.join(PROJECT_ROOT, 'config', 'audio_topics.json')
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, 'ai_trends_reports', 'audio_scripts')


def upload_audio(date_str: str) -> bool:
    with open(AUDIO_CONFIG, encoding='utf-8') as f:
        config = json.load(f)

    enabled = config.get('enabled_topics', [])
    folder_map = config.get('github_folder_map', {})
    token = os.environ.get('GITHUB_TOKEN', '')

    if not enabled:
        print('[audio-upload] No enabled topics — nothing to push.')
        return True

    if not token:
        print('[audio-upload] ❌ GITHUB_TOKEN not set')
        return False

    additions: list[tuple[Path, str]] = []
    deletions: list[str] = []

    for topic in enabled:
        topic_audio_dir = os.path.join(AUDIO_DIR, topic)
        wav_files = [str(p) for p in find_voice_files(Path(topic_audio_dir), topic, date_str)]
        if not wav_files:
            print(f'[audio-upload] ⚠️  No WAV for {topic}/{date_str} — skipping')
            continue

        dest_folder = folder_map.get(topic, topic).strip().replace(' ', '_').replace('-', '_').lower()

        for wav in wav_files:
            fname = os.path.basename(wav)
            github_path = f"voice/{dest_folder}/{fname}"
            additions.append((Path(wav), github_path))
            print(f'[audio-upload] ✅ Queued: {github_path} ({os.path.getsize(wav) / 1024 / 1024:.1f} MB)')

        # Queue deletion of old same-date files (replaced by new ones)
        date_patterns = [f"{date_str}.wav", f"{date_str}-*.wav"]
        new_fnames = {os.path.basename(w) for w in wav_files}
        for pat in date_patterns:
            for old in _glob.glob(os.path.join(topic_audio_dir, pat)):
                fname = os.path.basename(old)
                if fname not in new_fnames:
                    deletions.append(f"voice/{dest_folder}/{fname}")

    for topic in enabled:
        dest_folder = folder_map.get(topic, topic).strip().replace(' ', '_').replace('-', '_').lower()
        topic_scripts_dir = os.path.join(SCRIPTS_DIR, topic)
        script_files = _glob.glob(os.path.join(topic_scripts_dir, f'{date_str}-v*.md'))
        for src in script_files:
            fname = os.path.basename(src)
            github_path = f"audio_scripts/{dest_folder}/{fname}"
            additions.append((Path(src), github_path))
            print(f'[audio-upload] 📄 Queued: {github_path}')

    if not additions and not deletions:
        print('[audio-upload] Nothing to upload.')
        return True

    try:
        changed = upload_files(
            token=token,
            additions=additions,
            deletions=deletions,
            commit_message=f"auto: audio reports {date_str}",
        )
    except ApiError as exc:
        print(f'[audio-upload] ❌ {exc}')
        return False

    if not changed:
        print('[audio-upload] No changes to commit (files already up to date).')

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
