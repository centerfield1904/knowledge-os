import json
import sqlite3
from datetime import date

import pytest

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
                    "cadence": "daily",
                    "freshness_days": 1,
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
                    "cadence": "weekly",
                    "send_days": ["mon"],
                    "freshness_days": 7,
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


def _write_custom_catalog(path, personas):
    path.write_text(json.dumps({"personas": personas}))


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
              ('https://example.com/b', 'Pure design story', 'substack', '', 'bea', 0, 'body', '2026-05-24T00:00:00', '2026-05-24T00:00:00'),
              ('https://example.com/c', 'Older AI story', 'hackernews', '102', 'cam', 80, 'body', '2026-05-25T00:00:00', '2026-05-24T00:00:00'),
              ('https://example.com/d', 'Stale design story', 'substack', '', 'dee', 90, 'body', '2026-05-25T00:00:00', '2026-05-18T00:00:00')
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
              (2, 2, 1, 0.52),
              (3, 1, 1, 0.80),
              (4, 2, 1, 0.90)
            """
        )
        conn.commit()
    finally:
        conn.close()


def _seed_selection_edge_cases(db_path):
    init_target_schema(str(db_path))
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO items
              (url, title, source, external_id, author_name, score, item_text, fetched_at, published_at)
            VALUES
              ('https://example.com/pass-ai', 'Good daily AI story', 'hackernews', '201', 'alice', 50, 'body', '2026-05-25T00:00:00', '2026-05-25T00:00:00'),
              ('https://example.com/low-ai', 'Low score AI story', 'hackernews', '202', 'bea', 60, 'body', '2026-05-25T00:00:00', '2026-05-25T00:00:00'),
              ('https://example.com/source-ai', 'Wrong source AI story', 'substack', '', 'cam', 0, 'body', '2026-05-25T00:00:00', '2026-05-25T00:00:00'),
              ('https://example.com/missing-ai', 'Missing published AI story', 'hackernews', '203', 'dee', 70, 'body', '2026-05-25T00:00:00', NULL),
              ('https://example.com/old-ai', 'Previous day AI story', 'hackernews', '204', 'eli', 80, 'body', '2026-05-25T00:00:00', '2026-05-24T00:00:00'),
              ('https://example.com/stale-fetch-ai', 'Stale fetched AI story', 'hackernews', '205', 'fay', 85, 'body', '2026-05-24T00:00:00', '2026-05-25T00:00:00'),
              ('https://example.com/pass-ux', 'Weekly in-window design story', 'substack', '', 'fay', 0, 'body', '2026-05-25T00:00:00', '2026-05-20T00:00:00'),
              ('https://example.com/stale-ux', 'Weekly stale design story', 'substack', '', 'gus', 0, 'body', '2026-05-25T00:00:00', '2026-05-18T00:00:00'),
              ('https://example.com/missing-ux', 'Missing published design story', 'substack', '', 'hal', 0, 'body', '2026-05-25T00:00:00', NULL),
              ('https://example.com/security', 'Ignored security story', 'hackernews', '206', 'ian', 90, 'body', '2026-05-25T00:00:00', '2026-05-25T00:00:00')
            """
        )
        conn.execute("INSERT INTO topics (name, keywords_json) VALUES ('AI Research', '[]')")
        conn.execute("INSERT INTO topics (name, keywords_json) VALUES ('UX / Design', '[]')")
        conn.execute("INSERT INTO topics (name, keywords_json) VALUES ('Security', '[]')")
        conn.execute("INSERT INTO topic_scoring_configs (name, model, content_fields_json) VALUES ('test', 'model', '[]')")
        conn.execute(
            """
            INSERT INTO item_topic_scores (item_id, topic_id, scoring_config_id, score)
            VALUES
              (1, 1, 1, 0.72),
              (2, 1, 1, 0.39),
              (3, 1, 1, 0.80),
              (4, 1, 1, 0.80),
              (5, 1, 1, 0.90),
              (6, 1, 1, 0.85),
              (7, 2, 1, 0.52),
              (8, 2, 1, 0.90),
              (9, 2, 1, 0.50),
              (10, 3, 1, 0.95)
            """
        )
        conn.commit()
    finally:
        conn.close()


def _seed_two_daily_ai_items(db_path):
    init_target_schema(str(db_path))
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO items
              (url, title, source, external_id, author_name, score, item_text, fetched_at, published_at)
            VALUES
              ('https://example.com/best-ai', 'Best AI story', 'hackernews', '301', 'alice', 20, 'body', '2026-05-25T00:00:00', '2026-05-25T00:00:00'),
              ('https://example.com/second-ai', 'Second AI story', 'hackernews', '302', 'bea', 500, 'body', '2026-05-25T00:00:00', '2026-05-25T00:00:00')
            """
        )
        conn.execute("INSERT INTO topics (name, keywords_json) VALUES ('AI Research', '[]')")
        conn.execute("INSERT INTO topic_scoring_configs (name, model, content_fields_json) VALUES ('test', 'model', '[]')")
        conn.execute(
            """
            INSERT INTO item_topic_scores (item_id, topic_id, scoring_config_id, score)
            VALUES
              (1, 1, 1, 0.91),
              (2, 1, 1, 0.89)
            """
        )
        conn.commit()
    finally:
        conn.close()


def _seed_weekly_hn_items(db_path):
    init_target_schema(str(db_path))
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO items
              (url, title, source, external_id, author_name, score, item_text, fetched_at, published_at)
            VALUES
              ('https://example.com/weekly-hn-in-window', 'Weekly HN fetched in window', 'hackernews', '401', 'alice', 100, 'body', '2026-05-20T00:00:00', '2026-05-01T00:00:00'),
              ('https://example.com/weekly-hn-outside-window', 'Weekly HN fetched outside window', 'hackernews', '402', 'bea', 200, 'body', '2026-05-18T00:00:00', '2026-05-25T00:00:00')
            """
        )
        conn.execute("INSERT INTO topics (name, keywords_json) VALUES ('AI Research', '[]')")
        conn.execute("INSERT INTO topic_scoring_configs (name, model, content_fields_json) VALUES ('test', 'model', '[]')")
        conn.execute(
            """
            INSERT INTO item_topic_scores (item_id, topic_id, scoring_config_id, score)
            VALUES
              (1, 1, 1, 0.80),
              (2, 1, 1, 0.90)
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
        ("Older AI story", "ai_researcher"),
        ("Shared AI UX story", "ai_researcher"),
        ("Pure design story", "ux_design"),
    ]


def test_select_persona_items_only_uses_published_at_cadence_window(tmp_path):
    db_path = tmp_path / "target.db"
    catalog_path = tmp_path / "catalog.json"
    _write_catalog(catalog_path)
    _seed_scores(db_path)

    selected = select_persona_items(str(db_path), str(catalog_path), today=date(2026, 5, 26))

    assert selected == []


def test_select_persona_items_uses_fetched_at_for_hackernews_and_published_at_for_other_sources(tmp_path):
    db_path = tmp_path / "target.db"
    catalog_path = tmp_path / "catalog.json"
    _write_catalog(catalog_path)
    _seed_selection_edge_cases(db_path)

    selected = select_persona_items(str(db_path), str(catalog_path), today=date(2026, 5, 25))

    assert [(item.title, item.persona_id) for item in selected] == [
        ("Previous day AI story", "ai_researcher"),
        ("Missing published AI story", "ai_researcher"),
        ("Good daily AI story", "ai_researcher"),
        ("Weekly in-window design story", "ux_design"),
    ]
    assert "Stale fetched AI story" not in [item.title for item in selected]
    assert "Missing published design story" not in [item.title for item in selected]


def test_select_persona_items_uses_fetched_at_for_weekly_hackernews(tmp_path):
    db_path = tmp_path / "target.db"
    catalog_path = tmp_path / "catalog.json"
    _write_custom_catalog(
        catalog_path,
        {
            "ai_researcher": {
                "name": "AI Research",
                "selection": {
                    "min_topic_score": 0.4,
                    "cadence": "weekly",
                    "send_days": ["mon"],
                    "freshness_days": 7,
                    "sources": ["hackernews"],
                    "max_items": 5,
                },
                "topics": [{
                    "name": "AI Research",
                    "description": "AI research",
                    "keywords": ["benchmarks"],
                }],
            }
        },
    )
    _seed_weekly_hn_items(db_path)

    selected = select_persona_items(str(db_path), str(catalog_path), today=date(2026, 5, 25))

    assert [item.title for item in selected] == ["Weekly HN fetched in window"]


def test_select_persona_items_respects_weekly_send_day(tmp_path):
    db_path = tmp_path / "target.db"
    catalog_path = tmp_path / "catalog.json"
    _write_catalog(catalog_path)
    _seed_selection_edge_cases(db_path)

    selected = select_persona_items(str(db_path), str(catalog_path), today=date(2026, 5, 26))

    assert selected == []


def test_select_persona_items_ignores_scored_topics_not_in_catalog(tmp_path):
    db_path = tmp_path / "target.db"
    catalog_path = tmp_path / "catalog.json"
    _write_catalog(catalog_path)
    _seed_selection_edge_cases(db_path)

    selected = select_persona_items(str(db_path), str(catalog_path), today=date(2026, 5, 25))

    assert "Ignored security story" not in [item.title for item in selected]


def test_select_persona_items_applies_per_persona_max_items(tmp_path):
    db_path = tmp_path / "target.db"
    catalog_path = tmp_path / "catalog.json"
    _write_custom_catalog(
        catalog_path,
        {
            "ai_researcher": {
                "name": "AI Research",
                "selection": {
                    "min_topic_score": 0.4,
                    "cadence": "daily",
                    "freshness_days": 1,
                    "sources": ["hackernews"],
                    "max_items": 1,
                },
                "topics": [{
                    "name": "AI Research",
                    "description": "AI research",
                    "keywords": ["benchmarks"],
                }],
            }
        },
    )
    _seed_two_daily_ai_items(db_path)

    selected = select_persona_items(str(db_path), str(catalog_path), today=date(2026, 5, 25))

    assert [item.title for item in selected] == ["Best AI story"]


def test_select_persona_items_raises_for_invalid_send_day(tmp_path):
    db_path = tmp_path / "target.db"
    catalog_path = tmp_path / "catalog.json"
    _write_custom_catalog(
        catalog_path,
        {
            "ux_design": {
                "name": "UX / Design",
                "selection": {
                    "min_topic_score": 0.3,
                    "cadence": "weekly",
                    "send_days": ["funday"],
                    "freshness_days": 7,
                    "sources": ["substack"],
                    "max_items": 5,
                },
                "topics": [{
                    "name": "UX / Design",
                    "description": "Design craft",
                    "keywords": ["interfaces"],
                }],
            }
        },
    )
    _seed_selection_edge_cases(db_path)

    with pytest.raises(ValueError, match="Unsupported send day"):
        select_persona_items(str(db_path), str(catalog_path), today=date(2026, 5, 25))


def test_select_persona_items_raises_for_unknown_cadence(tmp_path):
    db_path = tmp_path / "target.db"
    catalog_path = tmp_path / "catalog.json"
    _write_custom_catalog(
        catalog_path,
        {
            "ai_researcher": {
                "name": "AI Research",
                "selection": {
                    "min_topic_score": 0.4,
                    "cadence": "monthly",
                    "freshness_days": 30,
                    "sources": ["hackernews"],
                    "max_items": 5,
                },
                "topics": [{
                    "name": "AI Research",
                    "description": "AI research",
                    "keywords": ["benchmarks"],
                }],
            }
        },
    )
    _seed_selection_edge_cases(db_path)

    with pytest.raises(ValueError, match="Unsupported persona cadence"):
        select_persona_items(str(db_path), str(catalog_path), today=date(2026, 5, 25))


def test_select_persona_items_logs_info_summary(tmp_path, capsys):
    db_path = tmp_path / "target.db"
    catalog_path = tmp_path / "catalog.json"
    _write_catalog(catalog_path)
    _seed_selection_edge_cases(db_path)

    select_persona_items(str(db_path), str(catalog_path), today=date(2026, 5, 25))

    captured = capsys.readouterr()
    assert "Selecting persona digest items" in captured.err
    assert "Persona selection summary:" in captured.err
    assert "scored_rows=10" in captured.err
    assert "unknown_topic_rows=1" in captured.err
    assert "selected_items=4" in captured.err
    assert "Candidate drop reasons:" in captured.err


def test_select_persona_items_debug_logs_candidate_decisions(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "target.db"
    catalog_path = tmp_path / "catalog.json"
    _write_catalog(catalog_path)
    _seed_selection_edge_cases(db_path)
    monkeypatch.setenv("KNOS_PERSONA_DIGEST_LOG_LEVEL", "DEBUG")

    select_persona_items(str(db_path), str(catalog_path), today=date(2026, 5, 25))

    captured = capsys.readouterr()
    assert "Accepted candidate" in captured.err
    assert "Dropped candidate" in captured.err
    assert "below_min_topic_score" in captured.err
    assert "source_not_allowed" in captured.err
    assert "missing_published_at" in captured.err
    assert "outside_cadence_window" in captured.err
    assert "cadence_field=fetched_at" in captured.err
    assert "cadence_field=published_at" in captured.err
    assert "Ignoring scored row for non-catalog topic='Security'" in captured.err


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
    assert "- [ ] Older AI story" in text
    assert "- [ ] 📰 Pure design story" in text
    parsed = parse_persona_markdown(str(path))
    assert parsed[0]["persona_id"] == "ai_researcher"
    assert parsed[1]["persona_id"] == "ai_researcher"
    assert parsed[2]["persona_id"] == "ux_design"


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


def test_whatsapp_summary_ranks_teasers_by_points_and_strips_emoji(tmp_path):
    users_dir = tmp_path / "users"
    users_dir.mkdir(exist_ok=True)
    _write_user(users_dir / "vb.json", "vb", ["ai_researcher"])
    digest = tmp_path / "2026-05-30.md"
    digest.write_text(
        "\n".join([
            "🦅 *Knowledge Digest* - 2026-05-30",
            "",
            "<!-- knos-persona: ai_researcher | AI / ML Researcher -->",
            "## AI / ML Researcher",
            "",
            "*AI Research*",
            "- [ ] Low signal piece",
            "  published: 2026-05-29 | source: hackernews | ↑10 | by a",
            "  🔗 https://example.com/low",
            "- [ ] 📰 Newsletter headliner",
            "  published: 2026-05-29 | source: substack | by b",
            "  🔗 https://example.com/news",
            "- [ ] High signal piece",
            "  published: 2026-05-29 | source: hackernews | ↑1989 | by c",
            "  🔗 https://example.com/high",
            "- [ ] Mid signal piece",
            "  published: 2026-05-29 | source: hackernews | ↑500 | by d",
            "  🔗 https://example.com/mid",
            "",
        ])
    )
    summary = whatsapp_summary(str(users_dir / "vb.json"), str(digest))
    lines = summary["message"].splitlines()
    teasers = [l[2:] for l in lines if l.startswith("- ")]
    # Top 3 by points, highest first; the 10-point item is dropped from teasers.
    assert teasers == ["High signal piece", "Mid signal piece", "Newsletter headliner"]
    # The leading source emoji must not appear in the teaser.
    assert "📰" not in summary["message"]
    # Four items total, so the footer advertises the full set, not "Read it here".
    assert "Full set (4):" in summary["message"]
    assert summary["message"].startswith("Made you a digest — a few worth a look:")
