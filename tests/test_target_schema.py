"""Tests for the target four-module schema."""
import json
import sqlite3

from knowledge_os.feedback_events import insert_feedback_event
from knowledge_os.schema import init_target_schema
from knowledge_os.subscriptions import load_user_subscriptions


def _tables(db_path):
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {row[0] for row in rows}
    finally:
        conn.close()


def test_init_target_schema_creates_four_module_tables(tmp_path):
    db_path = str(tmp_path / "target.db")

    init_target_schema(db_path)

    assert {
        "items",
        "authors",
        "item_content",
        "topics",
        "topic_scoring_configs",
        "item_topic_scores",
        "topic_origins",
        "users",
        "user_topic_subscriptions",
        "digests",
        "digest_items",
        "feedback",
        "delivery_events",
    }.issubset(_tables(db_path))


def test_historical_scores_are_keyed_by_scoring_config(tmp_path):
    db_path = str(tmp_path / "target.db")
    init_target_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO items (url, title, source, fetched_at) VALUES (?, ?, ?, ?)",
            ("https://example.com/1", "Story", "test", "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO topics (name, keywords_json) VALUES (?, ?)",
            ("AI", json.dumps(["ai"])),
        )
        conn.execute(
            """
            INSERT INTO topic_scoring_configs (name, model, content_fields_json)
            VALUES (?, ?, ?), (?, ?, ?)
            """,
            ("v1", "m", "[]", "v2", "m", "[]"),
        )
        conn.execute(
            """
            INSERT INTO item_topic_scores
              (item_id, topic_id, scoring_config_id, score)
            VALUES (1, 1, 1, 0.4), (1, 1, 2, 0.6)
            """
        )
        rows = conn.execute(
            "SELECT score FROM item_topic_scores WHERE item_id = 1 AND topic_id = 1 ORDER BY scoring_config_id"
        ).fetchall()
        assert [row[0] for row in rows] == [0.4, 0.6]
    finally:
        conn.close()


def test_items_schema_tracks_source_api_and_backfills_existing_rows(tmp_path):
    db_path = str(tmp_path / "target.db")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                external_id TEXT,
                author_id INTEGER,
                author_name TEXT,
                score INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                item_text TEXT,
                fetched_at TEXT NOT NULL,
                published_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO items (url, title, source, fetched_at) VALUES (?, ?, ?, ?)",
            ("https://example.com/1", "Story", "hackernews", "2026-01-01T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    init_target_schema(db_path)

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT source_api FROM items WHERE item_id = 1").fetchone()
        assert row[0] == "hackernews_firebase"
    finally:
        conn.close()


def test_feedback_event_is_user_per_item(tmp_path):
    db_path = str(tmp_path / "target.db")
    init_target_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO items (url, title, source, fetched_at) VALUES (?, ?, ?, ?)",
            ("https://example.com/1", "Story", "test", "2026-01-01T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    feedback_id = insert_feedback_event(
        db_path,
        user_identifier="reader",
        item_id=1,
        action="saved",
        metadata={"reason": "important"},
    )

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT f.feedback_id, u.identifier, f.item_id, f.action, f.metadata_json
            FROM feedback f
            JOIN users u ON u.user_id = f.user_id
            """
        ).fetchone()
        assert row == (feedback_id, "reader", 1, "saved", '{"reason": "important"}')
    finally:
        conn.close()


def test_load_user_subscriptions_uses_global_topics(tmp_path):
    db_path = str(tmp_path / "target.db")
    config_path = tmp_path / "user.json"
    init_target_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO topics (name, keywords_json) VALUES (?, ?)",
            ("AI", json.dumps(["ai"])),
        )
        conn.commit()
    finally:
        conn.close()

    config_path.write_text(json.dumps({
        "user": {"identifier": "reader", "timezone": "Asia/Calcutta"},
        "subscriptions": [{
            "topic": "AI",
            "min_topic_score": 0.42,
            "freshness_days": 3,
            "sources": ["hackernews"],
            "authors": {"allow": [], "deny": ["noisy"]},
            "max_items": 5,
            "suppress_delivered": True,
        }],
        "digest": {"max_items": 10, "format": "markdown"},
    }))

    assert load_user_subscriptions(db_path, str(config_path)) == 1

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT u.identifier, t.name, s.min_topic_score, s.source_filter_json, s.author_filter_json
            FROM user_topic_subscriptions s
            JOIN users u ON u.user_id = s.user_id
            JOIN topics t ON t.topic_id = s.topic_id
            """
        ).fetchone()
        assert row == (
            "reader",
            "AI",
            0.42,
            '["hackernews"]',
            '{"allow": [], "deny": ["noisy"]}',
        )
    finally:
        conn.close()
