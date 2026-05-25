#!/usr/bin/env python3
"""Materialize persona/user config into global topics and subscriptions."""
import argparse
import glob
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

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


def persona_selection(persona: Dict) -> Dict:
    """Return canonical selection defaults for a persona stream."""
    selection = dict(persona.get("selection", {}))
    selection.setdefault("min_topic_score", 0.35)
    selection.setdefault("freshness_days", 7)
    selection.setdefault("sources", ["hackernews", "substack"])
    selection.setdefault("max_items", 8)
    selection.setdefault("suppress_delivered", True)
    return selection


def validate_catalog(persona_catalog: Dict) -> None:
    """Require every topic to be owned by exactly one persona."""
    seen: Dict[str, str] = {}
    for persona_id, persona in persona_catalog.get("personas", {}).items():
        if not persona.get("topics"):
            raise ValueError(f"Persona has no topics: {persona_id}")
        for topic in persona.get("topics", []):
            key = _topic_key(topic)
            if key in seen:
                raise ValueError(
                    f"Topic '{topic['name']}' is owned by both '{seen[key]}' and '{persona_id}'"
                )
            seen[key] = persona_id


def iter_persona_topics(persona_catalog: Dict) -> Iterable[tuple[str, Dict, Dict]]:
    validate_catalog(persona_catalog)
    for persona_id, persona in persona_catalog.get("personas", {}).items():
        for topic in persona.get("topics", []):
            yield persona_id, persona, topic


def resolve_topics(persona_catalog: Dict, user_config: Dict) -> List[Dict]:
    """Resolve user personas into their catalog-owned topics."""
    validate_catalog(persona_catalog)
    user = user_config["user"]
    if user.get("personal_topics"):
        raise ValueError("personal_topics are no longer supported; create a catalog persona instead")

    resolved: List[Dict] = []

    for persona_id in user.get("personas", []):
        persona = persona_catalog.get("personas", {}).get(persona_id)
        if not persona:
            raise ValueError(f"Unknown persona: {persona_id}")
        for topic in persona.get("topics", []):
            topic = dict(topic)
            topic["persona_id"] = persona_id
            topic["persona_name"] = persona.get("name", persona_id)
            resolved.append(topic)

    return resolved


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


def _upsert_catalog_topics(conn: sqlite3.Connection, catalog: Dict) -> int:
    written = 0
    for persona_id, persona, topic in iter_persona_topics(catalog):
        topic_id = _upsert_topic(conn, topic)
        conn.execute(
            """
            INSERT OR REPLACE INTO topic_origins
                (topic_id, origin_type, origin_id, metadata_json)
            VALUES (?, 'persona', ?, ?)
            """,
            (
                topic_id,
                persona_id,
                _json({
                    "persona_name": persona.get("name", persona_id),
                    "selection": persona_selection(persona),
                }),
            ),
        )
        written += 1
    return written


def _load_user_configs(user_config_path: Optional[str], users_dir: Optional[str]) -> List[Dict]:
    paths: List[str] = []
    if user_config_path:
        paths.append(user_config_path)
    if users_dir:
        paths.extend(sorted(glob.glob(str(Path(users_dir) / "*.json"))))
    return [_load(path) for path in dict.fromkeys(paths)]


def _selection_for_topic(catalog: Dict, topic_name: str) -> Dict:
    key = topic_name.strip().lower()
    for _persona_id, persona, topic in iter_persona_topics(catalog):
        if _topic_key(topic) == key:
            return persona_selection(persona)
    raise ValueError(f"Topic is not owned by any persona: {topic_name}")


def materialize_personas(
    db_path: str,
    catalog_path: str,
    user_config_path: Optional[str] = None,
    users_dir: Optional[str] = None,
) -> Dict:
    """Upsert persona-owned topics and user persona subscriptions."""
    init_target_schema(db_path)
    _log(f"Loading persona catalog from {catalog_path}")
    catalog = _load(catalog_path)
    validate_catalog(catalog)
    user_configs = _load_user_configs(user_config_path, users_dir)
    for user_config in user_configs:
        _log(f"Loading user config for user={user_config['user']['identifier']}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _log("Materializing catalog persona topics")
        written_topics = _upsert_catalog_topics(conn, catalog)
        written_users = 0
        written_subs = 0
        for user_config in user_configs:
            user = user_config["user"]
            delivery = user_config.get("delivery", {})
            digest = user_config.get("digest", {})
            topics = resolve_topics(catalog, user_config)
            _log(f"Materializing user={user['identifier']} personas={user.get('personas', [])}")
            user_id = _upsert_user(conn, user, delivery, digest)
            written_users += 1
            conn.execute(
                """
                UPDATE user_topic_subscriptions
                SET active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (user_id,),
            )
            for topic in topics:
                topic_id = _upsert_topic(conn, topic)
                defaults = _selection_for_topic(catalog, topic["name"])
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
                        _json({"allow": [], "deny": []}),
                        _json(defaults.get("sources", ["hackernews", "substack"])),
                        int(defaults.get("freshness_days", 7)),
                        int(defaults.get("max_items", 8)),
                        1 if defaults.get("suppress_delivered", True) else 0,
                    ),
                )
                written_subs += 1
        conn.commit()
        _log(f"Materialized {written_topics} topic(s), {written_users} user(s), and {written_subs} subscription(s)")
        return {
            "topics": written_topics,
            "users": written_users,
            "subscriptions": written_subs,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize personas into global topics and subscriptions.")
    parser.add_argument("--db", default="knowledge_os.db")
    parser.add_argument("--catalog", default="personas/catalog.json")
    parser.add_argument("--user-config")
    parser.add_argument("--users-dir")
    args = parser.parse_args()

    result = materialize_personas(args.db, args.catalog, user_config_path=args.user_config, users_dir=args.users_dir)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
