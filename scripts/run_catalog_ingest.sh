#!/bin/bash
# Cron-safe wrapper for the canonical ingest + render pipeline, then publish the digest artifact.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

DATE="$(date +%F)"
STATE_DIR="${KNOS_CRON_STATE_DIR:-$HOME/Library/Application Support/knowledge-os/cron}"
WEBSITE_REPO="${KNOS_WEBSITE_REPO:-centerfield1904/bvaibhav-info}"
WEBSITE_WORKFLOW="${KNOS_WEBSITE_WORKFLOW:-update-digest.yml}"
WEBSITE_WORKFLOW_STATUS="not_triggered"
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
        echo "website_repo=$WEBSITE_REPO"
        echo "website_workflow=$WEBSITE_WORKFLOW"
        echo "website_workflow_status=$WEBSITE_WORKFLOW_STATUS"
        echo "completed_at=$(date '+%Y-%m-%dT%H:%M:%S%z')"
    } > "$STATE_DIR/ingest-${DATE}.env"
}

trigger_website_workflow() {
    if ! command -v gh >/dev/null 2>&1; then
        WEBSITE_WORKFLOW_STATUS="gh_missing"
        echo "GitHub CLI not found; cannot trigger ${WEBSITE_REPO}/${WEBSITE_WORKFLOW}" >&2
        return 1
    fi
    if ! gh auth status --hostname github.com >/dev/null 2>&1; then
        WEBSITE_WORKFLOW_STATUS="gh_not_authenticated"
        echo "GitHub CLI is not authenticated; run gh auth login before relying on cron dispatch" >&2
        return 1
    fi
    echo "Triggering website digest workflow: ${WEBSITE_REPO}/${WEBSITE_WORKFLOW}" >&2
    gh workflow run "$WEBSITE_WORKFLOW" --repo "$WEBSITE_REPO"
    WEBSITE_WORKFLOW_STATUS="triggered"
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
    trigger_website_workflow
    write_success_marker
    exit 0
fi

digest_date="$(basename "$latest_digest" .md)"
git commit -m "digest: ${digest_date}"
git push origin HEAD
trigger_website_workflow
write_success_marker
