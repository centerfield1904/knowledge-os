"""Tests for digest runtime context assembly."""
from knowledge_os.digest_context import build_digest_context, ensure_topics
from knowledge_os.storage_sqlite import SQLiteStorage


def _config(db_path):
    return {
        "storage": {
            "backend": "sqlite",
            "sqlite": {"db_path": str(db_path)},
        },
        "user": {
            "identifier": "reader@example.com",
            "timezone": "Asia/Calcutta",
        },
        "topics": [
            {"name": "AI", "keywords": ["machine learning"], "weight": 1.2},
            {"name": "Design", "keywords": ["ux", "accessibility"]},
        ],
        "settings": {
            "similarity_threshold": 0.3,
            "notable_author_threshold": 3,
        },
    }


def test_build_digest_context_creates_user_and_topics(tmp_path):
    config = _config(tmp_path / "test.db")

    context = build_digest_context(config)

    assert context.user_id >= 1
    assert context.config is config
    assert len(context.topics) == 2
    assert [topic["name"] for topic in context.topics] == ["AI", "Design"]
    assert context.topics[0]["weight"] == 1.2


def test_ensure_topics_preserves_existing_topics(tmp_path):
    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    user_id = storage.get_or_create_user("reader@example.com")
    storage.insert_topic(user_id, "Existing", ["already here"], weight=1.0)

    config = _config(tmp_path / "test.db")
    context = build_digest_context(config)

    assert [topic["name"] for topic in context.topics] == ["Existing"]
    assert len(storage.get_topics(user_id)) == 1


def test_ensure_topics_empty_input_returns_existing_topics(tmp_path):
    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    user_id = storage.get_or_create_user("reader@example.com")

    assert ensure_topics(storage, user_id, []) == []
