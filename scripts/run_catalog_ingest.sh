#!/bin/bash
# Cron-safe wrapper for the canonical ingest + render pipeline.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

exec bash scripts/run_modular_digest.sh --overwrite "$@"
