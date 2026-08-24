import json
import sqlite3
from collections import Counter
from datetime import date, datetime, timezone

from knowledge_os.launch_health import _user_health, build_launch_health
from knowledge_os.persona_digest import select_persona_items
from knowledge_os.schema import init_target_schema


def _catalog():
    return {
        "personas": {
            "daily": {
                "name": "Daily",
                "selection": {
                    "min_topic_score": 0.5,
                    "cadence": "daily",
                    "sources": ["hackernews"],
                    "max_items": 5,
                },
                "topics": [{"name": "Daily topic", "keywords": ["daily"]}],
            },
            "weekly": {
                "name": "Weekly",
                "selection": {
                    "min_topic_score": 0.5,
                    "cadence": "weekly",
                    "send_days": ["mon"],
                    "sources": ["substack"],
                    "max_items": 5,
                },
                "topics": [{"name": "Weekly topic", "keywords": ["weekly"]}],
            },
        }
    }


def _config(user_id, personas):
    return {"user": {"identifier": user_id, "personas": personas}}


def _seed(db_path):
    init_target_schema(str(db_path))
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO items
              (url, title, source, source_api, external_id, score, fetched_at, published_at)
            VALUES
              ('https://example.com/a', 'Selected', 'hackernews', 'hackernews_firebase', '1', 20,
               '2026-06-22T08:00:00', '2026-06-22T07:00:00'),
              ('https://example.com/b', 'Low score', 'hackernews', 'hackernews_firebase', '2', 10,
               '2026-06-22T08:00:00', '2026-06-22T07:00:00'),
              ('https://example.com/c', 'Wrong source', 'substack', 'rss', '', 0,
               '2026-06-22T08:00:00', '2026-06-22T07:00:00')
            """
        )
        conn.execute("INSERT INTO topics (name, keywords_json) VALUES ('Daily topic', '[]')")
        conn.execute("INSERT INTO topic_scoring_configs (name, model, content_fields_json) VALUES ('test', 'test', '[]')")
        conn.executemany(
            "INSERT INTO item_topic_scores (item_id, topic_id, scoring_config_id, score) VALUES (?, 1, 1, ?)",
            [(1, 0.8), (2, 0.2), (3, 0.9)],
        )
        conn.commit()
    finally:
        conn.close()


def test_launch_health_report_matches_renderer_selection(tmp_path):
    db_path = tmp_path / "health.db"
    catalog_path = tmp_path / "catalog.json"
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    catalog_path.write_text(json.dumps(_catalog()))
    (users_dir / "vb.json").write_text(json.dumps(_config("vb", ["daily"])))
    _seed(db_path)

    report = build_launch_health(
        str(db_path), str(catalog_path), str(users_dir), ["vb"], date(2026, 6, 22)
    )
    selected = select_persona_items(str(db_path), str(catalog_path), date(2026, 6, 22))

    assert set(report) >= {
        "catalog", "scoring", "selection", "users", "status", "operational_status", "operations"
    }
    assert report["catalog"]["counts_by_source"] == {"hackernews": 2, "substack": 1}
    assert report["catalog"]["counts_by_source_api"] == {"hackernews_firebase": 2, "rss": 1}
    assert report["scoring"]["counts_by_topic"]["Daily topic"] == 3
    assert report["selection"]["selected_count"] == len(selected) == 1
    assert report["selection"]["candidates_before_filters"] == 3
    assert report["selection"]["candidates_after_filters"] == 1
    assert report["selection"]["drop_reasons"]["score_threshold"] == 1
    assert report["selection"]["drop_reasons"]["source_filter"] == 1
    assert report["users"]["vb"]["status"] == "low"


def test_user_risk_statuses_cover_ok_low_empty_not_scheduled_and_stale():
    catalog = _catalog()
    configs = {
        "ok": _config("ok", ["daily"]),
        "low": _config("low", ["weekly"]),
        "empty": _config("empty", ["daily", "weekly"]),
    }
    monday = date(2026, 6, 22)

    health = _user_health(catalog, configs, Counter({"daily": 2, "weekly": 1}), monday, False)
    assert health["ok"]["status"] == "ok"
    assert health["low"]["status"] == "low"

    empty = _user_health(catalog, {"empty": configs["empty"]}, Counter(), monday, False)
    assert empty["empty"]["status"] == "empty"
    assert empty["empty"]["empty_digest_risk"] is True

    tuesday = _user_health(catalog, {"weekly": _config("weekly", ["weekly"])}, Counter(), date(2026, 6, 23), False)
    assert tuesday["weekly"]["status"] == "not_scheduled"

    stale = _user_health(catalog, {"ok": configs["ok"]}, Counter({"daily": 2}), monday, True)
    assert stale["ok"]["status"] == "stale_catalog"


def test_launch_health_reports_ingest_and_delivery_provenance(tmp_path):
    db_path = tmp_path / "health.db"
    catalog_path = tmp_path / "catalog.json"
    users_dir = tmp_path / "users"
    state_dir = tmp_path / "state"
    users_dir.mkdir()
    state_dir.mkdir()
    catalog_path.write_text(json.dumps(_catalog()))
    user = _config("vb", ["daily"])
    user["delivery"] = {
        "schedule": {"cadence": "daily", "time": "14:00", "timezone": "Asia/Kolkata"}
    }
    (users_dir / "vb.json").write_text(json.dumps(user))
    _seed(db_path)
    (state_dir / "ingest-2026-06-22.env").write_text("""date=2026-06-22
status=succeeded
trigger=automatic
trigger_evidence=process_ancestry
started_at=2026-06-22T09:00:00+0530
completed_at=2026-06-22T09:04:30+0530
website_workflow_status=triggered
""")
    (state_dir / "delivery-2026-06-22-vb.json").write_text(json.dumps({
        "user": "vb",
        "digest_date": "2026-06-22",
        "status": "delivered",
        "trigger": "automatic",
        "started_at": "2026-06-22T08:30:00Z",
        "sent_at": "2026-06-22T08:30:02Z",
        "receipt_at": "2026-06-22T08:30:03Z",
        "receipt_status": "delivery_ack",
    }))

    report = build_launch_health(
        str(db_path),
        str(catalog_path),
        str(users_dir),
        ["vb"],
        date(2026, 6, 22),
        state_dir=str(state_dir),
        now=datetime(2026, 6, 22, 10, tzinfo=timezone.utc),
    )

    assert report["operational_status"] == "ok"
    assert report["operations"]["ingest"]["trigger"] == "automatic"
    assert report["operations"]["ingest"]["duration_seconds"] == 270
    delivery = report["users"]["vb"]["delivery"]
    assert delivery["status"] == "delivered"
    assert delivery["scheduled_at"] == "2026-06-22T14:00:00+05:30"
    assert delivery["sent_at"] == "2026-06-22T08:30:02Z"
    assert delivery["receipt_status"] == "delivery_ack"
    assert delivery["trigger"] == "automatic"
