#!/bin/bash
# Finalize, publish, and optionally send a curated weekly edition.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

PYTHON="${PYTHON:-venv/bin/python}"
WEBSITE_REPO="${KNOS_WEBSITE_REPO:-centerfield1904/bvaibhav-info}"
WEBSITE_WORKFLOW="${KNOS_WEBSITE_WORKFLOW:-update-digest.yml}"
WEEK=""
TO=""
SEND=0
FINALIZE=1
PUSH=1
TRIGGER_SITE=1
OVERWRITE=0

usage() {
    cat <<'EOF'
Usage: scripts/publish_weekly_summary.sh --week YYYY-Www [options]

Options:
  --week WEEK       ISO week to publish (required)
  --overwrite       Replace an existing finalized edition
  --skip-finalize   Publish an already-finalized knos-weekly/WEEK.md
  --skip-push       Do not commit or push the finalized edition
  --skip-site       Do not trigger the website export workflow
  --send            Send the weekly message through the local Baileys sender
  --to PHONE        E.164 WhatsApp destination; required with --send
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --week) WEEK="$2"; shift 2 ;;
        --overwrite) OVERWRITE=1; shift ;;
        --skip-finalize) FINALIZE=0; shift ;;
        --skip-push) PUSH=0; shift ;;
        --skip-site) TRIGGER_SITE=0; shift ;;
        --send) SEND=1; shift ;;
        --to) TO="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [ -z "$WEEK" ]; then
    echo "--week is required" >&2
    exit 2
fi
if [ "$SEND" -eq 1 ] && [ -z "$TO" ]; then
    echo "--to is required with --send" >&2
    exit 2
fi

SUMMARY_PATH="knos-weekly/${WEEK}.md"
if [ "$FINALIZE" -eq 1 ]; then
    finalize_args=(finalize --week "$WEEK")
    if [ "$OVERWRITE" -eq 1 ]; then
        finalize_args+=(--overwrite)
    fi
    "$PYTHON" -m knowledge_os.weekly_summary "${finalize_args[@]}"
fi
if [ ! -f "$SUMMARY_PATH" ]; then
    echo "Final weekly summary not found: $SUMMARY_PATH" >&2
    exit 1
fi

if [ "$PUSH" -eq 1 ]; then
    git add "$SUMMARY_PATH"
    if ! git diff --cached --quiet -- "$SUMMARY_PATH"; then
        git commit -m "weekly: ${WEEK}"
        git push origin HEAD
    else
        echo "No weekly summary changes to push: $SUMMARY_PATH" >&2
    fi
fi

if [ "$TRIGGER_SITE" -eq 1 ]; then
    gh workflow run "$WEBSITE_WORKFLOW" --repo "$WEBSITE_REPO"
fi

"$PYTHON" -m knowledge_os.weekly_summary whatsapp --week "$WEEK"

if [ "$SEND" -eq 1 ]; then
    MESSAGE="$("$PYTHON" - "$WEEK" <<'PY'
import sys
from knowledge_os.weekly_summary import weekly_whatsapp_summary
print(weekly_whatsapp_summary(sys.argv[1])["message"])
PY
)"
    node scripts/baileys_send.mjs --to "$TO" --message "$MESSAGE"
fi
