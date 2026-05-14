import json
import sqlite3

from knowledge_os.feedback_events import sync_markdown_feedback
from knowledge_os.render_digest import load_digest_items, render_digest_file, render_digest_text
from knowledge_os.schema import init_target_schema


def _seed_digest(db_path):
    init_target_schema(str(db_path))
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO authors (source, author_name)
            VALUES ('hackernews', 'alice')
            """
        )
        conn.execute(
            """
            INSERT INTO items
              (url, title, source, external_id, author_id, author_name, score, comment_count,
               item_text, fetched_at, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://example.com/story",
                "Useful ranking systems",
                "hackernews",
                "123",
                1,
                "alice",
                42,
                7,
                "body",
                "2026-05-13T00:00:00",
                "2026-05-13T00:00:00",
            ),
        )
        conn.execute(
            "INSERT INTO topics (name, keywords_json) VALUES (?, ?)",
            ("AI", json.dumps(["ranking"])),
        )
        conn.execute("INSERT INTO users (identifier, timezone) VALUES ('vb', 'Asia/Calcutta')")
        conn.execute(
            """
            INSERT INTO digests (user_id, generated_at, status, metadata_json)
            VALUES (1, '2026-05-13T12:00:00', 'generated', '{}')
            """
        )
        conn.execute(
            """
            INSERT INTO digest_items
              (digest_id, item_id, topic_id, topic_score, rank, selection_reason_json)
            VALUES (1, 1, 1, 0.8123, 1, '{}')
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_render_digest_text_groups_items_by_topic(tmp_path):
    db_path = tmp_path / "target.db"
    _seed_digest(db_path)

    digest, rows = load_digest_items(str(db_path), user="vb", digest_id=1)
    text = render_digest_text(digest, rows)

    assert "🦅 *Knowledge Digest* - 2026-05-13" in text
    assert "_1 selected item · digest_id: 1_" in text
    assert "*AI*" in text
    assert "- [ ] Useful ranking systems" in text
    assert "topic: 0.812" in text
    assert "🔗 https://example.com/story" in text
    assert "→ HN: https://news.ycombinator.com/item?id=123" in text


def test_render_digest_file_is_feedback_sync_compatible(tmp_path):
    db_path = tmp_path / "target.db"
    output = tmp_path / "digest.md"
    _seed_digest(db_path)

    path = render_digest_file(
        str(db_path),
        user="vb",
        digest_id=1,
        output=str(output),
    )
    text = path.read_text()
    path.write_text(text.replace("- [ ] Useful ranking systems", "- [x] Useful ranking systems"))

    assert sync_markdown_feedback(str(db_path), "vb", str(path), digest_id=1) == 1

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT item_id, digest_id, action FROM feedback WHERE action = 'read'"
        ).fetchone()
        assert row == (1, 1, "read")
    finally:
        conn.close()


def test_render_digest_file_defaults_to_user_scoped_output(tmp_path, monkeypatch):
    db_path = tmp_path / "target.db"
    _seed_digest(db_path)
    monkeypatch.chdir(tmp_path)

    path = render_digest_file(str(db_path), user="vb", digest_id=1)

    assert path.as_posix() == "knos-digest/vb/2026-05-13.md"
    assert path.exists()
