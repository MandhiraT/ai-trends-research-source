#!/bin/bash
# Run full daily pipeline manually (same sequence as cron)
# Usage: bash scripts/run_all_today.sh

set -e
_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS="$_DIR/../logs"
mkdir -p "$LOGS"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

log "=== AI Trends Full Pipeline — $(date '+%Y-%m-%d') ==="

log "1/17 AI Agents..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "AI Agents" --max-results 5 --detailed >> "$LOGS/ai_agents.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed (check logs/ai_agents.log)"

log "2/17 Claude Code..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Claude Code" --max-results 5 --detailed >> "$LOGS/claude_code.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "3/17 AI Viral Niche..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "AI Viral Niche" --max-results 5 --detailed >> "$LOGS/ai_viral_niche.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "4/17 NATEHERK channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "NATEHERK" --channel "https://youtube.com/@NATEHERK" --max-results 3 --detailed >> "$LOGS/nateherk.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "5/17 Joanna Wiebe channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Joanna Wiebe" --channel "https://youtube.com/@joanna-wiebe" --max-results 3 --detailed >> "$LOGS/joanna_wiebe.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "6/17 Claude Code Subtopics..."
bash "$_DIR/run_claude_code_subtopics_with_creds.sh" --max-results 3 --total-videos 18 --detailed >> "$LOGS/claude_code_subtopics.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "7/17 Claude Code New Subtopics..."
bash "$_DIR/run_claude_code_subtopics_with_creds.sh" --only "seedance,higgsfield,shopify,hyperframe" --max-results 5 --total-videos 20 --detailed >> "$LOGS/claude_code_new_subtopics.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "8/17 Jacksons AI channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Jacksons AI" --channel "https://youtube.com/@Jacksons_ai" --max-results 3 --detailed >> "$LOGS/jacksons_ai.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "9/17 Make Money Matt channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Make Money Matt" --channel "https://youtube.com/@makemoneymatt" --max-results 3 --detailed >> "$LOGS/make_money_matt.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "10/17 Miss Luna Vega playlist..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Miss Luna Vega" --channel "https://youtube.com/playlist?list=PLrpRRQWZ5EaEhot8F_6nJv3PA7Hk2eDe6" --max-results 3 --detailed >> "$LOGS/miss_luna_vega.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "11/17 Finance Money Coach channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Finance Money Coach" --channel "https://youtube.com/@THEMONEYCOACHTH" --max-results 3 --detailed >> "$LOGS/finance_money_coach.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "12/17 Finance Money Buffalo channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Finance Money Buffalo" --channel "https://www.youtube.com/c/MoneyBuffalo" --max-results 3 --detailed >> "$LOGS/finance_money_buffalo.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "13/17 Finance A-Academy channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Finance A-Academy" --channel "https://www.youtube.com/user/aacademychannel" --max-results 3 --detailed >> "$LOGS/finance_a_academy.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "14/17 Finance Financial Diet channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Finance Financial Diet" --channel "https://youtube.com/@thefinancialdiet" --max-results 3 --detailed >> "$LOGS/finance_financial_diet.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "15/17 Finance Humphrey Yang channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Finance Humphrey Yang" --channel "https://youtube.com/@humphrey" --max-results 3 --detailed >> "$LOGS/finance_humphrey_yang.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "16/17 Boom BigNose channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Boom BigNose" --channel "https://youtube.com/@BoomBigNose" --max-results 3 --detailed >> "$LOGS/boom_big_nose.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "17/17 Daily Summary + GitHub Upload..."
bash "$_DIR/run_daily_summary_cron.sh" >> "$LOGS/daily_summary.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "=== Pipeline complete ==="
