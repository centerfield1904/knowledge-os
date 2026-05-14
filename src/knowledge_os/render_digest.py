#!/usr/bin/env python3
"""Render a modular digest from digests/digest_items."""
import argparse
import sqlite3
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from .schema import init_target_schema


def _log(message: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] [render_digest] {message}", file=sys.stderr)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _latest_digest(conn: sqlite3.Connection, user: Optional[str], digest_id: Optional[int]) -> sqlite3.Row:
    clauses = []
    params = []
    if digest_id is not None:
        clauses.append("d.digest_id = ?")
        params.append(digest_id)
    if user:
        clauses.append("u.identifier = ?")
        params.append(user)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    row = conn.execute(
        f"""
        SELECT d.digest_id, d.user_id, d.generated_at, d.status, u.identifier
        FROM digests d
        JOIN users u ON u.user_id = d.user_id
        {where}
        ORDER BY d.digest_id DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
    if not row:
        target = f"digest_id={digest_id}" if digest_id is not None else "latest digest"
        if user:
            target += f" for user={user}"
        raise ValueError(f"No {target} found")
    return row


def load_digest_items(db_path: str, user: Optional[str] = None, digest_id: Optional[int] = None):
    """Load one digest header and its ranked item rows."""
    init_target_schema(db_path)
    _log(f"Loading digest items from {db_path}")
    with _connect(db_path) as conn:
        digest = _latest_digest(conn, user, digest_id)
        _log(f"Rendering digest_id={digest['digest_id']} user={digest['identifier']}")
        rows = conn.execute(
            """
            SELECT
                di.rank,
                di.topic_score,
                di.selection_reason_json,
                i.item_id,
                i.title,
                i.url,
                i.source,
                i.external_id,
                COALESCE(i.author_name, '') AS author_name,
                COALESCE(i.score, 0) AS item_score,
                COALESCE(i.comment_count, 0) AS comment_count,
                COALESCE(i.published_at, i.fetched_at) AS published_at,
                COALESCE(t.name, 'Selected') AS topic_name
            FROM digest_items di
            JOIN items i ON i.item_id = di.item_id
            LEFT JOIN topics t ON t.topic_id = di.topic_id
            WHERE di.digest_id = ?
            ORDER BY di.rank ASC
            """,
            (digest["digest_id"],),
        ).fetchall()
    return digest, rows


def _digest_date(generated_at: Optional[str]) -> str:
    if generated_at:
        try:
            return datetime.fromisoformat(generated_at.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return generated_at[:10]
    return datetime.now().date().isoformat()


def render_digest_text(digest: sqlite3.Row, rows: Iterable[sqlite3.Row]) -> str:
    """Render a markdown digest from ranked DB rows."""
    rows = list(rows)
    date = _digest_date(digest["generated_at"])
    if not rows:
        return (
            f"🦅 *Knowledge Digest* - {date}\n"
            f"_digest_id: {digest['digest_id']}_\n\n"
            "_No selected items for this run._\n"
        )

    by_topic = OrderedDict()
    for row in rows:
        by_topic.setdefault(row["topic_name"], []).append(row)

    lines = [
        f"🦅 *Knowledge Digest* - {date}",
        f"_{len(rows)} selected item{'s' if len(rows) != 1 else ''} · digest_id: {digest['digest_id']}_",
        "",
    ]

    for topic, topic_rows in by_topic.items():
        lines.append(f"*{topic}*")
        for row in topic_rows:
            source_icon = "📰 " if row["source"] == "substack" else ""
            lines.append(f"- [ ] {source_icon}{row['title']}")
            meta = [f"↑{row['item_score']}", f"topic: {row['topic_score']:.3f}", f"by {row['author_name']}"]
            lines.append(f"  {' | '.join(meta)}")
            lines.append(f"  🔗 {row['url']}")
            if row["source"] == "hackernews" and row["external_id"]:
                lines.append(f"  → HN: https://news.ycombinator.com/item?id={row['external_id']}")
            lines.append("  Notes: ")
        lines.append("")

    return "\n".join(lines)


def render_digest_file(
    db_path: str,
    user: Optional[str] = None,
    digest_id: Optional[int] = None,
    output: Optional[str] = None,
    overwrite: bool = False,
) -> Path:
    """Render one digest to a markdown file and return its path."""
    digest, rows = load_digest_items(db_path, user=user, digest_id=digest_id)
    text = render_digest_text(digest, rows)
    if output:
        path = Path(output)
    else:
        user_dir = digest["identifier"] if digest["identifier"] else "unknown"
        path = Path("knos-digest") / user_dir / f"{_digest_date(digest['generated_at'])}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists; pass --overwrite to replace it")
    path.write_text(text + "\n")
    _log(f"Wrote digest markdown to {path}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render markdown from a modular digest run.")
    parser.add_argument("--db", default="knowledge_os.db")
    parser.add_argument("--user")
    parser.add_argument("--digest-id", type=int)
    parser.add_argument("--output")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    path = render_digest_file(
        db_path=args.db,
        user=args.user,
        digest_id=args.digest_id,
        output=args.output,
        overwrite=args.overwrite,
    )
    print(path)


if __name__ == "__main__":
    main()
