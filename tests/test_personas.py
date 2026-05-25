import json
import sqlite3

from knowledge_os.personas import materialize_personas, resolve_topics, validate_catalog
from knowledge_os.schema import init_target_schema
from knowledge_os.topic_scoring import _load_active_topics


def test_resolve_topics_uses_catalog_personas_only():
    catalog = {
        "personas": {
            "llm_researcher": {
                "topics": [{"name": "AI/ML/LLMs", "keywords": ["agents"]}]
            },
            "ai_researcher": {
                "topics": [{"name": "AI Research", "keywords": ["benchmarks"]}]
            },
        }
    }
    user_config = {
        "user": {
            "identifier": "reader",
            "personas": ["llm_researcher", "ai_researcher"],
        }
    }

    topics = resolve_topics(catalog, user_config)

    assert [topic["name"] for topic in topics] == ["AI/ML/LLMs", "AI Research"]
    assert topics[0]["persona_id"] == "llm_researcher"


def test_validate_catalog_rejects_duplicate_topic_owners():
    catalog = {
        "personas": {
            "one": {"topics": [{"name": "AI", "keywords": ["agents"]}]},
            "two": {"topics": [{"name": " ai ", "keywords": ["benchmarks"]}]},
        }
    }

    try:
        validate_catalog(catalog)
    except ValueError as exc:
        assert "owned by both" in str(exc)
    else:
        raise AssertionError("expected duplicate topic validation failure")


def test_materialize_personas_creates_global_topics_and_subscriptions(tmp_path):
    db_path = tmp_path / "target.db"
    catalog_path = tmp_path / "catalog.json"
    user_path = tmp_path / "user.json"
    catalog_path.write_text(json.dumps({
        "personas": {
            "ux_design": {
                "name": "UX / Design",
                "selection": {
                    "min_topic_score": 0.32,
                    "freshness_days": 14,
                    "sources": ["substack"],
                    "max_items": 6,
                },
                "topics": [{
                    "name": "UX / Design",
                    "description": "Design craft",
                    "keywords": ["usability", "accessibility"],
                }]
            },
            "llm_researcher": {
                "topics": [{
                    "name": "AI/ML/LLMs",
                    "description": "LLMs",
                    "keywords": ["agents"],
                }]
            }
        }
    }))
    user_path.write_text(json.dumps({
        "user": {
            "identifier": "kintu",
            "timezone": "Asia/Calcutta",
            "personas": ["ux_design"],
        },
        "digest": {"max_items": 12},
        "delivery": {"type": "website_link"},
    }))

    result = materialize_personas(str(db_path), str(catalog_path), user_config_path=str(user_path))

    assert result == {"topics": 2, "users": 1, "subscriptions": 1}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        sub = conn.execute(
            """
            SELECT u.identifier, t.name, s.min_topic_score, s.source_filter_json
            FROM user_topic_subscriptions s
            JOIN users u ON u.user_id = s.user_id
            JOIN topics t ON t.topic_id = s.topic_id
            """
        ).fetchone()
        assert tuple(sub) == ("kintu", "UX / Design", 0.32, '["substack"]')
        origin = conn.execute(
            """
            SELECT o.origin_type, o.origin_id, o.metadata_json
            FROM topic_origins o
            JOIN topics t ON t.topic_id = o.topic_id
            WHERE t.name = 'UX / Design'
            """
        ).fetchone()
        assert tuple(origin)[:2] == ("persona", "ux_design")
        assert json.loads(origin["metadata_json"])["persona_name"] == "UX / Design"
        active_topics = _load_active_topics(conn)
        assert [topic["name"] for topic in active_topics] == ["AI/ML/LLMs", "UX / Design"]
    finally:
        conn.close()
