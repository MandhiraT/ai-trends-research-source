#!/bin/bash
# Run full daily pipeline manually (same sequence as cron)
# Usage: bash scripts/run_all_today.sh

set -e
_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS="$_DIR/../logs"
mkdir -p "$LOGS"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

log "=== AI Trends Full Pipeline — $(date '+%Y-%m-%d') ==="

log "1/29 AI Agents..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "AI Agents" --max-results 5 --transcript-langs "en,th,all" --detailed >> "$LOGS/ai_agents.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed (check logs/ai_agents.log)"

log "2/29 Claude Code..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Claude Code" --max-results 5 --transcript-langs "en,th,all" --detailed >> "$LOGS/claude_code.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "3/29 AI Viral Niche..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "AI Viral Niche" --max-results 5 --transcript-langs "en,th,all" --detailed >> "$LOGS/ai_viral_niche.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "4/29 NATEHERK channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "NATEHERK" --channel "https://youtube.com/@NATEHERK" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/nateherk.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "5/29 Joanna Wiebe channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Joanna Wiebe" --channel "https://youtube.com/@joanna-wiebe" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/joanna_wiebe.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "6/29 Claude Code Subtopics..."
bash "$_DIR/run_claude_code_subtopics_with_creds.sh" --max-results 3 --total-videos 18 --detailed >> "$LOGS/claude_code_subtopics.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "7/29 Claude Code New Subtopics..."
bash "$_DIR/run_claude_code_subtopics_with_creds.sh" --only "seedance,higgsfield,shopify,hyperframe" --max-results 5 --total-videos 20 --detailed >> "$LOGS/claude_code_new_subtopics.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "8/29 Jacksons AI channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Jacksons AI" --channel "https://youtube.com/@Jacksons_ai" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/jacksons_ai.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "9/29 Make Money Matt channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Make Money Matt" --channel "https://youtube.com/@makemoneymatt" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/make_money_matt.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "10/29 Miss Luna Vega playlist..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Miss Luna Vega" --channel "https://youtube.com/playlist?list=PLrpRRQWZ5EaEhot8F_6nJv3PA7Hk2eDe6" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/miss_luna_vega.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "11/29 Finance Money Coach channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Finance Money Coach" --channel "https://youtube.com/@THEMONEYCOACHTH" --max-results 3 --transcript-langs "th,en,all" --detailed >> "$LOGS/finance_money_coach.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "12/29 Finance Money Buffalo channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Finance Money Buffalo" --channel "https://www.youtube.com/c/MoneyBuffalo" --max-results 3 --transcript-langs "th,en,all" --detailed >> "$LOGS/finance_money_buffalo.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "13/29 Finance A-Academy channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Finance A-Academy" --channel "https://www.youtube.com/user/aacademychannel" --max-results 3 --transcript-langs "th,en,all" --detailed >> "$LOGS/finance_a_academy.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "14/29 Finance Financial Diet channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Finance Financial Diet" --channel "https://youtube.com/@thefinancialdiet" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/finance_financial_diet.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "15/29 Finance Humphrey Yang channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Finance Humphrey Yang" --channel "https://youtube.com/@humphrey" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/finance_humphrey_yang.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "16/29 Boom BigNose channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Boom BigNose" --channel "https://youtube.com/@BoomBigNose" --max-results 3 --transcript-langs "th,en,all" --detailed >> "$LOGS/boom_big_nose.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "17/29 Health — อาหารบำรุงสุขภาพ topic..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "อาหารบำรุงสุขภาพ" --report-folder "health/health_food_nutrition" --max-results 5 --transcript-langs "th,en,all" --detailed >> "$LOGS/health_food_nutrition.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "18/29 Health — Top to Toe playlist..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Top to Toe" --report-folder "health/top_to_toe" --channel "https://youtube.com/playlist?list=PLUaBTRNM7hIVi9p5t8-NtYgGN8zmi0X8N" --max-results 5 --transcript-langs "th,en,all" --detailed >> "$LOGS/health_top_to_toe.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "19/29 Self Help — Psychology — Therapy in a Nutshell channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Self Help Therapy in a Nutshell" --report-folder "self_help/psychology/therapy_in_a_nutshell" --channel "https://youtube.com/@TherapyinaNutshell" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/self_help_therapy_in_a_nutshell.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "20/29 Self Help — Psychology — HealthyGamerGG channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Self Help HealthyGamerGG" --report-folder "self_help/psychology/healthygamergg" --channel "https://youtube.com/@HealthyGamerGG" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/self_help_healthygamergg.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "21/29 Self Help — Psychology — The School of Life channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Self Help The School of Life" --report-folder "self_help/psychology/school_of_life" --channel "https://youtube.com/@theschooloflifetv" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/self_help_school_of_life.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "22/29 Self Help — Psychology — Dr. Tracey Marks channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Self Help Dr Tracey Marks" --report-folder "self_help/psychology/dr_tracey_marks" --channel "https://youtube.com/@DrTraceyMarks" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/self_help_dr_tracey_marks.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "23/29 Self Help — Habits — Ali Abdaal channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Self Help Ali Abdaal" --report-folder "self_help/habits/ali_abdaal" --channel "https://youtube.com/@aliabdaal" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/self_help_ali_abdaal.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "24/29 Self Help — Habits — James Clear channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Self Help James Clear" --report-folder "self_help/habits/james_clear" --channel "https://youtube.com/@jamesclear" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/self_help_james_clear.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "25/29 Self Help — Habits — Better Ideas channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Self Help Better Ideas" --report-folder "self_help/habits/better_ideas" --channel "https://youtube.com/@betterideas" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/self_help_better_ideas.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "26/29 Self Help — Habits — Struthless channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Self Help Struthless" --report-folder "self_help/habits/struthless" --channel "https://youtube.com/@struthless" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/self_help_struthless.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "27/29 Self Help — Modern Dharma — Doug's Dharma channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Self Help Doug's Dharma" --report-folder "self_help/modern_dharma/dougs_dharma" --channel "https://youtube.com/@DougsDharma" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/self_help_dougs_dharma.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "28/29 Self Help — Modern Dharma — Einzelgänger channel..."
bash "$_DIR/run_ai_trends_with_creds.sh" --topic "Self Help Einzelgänger" --report-folder "self_help/modern_dharma/einzelganger" --channel "https://youtube.com/@einzelganger" --max-results 3 --transcript-langs "en,th,all" --detailed >> "$LOGS/self_help_einzelganger.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "29/29 Daily Summary + GitHub Upload..."
bash "$_DIR/run_daily_summary_cron.sh" >> "$LOGS/daily_summary.log" 2>&1 && log "  ✅ Done" || log "  ❌ Failed"

log "=== Pipeline complete ==="
