#!/bin/bash
# Query digest runs and selected digest items.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

PYTHON="${PYTHON:-$PROJECT_ROOT/venv/bin/python}"
DB="${DB:-knowledge_os.db}"

if [ "${1:-}" = "--digest-id" ]; then
    "$PYTHON" -m knowledge_os.query_pipeline --db "$DB" digest-items --digest-id "$2"
else
    "$PYTHON" -m knowledge_os.query_pipeline --db "$DB" digests --limit "${LIMIT:-10}" "$@"
fi
