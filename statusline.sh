#!/usr/bin/env bash
# Claude Code HUD statusline plugin
# Reads JSON from stdin and outputs a formatted status line

set -euo pipefail

input=$(cat)

# Extract fields (with safe defaults)
MODEL=$(echo "$input" | jq -r '.model.display_name // "unknown"')
USED_PCT=$(echo "$input" | jq -r '(.context_window.used_percentage // 0) | floor')
COST=$(echo "$input" | jq -r '(.cost.total_cost_usd // 0) | (. * 100 | round | . / 100) | tostring')
AGENT=$(echo "$input" | jq -r '.agent.name // ""')
DIR=$(echo "$input" | jq -r '.workspace.current_dir // ""' | sed "s|$HOME|~|")

# ANSI colors
RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# Context color based on usage
if [ "$USED_PCT" -ge 90 ]; then
  CTX_COLOR="$RED"
elif [ "$USED_PCT" -ge 70 ]; then
  CTX_COLOR="$YELLOW"
else
  CTX_COLOR="$GREEN"
fi

# Build a 10-char progress bar
FILLED=$(( USED_PCT / 10 ))
EMPTY=$(( 10 - FILLED ))
BAR=""
for ((i=0; i<FILLED; i++)); do BAR+="█"; done
for ((i=0; i<EMPTY; i++));  do BAR+="░"; done

# Agent segment (only shown when inside a subagent)
AGENT_SEG=""
if [ -n "$AGENT" ]; then
  AGENT_SEG=" ${DIM}[${AGENT}]${RESET}"
fi

# Dir segment
DIR_SEG=""
if [ -n "$DIR" ]; then
  DIR_SEG=" ${DIM}${DIR}${RESET}"
fi

printf "${BOLD}${CYAN}%s${RESET}${AGENT_SEG}${DIR_SEG}  ${CTX_COLOR}[%s]${RESET} ${USED_PCT}%%  ${DIM}\$${COST}${RESET}\n" \
  "$MODEL" "$BAR"
