#!/bin/bash
# Daily Summary + GitHub Upload + Audio
# Split mode supports:
#   --group morning   upload morning reports + audio + morning Telegram summary
#   --group self_help upload self-help reports + self-help Telegram summary
#   --group all       legacy all-topic pipeline

set -e

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

# 1. Push MD reports to GitHub for this round. The uploader is idempotent and
# syncs the current local reports tree; running it in both rounds publishes
# morning reports early and self-help reports after the self-help block.
/usr/bin/python3 "$SCRIPTS_DIR/upload_reports_to_github_fixed.py"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] GitHub reports upload done group=$_GROUP"

if [[ "$_GROUP" == "morning" || "$_GROUP" == "all" ]]; then
    # 2. Generate audio reports (per-video mode) only in the morning/all round.
    /usr/bin/python3 "$SCRIPTS_DIR/generate_audio_report.py" --all-enabled --per-video --date "$(date +%Y-%m-%d)" || true
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Audio generation done"

    # 3. Push audio WAV files to GitHub
    /usr/bin/python3 "$SCRIPTS_DIR/upload_audio_to_github.py" --date "$(date +%Y-%m-%d)" || true
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Audio GitHub push done"

    # 4. Per-topic notifications (email + Telegram DM per routing config)
    /usr/bin/python3 "$SCRIPTS_DIR/notify_topic.py" --all --date "$(date +%Y-%m-%d)" || true
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Per-topic notifications done"

    /usr/bin/python3 "$SCRIPTS_DIR/ai_trends_daily_summary_thai.py" --group "$_GROUP"
else
    # Self-help round: report push + self-help Telegram summary only.
    /usr/bin/python3 "$SCRIPTS_DIR/ai_trends_daily_summary_thai.py" --group self_help --no-audio-status
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Daily summary + Telegram notification done group=$_GROUP"
