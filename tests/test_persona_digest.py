import json
import sqlite3
from datetime import date

from knowledge_os.persona_digest import (
    parse_persona_markdown,
    render_persona_digest_file,
    render_persona_digest_text,
    select_persona_items,
    whatsapp_summary,
)
from knowledge_os.schema import init_target_schema


def _write_catalog(path):
    path.write_text(json.dumps({
        "personas": {
            "ai_researcher": {
                "name": "AI Research",
                "selection": {
                    "min_topic_score": 0.4,
                    "freshness_days": 30,
                    "sources": ["hackernews"],
                    "max_items": 5,
                },
                "topics": [{
                    "name": "AI Research",
                    "description": "AI research",
                    "keywords": ["benchmarks"],
                }],
            },
            "ux_design": {
                "name": "UX / Design",
                "selection": {
                    "min_topic_score": 0.3,
                    "freshness_days": 30,
                    "sources": ["hackernews", "substack"],
                    "max_items": 5,
                },
                "topics": [{
                    "name": "UX / Design",
                    "description": "Design craft",
                    "keywords": ["interfaces"],
                }],
            },
        }
    }))


def _seed_scores(db_path):
    init_target_schema(str(db_path))
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO items
              (url, title, source, external_id, author_name, score, item_text, fetched_at, published_at)
            VALUES
              ('https://example.com/a', 'Shared AI UX story', 'hackernews', '101', 'alice', 50, 'body', '2026-05-25T00:00:00', '2026-05-25T00:00:00'),
              ('https://example.com/b', 'Pure design story', 'substack', '', 'bea', 0, 'body', '2026-05-24T00:00:00', '2026-05-24T00:00:00')
            """
        )
        conn.execute("INSERT INTO topics (name, keywords_json) VALUES ('AI Research', '[]')")
        conn.execute("INSERT INTO topics (name, keywords_json) VALUES ('UX / Design', '[]')")
        conn.execute("INSERT INTO topic_scoring_configs (name, model, content_fields_json) VALUES ('test', 'model', '[]')")
        conn.execute(
            """
            INSERT INTO item_topic_scores (item_id, topic_id, scoring_config_id, score)
            VALUES
              (1, 1, 1, 0.72),
              (1, 2, 1, 0.71),
              (2, 2, 1, 0.52)
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_select_persona_items_assigns_each_story_to_one_persona(tmp_path):
    db_path = tmp_path / "target.db"
    catalog_path = tmp_path / "catalog.json"
    _write_catalog(catalog_path)
    _seed_scores(db_path)

    selected = select_persona_items(str(db_path), str(catalog_path), today=date(2026, 5, 25))

    assert [(item.title, item.persona_id) for item in selected] == [
        ("Shared AI UX story", "ai_researcher"),
        ("Pure design story", "ux_design"),
    ]


def test_render_persona_digest_file_writes_combined_markdown(tmp_path, monkeypatch):
    db_path = tmp_path / "target.db"
    catalog_path = tmp_path / "catalog.json"
    _write_catalog(catalog_path)
    _seed_scores(db_path)
    monkeypatch.chdir(tmp_path)

    path = render_persona_digest_file(
        str(db_path),
        str(catalog_path),
        digest_date="2026-05-25",
    )

    assert path.as_posix() == "knos-digest/2026-05-25.md"
    text = path.read_text()
    assert "<!-- knos-persona: ai_researcher | AI Research -->" in text
    assert "## UX / Design" in text
    assert "- [ ] Shared AI UX story" in text
    assert "- [ ] 📰 Pure design story" in text
    parsed = parse_persona_markdown(str(path))
    assert parsed[0]["persona_id"] == "ai_researcher"
    assert parsed[1]["persona_id"] == "ux_design"


def test_whatsapp_summary_uses_user_persona_url(tmp_path):
    catalog_path = tmp_path / "catalog.json"
    digest_path = tmp_path / "digest.md"
    user_path = tmp_path / "user.json"
    _write_catalog(catalog_path)
    digest_path.write_text(render_persona_digest_text([
        type("Row", (), {
            "persona_id": "ux_design",
            "persona_name": "UX / Design",
            "topic_name": "UX / Design",
            "topic_score": 0.52,
            "item_id": 1,
            "title": "Pure design story",
            "url": "https://example.com/b",
            "source": "substack",
            "external_id": "",
            "author_name": "bea",
            "item_score": 0,
            "published_at": "2026-05-24T00:00:00",
        })(),
    ], "2026-05-25", str(catalog_path)))
    user_path.write_text(json.dumps({
        "user": {"identifier": "kintu", "personas": ["ux_design"]},
        "delivery": {"base_url": "https://www.bvaibhav.info/knos-digest"},
    }))

    summary = whatsapp_summary(str(user_path), str(digest_path))

    assert summary["website_url"] == "https://www.bvaibhav.info/knos-digest?personas=ux_design"
    assert summary["item_count"] == 1
    assert "Pure design story" in summary["message"]
