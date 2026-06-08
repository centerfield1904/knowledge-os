#!/bin/bash
# Cron-safe wrapper for the canonical ingest + render pipeline, then push the digest artifact.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

DATE="$(date +%F)"
STATE_DIR="${KNOS_CRON_STATE_DIR:-$HOME/Library/Application Support/knowledge-os/cron}"
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
    if [ "${args[$i]}" = "--date" ] && [ $((i + 1)) -lt ${#args[@]} ]; then
        DATE="${args[$((i + 1))]}"
    fi
done

write_success_marker() {
    mkdir -p "$STATE_DIR"
    {
        echo "date=$DATE"
        echo "digest_path=$latest_digest"
        echo "git_commit=$(git rev-parse HEAD)"
        echo "website_publish_source=github_actions_schedule"
        echo "completed_at=$(date '+%Y-%m-%dT%H:%M:%S%z')"
    } > "$STATE_DIR/ingest-${DATE}.env"
}

bash scripts/run_modular_digest.sh --overwrite "$@"

latest_digest="knos-digest/${DATE}.md"
if [ ! -f "$latest_digest" ]; then
    echo "Digest markdown not found: $latest_digest" >&2
    exit 1
fi

git add "$latest_digest"
if git diff --cached --quiet -- "$latest_digest"; then
    echo "No digest changes to push: $latest_digest" >&2
    write_success_marker
    exit 0
fi

digest_date="$(basename "$latest_digest" .md)"
git commit -m "digest: ${digest_date}"
git push origin HEAD
write_success_marker
