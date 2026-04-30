#!/usr/bin/env python3
"""
Parse checked items from a digest .md file and sync read status to the DB.

Usage:
    venv/bin/python -m knowledge_os.sync_reading_log knos-digest/2026-02-24.md
"""
import json
import re
import sys
from .storage_interface import get_storage


def parse_read_items(md_text: str) -> list[dict]:
    """
    Parse checked inline items from digest markdown.

    Looks for lines like:
        - [x] Story Title
        - [x] 📰 Story Title
        - [x] 💬 Story Title
        - [x] 🔥 Story Title

    Notes are gathered from indented lines below until the next list item.

    Returns list of dicts: {'title': str, 'note': str, 'link': str}
    """
    results = []
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        # Match checked items: - [x] or - [X], optionally with emoji prefix
        m = re.match(r'^- \[x\]\s+(?:[^\w\s]\s*)*(.+?)\s*$', line, re.IGNORECASE)
        if m:
            title = m.group(1).strip()
            # Collect indented note lines below
            note_lines = []
            link = ""
            j = i + 1
            while j < len(lines) and not lines[j].startswith('- ['):
                content = lines[j]
                link_match = re.match(r'^\s+🔗\s*(\S+)\s*$', content)
                if link_match:
                    link = link_match.group(1).strip()
                    j += 1
                    continue
                # Skip metadata lines (score, link, comment summary, action prompt)
                if re.match(r'^\s+(↑|🔗|💬|→)\s*', content):
                    j += 1
                    continue
                # Strip "Notes: " prefix from first note line
                note_match = re.match(r'^\s+Notes:\s*(.*)', content)
                if note_match:
                    text = note_match.group(1).strip()
                    if text:
                        note_lines.append(text)
                elif content.strip():
                    note_lines.append(content.strip())
                j += 1
            note = "\n".join(note_lines).strip()
            results.append({'title': title, 'note': note, 'link': link})
            i = j
            continue
        i += 1
    return results


def _lookup_item_id(storage, item: dict):
    """Resolve a digest item to a DB row using the most specific identifier available."""
    link = item.get('link', '')
    if link:
        hn_match = re.search(r'news\.ycombinator\.com/item\?id=(\d+)', link)
        if hn_match:
            conn = storage._get_conn()
            c = conn.cursor()
            c.execute(
                'SELECT item_id, title FROM items WHERE source = ? AND external_id = ?',
                ('hackernews', hn_match.group(1))
            )
            row = c.fetchone()
            conn.close()
            if row:
                return row

        conn = storage._get_conn()
        c = conn.cursor()
        c.execute('SELECT item_id, title FROM items WHERE url = ?', (link,))
        row = c.fetchone()
        conn.close()
        if row:
            return row

    conn = storage._get_conn()
    c = conn.cursor()
    c.execute('SELECT item_id, title FROM items WHERE title = ?', (item['title'],))
    row = c.fetchone()
    conn.close()
    return row


def sync_to_db(read_items: list[dict], config_path: str = "config.json") -> list[dict]:
    """
    Look up each read item in the DB and insert feedback.
    Returns list of synced items with their item_ids.
    """
    with open(config_path) as f:
        config = json.load(f)

    storage_config = config['storage']
    storage = get_storage(
        backend=storage_config['backend'],
        **storage_config.get(storage_config['backend'], {})
    )

    user_id = storage.get_or_create_user(config['user']['identifier'])

    synced = []
    for item in read_items:
        row = _lookup_item_id(storage, item)

        if not row:
            print(f"  [skip] Not found in DB: {item['title']}")
            continue

        item_id = row['item_id']
        action = 'read_with_note' if item['note'] else 'read'
        metadata = {'note': item['note']} if item['note'] else None

        storage.insert_feedback(
            user_id=user_id,
            item_id=item_id,
            action=action,
            metadata=metadata
        )
        synced.append({'item_id': item_id, 'title': item['title'], 'action': action})
        print(f"  [synced] {action}: {item['title']}")

    return synced


def main():
    if len(sys.argv) < 2:
        print("Usage: sync_reading_log.py <digest.md>")
        sys.exit(1)

    md_path = sys.argv[1]
    with open(md_path) as f:
        md_text = f.read()

    read_items = parse_read_items(md_text)
    if not read_items:
        print("No checked items found.")
        return

    print(f"Found {len(read_items)} checked item(s):")
    synced = sync_to_db(read_items)
    print(f"\nSynced {len(synced)} item(s) to DB.")


if __name__ == "__main__":
    main()
