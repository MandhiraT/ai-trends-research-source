#!/bin/bash
# AI Trends Research — Path Configuration
# Source this at the top of every shell script:
#   source "$(dirname "$0")/../config/environment.sh"

# Auto-detect PROJECT_ROOT from this file's location (config/ -> parent)
export PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# Derived paths
export SCRIPTS_DIR="$PROJECT_ROOT/scripts"
export PROMPTS_DIR="$PROJECT_ROOT/prompts"
export REPORTS_DIR="$PROJECT_ROOT/ai_trends_reports"
export LOGS_DIR="$PROJECT_ROOT/logs"

# Dashboard/systemd services can start with a minimal PATH. ATS shell wrappers
# need user-installed tools such as yt-dlp (~/.local/bin) and bun/claude helpers
# even when launched from the dashboard service rather than an interactive shell.
export PATH="$HOME/.local/bin:$HOME/.bun/bin:$HOME/.npm-global/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

# Credentials (override via env var; default to global ~/.credentials.env like FAW)
export CREDENTIALS_FILE="${CREDENTIALS_FILE:-$HOME/.credentials.env}"

# Load credentials if file exists
if [ -f "$CREDENTIALS_FILE" ]; then
    set -a; source "$CREDENTIALS_FILE"; set +a
fi

# Ensure directories exist
mkdir -p "$LOGS_DIR" "$REPORTS_DIR/reports"
