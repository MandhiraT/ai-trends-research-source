#!/bin/bash
# Daily Summary + GitHub Upload + Audio
# Runs after all research jobs complete (~14:55 Bangkok / 07:55 UTC)
# Order: upload reports → generate audio → push audio → send Telegram summary
# (Telegram summary is LAST so it can report audio status)

set -e

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

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting daily pipeline"

# 1. Push MD reports to GitHub
python3 "$SCRIPTS_DIR/upload_reports_to_github_fixed.py"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] GitHub reports upload done"

# 2. Generate audio reports (per-video mode)
python3 "$SCRIPTS_DIR/generate_audio_report.py" --all-enabled --per-video --date "$(date +%Y-%m-%d)" || true
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Audio generation done"

# 3. Push audio WAV files to GitHub
python3 "$SCRIPTS_DIR/upload_audio_to_github.py" --date "$(date +%Y-%m-%d)" || true
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Audio GitHub push done"

# 4. Send daily summary to Telegram (LAST — includes audio status)
python3 "$SCRIPTS_DIR/ai_trends_daily_summary_thai.py"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Daily summary + Telegram notification done"
