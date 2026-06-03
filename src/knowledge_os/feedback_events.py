#!/usr/bin/env python3
"""Common feedback event ingestion."""
import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from typing import Dict, Iterable, Optional

from .schema import init_target_schema

def _log(message: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] [feedback] {message}", file=sys.stderr)


def _json(value: Optional[Dict]) -> Optional[str]:
    return json.dumps(value, ensure_ascii=True, sort_keys=True) if value else None


def parse_read_items(md_text: str) -> list[dict]:
    """Parse checked markdown digest items into title/note/link dictionaries."""
    results = []
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.match(r"^- \[x\]\s+(?:[^\w\s]\s*)*(.+?)\s*$", line, re.IGNORECASE)
        if not match:
            i += 1
            continue

        title = match.group(1).strip()
        note_lines = []
        link = ""
        j = i + 1
        while j < len(lines) and not lines[j].startswith("- ["):
            content = lines[j]
            link_match = re.match(r"^\s+🔗\s*(\S+)\s*$", content)
            if link_match:
                link = link_match.group(1).strip()
                j += 1
                continue
            if re.match(r"^\s+(↑|🔗|💬|→)\s*", content):
                j += 1
                continue
            note_match = re.match(r"^\s+Notes:\s*(.*)", content)
            if note_match:
                text = note_match.group(1).strip()
                if text:
                    note_lines.append(text)
            elif content.strip():
                note_lines.append(content.strip())
            j += 1

        results.append({"title": title, "note": "\n".join(note_lines).strip(), "link": link})
        i = j
    return results


def _get_user_id(conn: sqlite3.Connection, identifier: str, timezone: Optional[str] = None) -> int:
    conn.execute(
        """
        INSERT INTO users (identifier, timezone)
        VALUES (?, ?)
        ON CONFLICT(identifier) DO UPDATE SET
            timezone = COALESCE(excluded.timezone, users.timezone)
        """,
        (identifier, timezone),
    )
    row = conn.execute("SELECT user_id FROM users WHERE identifier = ?", (identifier,)).fetchone()
    return int(row["user_id"])


def _find_item(conn: sqlite3.Connection, title: str, link: str = "") -> Optional[sqlite3.Row]:
    if link:
        hn_match = re.search(r"news\.ycombinator\.com/item\?id=(\d+)", link)
        if hn_match:
            row = conn.execute(
                "SELECT * FROM items WHERE source = ? AND external_id = ?",
                ("hackernews", hn_match.group(1)),
            ).fetchone()
            if row:
                return row
        row = conn.execute("SELECT * FROM items WHERE url = ?", (link,)).fetchone()
        if row:
            return row
    return conn.execute("SELECT * FROM items WHERE title = ?", (title,)).fetchone()


def insert_feedback_event(
    db_path: str,
    user_identifier: str,
    item_id: int,
    action: str,
    digest_id: Optional[int] = None,
    metadata: Optional[Dict] = None,
) -> int:
    init_target_schema(db_path)
    _log(f"Inserting action={action} user={user_identifier} item_id={item_id} digest_id={digest_id}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        user_id = _get_user_id(conn, user_identifier)
        cur = conn.execute(
            """
            INSERT INTO feedback (user_id, item_id, digest_id, action, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, item_id, digest_id, action, _json(metadata)),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def sync_markdown_feedback(
    db_path: str,
    user_identifier: str,
    markdown_path: str,
    digest_id: Optional[int] = None,
) -> int:
    """Parse checked digest items from markdown and insert read feedback."""
    init_target_schema(db_path)
    _log(f"Parsing markdown feedback from {markdown_path}")
    with open(markdown_path) as f:
        read_items = parse_read_items(f.read())
    _log(f"Found {len(read_items)} checked item(s)")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        user_id = _get_user_id(conn, user_identifier)
        written = 0
        for item in read_items:
            row = _find_item(conn, item["title"], item.get("link", ""))
            if not row:
                _log(f"Skipping unresolved item: {item['title']}")
                continue
            action = "read_with_note" if item.get("note") else "read"
            metadata = {"note": item.get("note", "")} if item.get("note") else None
            conn.execute(
                """
                INSERT INTO feedback (user_id, item_id, digest_id, action, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, row["item_id"], digest_id, action, _json(metadata)),
            )
            written += 1
        conn.commit()
        _log(f"Inserted {written} feedback event(s)")
        return written
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Insert common user/item feedback events.")
    parser.add_argument("--db", default="knowledge_os.db")
    parser.add_argument("--user", required=True)
    parser.add_argument("--source", help="Digest markdown file to parse")
    parser.add_argument("--digest-id", type=int)
    parser.add_argument("--item-id", type=int)
    parser.add_argument("--action")
    parser.add_argument("--metadata-json")
    args = parser.parse_args()

    if args.source:
        count = sync_markdown_feedback(args.db, args.user, args.source, digest_id=args.digest_id)
        print(f"Inserted {count} feedback event(s)")
        return

    if not args.item_id or not args.action:
        parser.error("Either --source or both --item-id and --action are required")
    metadata = json.loads(args.metadata_json) if args.metadata_json else None
    feedback_id = insert_feedback_event(
        args.db,
        args.user,
        args.item_id,
        args.action,
        digest_id=args.digest_id,
        metadata=metadata,
    )
    print(f"Inserted feedback event {feedback_id}")


if __name__ == "__main__":
    main()
