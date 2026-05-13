#!/usr/bin/env python3
"""Load user topic subscription configuration into the target schema."""
import argparse
import json
import sqlite3
from typing import Dict

from .schema import init_target_schema


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _load_config(path: str) -> Dict:
    with open(path) as f:
        return json.load(f)


def load_user_subscriptions(db_path: str, config_path: str) -> int:
    init_target_schema(db_path)
    cfg = _load_config(config_path)
    user_cfg = cfg["user"]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO users (identifier, timezone, settings_json)
            VALUES (?, ?, ?)
            ON CONFLICT(identifier) DO UPDATE SET
                timezone = COALESCE(excluded.timezone, users.timezone),
                settings_json = excluded.settings_json
            """,
            (
                user_cfg["identifier"],
                user_cfg.get("timezone"),
                _json(cfg.get("digest", {})),
            ),
        )
        user_id = conn.execute(
            "SELECT user_id FROM users WHERE identifier = ?",
            (user_cfg["identifier"],),
        ).fetchone()["user_id"]

        written = 0
        for sub in cfg.get("subscriptions", []):
            topic = conn.execute("SELECT topic_id FROM topics WHERE name = ?", (sub["topic"],)).fetchone()
            if not topic:
                raise ValueError(f"Unknown topic for subscription: {sub['topic']}")
            topic_id = topic["topic_id"]
            source_filter = sub.get("sources")
            author_filter = sub.get("authors")
            conn.execute(
                """
                INSERT INTO user_topic_subscriptions
                    (user_id, topic_id, min_topic_score, author_filter_json,
                     source_filter_json, freshness_days, max_items, suppress_delivered, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(user_id, topic_id) DO UPDATE SET
                    min_topic_score = excluded.min_topic_score,
                    author_filter_json = excluded.author_filter_json,
                    source_filter_json = excluded.source_filter_json,
                    freshness_days = excluded.freshness_days,
                    max_items = excluded.max_items,
                    suppress_delivered = excluded.suppress_delivered,
                    active = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    topic_id,
                    float(sub.get("min_topic_score", 0.3)),
                    _json(author_filter) if author_filter is not None else None,
                    _json(source_filter) if source_filter is not None else None,
                    int(sub.get("freshness_days", 7)),
                    int(sub.get("max_items", 10)),
                    1 if sub.get("suppress_delivered", True) else 0,
                ),
            )
            written += 1
        conn.commit()
        return written
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load user topic subscriptions.")
    parser.add_argument("--db", default="knowledge_os.db")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    written = load_user_subscriptions(args.db, args.config)
    print(f"Loaded {written} subscription(s)")


if __name__ == "__main__":
    main()
