#!/bin/bash
# Query topic scoring state.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

PYTHON="${PYTHON:-$PROJECT_ROOT/venv/bin/python}"
DB="${DB:-knowledge_os.db}"

"$PYTHON" -m knowledge_os.query_pipeline --db "$DB" topics
echo
"$PYTHON" -m knowledge_os.query_pipeline --db "$DB" score-configs
echo
"$PYTHON" -m knowledge_os.query_pipeline --db "$DB" top-scores --limit "${LIMIT:-20}" "$@"
