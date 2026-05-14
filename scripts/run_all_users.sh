#!/bin/bash
# Run shared ingestion/scoring once, then generate one digest per configured user.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

PYTHON="${PYTHON:-$PROJECT_ROOT/venv/bin/python}"
DB="knowledge_os.db"
SOURCES_CONFIG="config/sources.example.json"
SCORING_CONFIG="config/topic_scoring.example.json"
PERSONA_CATALOG="personas/catalog.json"
MAX_ITEMS="20"
OVERWRITE=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        --db) DB="$2"; shift 2 ;;
        --sources) SOURCES_CONFIG="$2"; shift 2 ;;
        --scoring) SCORING_CONFIG="$2"; shift 2 ;;
        --persona-catalog) PERSONA_CATALOG="$2"; shift 2 ;;
        --max-items) MAX_ITEMS="$2"; shift 2 ;;
        --overwrite) OVERWRITE=true; shift ;;
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

log_step "Running catalog ingestion"
run_sbt "runMain knowledgeos.Ingest --db $DB --sources $SOURCES_CONFIG"

for user_config in configs/users/*.json; do
    log_step "Materializing $(basename "$user_config" .json)"
    "$PYTHON" -m knowledge_os.personas --db "$DB" --catalog "$PERSONA_CATALOG" --user-config "$user_config"
done

log_step "Running topic scoring for all active global topics"
"$PYTHON" -m knowledge_os.topic_scoring --db "$DB" --config "$SCORING_CONFIG"

for user_config in configs/users/*.json; do
    user="$(basename "$user_config" .json)"
    log_step "Selecting and rendering ${user}"
    selection_output=$(run_sbt "runMain knowledgeos.GenerateDigest --db $DB --user $user --max-items $MAX_ITEMS")
    echo "$selection_output"
    digest_id=$(printf '%s\n' "$selection_output" | "$PYTHON" -c '
import json
import sys

for line in reversed(sys.stdin.read().splitlines()):
    line = line.strip()
    if line.startswith("{") and line.endswith("}"):
        print(json.loads(line)["digest_id"])
        break
else:
    raise SystemExit("Could not find digest JSON in GenerateDigest output")
')
    render_args=(--db "$DB" --user "$user" --digest-id "$digest_id")
    if $OVERWRITE; then
        render_args+=(--overwrite)
    fi
    "$PYTHON" -m knowledge_os.render_digest "${render_args[@]}"
done
