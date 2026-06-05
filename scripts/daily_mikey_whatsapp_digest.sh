#!/bin/bash
# Cron-safe daily Knowledge OS delivery for Mikey via Baileys.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

if [ -d /opt/homebrew/opt/openjdk ]; then
    export JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk}"
elif [ -d /usr/local/opt/openjdk ]; then
    export JAVA_HOME="${JAVA_HOME:-/usr/local/opt/openjdk}"
fi

if [ -n "${JAVA_HOME:-}" ]; then
    export PATH="$JAVA_HOME/bin:$PATH"
fi
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

DATE="$(TZ=America/Los_Angeles date +%F)"

bash scripts/check_daily_digest_ready.sh --user mikey --date "$DATE"
bash scripts/deliver_whatsapp_digest.sh --users mikey --date "$DATE" --skip-digest --skip-site --send
