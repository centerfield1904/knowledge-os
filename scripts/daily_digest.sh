#!/bin/bash
# Simple wrapper that generates digest and outputs it
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

# Run digest generation (v2 with new storage)
bash scripts/run_digest_v2.sh 2>/dev/null

# Output is already printed by run_digest_v2.sh
