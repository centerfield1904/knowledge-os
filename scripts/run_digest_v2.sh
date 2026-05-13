#!/bin/bash
# Main orchestration script for HN digest (v2 with new storage)

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

PYTHON="$PROJECT_ROOT/venv/bin/python"
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
FETCH_ONLY=false
PUSH=false
RERUN=false
for arg in "$@"; do
    if [ "$arg" = "--fetch-only" ]; then FETCH_ONLY=true; fi
    if [ "$arg" = "--push" ]; then PUSH=true; fi
    if [ "$arg" = "--rerun" ]; then RERUN=true; fi
done

if $RERUN; then
    DATE=$(date +%Y-%m-%d)
    log_step "🔄 Rerun mode — cleaning up today's archive and delivered feedback..."
    rm -f "archive/${DATE}_digest.txt" "archive/${DATE}_stories.json" "knos-digest/${DATE}.md"
    $PYTHON -c "
import sqlite3, json
db = sqlite3.connect('hn_digest_v2.db')
row = db.execute('SELECT item_ids FROM digests ORDER BY sent_at DESC LIMIT 1').fetchone()
if row:
    ids = json.loads(row[0])
    if ids:
        db.execute('DELETE FROM feedback WHERE action=\"delivered\" AND item_id IN (%s)' % ','.join('?'*len(ids)), ids)
        db.commit()
        print(f'Removed delivered feedback for {len(ids)} item(s)', flush=True)
db.close()
" >&2
    log_step "✓ Cleanup done"
fi

# Logging with timestamps
log_step() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >&2
}

START_TIME=$(date +%s)

if $FETCH_ONLY; then
    log_step "📥 Fetch-only mode — storing stories, skipping digest"
else
    log_step "🦅 Starting digest generation"
fi

log_step "📡 Fetching HN stories..."
FETCH_START=$(date +%s)
$PYTHON -m knowledge_os.fetch_stories > stories_raw.json
FETCH_END=$(date +%s)
FETCH_DURATION=$((FETCH_END - FETCH_START))
log_step "✓ HN stories fetched in ${FETCH_DURATION}s"

# Fetch Substack if enabled in config
log_step "📰 Fetching Substack feeds..."
SUBSTACK_START=$(date +%s)
$PYTHON -m knowledge_os.fetch_substack > substack_raw.json 2>/dev/null || echo "[]" > substack_raw.json
SUBSTACK_END=$(date +%s)
SUBSTACK_DURATION=$((SUBSTACK_END - SUBSTACK_START))
log_step "✓ Substack fetched in ${SUBSTACK_DURATION}s"

# Merge HN + Substack stories into a single JSON array
log_step "🔄 Merging stories..."
MERGE_START=$(date +%s)
$PYTHON -c "
import json
hn = json.load(open('stories_raw.json'))
ss = json.load(open('substack_raw.json'))
json.dump(hn + ss, open('all_stories.json', 'w'))
"
MERGE_END=$(date +%s)
MERGE_DURATION=$((MERGE_END - MERGE_START))
log_step "✓ Stories merged in ${MERGE_DURATION}s"

PROCESS_DURATION=0
ARCHIVE_DURATION=0

if ! $FETCH_ONLY; then
    log_step "🎯 Processing and generating digest..."
    PROCESS_START=$(date +%s)
    $PYTHON -m knowledge_os.process_digest all_stories.json > digest.txt
    PROCESS_END=$(date +%s)
    PROCESS_DURATION=$((PROCESS_END - PROCESS_START))
    log_step "✓ Digest generated in ${PROCESS_DURATION}s"

    log_step "📱 Digest ready!"
    cat digest.txt

    log_step "💾 Archiving results..."
    ARCHIVE_START=$(date +%s)
    DATE=$(date +%Y-%m-%d)
    mkdir -p archive
    mkdir -p knos-digest

    STORIES_ARCHIVE="archive/${DATE}_stories.json"
    DIGEST_ARCHIVE="archive/${DATE}_digest.txt"
    DIGEST_MD="knos-digest/${DATE}.md"

    if [ -e "$DIGEST_ARCHIVE" ] || [ -e "$DIGEST_MD" ]; then
        log_step "✗ Digest output already exists for ${DATE}."
        log_step "  Existing files:"
        [ -e "$DIGEST_ARCHIVE" ] && log_step "  - $DIGEST_ARCHIVE"
        [ -e "$DIGEST_MD" ] && log_step "  - $DIGEST_MD"
        log_step "  Delete or back up the existing file(s) first, then rerun."
        exit 1
    fi

    if [ -e "$STORIES_ARCHIVE" ]; then
        log_step "✗ Story archive already exists for ${DATE}: $STORIES_ARCHIVE"
        log_step "  Delete or back up the existing file first, then rerun."
        exit 1
    fi

    cp stories_raw.json "$STORIES_ARCHIVE"
    cp digest.txt "$DIGEST_ARCHIVE"
    cp digest.txt "$DIGEST_MD"

    ARCHIVE_END=$(date +%s)
    ARCHIVE_DURATION=$((ARCHIVE_END - ARCHIVE_START))
    log_step "✓ Archived in ${ARCHIVE_DURATION}s"

    if $PUSH; then
        log_step "📤 Pushing digest to GitHub..."
        git add "knos-digest/${DATE}.md"
        git diff --cached --quiet || git commit -m "digest: ${DATE}"
        git push origin HEAD
        log_step "✓ Digest pushed"
    else
        log_step "ℹ️  Skipping push (pass --push to enable)"
    fi
fi

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))

log_step "✅ Done! Total time: ${TOTAL_DURATION}s"
log_step "   Breakdown: Fetch=${FETCH_DURATION}s, Substack=${SUBSTACK_DURATION}s, Merge=${MERGE_DURATION}s, Process=${PROCESS_DURATION}s, Archive=${ARCHIVE_DURATION}s"
if ! $FETCH_ONLY; then
    log_step "   Digest saved to:"
    log_step "   - ${DIGEST_ARCHIVE}"
    log_step "   - ${DIGEST_MD}"
fi
