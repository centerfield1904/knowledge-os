#!/usr/bin/env python3
"""Runtime context assembly for digest processing."""
from dataclasses import dataclass
from typing import Dict, List, Optional

from .storage_interface import StorageInterface, get_storage


@dataclass(frozen=True)
class DigestUser:
    """Resolved user identity for one digest run."""

    identifier: str
    timezone: Optional[str] = None
    settings: Optional[Dict] = None


@dataclass(frozen=True)
class DigestTopic:
    """Resolved topic definition for one digest run."""

    name: str
    keywords: List[str]
    weight: float = 1.0


@dataclass
class DigestRunContext:
    """Runtime dependencies and resolved config for digest processing."""

    storage: StorageInterface
    user_id: int
    topics: List[Dict]
    config: Dict


def _resolve_user(config: Dict) -> DigestUser:
    user_cfg = config["user"]
    return DigestUser(
        identifier=user_cfg["identifier"],
        timezone=user_cfg.get("timezone"),
        settings=user_cfg.get("settings"),
    )


def _resolve_topics(config: Dict) -> List[DigestTopic]:
    return [
        DigestTopic(
            name=topic["name"],
            keywords=list(topic["keywords"]),
            weight=topic.get("weight", 1.0),
        )
        for topic in config["topics"]
    ]


def _build_storage(config: Dict) -> StorageInterface:
    storage_config = config["storage"]
    backend = storage_config["backend"]
    return get_storage(
        backend=backend,
        **storage_config.get(backend, {}),
    )


def ensure_topics(storage: StorageInterface, user_id: int, topics: List[DigestTopic]) -> List[Dict]:
    """Ensure the user has topic rows and return storage-backed topics.

    This preserves the current behavior: topics are inserted only when the user
    has no topics. Full config-to-DB topic sync is a later architecture step.
    """
    existing_topics = storage.get_topics(user_id)
    if existing_topics:
        return existing_topics

    for topic in topics:
        storage.insert_topic(
            user_id=user_id,
            name=topic.name,
            keywords=topic.keywords,
            weight=topic.weight,
        )
    return storage.get_topics(user_id)


def build_digest_context(config: Dict) -> DigestRunContext:
    """Build runtime dependencies from an already-resolved digest config."""
    storage = _build_storage(config)
    user = _resolve_user(config)
    user_id = storage.get_or_create_user(
        identifier=user.identifier,
        settings=user.settings,
    )
    topics = ensure_topics(storage, user_id, _resolve_topics(config))
    return DigestRunContext(
        storage=storage,
        user_id=user_id,
        topics=topics,
        config=config,
    )
