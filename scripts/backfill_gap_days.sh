#!/bin/bash
# Backfill missed Knowledge OS ingest/digest days discovered by gap_summary.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

PYTHON="${PYTHON:-$PROJECT_ROOT/venv/bin/python}"
DB="${DB:-knowledge_os.db}"
DIGEST_DIR="${DIGEST_DIR:-knos-digest}"
SINCE=""
UNTIL="$(date +%F)"
GAP_TYPES="ingest,digest"
DATES=""
PUBLISH=0
DRY_RUN=0
HISTORICAL_HN=1

usage() {
    cat <<'USAGE'
Usage: scripts/backfill_gap_days.sh [options]

Find gap days with knowledge_os.gap_summary, then run the modular pipeline for
each missing date. By default this renders locally only. Add --publish to commit,
push, and dispatch the website workflow through scripts/run_catalog_ingest.sh.

Options:
  --since YYYY-MM-DD       Start date; defaults to day after latest known run
  --until YYYY-MM-DD       End date, inclusive; defaults to today
  --db PATH                SQLite DB path; defaults to knowledge_os.db
  --digest-dir PATH        Digest artifact dir; defaults to knos-digest
  --dates LIST             Explicit dates to run, separated by comma, space, or newline
  --gap-types LIST         Missing date types; defaults to ingest,digest
                           Valid: ingest,digest,scoring,read,empty_digest
  --publish                Commit/push each digest and trigger website publish
  --dry-run                Print commands without running them
  --skip-historical-hn     Use current HN Firebase fetch instead of Algolia
  -h, --help               Show this help
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --since) SINCE="$2"; shift 2 ;;
        --until) UNTIL="$2"; shift 2 ;;
        --db) DB="$2"; shift 2 ;;
        --digest-dir) DIGEST_DIR="$2"; shift 2 ;;
        --dates) DATES="$2"; shift 2 ;;
        --gap-types) GAP_TYPES="$2"; shift 2 ;;
        --publish) PUBLISH=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --skip-historical-hn) HISTORICAL_HN=0; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [ -n "$DATES" ]; then
    dates="$(printf '%s\n' "$DATES" | tr ', ' '\n\n' | sed '/^$/d' | sort -u)"
else
    gap_args=(--db "$DB" --digest-dir "$DIGEST_DIR" --until "$UNTIL" --format dates --gap-types "$GAP_TYPES")
    if [ -n "$SINCE" ]; then
        gap_args+=(--since "$SINCE")
    fi

    dates="$("$PYTHON" -m knowledge_os.gap_summary "${gap_args[@]}")"
fi
if [ -z "$dates" ]; then
    echo "No gap days found for ${SINCE:-latest-known+1}..${UNTIL} (${GAP_TYPES})." >&2
    exit 0
fi

while IFS= read -r day; do
    [ -n "$day" ] || continue
    run_args=(--db "$DB" --date "$day" --overwrite)
    if [ "$HISTORICAL_HN" -eq 1 ]; then
        run_args+=(--historical-hn)
    fi

    if [ "$PUBLISH" -eq 1 ]; then
        command=(bash scripts/run_catalog_ingest.sh "${run_args[@]}")
    else
        command=(bash scripts/run_modular_digest.sh "${run_args[@]}")
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        printf '%q ' "${command[@]}"
        printf '\n'
    else
        echo "Backfilling ${day}" >&2
        "${command[@]}"
    fi
done <<< "$dates"
