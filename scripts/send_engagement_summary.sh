#!/bin/bash
# Engagement Summary Delivery Wrapper
# Generates yesterday's engagement summary and outputs for WhatsApp delivery

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

PYTHON="$PROJECT_ROOT/venv/bin/python"
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

# Generate summary
SUMMARY=$($PYTHON -m knowledge_os.engagement_summary hn_digest_v2.db)

# Only output if there's a summary (not NO_SUMMARY)
if [ "$SUMMARY" != "NO_SUMMARY" ]; then
    echo "$SUMMARY"
fi

# Note: If empty output, cron job should skip WhatsApp send
