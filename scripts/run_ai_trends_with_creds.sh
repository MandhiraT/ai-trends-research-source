#!/bin/bash

# Load path configuration
_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$_DIR/../config/environment.sh"
# Wrapper script for AI Trends Research
# Sources credentials.env and runs Python script
# Usage: ./run_ai_trends_with_creds.sh [python_args...]

# Source credentials
# CREDENTIALS_FILE loaded by environment.sh
if [ -f "$CREDENTIALS_FILE" ]; then
    set -a
    source "$CREDENTIALS_FILE"
    set +a
    echo "✅ Loaded credentials from $CREDENTIALS_FILE"
else
    echo "❌ Error: Credentials file not found: $CREDENTIALS_FILE"
    exit 1
fi

# Run Python script with sourced environment.
# Use system Python: google-genai / Vertex deps are installed there, not in Hermes venv.
# All args are passed through to the Python script
/usr/bin/python3 $SCRIPTS_DIR/run_ai_trends_research_enhanced.py "$@"
