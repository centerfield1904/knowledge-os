#!/usr/bin/env python3
"""Inspect the modular pipeline state in SQLite."""
import argparse
import json
import sqlite3
from datetime import date
from typing import Iterable, Optional, Sequence


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def _print_json(rows: Sequence[dict]) -> None:
    print(json.dumps(rows, indent=2, ensure_ascii=True))


def _print_table(rows: Sequence[dict]) -> None:
    if not rows:
        print("(no rows)")
        return
    columns = list(rows[0].keys())
    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }
    header = "  ".join(column.ljust(widths[column]) for column in columns)
    separator = "  ".join("-" * widths[column] for column in columns)
    print(header)
    print(separator)
    for row in rows:
        print("  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns))


def print_rows(rows: Sequence[dict], fmt: str) -> None:
    if fmt == "json":
        _print_json(rows)
    else:
        _print_table(rows)


def catalog_summary(conn: sqlite3.Connection) -> list[dict]:
    return rows_to_dicts(conn.execute(
        """
        SELECT
            i.source,
            COALESCE(i.source_api, '') AS source_api,
            COUNT(*) AS item_count,
            COUNT(DISTINCT i.author_id) AS author_count,
            MAX(i.fetched_at) AS latest_fetch
        FROM items i
        GROUP BY i.source, i.source_api
        ORDER BY item_count DESC
        """
    ))


def catalog_items(conn: sqlite3.Connection, limit: int, source: Optional[str] = None) -> list[dict]:
    return catalog_items_filtered(conn, limit=limit, source=source)


def _date_clauses(
    column_sql: str,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> tuple[list[str], list[object]]:
    clauses = []
    params: list[object] = []
    if since:
        clauses.append(f"date({column_sql}) >= date(?)")
        params.append(since)
    if until:
        clauses.append(f"date({column_sql}) <= date(?)")
        params.append(until)
    return clauses, params


def catalog_items_filtered(
    conn: sqlite3.Connection,
    limit: int,
    source: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> list[dict]:
    clauses = []
    params: list[object] = []
    if source:
        clauses.append("i.source = ?")
        params.append(source)
    date_filters, date_params = _date_clauses("COALESCE(i.published_at, i.fetched_at)", since, until)
    clauses.extend(date_filters)
    params.extend(date_params)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return rows_to_dicts(conn.execute(
        f"""
        SELECT
            i.item_id,
            i.source,
            COALESCE(i.source_api, '') AS source_api,
            i.score,
            i.comment_count,
            i.author_name,
            substr(i.title, 1, 90) AS title,
            i.published_at
        FROM items i
        {where}
        ORDER BY datetime(COALESCE(i.published_at, i.fetched_at)) DESC, i.score DESC
        LIMIT ?
        """,
        (*params, limit),
    ))


def authors(conn: sqlite3.Connection, limit: int, source: Optional[str] = None) -> list[dict]:
    where = "WHERE a.source = ?" if source else ""
    params = (source,) if source else ()
    return rows_to_dicts(conn.execute(
        f"""
        SELECT
            a.author_id,
            a.source,
            a.author_name,
            a.story_count,
            a.total_score,
            a.last_seen
        FROM authors a
        {where}
        ORDER BY a.last_seen DESC, a.total_score DESC
        LIMIT ?
        """,
        (*params, limit),
    ))


def topics(conn: sqlite3.Connection) -> list[dict]:
    return rows_to_dicts(conn.execute(
        """
        SELECT
            t.topic_id,
            t.name,
            t.active,
            COUNT(DISTINCT s.item_id) AS scored_items,
            ROUND(MAX(s.score), 3) AS max_score,
            ROUND(AVG(s.score), 3) AS avg_score
        FROM topics t
        LEFT JOIN item_topic_scores s ON s.topic_id = t.topic_id
        GROUP BY t.topic_id
        ORDER BY t.name
        """
    ))


def score_configs(conn: sqlite3.Connection) -> list[dict]:
    return rows_to_dicts(conn.execute(
        """
        SELECT
            scoring_config_id,
            name,
            model,
            content_fields_json,
            active,
            created_at
        FROM topic_scoring_configs
        ORDER BY scoring_config_id DESC
        """
    ))


def top_scores(conn: sqlite3.Connection, limit: int, topic: Optional[str] = None) -> list[dict]:
    return top_scores_filtered(conn, limit=limit, topic=topic)


def top_scores_filtered(
    conn: sqlite3.Connection,
    limit: int,
    topic: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> list[dict]:
    clauses = []
    params: list[object] = []
    if topic:
        clauses.append("t.name = ?")
        params.append(topic)
    date_filters, date_params = _date_clauses("COALESCE(i.published_at, i.fetched_at)", since, until)
    clauses.extend(date_filters)
    params.extend(date_params)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return rows_to_dicts(conn.execute(
        f"""
        SELECT
            ROUND(s.score, 3) AS topic_score,
            t.name AS topic,
            c.name AS scoring_config,
            i.item_id,
            i.source,
            i.score AS item_score,
            substr(i.title, 1, 90) AS title
        FROM item_topic_scores s
        JOIN topics t ON t.topic_id = s.topic_id
        JOIN topic_scoring_configs c ON c.scoring_config_id = s.scoring_config_id
        JOIN items i ON i.item_id = s.item_id
        {where}
        ORDER BY s.score DESC, i.score DESC
        LIMIT ?
        """,
        (*params, limit),
    ))


def fetched_items_filtered(
    conn: sqlite3.Connection,
    limit: int,
    fetch_date: str,
    min_score: Optional[int] = None,
    topic: Optional[str] = None,
    min_topic_score: Optional[float] = None,
    title: Optional[str] = None,
    source: Optional[str] = None,
    source_api: Optional[str] = None,
) -> list[dict]:
    clauses = ["date(i.fetched_at) = date(?)"]
    params: list[object] = [fetch_date]
    if min_score is not None:
        clauses.append("i.score >= ?")
        params.append(min_score)
    if title:
        clauses.append("LOWER(i.title) LIKE LOWER(?)")
        params.append(f"%{title}%")
    if source:
        clauses.append("i.source = ?")
        params.append(source)
    if source_api:
        clauses.append("i.source_api = ?")
        params.append(source_api)

    score_clauses = []
    score_params: list[object] = []
    if topic:
        score_clauses.append("LOWER(t.name) LIKE LOWER(?)")
        score_params.append(f"%{topic}%")
    if min_topic_score is not None:
        score_clauses.append("s.score >= ?")
        score_params.append(min_topic_score)
    if score_clauses:
        clauses.append("s.item_id IS NOT NULL")
    where = " AND ".join(clauses)
    score_where = f"WHERE {' AND '.join(score_clauses)}" if score_clauses else ""

    return rows_to_dicts(conn.execute(
        f"""
        WITH ranked_scores AS (
            SELECT
                s.item_id,
                t.name AS topic,
                s.score AS topic_score,
                ROW_NUMBER() OVER (
                    PARTITION BY s.item_id
                    ORDER BY s.score DESC, t.name
                ) AS topic_rank
            FROM item_topic_scores s
            JOIN topics t ON t.topic_id = s.topic_id
            {score_where}
        )
        SELECT
            i.item_id,
            i.source,
            COALESCE(i.source_api, '') AS source_api,
            i.score,
            ROUND(s.topic_score, 3) AS topic_score,
            s.topic,
            i.author_name,
            substr(i.title, 1, 100) AS title,
            i.published_at,
            i.fetched_at,
            i.url
        FROM items i
        LEFT JOIN ranked_scores s ON s.item_id = i.item_id AND s.topic_rank = 1
        WHERE {where}
        ORDER BY i.score DESC, s.topic_score DESC, datetime(i.published_at) DESC
        LIMIT ?
        """,
        (*score_params, *params, limit),
    ))


def users(conn: sqlite3.Connection) -> list[dict]:
    return rows_to_dicts(conn.execute(
        """
        SELECT
            u.user_id,
            u.identifier,
            u.timezone,
            COUNT(DISTINCT s.subscription_id) AS subscriptions,
            COUNT(DISTINCT d.digest_id) AS digests
        FROM users u
        LEFT JOIN user_topic_subscriptions s ON s.user_id = u.user_id
        LEFT JOIN digests d ON d.user_id = u.user_id
        GROUP BY u.user_id
        ORDER BY u.identifier
        """
    ))


def subscriptions(conn: sqlite3.Connection, user: Optional[str] = None) -> list[dict]:
    where = "WHERE u.identifier = ?" if user else ""
    params = (user,) if user else ()
    return rows_to_dicts(conn.execute(
        f"""
        SELECT
            u.identifier AS user,
            t.name AS topic,
            s.min_topic_score,
            s.freshness_days,
            s.max_items,
            s.suppress_delivered,
            s.source_filter_json,
            s.author_filter_json,
            s.active
        FROM user_topic_subscriptions s
        JOIN users u ON u.user_id = s.user_id
        JOIN topics t ON t.topic_id = s.topic_id
        {where}
        ORDER BY u.identifier, t.name
        """,
        params,
    ))


def digests(conn: sqlite3.Connection, user: Optional[str] = None, limit: int = 10) -> list[dict]:
    where = "WHERE u.identifier = ?" if user else ""
    params = (user,) if user else ()
    return rows_to_dicts(conn.execute(
        f"""
        SELECT
            d.digest_id,
            u.identifier AS user,
            d.generated_at,
            d.status,
            COUNT(di.item_id) AS item_count
        FROM digests d
        JOIN users u ON u.user_id = d.user_id
        LEFT JOIN digest_items di ON di.digest_id = d.digest_id
        {where}
        GROUP BY d.digest_id
        ORDER BY d.digest_id DESC
        LIMIT ?
        """,
        (*params, limit),
    ))


def digest_items(conn: sqlite3.Connection, digest_id: int) -> list[dict]:
    return rows_to_dicts(conn.execute(
        """
        SELECT
            di.rank,
            i.item_id,
            t.name AS topic,
            ROUND(di.topic_score, 3) AS topic_score,
            i.score AS item_score,
            i.author_name,
            substr(i.title, 1, 90) AS title,
            i.url
        FROM digest_items di
        JOIN items i ON i.item_id = di.item_id
        LEFT JOIN topics t ON t.topic_id = di.topic_id
        WHERE di.digest_id = ?
        ORDER BY di.rank
        """,
        (digest_id,),
    ))


def feedback(
    conn: sqlite3.Connection,
    user: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 25,
) -> list[dict]:
    clauses = []
    params: list[object] = []
    if user:
        clauses.append("u.identifier = ?")
        params.append(user)
    if action:
        clauses.append("f.action = ?")
        params.append(action)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return rows_to_dicts(conn.execute(
        f"""
        SELECT
            f.feedback_id,
            u.identifier AS user,
            f.action,
            f.digest_id,
            f.item_id,
            substr(i.title, 1, 90) AS title,
            f.created_at
        FROM feedback f
        JOIN users u ON u.user_id = f.user_id
        JOIN items i ON i.item_id = f.item_id
        {where}
        ORDER BY f.feedback_id DESC
        LIMIT ?
        """,
        (*params, limit),
    ))


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default="knowledge_os.db")
    parser.add_argument("--format", choices=["table", "json"], default="table")


def main() -> None:
    parser = argparse.ArgumentParser(description="Query modular knowledge-os pipeline state.")
    add_common_args(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("catalog-summary")

    p = sub.add_parser("items")
    p.add_argument("--source")
    p.add_argument("--since", help="Include items on or after YYYY-MM-DD")
    p.add_argument("--until", help="Include items on or before YYYY-MM-DD")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("authors")
    p.add_argument("--source")
    p.add_argument("--limit", type=int, default=20)

    sub.add_parser("topics")
    sub.add_parser("score-configs")

    p = sub.add_parser("top-scores")
    p.add_argument("--topic")
    p.add_argument("--since", help="Include scores for items on or after YYYY-MM-DD")
    p.add_argument("--until", help="Include scores for items on or before YYYY-MM-DD")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("fetched-items")
    p.add_argument("--date", default=date.today().isoformat(), help="Include items fetched on YYYY-MM-DD, defaults to today")
    p.add_argument("--min-score", type=int, help="Minimum item/source score")
    p.add_argument("--topic", help="Case-insensitive topic substring")
    p.add_argument("--min-topic-score", type=float)
    p.add_argument("--title", help="Case-insensitive title substring")
    p.add_argument("--source")
    p.add_argument("--source-api")
    p.add_argument("--limit", type=int, default=50)

    sub.add_parser("users")

    p = sub.add_parser("subscriptions")
    p.add_argument("--user")

    p = sub.add_parser("digests")
    p.add_argument("--user")
    p.add_argument("--limit", type=int, default=10)

    p = sub.add_parser("digest-items")
    p.add_argument("--digest-id", type=int, required=True)

    p = sub.add_parser("feedback")
    p.add_argument("--user")
    p.add_argument("--action")
    p.add_argument("--limit", type=int, default=25)

    args = parser.parse_args()
    with connect(args.db) as conn:
        if args.command == "catalog-summary":
            result = catalog_summary(conn)
        elif args.command == "items":
            result = catalog_items_filtered(
                conn,
                args.limit,
                source=args.source,
                since=args.since,
                until=args.until,
            )
        elif args.command == "authors":
            result = authors(conn, args.limit, source=args.source)
        elif args.command == "topics":
            result = topics(conn)
        elif args.command == "score-configs":
            result = score_configs(conn)
        elif args.command == "top-scores":
            result = top_scores_filtered(
                conn,
                args.limit,
                topic=args.topic,
                since=args.since,
                until=args.until,
            )
        elif args.command == "fetched-items":
            result = fetched_items_filtered(
                conn,
                args.limit,
                fetch_date=args.date,
                min_score=args.min_score,
                topic=args.topic,
                min_topic_score=args.min_topic_score,
                title=args.title,
                source=args.source,
                source_api=args.source_api,
            )
        elif args.command == "users":
            result = users(conn)
        elif args.command == "subscriptions":
            result = subscriptions(conn, user=args.user)
        elif args.command == "digests":
            result = digests(conn, user=args.user, limit=args.limit)
        elif args.command == "digest-items":
            result = digest_items(conn, args.digest_id)
        elif args.command == "feedback":
            result = feedback(conn, user=args.user, action=args.action, limit=args.limit)
        else:
            parser.error(f"Unknown command: {args.command}")
    print_rows(result, args.format)


if __name__ == "__main__":
    main()
