#!/bin/bash
# Generate the canonical digest, refresh the website export, and prepare/send WhatsApp messages.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

PYTHON="${PYTHON:-$PROJECT_ROOT/venv/bin/python}"
DATE="$(date +%F)"
DB="knowledge_os.db"
SITE_DIR="${SITE_DIR:-/Users/vb/dev/projects/bvaibhav-info}"
RECIPIENTS="${RECIPIENTS:-$HOME/.config/knowledge-os/whatsapp-recipients.json}"
USERS="vb,kintu,mikey"
USER_ARGS=()
BASE_URL="https://www.bvaibhav.info/knos-digest"
SEND=false
SEND_COMMAND="${WHATSAPP_SEND_COMMAND:-}"
if [ -z "$SEND_COMMAND" ]; then
    SEND_COMMAND='node scripts/baileys_send.mjs --to {phone} --message {message}'
fi
SKIP_DIGEST=false
SKIP_INGEST=false
SKIP_SITE=false
SKIP_BUILD=false
LOCK_DIR=""

usage() {
    cat <<'USAGE'
Usage: scripts/deliver_whatsapp_digest.sh [options]

Options:
  --date YYYY-MM-DD        Digest date, defaults to today
  --db PATH                SQLite DB path, defaults to knowledge_os.db
  --site-dir PATH          bvaibhav-info checkout, defaults to SITE_DIR or /Users/vb/dev/projects/bvaibhav-info
  --recipients PATH        Local user->phone JSON, defaults to RECIPIENTS or ~/.config/knowledge-os/whatsapp-recipients.json
  --users LIST             Comma-separated users, defaults to vb,kintu,mikey
  --user ID                Deliver to one user; may be repeated
  --base-url URL           Website digest base URL
  --send                   Call the configured WhatsApp sender
  --send-command COMMAND   Sender argv prefix or template; defaults to WHATSAPP_SEND_COMMAND or Baileys
  --dry-run                Print messages without sending; this is the default
  --skip-digest            Do not run the digest pipeline
  --skip-ingest            Run the digest pipeline without ingestion
  --skip-site              Do not run website export/build
  --skip-build             Run website export but skip npm run build
  -h, --help               Show this help

Sender command:
  If COMMAND contains {phone} or {message}, those placeholders are replaced.
  Otherwise delivery appends: --to PHONE --message MESSAGE
  Default: node scripts/baileys_send.mjs --to {phone} --message {message}
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --date) DATE="$2"; shift 2 ;;
        --db) DB="$2"; shift 2 ;;
        --site-dir) SITE_DIR="$2"; shift 2 ;;
        --recipients) RECIPIENTS="$2"; shift 2 ;;
        --users) USERS="$2"; shift 2 ;;
        --user) USER_ARGS+=(--user "$2"); shift 2 ;;
        --base-url) BASE_URL="$2"; shift 2 ;;
        --send) SEND=true; shift ;;
        --send-command) SEND_COMMAND="$2"; shift 2 ;;
        --dry-run) SEND=false; shift ;;
        --skip-digest) SKIP_DIGEST=true; shift ;;
        --skip-ingest) SKIP_INGEST=true; shift ;;
        --skip-site) SKIP_SITE=true; shift ;;
        --skip-build) SKIP_BUILD=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
done

log_step() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >&2
}

acquire_send_lock() {
    local lock_root="${WHATSAPP_LOCK_ROOT:-$HOME/Library/Application Support/knowledge-os/cron}"
    local timeout="${WHATSAPP_LOCK_TIMEOUT_SECONDS:-900}"
    local waited=0
    mkdir -p "$lock_root"
    LOCK_DIR="$lock_root/whatsapp-delivery.lock"

    while ! mkdir "$LOCK_DIR" 2>/dev/null; do
        local lock_pid=""
        if [ -f "$LOCK_DIR/pid" ]; then
            lock_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
        fi
        if [ -n "$lock_pid" ] && ! kill -0 "$lock_pid" 2>/dev/null; then
            rm -f "$LOCK_DIR/pid"
            rmdir "$LOCK_DIR" 2>/dev/null || true
            continue
        fi
        if [ "$waited" -ge "$timeout" ]; then
            echo "Timed out waiting for WhatsApp delivery lock: $LOCK_DIR" >&2
            exit 1
        fi
        log_step "Waiting for WhatsApp delivery lock"
        sleep 5
        waited=$((waited + 5))
    done

    echo "$$" > "$LOCK_DIR/pid"
    trap 'rm -f "$LOCK_DIR/pid" 2>/dev/null || true; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT
}

if ! $SKIP_DIGEST; then
    log_step "Generating canonical persona digest"
    RUN_ARGS=(--db "$DB" --date "$DATE" --overwrite)
    if $SKIP_INGEST; then
        RUN_ARGS+=(--skip-ingest)
    fi
    bash scripts/run_modular_digest.sh "${RUN_ARGS[@]}"
else
    log_step "Skipping digest generation"
fi

DIGEST_PATH="knos-digest/${DATE}.md"
if [ ! -f "$DIGEST_PATH" ]; then
    echo "Digest not found: $DIGEST_PATH" >&2
    exit 1
fi

if ! $SKIP_SITE; then
    if [ ! -d "$SITE_DIR" ]; then
        echo "Website repo not found: $SITE_DIR" >&2
        echo "Pass --site-dir or --skip-site." >&2
        exit 1
    fi
    log_step "Refreshing website digest export"
    (
        cd "$SITE_DIR"
        npm run export-digest
        if ! $SKIP_BUILD; then
            npm run build
        fi
    )
else
    log_step "Skipping website export/build"
fi

DELIVERY_ARGS=(
    --date "$DATE"
    --digest "$DIGEST_PATH"
    --users-dir "configs/users"
    --recipients "$RECIPIENTS"
    --base-url "$BASE_URL"
)

if [ "${#USER_ARGS[@]}" -gt 0 ]; then
    DELIVERY_ARGS+=("${USER_ARGS[@]}")
else
    DELIVERY_ARGS+=(--users "$USERS")
fi

if $SEND; then
    acquire_send_lock
    DELIVERY_ARGS+=(--send)
    if [ -n "$SEND_COMMAND" ]; then
        DELIVERY_ARGS+=(--send-command "$SEND_COMMAND")
    fi
    log_step "Sending WhatsApp messages"
else
    DELIVERY_ARGS+=(--dry-run)
    log_step "Printing WhatsApp delivery dry run"
fi

"$PYTHON" -m knowledge_os.whatsapp_delivery "${DELIVERY_ARGS[@]}"
