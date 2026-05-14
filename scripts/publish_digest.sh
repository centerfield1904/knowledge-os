#!/bin/bash
# Commit/push one rendered digest and print its GitHub URL.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

USER_ID=""
DATE="$(date +%Y-%m-%d)"
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

git add "$path"
git diff --cached --quiet || git commit -m "digest(${USER_ID}): ${DATE}"
git push "$REMOTE" "$BRANCH"

repo="$(git remote get-url "$REMOTE" | sed -E 's#git@github.com:#https://github.com/#; s#\.git$##')"
echo "${repo}/blob/${BRANCH}/${path}"
