import json
import sqlite3

from knowledge_os.personas import materialize_personas, resolve_topics
from knowledge_os.schema import init_target_schema
from knowledge_os.topic_scoring import _load_active_topics


def test_resolve_topics_dedupes_persona_and_personal_topics():
    catalog = {
        "personas": {
            "llm_researcher": {
                "topics": [{"name": "AI/ML/LLMs", "keywords": ["agents"]}]
            },
            "ai_researcher": {
                "topics": [{"name": "AI/ML/LLMs", "keywords": ["benchmarks"]}]
            },
        }
    }
    user_config = {
        "user": {
            "identifier": "reader",
            "personas": ["llm_researcher", "ai_researcher"],
            "personal_topics": [{"name": "Parenting", "keywords": ["schools"]}],
        }
    }

    topics = resolve_topics(catalog, user_config)

    assert [topic["name"] for topic in topics] == ["AI/ML/LLMs", "Parenting"]
    assert topics[0]["keywords"] == ["agents", "benchmarks"]


def test_materialize_personas_creates_global_topics_and_subscriptions(tmp_path):
    db_path = tmp_path / "target.db"
    catalog_path = tmp_path / "catalog.json"
    user_path = tmp_path / "user.json"
    catalog_path.write_text(json.dumps({
        "personas": {
            "ux_design": {
                "topics": [{
                    "name": "UX / Design",
                    "description": "Design craft",
                    "keywords": ["usability", "accessibility"],
                }]
            }
        }
    }))
    user_path.write_text(json.dumps({
        "user": {
            "identifier": "kintu",
            "timezone": "Asia/Calcutta",
            "personas": ["ux_design"],
            "personal_topics": [],
        },
        "subscriptions": {
            "defaults": {
                "min_topic_score": 0.32,
                "freshness_days": 14,
                "sources": ["substack"],
                "authors": {"allow": [], "deny": []},
                "max_items": 6,
                "suppress_delivered": True,
            }
        },
        "digest": {"max_items": 12},
        "delivery": {"type": "github_markdown", "path": "knos-digest/kintu"},
    }))

    result = materialize_personas(str(db_path), str(catalog_path), str(user_path))

    assert result == {"user": "kintu", "topics": 1, "subscriptions": 1}
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
            SELECT o.origin_type, o.origin_id
            FROM topic_origins o
            JOIN topics t ON t.topic_id = o.topic_id
            WHERE t.name = 'UX / Design'
            """
        ).fetchone()
        assert tuple(origin) == ("persona", "ux_design")
        active_topics = _load_active_topics(conn)
        assert active_topics[0]["name"] == "UX / Design"
    finally:
        conn.close()
