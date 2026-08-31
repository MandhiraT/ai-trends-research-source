#!/bin/bash
# Separate ATS audio generation/publish/notify job.
# This runs independently from the morning daily summary so a slow audio or git step
# cannot block report delivery.

set -euo pipefail

_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$_DIR/../config/environment.sh"

if [ -f "$CREDENTIALS_FILE" ]; then
    set -a
    source "$CREDENTIALS_FILE"
    set +a
else
    echo "❌ Credentials file not found: $CREDENTIALS_FILE"
    exit 1
fi

LOCK_DIR="${TMPDIR:-/tmp}/ats-audio-publish.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Another ATS audio publish job is already running — exiting"
    exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

DATE_STR="$(date +%Y-%m-%d)"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting separate ATS audio pipeline date=$DATE_STR"

/usr/bin/python3 -u "$SCRIPTS_DIR/generate_audio_report.py" --all-enabled --per-video --date "$DATE_STR" || true
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Audio generation done"

if /usr/bin/python3 -u "$SCRIPTS_DIR/upload_audio_to_github.py" --date "$DATE_STR"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Audio GitHub push done"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: Audio GitHub push failed"
fi

/usr/bin/python3 -u "$SCRIPTS_DIR/notify_topic.py" --all --date "$DATE_STR" || true
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Per-topic notifications done"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Separate ATS audio pipeline finished"
