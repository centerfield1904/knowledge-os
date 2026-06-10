#!/bin/bash
# Run the daily ingest/publish path and verify public readiness.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

DATE="$(date +%F)"
INGEST_LOG="${KNOS_INGEST_LOG:-$HOME/Library/Logs/knowledge-os-ingest.log}"
RUN_ARGS=()
WAIT_SECONDS=0
POLL_SECONDS=60

usage() {
    cat <<'USAGE'
Usage: scripts/run_daily_ingest_and_verify_publish.sh [options] [run_catalog_ingest options]

Runs the production morning ingest wrapper, which dispatches the bvaibhav-info
GitHub Action, then verifies that bvaibhav.info has published today's digest.

Options:
  --date YYYY-MM-DD       Digest date, defaults to today; forwarded to run_catalog_ingest.sh
  --log PATH              Ingest log path, defaults to ~/Library/Logs/knowledge-os-ingest.log
  --wait-seconds N        Poll readiness for up to N seconds after ingest; defaults to 0
  --poll-seconds N        Poll interval when waiting; defaults to 60
  -h, --help              Show this help

Any other options are forwarded to scripts/run_catalog_ingest.sh.
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --date)
            DATE="$2"
            RUN_ARGS+=(--date "$2")
            shift 2
            ;;
        --log) INGEST_LOG="$2"; shift 2 ;;
        --wait-seconds) WAIT_SECONDS="$2"; shift 2 ;;
        --poll-seconds) POLL_SECONDS="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *)
            RUN_ARGS+=("$1")
            shift
            ;;
    esac
done

mkdir -p "$(dirname "$INGEST_LOG")"

echo "Running daily ingest for ${DATE}; appending logs to ${INGEST_LOG}" >&2
bash scripts/run_catalog_ingest.sh "${RUN_ARGS[@]}" >> "$INGEST_LOG" 2>&1

echo "Ingest completed. Recent ingest log:" >&2
tail -n 80 "$INGEST_LOG" >&2

deadline=$((SECONDS + WAIT_SECONDS))
while ! bash scripts/check_daily_digest_ready.sh --date "$DATE"; do
    if [ "$SECONDS" -ge "$deadline" ]; then
        echo "Daily ingest completed, but website publish is not ready for ${DATE}" >&2
        echo "The scheduled bvaibhav-info GitHub Action may not have run yet." >&2
        exit 1
    fi
    sleep "$POLL_SECONDS"
done

echo "Daily ingest and website publish verified for ${DATE}" >&2
