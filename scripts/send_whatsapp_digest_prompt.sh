#!/bin/bash
# Print a WhatsApp delivery prompt linking to the persona-filtered website view.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

PYTHON="${PYTHON:-$PROJECT_ROOT/venv/bin/python}"
USER_ID=""
DATE="$(date +%F)"
BASE_URL="https://www.bvaibhav.info/knos-digest"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --user) USER_ID="$2"; shift 2 ;;
        --date) DATE="$2"; shift 2 ;;
        --base-url) BASE_URL="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$USER_ID" ]; then
    echo "--user is required" >&2
    exit 1
fi

user_config="configs/users/${USER_ID}.json"
if [ ! -f "$user_config" ]; then
    echo "User config not found: $user_config" >&2
    exit 1
fi

digest_path="knos-digest/${DATE}.md"
if [ ! -f "$digest_path" ]; then
    echo "Digest not found: $digest_path" >&2
    exit 1
fi

"$PYTHON" -m knowledge_os.persona_digest whatsapp \
    --user-config "$user_config" \
    --digest "$digest_path" \
    --base-url "$BASE_URL"
