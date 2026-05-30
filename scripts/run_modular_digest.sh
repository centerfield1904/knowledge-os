#!/bin/bash
# Modular persona digest flow: ingest, materialize personas, score, render one canonical digest.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

PYTHON="${PYTHON:-$PROJECT_ROOT/venv/bin/python}"
DB="knowledge_os.db"
SOURCES_CONFIG="config/sources.example.json"
SCORING_CONFIG="config/topic_scoring.example.json"
PERSONA_CATALOG="personas/catalog.json"
USERS_DIR="configs/users"
OUTPUT=""
DATE="$(date +%F)"
OVERWRITE=false
SKIP_INGEST=false
HISTORICAL_HN=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        --db) DB="$2"; shift 2 ;;
        --sources) SOURCES_CONFIG="$2"; shift 2 ;;
        --scoring) SCORING_CONFIG="$2"; shift 2 ;;
        --persona-catalog) PERSONA_CATALOG="$2"; shift 2 ;;
        --users-dir) USERS_DIR="$2"; shift 2 ;;
        --output) OUTPUT="$2"; shift 2 ;;
        --date) DATE="$2"; shift 2 ;;
        --overwrite) OVERWRITE=true; shift ;;
        --skip-ingest) SKIP_INGEST=true; shift ;;
        --historical-hn) HISTORICAL_HN=true; shift ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

log_step() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >&2
}

run_sbt() {
    JAVA_HOME="${JAVA_HOME:-/usr/local/opt/openjdk}" \
    PATH="${JAVA_HOME:-/usr/local/opt/openjdk}/bin:$PATH" \
    sbt --error "$1"
}

log_step "Initializing schema"
"$PYTHON" -m knowledge_os.schema --db "$DB"

if $SKIP_INGEST; then
    log_step "Skipping catalog ingestion"
else
    log_step "Running catalog ingestion"
    INGEST_ARGS="runMain knowledgeos.Ingest --db $DB --sources $SOURCES_CONFIG --date $DATE"
    if $HISTORICAL_HN; then
        INGEST_ARGS="$INGEST_ARGS --historical-hn"
    fi
    run_sbt "$INGEST_ARGS"
fi

log_step "Materializing persona catalog and user subscriptions"
"$PYTHON" -m knowledge_os.personas --db "$DB" --catalog "$PERSONA_CATALOG" --users-dir "$USERS_DIR"

log_step "Running topic scoring"
"$PYTHON" -m knowledge_os.topic_scoring --db "$DB" --config "$SCORING_CONFIG"

log_step "Rendering canonical persona digest"
RENDER_ARGS=(render --db "$DB" --catalog "$PERSONA_CATALOG" --date "$DATE")
if [ -n "$OUTPUT" ]; then
    RENDER_ARGS+=(--output "$OUTPUT")
fi
if $OVERWRITE; then
    RENDER_ARGS+=(--overwrite)
fi
DIGEST_PATH=$("$PYTHON" -m knowledge_os.persona_digest "${RENDER_ARGS[@]}")

log_step "Digest rendered to ${DIGEST_PATH}"
