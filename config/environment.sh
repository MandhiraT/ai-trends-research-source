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

# Credentials (override via env var or credentials.env)
export CREDENTIALS_FILE="${CREDENTIALS_FILE:-$PROJECT_ROOT/credentials.env}"

# Load credentials if file exists
if [ -f "$CREDENTIALS_FILE" ]; then
    set -a; source "$CREDENTIALS_FILE"; set +a
fi

# Ensure directories exist
mkdir -p "$LOGS_DIR" "$REPORTS_DIR/reports"
