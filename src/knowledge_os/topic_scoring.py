#!/usr/bin/env python3
"""Python topic scoring module for ML-heavy matching."""
import argparse
import json
import sqlite3
import sys
from datetime import datetime
from typing import Dict, Iterable, List, Tuple

from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

from .schema import init_target_schema


def _log(message: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] [topic_scoring] {message}", file=sys.stderr)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _load_config(path: str) -> Dict:
    with open(path) as f:
        return json.load(f)


def _upsert_scoring_config(conn: sqlite3.Connection, cfg: Dict) -> int:
    scoring = cfg["topic_scoring"]
    name = scoring["config_name"]
    conn.execute(
        """
        INSERT INTO topic_scoring_configs
            (name, model, content_fields_json, scoring_params_json, active)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(name) DO UPDATE SET
            model = excluded.model,
            content_fields_json = excluded.content_fields_json,
            scoring_params_json = excluded.scoring_params_json,
            active = 1
        """,
        (
            name,
            scoring.get("model", "all-MiniLM-L6-v2"),
            _json(scoring.get("content_fields", ["title"])),
            _json({
                key: value
                for key, value in scoring.items()
                if key not in {"config_name", "model", "content_fields"}
            }),
        ),
    )
    row = conn.execute(
        "SELECT scoring_config_id FROM topic_scoring_configs WHERE name = ?",
        (name,),
    ).fetchone()
    return int(row["scoring_config_id"])


def _upsert_topics(conn: sqlite3.Connection, topics: List[Dict]) -> List[Dict]:
    result = []
    for topic in topics:
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
        row = conn.execute("SELECT * FROM topics WHERE name = ?", (topic["name"],)).fetchone()
        row_dict = dict(row)
        row_dict["keywords"] = json.loads(row_dict["keywords_json"])
        result.append(row_dict)
    return result


def _load_active_topics(conn: sqlite3.Connection) -> List[Dict]:
    rows = conn.execute(
        """
        SELECT *
        FROM topics
        WHERE active = 1
        ORDER BY name
        """
    ).fetchall()
    result = []
    for row in rows:
        row_dict = dict(row)
        row_dict["keywords"] = json.loads(row_dict["keywords_json"] or "[]")
        result.append(row_dict)
    return result


def _iter_items(conn: sqlite3.Connection, only_unscored: bool, scoring_config_id: int) -> Iterable[sqlite3.Row]:
    if only_unscored:
        return conn.execute(
            """
            SELECT i.*
            FROM items i
            WHERE NOT EXISTS (
                SELECT 1 FROM item_topic_scores s
                WHERE s.item_id = i.item_id
                  AND s.scoring_config_id = ?
            )
            ORDER BY COALESCE(i.published_at, i.fetched_at) DESC
            """,
            (scoring_config_id,),
        )
    return conn.execute("SELECT * FROM items ORDER BY COALESCE(published_at, fetched_at) DESC")


def _item_text(conn: sqlite3.Connection, item: sqlite3.Row, fields: List[str]) -> Tuple[str, Dict]:
    parts = []
    evidence = {"fields": []}

    if "title" in fields and item["title"]:
        parts.append(item["title"])
        evidence["fields"].append("title")
    if "item_text" in fields and item["item_text"]:
        parts.append(item["item_text"])
        evidence["fields"].append("item_text")
    if "author_metadata" in fields and item["author_id"]:
        author = conn.execute("SELECT * FROM authors WHERE author_id = ?", (item["author_id"],)).fetchone()
        if author:
            author_text = " ".join(str(author[key] or "") for key in ("author_name", "metadata_json"))
            if author_text.strip():
                parts.append(author_text)
                evidence["fields"].append("author_metadata")

    content_fields = [field for field in fields if field not in {"title", "item_text", "author_metadata"}]
    if content_fields:
        placeholders = ",".join("?" for _ in content_fields)
        rows = conn.execute(
            f"""
            SELECT content_type, content_text
            FROM item_content
            WHERE item_id = ?
              AND content_type IN ({placeholders})
            ORDER BY content_id
            """,
            (item["item_id"], *content_fields),
        ).fetchall()
        for row in rows:
            parts.append(row["content_text"])
            evidence["fields"].append(row["content_type"])

    return "\n".join(part for part in parts if part), evidence


def score_topics(db_path: str, config_path: str, only_unscored: bool = False) -> int:
    """Score catalog items against configured topics."""
    init_target_schema(db_path)
    _log(f"Loading scoring config from {config_path}")
    cfg = _load_config(config_path)
    scoring_cfg = cfg["topic_scoring"]
    fields = scoring_cfg.get("content_fields", ["title"])
    threshold = float(scoring_cfg.get("similarity_threshold", 0.0))
    model_name = scoring_cfg.get("model", "all-MiniLM-L6-v2")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        scoring_config_id = _upsert_scoring_config(conn, cfg)
        configured_topics = cfg.get("topics", [])
        topics = _upsert_topics(conn, configured_topics) if configured_topics else _load_active_topics(conn)
        conn.commit()
        if not topics:
            _log("No active topics found; wrote 0 scores")
            return 0

        items = list(_iter_items(conn, only_unscored, scoring_config_id))
        if not items:
            _log("No items to score; wrote 0 scores")
            return 0

        _log(f"Scoring {len(items)} item(s) against {len(topics)} topic(s) with {model_name}")
        model = SentenceTransformer(model_name)
        topic_texts = [
            f"{topic['name']}. {topic.get('description') or ''} " + " ".join(topic["keywords"])
            for topic in topics
        ]
        topic_embeddings = model.encode(topic_texts)

        item_texts = []
        evidence_by_item = {}
        for item in items:
            text, evidence = _item_text(conn, item, fields)
            item_texts.append(text or item["title"])
            evidence_by_item[item["item_id"]] = evidence

        item_embeddings = model.encode(item_texts)
        written = 0
        computed_at = datetime.now().isoformat()
        for item_idx, item in enumerate(items):
            similarities = cosine_similarity(
                item_embeddings[item_idx].reshape(1, -1),
                topic_embeddings,
            )[0]
            for topic_idx, topic in enumerate(topics):
                score = float(similarities[topic_idx])
                if score < threshold:
                    continue
                evidence = dict(evidence_by_item[item["item_id"]])
                evidence["scoring_config"] = scoring_cfg.get("config_name")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO item_topic_scores
                        (item_id, topic_id, scoring_config_id, score, evidence_json, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["item_id"],
                        topic["topic_id"],
                        scoring_config_id,
                        score,
                        _json(evidence),
                        computed_at,
                    ),
                )
                written += 1
        conn.commit()
        _log(f"Wrote {written} item-topic score(s)")
        return written
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Score catalog items against global topics.")
    parser.add_argument("--db", default="knowledge_os.db")
    parser.add_argument("--config", required=True)
    parser.add_argument("--only-unscored", action="store_true")
    args = parser.parse_args()
    written = score_topics(args.db, args.config, only_unscored=args.only_unscored)
    print(f"Wrote {written} item-topic score(s)")


if __name__ == "__main__":
    main()
