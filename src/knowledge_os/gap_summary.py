#!/usr/bin/env python3
"""Summarize missed Knowledge OS ingest, digest, scoring, and read days."""
import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

from .feedback_events import parse_read_items
from .persona_digest import parse_persona_markdown


DIGEST_FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
READ_ACTIONS = ("read", "read_with_note")
GAP_TYPES = {
    "ingest": "missing_ingest_days",
    "digest": "missing_digest_days",
    "scoring": "unscored_ingest_days",
    "read": "unread_digest_days",
    "empty_digest": "empty_digest_days",
}


def _date_range(since: date, until: date) -> list[date]:
    if since > until:
        return []
    days = []
    current = since
    while current <= until:
        days.append(current)
        current += timedelta(days=1)
    return days


def _parse_db_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _digest_dates(digest_dir: str) -> set[date]:
    root = Path(digest_dir)
    if not root.is_dir():
        return set()
    result = set()
    for path in root.glob("*.md"):
        match = DIGEST_FILE_RE.match(path.name)
        if match:
            result.add(date.fromisoformat(match.group(1)))
    return result


def _latest_db_fetch_date(conn: sqlite3.Connection) -> Optional[date]:
    try:
        row = conn.execute("SELECT MAX(fetched_at) FROM items").fetchone()
    except sqlite3.OperationalError:
        return None
    return _parse_db_date(row[0] if row else None)


def infer_since(db_path: str, digest_dir: str, until: date) -> date:
    """Infer the first missing day after the latest known ingest or digest artifact."""
    latest_dates = []
    if Path(db_path).exists():
        conn = sqlite3.connect(db_path)
        try:
            latest = _latest_db_fetch_date(conn)
            if latest:
                latest_dates.append(latest)
        finally:
            conn.close()
    digest_dates = _digest_dates(digest_dir)
    if digest_dates:
        latest_dates.append(max(digest_dates))
    if not latest_dates:
        return until
    latest_known = max(latest_dates)
    if latest_known >= until:
        return until
    return latest_known + timedelta(days=1)


def _connect_readonly(db_path: str) -> sqlite3.Connection:
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _ingest_counts(conn: sqlite3.Connection, since: date, until: date) -> Dict[str, Dict]:
    if not _table_exists(conn, "items"):
        return {}
    result: Dict[str, Dict] = defaultdict(lambda: {"total": 0, "sources": Counter(), "source_apis": Counter()})
    rows = conn.execute(
        """
        SELECT
            date(fetched_at) AS day,
            source,
            COALESCE(NULLIF(source_api, ''), 'unknown') AS source_api,
            COUNT(*) AS item_count
        FROM items
        WHERE date(fetched_at) BETWEEN date(?) AND date(?)
        GROUP BY date(fetched_at), source, COALESCE(NULLIF(source_api, ''), 'unknown')
        ORDER BY day, source, source_api
        """,
        (since.isoformat(), until.isoformat()),
    ).fetchall()
    for row in rows:
        day = row["day"]
        count = int(row["item_count"])
        result[day]["total"] += count
        result[day]["sources"][row["source"]] += count
        result[day]["source_apis"][row["source_api"]] += count
    return result


def _scored_counts(conn: sqlite3.Connection, since: date, until: date) -> Dict[str, int]:
    if not (_table_exists(conn, "items") and _table_exists(conn, "item_topic_scores")):
        return {}
    rows = conn.execute(
        """
        SELECT date(i.fetched_at) AS day, COUNT(DISTINCT s.item_id) AS scored_items
        FROM items i
        JOIN item_topic_scores s ON s.item_id = i.item_id
        WHERE date(i.fetched_at) BETWEEN date(?) AND date(?)
        GROUP BY date(i.fetched_at)
        ORDER BY day
        """,
        (since.isoformat(), until.isoformat()),
    ).fetchall()
    return {row["day"]: int(row["scored_items"]) for row in rows}


def _feedback_read_counts(
    conn: sqlite3.Connection,
    since: date,
    until: date,
    users: Sequence[str],
) -> Dict[str, int]:
    if not (_table_exists(conn, "items") and _table_exists(conn, "feedback")):
        return {}
    params = [since.isoformat(), until.isoformat(), *READ_ACTIONS]
    user_join = ""
    user_clause = ""
    if users:
        user_join = "JOIN users u ON u.user_id = f.user_id"
        placeholders = ",".join("?" for _ in users)
        user_clause = f"AND u.identifier IN ({placeholders})"
        params.extend(users)
    rows = conn.execute(
        f"""
        SELECT date(i.fetched_at) AS day, COUNT(*) AS read_events
        FROM feedback f
        JOIN items i ON i.item_id = f.item_id
        {user_join}
        WHERE date(i.fetched_at) BETWEEN date(?) AND date(?)
          AND f.action IN (?, ?)
          {user_clause}
        GROUP BY date(i.fetched_at)
        ORDER BY day
        """,
        params,
    ).fetchall()
    return {row["day"]: int(row["read_events"]) for row in rows}


def _digest_file_stats(digest_dir: str, since: date, until: date) -> Dict[str, Dict]:
    root = Path(digest_dir)
    result = {}
    if not root.is_dir():
        return result
    for day in _date_range(since, until):
        path = root / f"{day.isoformat()}.md"
        if not path.is_file():
            continue
        text = path.read_text(errors="replace")
        try:
            item_count = len(parse_persona_markdown(str(path)))
        except Exception:
            item_count = len(re.findall(r"^- \[[ xX]\]\s+", text, flags=re.MULTILINE))
        try:
            checked_count = len(parse_read_items(text))
        except Exception:
            checked_count = 0
        result[day.isoformat()] = {
            "path": str(path),
            "item_count": item_count,
            "checked_read_items": checked_count,
        }
    return result


def build_gap_summary(
    db_path: str = "knowledge_os.db",
    digest_dir: str = "knos-digest",
    since: Optional[date] = None,
    until: Optional[date] = None,
    users: Optional[Iterable[str]] = None,
) -> Dict:
    until = until or date.today()
    since = since or infer_since(db_path, digest_dir, until)
    users = [user.strip() for user in (users or []) if user.strip()]
    days = _date_range(since, until)

    if Path(db_path).exists():
        conn = _connect_readonly(db_path)
        try:
            ingest_counts = _ingest_counts(conn, since, until)
            scored_counts = _scored_counts(conn, since, until)
            feedback_counts = _feedback_read_counts(conn, since, until, users)
        finally:
            conn.close()
    else:
        ingest_counts = {}
        scored_counts = {}
        feedback_counts = {}

    digest_stats = _digest_file_stats(digest_dir, since, until)
    day_rows = []
    for day in days:
        key = day.isoformat()
        ingest = ingest_counts.get(key, {"total": 0, "sources": Counter(), "source_apis": Counter()})
        digest = digest_stats.get(key)
        item_count = int(ingest["total"])
        scored_item_count = int(scored_counts.get(key, 0))
        checked_read_items = int(digest.get("checked_read_items", 0)) if digest else 0
        feedback_read_events = int(feedback_counts.get(key, 0))
        digest_item_count = int(digest.get("item_count", 0)) if digest else 0
        statuses = []
        if item_count == 0:
            statuses.append("missing_ingest")
        if not digest:
            statuses.append("missing_digest")
        elif digest_item_count == 0:
            statuses.append("empty_digest")
        if item_count > 0 and scored_item_count == 0:
            statuses.append("unscored")
        if digest and digest_item_count > 0 and checked_read_items == 0 and feedback_read_events == 0:
            statuses.append("unread")
        day_rows.append({
            "date": key,
            "ingested": item_count > 0,
            "item_count": item_count,
            "sources": dict(sorted(ingest["sources"].items())),
            "source_apis": dict(sorted(ingest["source_apis"].items())),
            "scored_item_count": scored_item_count,
            "digest_path": digest["path"] if digest else None,
            "digest_item_count": digest_item_count,
            "checked_read_items": checked_read_items,
            "feedback_read_events": feedback_read_events,
            "read_signal_count": checked_read_items + feedback_read_events,
            "statuses": statuses or ["ok"],
        })

    missing_ingest = [row["date"] for row in day_rows if "missing_ingest" in row["statuses"]]
    missing_digest = [row["date"] for row in day_rows if "missing_digest" in row["statuses"]]
    unscored = [row["date"] for row in day_rows if "unscored" in row["statuses"]]
    unread = [row["date"] for row in day_rows if "unread" in row["statuses"]]
    empty_digest = [row["date"] for row in day_rows if "empty_digest" in row["statuses"]]
    return {
        "request": {
            "db": db_path,
            "digest_dir": digest_dir,
            "since": since.isoformat(),
            "until": until.isoformat(),
            "users": users,
        },
        "summary": {
            "expected_days": len(day_rows),
            "missing_ingest_days": missing_ingest,
            "missing_digest_days": missing_digest,
            "unscored_ingest_days": unscored,
            "unread_digest_days": unread,
            "empty_digest_days": empty_digest,
        },
        "days": day_rows,
    }


def _has_gap(row: Dict) -> bool:
    return row["statuses"] != ["ok"]


def render_text(report: Dict, all_days: bool = False) -> str:
    summary = report["summary"]
    request = report["request"]
    lines = [
        f"Gap summary: {request['since']}..{request['until']}",
        f"Missing ingest: {len(summary['missing_ingest_days'])} day(s)",
        f"Missing digest: {len(summary['missing_digest_days'])} day(s)",
        f"Unscored ingest: {len(summary['unscored_ingest_days'])} day(s)",
        f"Unread digest: {len(summary['unread_digest_days'])} day(s)",
        f"Empty digest: {len(summary['empty_digest_days'])} day(s)",
        "",
        "date        items  scored  digest_items  reads  status",
        "----------  -----  ------  ------------  -----  ------",
    ]
    rows = report["days"] if all_days else [row for row in report["days"] if _has_gap(row)]
    if not rows:
        lines.append("(no gap days)")
        return "\n".join(lines) + "\n"
    for row in rows:
        lines.append(
            f"{row['date']}  "
            f"{row['item_count']:>5}  "
            f"{row['scored_item_count']:>6}  "
            f"{row['digest_item_count']:>12}  "
            f"{row['read_signal_count']:>5}  "
            f"{','.join(row['statuses'])}"
        )
    return "\n".join(lines) + "\n"


def gap_dates(report: Dict, gap_types: Iterable[str]) -> list[str]:
    selected = set()
    for gap_type in gap_types:
        key = GAP_TYPES[gap_type]
        selected.update(report["summary"][key])
    return sorted(selected)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Knowledge OS gap days.")
    parser.add_argument("--db", default="knowledge_os.db")
    parser.add_argument("--digest-dir", default="knos-digest")
    parser.add_argument("--since", help="Start date YYYY-MM-DD; defaults to day after latest known run")
    parser.add_argument("--until", default=date.today().isoformat(), help="End date YYYY-MM-DD, inclusive")
    parser.add_argument("--users", default="", help="Comma-separated users for DB feedback read counts")
    parser.add_argument("--format", choices=("text", "json", "dates"), default="text")
    parser.add_argument(
        "--gap-types",
        default="ingest,digest",
        help="Comma-separated date output types for --format dates: ingest,digest,scoring,read,empty_digest",
    )
    parser.add_argument("--all-days", action="store_true", help="Show all days in text output, not just gap rows")
    args = parser.parse_args()

    users = [user.strip() for user in args.users.split(",") if user.strip()]
    requested_until = date.fromisoformat(args.until)
    requested_since = date.fromisoformat(args.since) if args.since else None
    report = build_gap_summary(
        db_path=args.db,
        digest_dir=args.digest_dir,
        since=requested_since,
        until=requested_until,
        users=users,
    )
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.format == "dates":
        selected_types = [value.strip() for value in args.gap_types.split(",") if value.strip()]
        unknown = [value for value in selected_types if value not in GAP_TYPES]
        if unknown:
            parser.error(f"Unknown gap type(s): {', '.join(unknown)}")
        for value in gap_dates(report, selected_types):
            print(value)
    else:
        print(render_text(report, all_days=args.all_days), end="")


if __name__ == "__main__":
    main()
