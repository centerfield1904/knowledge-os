#!/usr/bin/env python3
"""CLI and compatibility exports for digest processing."""
import json
import sys
from pathlib import Path

from . import digest_pipeline as _pipeline
from .digest_filters import (
    apply_weekend_mode as _apply_weekend_mode,
    filter_by_age as _filter_by_age,
    is_weekend as _is_weekend,
    source_is_due as _source_is_due,
)
from .digest_formatter import (
    extract_first_sentence as _extract_first_sentence,
    extract_keywords as _extract_keywords,
    generate_digest_text as _generate_digest_text,
    summarize_comments,
)
from .match_topics import TopicMatcher

try:
    from .engagement import EngagementDetector, format_engagement_section
    ENGAGEMENT_ENABLED = True
except ImportError:
    EngagementDetector = None
    format_engagement_section = None
    ENGAGEMENT_ENABLED = False
    print("Warning: Engagement module not available", file=sys.stderr)


def load_config(config_path: str = "config.json") -> dict:
    """Load configuration."""
    with open(config_path) as f:
        return json.load(f)


def process_stories(stories, config):
    """Compatibility wrapper around digest_pipeline.process_stories."""
    _pipeline.TopicMatcher = TopicMatcher
    _pipeline.EngagementDetector = EngagementDetector
    _pipeline.ENGAGEMENT_ENABLED = ENGAGEMENT_ENABLED
    _pipeline.filter_by_age = _filter_by_age
    _pipeline.is_weekend = _is_weekend
    _pipeline.source_is_due = _source_is_due
    return _pipeline.process_stories(stories, config)


def generate_digest_text(result, config=None, weekend_sections=None):
    """Compatibility wrapper around digest_formatter.generate_digest_text."""
    return _generate_digest_text(
        result,
        config=config,
        weekend_sections=weekend_sections,
        engagement_enabled=ENGAGEMENT_ENABLED,
        engagement_formatter=format_engagement_section,
    )


def _write_feedback_metadata(result):
    """Save story metadata for the feedback system."""
    metadata = {
        "stories": [
            {
                "id": story.get("id"),
                "title": story["title"],
                "url": story["url"],
                "score": story["score"],
                "by": story["by"],
            }
            for story in result["stories"][:10]
        ]
    }

    metadata_path = Path(__file__).resolve().parent.parent / "digest_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)


def main():
    config = load_config()

    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            stories = json.load(f)
    else:
        stories = json.load(sys.stdin)

    result = process_stories(stories, config)

    wm = config.get("settings", {}).get("weekend_mode", {})
    weekend_sections = None
    if wm.get("enabled") and _is_weekend():
        scored_stories = result.get("all_scored_stories") or [
            (story, max(story.get("all_topic_scores", {}).values(), default=0.0))
            for story in result["stories"]
        ]
        weekend_sections = _apply_weekend_mode(scored_stories, config)

    print(generate_digest_text(result, config=config, weekend_sections=weekend_sections))
    _write_feedback_metadata(result)


if __name__ == "__main__":
    main()
