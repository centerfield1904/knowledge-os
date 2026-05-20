#!/bin/bash
# Refresh the shared item catalog without generating or sending a digest.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

PYTHON="${PYTHON:-$PROJECT_ROOT/venv/bin/python}"
DB="knowledge_os.db"
SOURCES_CONFIG="config/sources.example.json"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --db) DB="$2"; shift 2 ;;
        --sources) SOURCES_CONFIG="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

"$PYTHON" -m knowledge_os.schema --db "$DB"

JAVA_HOME="${JAVA_HOME:-/usr/local/opt/openjdk}" \
PATH="${JAVA_HOME:-/usr/local/opt/openjdk}/bin:$PATH" \
sbt --error "runMain knowledgeos.Ingest --db $DB --sources $SOURCES_CONFIG"
