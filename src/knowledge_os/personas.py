#!/usr/bin/env python3
"""Materialize persona/user config into global topics and subscriptions."""
import argparse
import json
import sqlite3
import sys
from datetime import datetime
from typing import Dict, Iterable, List

from .schema import init_target_schema


def _log(message: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] [personas] {message}", file=sys.stderr)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _load(path: str) -> Dict:
    with open(path) as f:
        return json.load(f)


def _topic_key(topic: Dict) -> str:
    return topic["name"].strip().lower()


def resolve_topics(persona_catalog: Dict, user_config: Dict) -> List[Dict]:
    """Resolve user personas + personal_topics into a deduped global topic list."""
    user = user_config["user"]
    merged: Dict[str, Dict] = {}

    for persona_id in user.get("personas", []):
        persona = persona_catalog.get("personas", {}).get(persona_id)
        if not persona:
            raise ValueError(f"Unknown persona: {persona_id}")
        for topic in persona.get("topics", []):
            topic = dict(topic)
            topic.setdefault("origin_type", "persona")
            topic.setdefault("origin_id", persona_id)
            key = _topic_key(topic)
            if key in merged:
                existing = merged[key]
                existing["keywords"] = sorted(set(existing.get("keywords", [])) | set(topic.get("keywords", [])))
                existing.setdefault("origins", []).append({"type": "persona", "id": persona_id})
            else:
                topic["origins"] = [{"type": "persona", "id": persona_id}]
                merged[key] = topic

    for topic in user.get("personal_topics", []):
        topic = dict(topic)
        topic.setdefault("origin_type", "personal_topic")
        topic.setdefault("origin_id", user["identifier"])
        key = _topic_key(topic)
        if key in merged:
            existing = merged[key]
            existing["keywords"] = sorted(set(existing.get("keywords", [])) | set(topic.get("keywords", [])))
            existing.setdefault("origins", []).append({"type": "personal_topic", "id": user["identifier"]})
        else:
            topic["origins"] = [{"type": "personal_topic", "id": user["identifier"]}]
            merged[key] = topic

    return list(merged.values())


def _upsert_user(conn: sqlite3.Connection, user: Dict, delivery: Dict, digest: Dict) -> int:
    settings = {
        "personas": user.get("personas", []),
        "delivery": delivery,
        "digest": digest,
    }
    conn.execute(
        """
        INSERT INTO users (identifier, timezone, settings_json)
        VALUES (?, ?, ?)
        ON CONFLICT(identifier) DO UPDATE SET
            timezone = COALESCE(excluded.timezone, users.timezone),
            settings_json = excluded.settings_json
        """,
        (user["identifier"], user.get("timezone"), _json(settings)),
    )
    return int(conn.execute(
        "SELECT user_id FROM users WHERE identifier = ?",
        (user["identifier"],),
    ).fetchone()["user_id"])


def _upsert_topic(conn: sqlite3.Connection, topic: Dict) -> int:
    conn.execute(
        """
        INSERT INTO topics (name, description, keywords_json, default_weight, active)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(name) DO UPDATE SET
            description = excluded.description,
            keywords_json = excluded.keywords_json,
            default_weight = excluded.default_weight,
            active = 1,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            topic["name"],
            topic.get("description"),
            _json(topic.get("keywords", [])),
            float(topic.get("default_weight", topic.get("weight", 1.0))),
        ),
    )
    return int(conn.execute("SELECT topic_id FROM topics WHERE name = ?", (topic["name"],)).fetchone()["topic_id"])


def _subscription_defaults(user_config: Dict) -> Dict:
    subscriptions = user_config.get("subscriptions", {})
    if isinstance(subscriptions, dict):
        return subscriptions.get("defaults", {})
    return {}


def materialize_personas(db_path: str, catalog_path: str, user_config_path: str) -> Dict:
    """Upsert global topics and user subscriptions for one user config."""
    init_target_schema(db_path)
    _log(f"Loading persona catalog from {catalog_path}")
    catalog = _load(catalog_path)
    _log(f"Loading user config from {user_config_path}")
    user_config = _load(user_config_path)
    topics = resolve_topics(catalog, user_config)
    user = user_config["user"]
    delivery = user_config.get("delivery", {})
    digest = user_config.get("digest", {})
    defaults = _subscription_defaults(user_config)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _log(f"Materializing user={user['identifier']} personas={user.get('personas', [])}")
        user_id = _upsert_user(conn, user, delivery, digest)
        written_topics = 0
        written_subs = 0
        for topic in topics:
            topic_id = _upsert_topic(conn, topic)
            written_topics += 1
            for origin in topic.get("origins", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO topic_origins
                        (topic_id, origin_type, origin_id, metadata_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (topic_id, origin["type"], origin["id"], _json({"user": user["identifier"]})),
                )
            conn.execute(
                """
                INSERT INTO user_topic_subscriptions
                    (user_id, topic_id, min_topic_score, author_filter_json,
                     source_filter_json, freshness_days, max_items, suppress_delivered, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(user_id, topic_id) DO UPDATE SET
                    min_topic_score = excluded.min_topic_score,
                    author_filter_json = excluded.author_filter_json,
                    source_filter_json = excluded.source_filter_json,
                    freshness_days = excluded.freshness_days,
                    max_items = excluded.max_items,
                    suppress_delivered = excluded.suppress_delivered,
                    active = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    topic_id,
                    float(defaults.get("min_topic_score", 0.35)),
                    _json(defaults.get("authors", {"allow": [], "deny": []})),
                    _json(defaults.get("sources", ["hackernews", "substack"])),
                    int(defaults.get("freshness_days", 7)),
                    int(defaults.get("max_items", digest.get("max_items", 10))),
                    1 if defaults.get("suppress_delivered", True) else 0,
                ),
            )
            written_subs += 1
        conn.commit()
        _log(f"Materialized {written_topics} topic(s) and {written_subs} subscription(s)")
        return {
            "user": user["identifier"],
            "topics": written_topics,
            "subscriptions": written_subs,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize personas into global topics and subscriptions.")
    parser.add_argument("--db", default="knowledge_os.db")
    parser.add_argument("--catalog", default="personas/catalog.json")
    parser.add_argument("--user-config", required=True)
    args = parser.parse_args()

    result = materialize_personas(args.db, args.catalog, args.user_config)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
