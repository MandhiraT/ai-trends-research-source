#!/bin/bash
# Run full daily pipeline manually (same sequence as cron)
# Usage: bash scripts/run_all_today.sh

set -e
_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS="$_DIR/../logs"
mkdir -p "$LOGS"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

log "=== AI Trends Full Pipeline — $(date '+%Y-%m-%d') ==="

log "1/7 AI Agents..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "AI Agents" --max-results 5 --detailed >> "$LOGS/ai_agents.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed (check logs/ai_agents.log)"

log "2/7 Claude Code..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Claude Code" --max-results 5 --detailed >> "$LOGS/claude_code.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "3/7 AI Viral Niche..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "AI Viral Niche" --max-results 5 --detailed >> "$LOGS/ai_viral_niche.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "4/7 NATEHERK channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "NATEHERK" --channel "https://youtube.com/@NATEHERK" --max-results 3 --detailed >> "$LOGS/nateherk.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "5/7 Joanna Wiebe channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Joanna Wiebe" --channel "https://youtube.com/@joanna-wiebe" --max-results 3 --detailed >> "$LOGS/joanna_wiebe.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "6/7 Claude Code Subtopics..."
bash "$_DIR/run_claude_code_subtopics_with_creds.sh" --max-results 3 --total-videos 8 --detailed >> "$LOGS/claude_code_subtopics.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "7/7 Daily Summary + GitHub Upload..."
bash "$_DIR/run_daily_summary_cron.sh" >> "$LOGS/daily_summary.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "=== Pipeline complete ==="
