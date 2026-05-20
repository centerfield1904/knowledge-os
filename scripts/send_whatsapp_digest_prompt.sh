#!/bin/bash
# Print a WhatsApp delivery prompt for an already-rendered digest.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

USER_ID=""
DATE="$(date +%F)"
REMOTE="origin"
BRANCH="$(git branch --show-current)"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --user) USER_ID="$2"; shift 2 ;;
        --date) DATE="$2"; shift 2 ;;
        --remote) REMOTE="$2"; shift 2 ;;
        --branch) BRANCH="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$USER_ID" ]; then
    echo "--user is required" >&2
    exit 1
fi

path="knos-digest/${USER_ID}/${DATE}.md"
if [ ! -f "$path" ]; then
    echo "Digest not found: $path" >&2
    exit 1
fi

item_count="$(grep -c '^- \\[ \\]' "$path" || true)"
if [ "$item_count" -eq 0 ]; then
    echo "Digest has no selected items: $path" >&2
    exit 2
fi

repo="$(git remote get-url "$REMOTE" | sed -E 's#git@github.com:#https://github.com/#; s#\.git$##')"
url="${repo}/blob/${BRANCH}/${path}"

case "$USER_ID" in
    kintu)
        message="Made you a small UX/design digest for today:
${url}

Did any of these links feel worth opening?"
        ;;
    mikey)
        message="I made you a small AI/LLM digest:
${url}

Was this too broad, too technical, or roughly right?"
        ;;
    *)
        message="Made you a small digest:
${url}

Did any of these links feel worth opening?"
        ;;
esac

printf 'digest_path: %s\n' "$path"
printf 'github_url: %s\n\n' "$url"
printf '%s\n' "$message"
