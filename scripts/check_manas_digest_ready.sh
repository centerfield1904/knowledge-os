#!/bin/bash
# Verify the daily ingest has produced and published today's website digest.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

DATE="$(date +%F)"
USER_ID="manas"
DATA_URL="${KNOS_DIGEST_DATA_URL:-https://www.bvaibhav.info/data/knos-digest.json}"
STATE_DIR="${KNOS_CRON_STATE_DIR:-$HOME/Library/Application Support/knowledge-os/cron}"
RECIPIENTS="${RECIPIENTS:-$HOME/.config/knowledge-os/whatsapp-recipients.json}"
PYTHON="${PYTHON:-$PROJECT_ROOT/venv/bin/python}"
ALERT_VB=false
ALERT_ONCE=true

usage() {
    cat <<'USAGE'
Usage: scripts/check_manas_digest_ready.sh [options]

Options:
  --user ID              Optional delivery context for logs, defaults to manas
  --date YYYY-MM-DD       Digest date, defaults to today
  --data-url URL          Published website JSON, defaults to bvaibhav.info data URL
  --state-dir PATH        Cron state dir, defaults to ~/Library/Application Support/knowledge-os/cron
  --recipients PATH       WhatsApp recipients JSON, defaults to ~/.config/knowledge-os/whatsapp-recipients.json
  --alert-vb              Send a WhatsApp alert to vb if daily publish readiness fails
  --alert-repeat          Send even if an alert marker already exists for the date
  -h, --help              Show this help
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --user) USER_ID="$2"; shift 2 ;;
        --date) DATE="$2"; shift 2 ;;
        --data-url) DATA_URL="$2"; shift 2 ;;
        --state-dir) STATE_DIR="$2"; shift 2 ;;
        --recipients) RECIPIENTS="$2"; shift 2 ;;
        --alert-vb) ALERT_VB=true; shift ;;
        --alert-repeat) ALERT_ONCE=false; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
done

DIGEST_PATH="knos-digest/${DATE}.md"
MARKER_PATH="$STATE_DIR/ingest-${DATE}.env"
ALERT_MARKER="$STATE_DIR/daily-publish-readiness-alert-${DATE}.sent"
FAILURES=()

add_failure() {
    FAILURES+=("$1")
}

if [ ! -s "$DIGEST_PATH" ]; then
    add_failure "Missing digest artifact: $DIGEST_PATH"
fi

if [ ! -s "$MARKER_PATH" ]; then
    add_failure "Morning ingest success marker missing: $MARKER_PATH"
elif ! grep -q '^website_workflow_status=triggered$' "$MARKER_PATH"; then
    add_failure "Website GitHub Action was not triggered successfully: $MARKER_PATH"
fi

if ! git cat-file -e "HEAD:${DIGEST_PATH}" 2>/dev/null; then
    add_failure "Digest artifact is not present in the current git HEAD: $DIGEST_PATH"
fi

published_json="$(mktemp "${TMPDIR:-/tmp}/knos-digest-ready.XXXXXX.json")"
cleanup() {
    rm -f "$published_json"
}
trap cleanup EXIT

if ! curl --fail --location --silent --show-error --max-time 45 "$DATA_URL" -o "$published_json"; then
    add_failure "Could not fetch published website data: $DATA_URL"
elif ! "$PYTHON" - "$published_json" "$DATE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
target_date = sys.argv[2]
data = json.loads(path.read_text())
digests = data.get("digests", [])
match = next((item for item in digests if item.get("date") == target_date), None)
if not match:
    raise SystemExit(f"{target_date} is not present in published digests")
stories = match.get("stories", [])
if not isinstance(stories, list) or not stories:
    raise SystemExit(f"{target_date} is present but has no published stories")
PY
then
    add_failure "Published website data is not ready for ${DATE}: $DATA_URL"
fi

send_alert() {
    mkdir -p "$STATE_DIR"
    if $ALERT_ONCE && [ -e "$ALERT_MARKER" ]; then
        echo "Daily publish readiness alert already sent for ${DATE}: $ALERT_MARKER" >&2
        return
    fi

    vb_phone="$("$PYTHON" - "$RECIPIENTS" <<'PY'
import json
import sys

with open(sys.argv[1]) as f:
    recipients = json.load(f)
phone = recipients.get("vb")
if not phone:
    raise SystemExit("No vb phone configured")
print(phone)
PY
)"

    message=$(
        printf 'Knowledge OS alert: daily digest is not published by 10:30 IST for %s.\n\n' "$DATE"
        printf 'The morning ingest/publish flow needs attention before external digest links go out.\n\n'
        printf 'Failures:\n'
        for failure in "${FAILURES[@]}"; do
            printf '%s\n' "- $failure"
        done
        printf '\nCheck logs:\n'
        printf '%s\n' '- /Users/vb/Library/Logs/knowledge-os-ingest.log'
        printf '%s\n' '- /Users/vb/Library/Logs/knowledge-os-delivery.log'
    )

    node scripts/baileys_send.mjs --to "$vb_phone" --message "$message"
    date '+%Y-%m-%dT%H:%M:%S%z' > "$ALERT_MARKER"
}

if [ "${#FAILURES[@]}" -gt 0 ]; then
    printf 'Daily digest publish readiness failed for %s' "$DATE" >&2
    if [ -n "$USER_ID" ]; then
        printf ' before %s delivery' "$USER_ID" >&2
    fi
    printf ':\n' >&2
    for failure in "${FAILURES[@]}"; do
        printf '%s\n' "- $failure" >&2
    done
    if $ALERT_VB; then
        send_alert
    fi
    exit 1
fi

echo "Daily digest published and ready for ${DATE}: ${DATA_URL}" >&2
