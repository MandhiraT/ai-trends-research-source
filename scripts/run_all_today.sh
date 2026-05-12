#!/bin/bash
# Run full daily pipeline manually (same sequence as cron)
# Usage: bash scripts/run_all_today.sh

set -e
_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS="$_DIR/../logs"
mkdir -p "$LOGS"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

log "=== AI Trends Full Pipeline — $(date '+%Y-%m-%d') ==="

log "1/10 AI Agents..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "AI Agents" --max-results 5 --detailed >> "$LOGS/ai_agents.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed (check logs/ai_agents.log)"

log "2/10 Claude Code..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Claude Code" --max-results 5 --detailed >> "$LOGS/claude_code.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "3/10 AI Viral Niche..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "AI Viral Niche" --max-results 5 --detailed >> "$LOGS/ai_viral_niche.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "4/10 NATEHERK channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "NATEHERK" --channel "https://youtube.com/@NATEHERK" --max-results 3 --detailed >> "$LOGS/nateherk.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "5/10 Joanna Wiebe channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Joanna Wiebe" --channel "https://youtube.com/@joanna-wiebe" --max-results 3 --detailed >> "$LOGS/joanna_wiebe.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "6/11 Claude Code Subtopics..."
bash "$_DIR/run_claude_code_subtopics_with_creds.sh" --max-results 3 --total-videos 18 --detailed >> "$LOGS/claude_code_subtopics.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "7/11 Claude Code New Subtopics..."
bash "$_DIR/run_claude_code_subtopics_with_creds.sh" --only "seedance,higgsfield,shopify" --max-results 5 --total-videos 15 --detailed >> "$LOGS/claude_code_new_subtopics.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "8/11 Jacksons AI channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Jacksons AI" --channel "https://youtube.com/@Jacksons_ai" --max-results 3 --detailed >> "$LOGS/jacksons_ai.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "9/11 Make Money Matt channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Make Money Matt" --channel "https://youtube.com/@makemoneymatt" --max-results 3 --detailed >> "$LOGS/make_money_matt.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "10/11 Miss Luna Vega playlist..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Miss Luna Vega" --channel "https://youtube.com/playlist?list=PLrpRRQWZ5EaEhot8F_6nJv3PA7Hk2eDe6" --max-results 3 --detailed >> "$LOGS/miss_luna_vega.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "11/11 Daily Summary + GitHub Upload..."
bash "$_DIR/run_daily_summary_cron.sh" >> "$LOGS/daily_summary.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "=== Pipeline complete ==="
