#!/bin/bash
# Daily Summary + GitHub Upload
# Split mode supports:
#   --group morning   upload morning reports + morning Telegram summary only
#   --group self_help upload self-help reports + self-help Telegram summary
#   --group all       legacy all-topic pipeline without audio

set -euo pipefail

_GROUP="all"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --group) _GROUP="$2"; shift 2 ;;
        --group=*) _GROUP="${1#*=}"; shift ;;
        *) echo "Unknown argument: $1"; exit 2 ;;
    esac
done

if [[ "$_GROUP" != "all" && "$_GROUP" != "morning" && "$_GROUP" != "self_help" ]]; then
    echo "Invalid --group: $_GROUP (expected all, morning, self_help)"
    exit 2
fi

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

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting daily pipeline group=$_GROUP"

report_publish_status="ok"
# 1. Push MD reports to GitHub for this round.
if /usr/bin/python3 "$SCRIPTS_DIR/upload_reports_to_github_fixed.py"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] GitHub reports upload done group=$_GROUP"
else
    report_publish_status="failed"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: GitHub reports upload failed group=$_GROUP"
fi

if [[ "$_GROUP" == "morning" || "$_GROUP" == "all" ]]; then
    # 2. Send the main Telegram summary immediately after report upload.
    # Audio/TTS is handled by a separate cron job and must not delay this report.
    /usr/bin/python3 -u "$SCRIPTS_DIR/ai_trends_daily_summary_thai.py" \
        --group "$_GROUP" \
        --no-audio-status \
        --report-publish-status "$report_publish_status"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Morning summary sent"
else
    # Self-help round: report push + self-help Telegram summary only.
    /usr/bin/python3 -u "$SCRIPTS_DIR/ai_trends_daily_summary_thai.py" \
        --group self_help \
        --no-audio-status \
        --report-publish-status "$report_publish_status"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Daily summary + Telegram notification done group=$_GROUP"
