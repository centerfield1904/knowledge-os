#!/bin/bash
# Run the daily ingest/publish path, monitor the website workflow, and verify public readiness.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

DATE="$(date +%F)"
INGEST_LOG="${KNOS_INGEST_LOG:-$HOME/Library/Logs/knowledge-os-ingest.log}"
WEBSITE_REPO="${KNOS_WEBSITE_REPO:-centerfield1904/bvaibhav-info}"
WEBSITE_WORKFLOW="${KNOS_WEBSITE_WORKFLOW:-update-digest.yml}"
PYTHON="${PYTHON:-$PROJECT_ROOT/venv/bin/python}"
RUN_ARGS=()
WATCH_WORKFLOW=true

usage() {
    cat <<'USAGE'
Usage: scripts/run_daily_ingest_and_verify_publish.sh [options] [run_catalog_ingest options]

Runs the production morning ingest wrapper, watches the triggered bvaibhav-info
GitHub Action, and verifies that bvaibhav.info has published today's digest.

Options:
  --date YYYY-MM-DD       Digest date, defaults to today; forwarded to run_catalog_ingest.sh
  --log PATH              Ingest log path, defaults to ~/Library/Logs/knowledge-os-ingest.log
  --no-watch              Do not watch the GitHub Action; still list the latest run
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
        --no-watch) WATCH_WORKFLOW=false; shift ;;
        -h|--help) usage; exit 0 ;;
        *)
            RUN_ARGS+=("$1")
            shift
            ;;
    esac
done

if ! command -v gh >/dev/null 2>&1; then
    echo "GitHub CLI not found. Install gh before running the publish monitor." >&2
    exit 1
fi

if ! gh auth status --hostname github.com >/dev/null 2>&1; then
    echo "GitHub CLI is not authenticated. Run: gh auth login -h github.com" >&2
    exit 1
fi

mkdir -p "$(dirname "$INGEST_LOG")"

echo "Running daily ingest for ${DATE}; appending logs to ${INGEST_LOG}" >&2
bash scripts/run_catalog_ingest.sh "${RUN_ARGS[@]}" >> "$INGEST_LOG" 2>&1

echo "Ingest completed. Recent ingest log:" >&2
tail -n 80 "$INGEST_LOG" >&2

run_json="$(gh run list \
    --repo "$WEBSITE_REPO" \
    --workflow "$WEBSITE_WORKFLOW" \
    --event workflow_dispatch \
    --limit 1 \
    --json databaseId,status,conclusion,createdAt,url)"

run_id="$("$PYTHON" -c 'import json,sys; runs=json.load(sys.stdin); print(runs[0]["databaseId"] if runs else "")' <<< "$run_json")"
run_url="$("$PYTHON" -c 'import json,sys; runs=json.load(sys.stdin); print(runs[0]["url"] if runs else "")' <<< "$run_json")"

if [ -z "$run_id" ]; then
    echo "No recent workflow_dispatch run found for ${WEBSITE_REPO}/${WEBSITE_WORKFLOW}" >&2
    exit 1
fi

echo "Latest website publish workflow run: ${run_url}" >&2
if $WATCH_WORKFLOW; then
    gh run watch "$run_id" --repo "$WEBSITE_REPO" --exit-status
fi

bash scripts/check_daily_digest_ready.sh --date "$DATE"
echo "Daily ingest and website publish verified for ${DATE}" >&2
