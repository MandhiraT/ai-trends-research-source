#!/bin/bash
# Daily Summary + GitHub Upload
# Runs after all research jobs complete (~07:40 Bangkok)
# Generates Thai daily summary then pushes all reports to GitHub

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

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting daily summary + GitHub upload"

python3 "$SCRIPTS_DIR/ai_trends_daily_summary_thai.py"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Daily summary done"

python3 "$SCRIPTS_DIR/upload_reports_to_github_fixed.py"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] GitHub upload done"
