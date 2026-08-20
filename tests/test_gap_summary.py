import sqlite3
from datetime import date

from knowledge_os.gap_summary import build_gap_summary, gap_dates, infer_since, render_text
from knowledge_os.schema import init_target_schema


def _seed(db_path):
    init_target_schema(str(db_path))
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO users (identifier) VALUES ('vb')")
        conn.execute(
            """
            INSERT INTO items
              (url, title, source, source_api, external_id, author_name, score, fetched_at, published_at)
            VALUES
              ('https://example.com/read', 'Read story', 'hackernews', 'hackernews_firebase', '1', 'alice', 90,
               '2026-08-01T00:00:00', '2026-08-01T00:00:00'),
              ('https://example.com/unscored', 'Unscored story', 'substack', 'rss', '', 'bea', 0,
               '2026-08-03T00:00:00', '2026-08-03T00:00:00'),
              ('https://example.com/no-digest', 'No digest story', 'hackernews', 'hackernews_algolia', '3', 'cam', 120,
               '2026-08-04T00:00:00', '2026-08-04T00:00:00')
            """
        )
        conn.execute("INSERT INTO topics (name, keywords_json) VALUES ('AI', '[]')")
        conn.execute("INSERT INTO topic_scoring_configs (name, model, content_fields_json) VALUES ('test', 'test', '[]')")
        conn.executemany(
            "INSERT INTO item_topic_scores (item_id, topic_id, scoring_config_id, score) VALUES (?, 1, 1, ?)",
            [(1, 0.8), (3, 0.7)],
        )
        conn.execute(
            "INSERT INTO feedback (user_id, item_id, action, created_at) VALUES (1, 1, 'read', '2026-08-02T10:00:00')"
        )
        conn.commit()
    finally:
        conn.close()


def _write_digest(path, title, checked):
    mark = "x" if checked else " "
    path.write_text(
        "\n".join([
            "*Knowledge Digest* - 2026-08-01",
            "",
            "<!-- knos-persona: ai_researcher | AI Research -->",
            "## AI Research",
            "",
            "*AI*",
            f"- [{mark}] {title}",
            "  published: 2026-08-01 | source: hackernews | by alice",
            "  https://example.com/read",
            "",
        ])
    )


def test_gap_summary_classifies_missing_ingest_digest_scoring_and_read_days(tmp_path):
    db_path = tmp_path / "knowledge.db"
    digest_dir = tmp_path / "knos-digest"
    digest_dir.mkdir()
    _seed(db_path)
    _write_digest(digest_dir / "2026-08-01.md", "Read story", checked=True)
    _write_digest(digest_dir / "2026-08-03.md", "Unread story", checked=False)

    report = build_gap_summary(
        db_path=str(db_path),
        digest_dir=str(digest_dir),
        since=date(2026, 8, 1),
        until=date(2026, 8, 4),
        users=["vb"],
    )

    assert report["summary"]["missing_ingest_days"] == ["2026-08-02"]
    assert report["summary"]["missing_digest_days"] == ["2026-08-02", "2026-08-04"]
    assert report["summary"]["unscored_ingest_days"] == ["2026-08-03"]
    assert report["summary"]["unread_digest_days"] == ["2026-08-03"]
    assert gap_dates(report, ["ingest", "digest"]) == ["2026-08-02", "2026-08-04"]
    assert "2026-08-03" in render_text(report)


def test_gap_summary_infers_since_after_latest_known_run(tmp_path):
    db_path = tmp_path / "knowledge.db"
    digest_dir = tmp_path / "knos-digest"
    digest_dir.mkdir()
    _seed(db_path)
    _write_digest(digest_dir / "2026-08-05.md", "Latest digest", checked=False)

    assert infer_since(str(db_path), str(digest_dir), date(2026, 8, 8)) == date(2026, 8, 6)
