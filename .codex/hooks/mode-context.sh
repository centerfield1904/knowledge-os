#!/usr/bin/env bash
MODE=$(cat "$HOME/.claude/current-mode" 2>/dev/null || echo "engineering")
[ "$MODE" = "engg" ] && MODE="engineering"

if [ "$MODE" = "pm" ]; then
  CONTEXT="SESSION MODE: PM Mode — Helping an engineer build PM skills. For every task: start with the problem and who it affects; frame tradeoffs as user value vs effort; ask 'what does success look like?' before implementation; reference pm/PRODUCT_STRATEGY.md for context; suggest PM_NOTEBOOK.md entries when a PM concept surfaces. Think PM-first, engineer-second. Type /mode to switch."
else
  CONTEXT="SESSION MODE: Engineering Mode — Standard engineering session. Clean code, tests, architecture. Type /mode to switch to PM mode."
fi

jq -n --arg ctx "$CONTEXT" \
  '{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": $ctx}}'
