#!/usr/bin/env python3
"""Target schema for the four-module knowledge-os architecture."""
import sqlite3
from pathlib import Path


def init_target_schema(db_path: str = "knowledge_os.db") -> None:
    """Create the target schema if it does not already exist."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True) if Path(db_path).parent != Path(".") else None
    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        c.execute("PRAGMA foreign_keys = ON")

        c.execute("""
            CREATE TABLE IF NOT EXISTS authors (
                author_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                external_author_id TEXT,
                author_name TEXT NOT NULL,
                profile_url TEXT,
                story_count INTEGER DEFAULT 0,
                total_score REAL DEFAULT 0.0,
                metadata_json TEXT,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source, author_name)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                source_api TEXT,
                external_id TEXT,
                author_id INTEGER,
                author_name TEXT,
                score INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                item_text TEXT,
                fetched_at TEXT NOT NULL,
                published_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT,
                FOREIGN KEY (author_id) REFERENCES authors(author_id)
            )
        """)
        _ensure_column(c, "items", "source_api", "source_api TEXT")
        c.execute("""
            UPDATE items
            SET source_api = CASE
                WHEN source = 'hackernews' THEN 'hackernews_firebase'
                WHEN source = 'substack' THEN 'rss'
                ELSE source
            END
            WHERE source_api IS NULL OR source_api = ''
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS item_content (
                content_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                content_text TEXT NOT NULL,
                source TEXT,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items(item_id),
                UNIQUE(item_id, content_type, source)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                keywords_json TEXT NOT NULL,
                default_weight REAL DEFAULT 1.0,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS topic_scoring_configs (
                scoring_config_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                model TEXT NOT NULL,
                content_fields_json TEXT NOT NULL,
                scoring_params_json TEXT,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS item_topic_scores (
                item_id INTEGER NOT NULL,
                topic_id INTEGER NOT NULL,
                scoring_config_id INTEGER NOT NULL,
                score REAL NOT NULL,
                evidence_json TEXT,
                computed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (item_id, topic_id, scoring_config_id),
                FOREIGN KEY (item_id) REFERENCES items(item_id),
                FOREIGN KEY (topic_id) REFERENCES topics(topic_id),
                FOREIGN KEY (scoring_config_id) REFERENCES topic_scoring_configs(scoring_config_id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS topic_origins (
                topic_id INTEGER NOT NULL,
                origin_type TEXT NOT NULL,
                origin_id TEXT NOT NULL,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (topic_id, origin_type, origin_id),
                FOREIGN KEY (topic_id) REFERENCES topics(topic_id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT NOT NULL UNIQUE,
                timezone TEXT,
                settings_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS user_topic_subscriptions (
                subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                topic_id INTEGER NOT NULL,
                min_topic_score REAL DEFAULT 0.3,
                author_filter_json TEXT,
                source_filter_json TEXT,
                freshness_days INTEGER DEFAULT 7,
                max_items INTEGER DEFAULT 10,
                suppress_delivered INTEGER DEFAULT 1,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (topic_id) REFERENCES topics(topic_id),
                UNIQUE(user_id, topic_id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS digests (
                digest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'generated',
                metadata_json TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS digest_items (
                digest_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                topic_id INTEGER,
                topic_score REAL,
                rank INTEGER NOT NULL,
                selection_reason_json TEXT,
                PRIMARY KEY (digest_id, item_id),
                FOREIGN KEY (digest_id) REFERENCES digests(digest_id),
                FOREIGN KEY (item_id) REFERENCES items(item_id),
                FOREIGN KEY (topic_id) REFERENCES topics(topic_id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                digest_id INTEGER,
                action TEXT NOT NULL,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (item_id) REFERENCES items(item_id),
                FOREIGN KEY (digest_id) REFERENCES digests(digest_id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS delivery_events (
                delivery_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                digest_id INTEGER NOT NULL,
                channel TEXT NOT NULL,
                status TEXT NOT NULL,
                artifact_path TEXT,
                artifact_url TEXT,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (digest_id) REFERENCES digests(digest_id)
            )
        """)

        c.execute("CREATE INDEX IF NOT EXISTS idx_items_url ON items(url)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_items_source_external ON items(source, external_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_items_source_api ON items(source_api)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_item_content_item_type ON item_content(item_id, content_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_scores_topic_score ON item_topic_scores(topic_id, score)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_feedback_user_item_action ON feedback(user_id, item_id, action)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_digest_items_digest ON digest_items(digest_id, rank)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_topic_origins_origin ON topic_origins(origin_type, origin_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_delivery_events_digest ON delivery_events(digest_id)")

        conn.commit()
    finally:
        conn.close()


def _ensure_column(c: sqlite3.Cursor, table: str, column: str, ddl: str) -> None:
    columns = {row[1] for row in c.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Initialize the target knowledge-os schema.")
    parser.add_argument("--db", default="knowledge_os.db", help="SQLite database path")
    args = parser.parse_args()
    init_target_schema(args.db)


if __name__ == "__main__":
    main()
