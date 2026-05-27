#!/bin/bash
# Query feedback and engagement events.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

PYTHON="${PYTHON:-$PROJECT_ROOT/venv/bin/python}"
DB="${DB:-knowledge_os.db}"
QUERY_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db)
      DB="$2"
      shift 2
      ;;
    --db=*)
      DB="${1#*=}"
      shift
      ;;
    --)
      shift
      QUERY_ARGS+=("$@")
      break
      ;;
    *)
      QUERY_ARGS+=("$1")
      shift
      ;;
  esac
done

"$PYTHON" -m knowledge_os.query_pipeline --db "$DB" feedback --limit "${LIMIT:-25}" "${QUERY_ARGS[@]}"
