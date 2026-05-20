#!/bin/bash
# Run the modular digest flow for one configured user.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

USER_ID="vb"
DB="knowledge_os.db"
OVERWRITE=false
SKIP_INGEST=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        --user) USER_ID="$2"; shift 2 ;;
        --db) DB="$2"; shift 2 ;;
        --overwrite) OVERWRITE=true; shift ;;
        --skip-ingest) SKIP_INGEST=true; shift ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

ARGS=(--db "$DB" --user "$USER_ID" --user-config "configs/users/${USER_ID}.json")
if $OVERWRITE; then
    ARGS+=(--overwrite)
fi
if $SKIP_INGEST; then
    ARGS+=(--skip-ingest)
fi

bash scripts/run_modular_digest.sh "${ARGS[@]}"
