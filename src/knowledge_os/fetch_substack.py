#!/usr/bin/env python3
"""
Fetch articles from Substack RSS feeds.
Output JSON to stdout in the same schema as fetch_stories.py.
"""
import hashlib
import json
import sys
from datetime import datetime
from typing import List, Dict

import feedparser

_WEEKDAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _feed_is_due(frequency, today: datetime = None) -> bool:
    """Return True if this feed should be fetched today based on its frequency."""
    if today is None:
        today = datetime.now()
    if not frequency or frequency == "daily":
        return True
    if isinstance(frequency, list):
        day_name = _WEEKDAY_NAMES[today.weekday()]
        return day_name in [d.lower()[:3] for d in frequency]
    freq = frequency.lower()
    if freq == "weekly":
        return today.weekday() == 0
    if freq == "biweekly":
        return today.weekday() == 0 and today.isocalendar()[1] % 2 == 0
    if freq == "monthly":
        return today.day == 1
    return True


def _stable_id(url: str) -> int:
    """Generate a stable numeric ID from a URL (positive 32-bit int)."""
    return int(hashlib.sha256(url.encode()).hexdigest()[:8], 16)


def fetch_feed(feed_url: str, max_items: int = 10) -> List[Dict]:
    """Fetch and normalize entries from a single Substack RSS feed."""
    feed = feedparser.parse(feed_url)
    stories = []

    for entry in feed.entries[:max_items]:
        url = entry.get("link", "")
        if not url:
            continue

        # Parse publish time
        published = entry.get("published_parsed")
        if published:
            ts = int(datetime(*published[:6]).timestamp())
        else:
            ts = 0

        fetched_at = datetime.now().isoformat()
        updated = entry.get("updated_parsed")
        date_tuple = updated or published  # prefer updated (captures edits)
        if date_tuple:
            published_at = datetime(*date_tuple[:6]).isoformat()
        else:
            published_at = fetched_at
            print(f"Warning: no date for {url}", file=sys.stderr)

        stories.append({
            "id": _stable_id(url),
            "title": entry.get("title", ""),
            "url": url,
            "score": 0,
            "by": entry.get("author", feed.feed.get("title", "unknown")),
            "time": ts,
            "descendants": 0,
            "text": entry.get("summary", ""),
            "source": "substack",
            "fetched_at": fetched_at,
            "published_at": published_at,
        })

    return stories


def fetch_all_feeds(config: Dict) -> List[Dict]:
    """Fetch stories from all configured Substack feeds."""
    substack_cfg = config.get("sources", {}).get("substack", {})
    if not substack_cfg.get("enabled", False):
        return []

    feeds = substack_cfg.get("feeds", [])
    max_items = substack_cfg.get("max_items", 10)
    source_frequency = substack_cfg.get("frequency", "daily")

    all_stories = []
    for feed_entry in feeds:
        # Feeds can be plain strings or {"url": "...", "frequency": "..."} dicts
        if isinstance(feed_entry, dict):
            feed_url = feed_entry["url"]
            frequency = feed_entry.get("frequency", source_frequency)
        else:
            feed_url = feed_entry
            frequency = source_frequency

        if not _feed_is_due(frequency):
            continue

        try:
            stories = fetch_feed(feed_url, max_items=max_items)
            all_stories.extend(stories)
            print(f"Fetched {len(stories)} items from {feed_url}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Failed to fetch {feed_url}: {e}", file=sys.stderr)

    return all_stories


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    with open(config_path) as f:
        config = json.load(f)

    stories = fetch_all_feeds(config)
    print(json.dumps(stories, indent=2))
