#!/bin/bash
# Query users and topic subscriptions.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

PYTHON="${PYTHON:-$PROJECT_ROOT/venv/bin/python}"
DB="${DB:-knowledge_os.db}"

"$PYTHON" -m knowledge_os.query_pipeline --db "$DB" users
echo
"$PYTHON" -m knowledge_os.query_pipeline --db "$DB" subscriptions "$@"
