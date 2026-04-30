#!/usr/bin/env python3
"""Filtering and weekend-section helpers for digest generation."""
from datetime import datetime, timedelta
from typing import Dict, List


WEEKDAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def source_is_due(frequency, today: datetime = None) -> bool:
    """Return True if this source should surface in today's digest."""
    if today is None:
        today = datetime.now()
    if not frequency or frequency == "daily":
        return True
    if isinstance(frequency, list):
        day_name = WEEKDAY_NAMES[today.weekday()]
        return day_name in [d.lower()[:3] for d in frequency]
    freq = frequency.lower()
    if freq == "weekly":
        return today.weekday() == 0
    if freq == "biweekly":
        return today.weekday() == 0 and today.isocalendar()[1] % 2 == 0
    if freq == "monthly":
        return today.day == 1
    if freq == "quarterly":
        return today.day == 1 and today.month in (1, 4, 7, 10)
    return True


def is_weekend(today: datetime = None) -> bool:
    """Return True if today is Saturday or Sunday."""
    if today is None:
        today = datetime.now()
    return today.weekday() in (5, 6)


def filter_by_age(stories: List[Dict], max_age_days: int) -> List[Dict]:
    """Return only stories whose published_at is within max_age_days of now.

    Stories with missing or unparseable published_at are kept.
    """
    cutoff = datetime.now() - timedelta(days=max_age_days)
    result = []
    for story in stories:
        pub = story.get("published_at", "")
        if not pub:
            result.append(story)
            continue
        try:
            if datetime.fromisoformat(pub) >= cutoff:
                result.append(story)
        except ValueError:
            result.append(story)
    return result


def apply_weekend_mode(scored_stories, config, today=None):
    """
    Split stories into (top_matches, interesting_reads) for weekend digest.

    - top_matches: max topic similarity >= weekend threshold, sorted by HN score
    - interesting_reads: remaining high-score stories, sorted by HN score
    """
    wm = config.get("settings", {}).get("weekend_mode", {})
    threshold = float(wm.get("similarity_threshold", 0.45))
    max_top = int(wm.get("max_top_matches", 10))
    interesting_count = int(wm.get("interesting_reads_count", 10))
    interesting_min_score = int(wm.get("interesting_min_score", 100))

    top_matches = [s for s, sim in scored_stories if sim >= threshold]
    top_matches = sorted(top_matches, key=lambda s: s.get("score", 0), reverse=True)[:max_top]
    top_match_urls = {s["url"] for s in top_matches}

    interesting = [
        s for s, _ in scored_stories
        if s["url"] not in top_match_urls and s.get("score", 0) >= interesting_min_score
    ]
    interesting = sorted(interesting, key=lambda s: s.get("score", 0), reverse=True)[:interesting_count]

    return top_matches, interesting
