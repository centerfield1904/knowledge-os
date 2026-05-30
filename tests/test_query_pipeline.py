import json
import sqlite3

from knowledge_os.query_pipeline import (
    catalog_items,
    catalog_items_filtered,
    catalog_summary,
    digest_items,
    digests,
    feedback,
    fetched_items_filtered,
    subscriptions,
    top_scores,
    top_scores_filtered,
    topics,
    users,
)
from knowledge_os.schema import init_target_schema


def _seed(db_path):
    init_target_schema(str(db_path))
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO authors (source, author_name) VALUES ('hackernews', 'alice')")
        conn.execute(
            """
            INSERT INTO items
              (url, title, source, source_api, external_id, author_id, author_name, score, comment_count,
               fetched_at, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://example.com/a",
                "Ranking agents well",
                "hackernews",
                "hackernews_firebase",
                "100",
                1,
                "alice",
                99,
                12,
                "2026-05-14T00:00:00",
                "2026-05-14T00:00:00",
            ),
        )
        conn.execute("INSERT INTO topics (name, keywords_json) VALUES ('AI', ?)", (json.dumps(["ai"]),))
        conn.execute(
            """
            INSERT INTO topic_scoring_configs (name, model, content_fields_json)
            VALUES ('v1', 'all-MiniLM-L6-v2', '["title"]')
            """
        )
        conn.execute(
            """
            INSERT INTO item_topic_scores (item_id, topic_id, scoring_config_id, score)
            VALUES (1, 1, 1, 0.75)
            """
        )
        conn.execute("INSERT INTO users (identifier, timezone) VALUES ('vb', 'Asia/Calcutta')")
        conn.execute(
            """
            INSERT INTO user_topic_subscriptions
              (user_id, topic_id, min_topic_score, source_filter_json, author_filter_json)
            VALUES (1, 1, 0.4, '["hackernews"]', '{"allow": [], "deny": []}')
            """
        )
        conn.execute("INSERT INTO digests (user_id, status) VALUES (1, 'generated')")
        conn.execute(
            """
            INSERT INTO digest_items (digest_id, item_id, topic_id, topic_score, rank)
            VALUES (1, 1, 1, 0.75, 1)
            """
        )
        conn.execute(
            """
            INSERT INTO feedback (user_id, item_id, digest_id, action)
            VALUES (1, 1, 1, 'delivered')
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_query_pipeline_sections(tmp_path):
    db_path = tmp_path / "target.db"
    _seed(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        assert catalog_summary(conn)[0]["item_count"] == 1
        assert catalog_items(conn, limit=5)[0]["title"] == "Ranking agents well"
        assert topics(conn)[0]["scored_items"] == 1
        assert top_scores(conn, limit=5)[0]["topic_score"] == 0.75
        assert users(conn)[0]["identifier"] == "vb"
        assert subscriptions(conn, user="vb")[0]["topic"] == "AI"
        assert digests(conn, user="vb")[0]["item_count"] == 1
        assert digest_items(conn, digest_id=1)[0]["rank"] == 1
        assert feedback(conn, user="vb", action="delivered")[0]["action"] == "delivered"
    finally:
        conn.close()


def test_catalog_and_score_queries_support_date_filters(tmp_path):
    db_path = tmp_path / "target.db"
    _seed(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        assert catalog_items_filtered(conn, limit=5, since="2026-05-14")[0]["item_id"] == 1
        assert catalog_items_filtered(conn, limit=5, until="2026-05-13") == []
        assert top_scores_filtered(conn, limit=5, since="2026-05-14")[0]["item_id"] == 1
        assert top_scores_filtered(conn, limit=5, until="2026-05-13") == []
    finally:
        conn.close()


def test_fetched_items_query_supports_browse_filters(tmp_path):
    db_path = tmp_path / "target.db"
    _seed(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        assert fetched_items_filtered(conn, limit=5, fetch_date="2026-05-14")[0]["item_id"] == 1
        assert fetched_items_filtered(conn, limit=5, fetch_date="2026-05-14", min_score=100) == []
        assert fetched_items_filtered(conn, limit=5, fetch_date="2026-05-14", topic="AI")[0]["topic"] == "AI"
        assert fetched_items_filtered(conn, limit=5, fetch_date="2026-05-14", min_topic_score=0.8) == []
        assert fetched_items_filtered(conn, limit=5, fetch_date="2026-05-14", title="agents")[0]["item_id"] == 1
        assert fetched_items_filtered(conn, limit=5, fetch_date="2026-05-14", source="substack") == []
        assert fetched_items_filtered(conn, limit=5, fetch_date="2026-05-14", source_api="hackernews_firebase")[0]["item_id"] == 1
        assert fetched_items_filtered(conn, limit=5, fetch_date="2026-05-14", source_api="hackernews_algolia") == []
    finally:
        conn.close()
