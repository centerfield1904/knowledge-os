#!/usr/bin/env python3
"""Main digest processing pipeline."""
import sys
import time
from datetime import datetime
from typing import Dict, List

from .digest_context import DigestRunContext
from .digest_filters import filter_by_age, is_weekend, source_is_due
from .digest_formatter import summarize_comments
from .match_topics import TopicMatcher

try:
    from .engagement import EngagementDetector
    ENGAGEMENT_ENABLED = True
except ImportError:
    EngagementDetector = None
    ENGAGEMENT_ENABLED = False


def _log(message: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", file=sys.stderr)


def process_stories(stories: List[Dict], context: DigestRunContext) -> Dict:
    """Process stories through filtering, matching, storage, and enrichment."""
    config = context.config
    storage = context.storage
    user_id = context.user_id
    topics = context.topics

    _log(f"Processing {len(stories)} stories...")
    start_time = time.time()

    max_age_days = config["settings"].get("max_age_days", 7)
    before = len(stories)
    stories = filter_by_age(stories, max_age_days)
    _log(f"Age filter ({max_age_days}d): {before} → {len(stories)} stories")

    sources_cfg = config.get("sources", {})
    before = len(stories)
    stories = [
        story for story in stories
        if source_is_due(
            sources_cfg.get(story.get("source", "hackernews"), {}).get("frequency", "daily")
        )
    ]
    _log(f"Frequency filter: {before} → {len(stories)} stories")

    _log(f"Runtime context loaded ({len(topics)} topics)")

    _log("Starting topic matching (embeddings)...")
    matcher_start = time.time()
    matcher = TopicMatcher(config=config)
    matched_stories = matcher.match_stories(stories)
    _log(f"Topic matching completed in {time.time() - matcher_start:.1f}s ({len(matched_stories)} matched)")

    wm_cfg = config.get("settings", {}).get("weekend_mode", {})
    all_scored_stories = None
    if wm_cfg.get("enabled"):
        _log("Scoring all stories for weekend mode...")
        all_scored_stories = matcher.score_all_stories(stories)

    weekend_mode_active = wm_cfg.get("enabled") and is_weekend()
    stories_to_store = matched_stories
    if weekend_mode_active and all_scored_stories is not None:
        stories_to_store = [story for story, _ in all_scored_stories]

    _log(f"Storing {len(stories_to_store)} stories in database...")
    db_start = time.time()
    url_to_item_id = {}

    for story in stories_to_store:
        item_id, _ = storage.insert_item(
            url=story["url"],
            title=story["title"],
            source=story.get("source", "hackernews"),
            author=story["by"],
            score=story["score"],
            fetched_at=story["fetched_at"],
            published_at=story.get("published_at", ""),
            external_id=str(story["id"]) if story.get("id") is not None else None,
        )

        for topic in topics:
            if topic["name"] in story["all_topic_scores"]:
                score = story["all_topic_scores"][topic["name"]]
                storage.insert_item_topic_score(
                    item_id=item_id,
                    topic_id=topic["topic_id"],
                    score=score,
                )

        storage.upsert_author(
            user_id=user_id,
            author_name=story["by"],
            item_id=item_id,
            topic_scores=story["all_topic_scores"],
        )

        url_to_item_id[story["url"]] = item_id

    undelivered_ids = storage.get_undelivered_item_ids(list(url_to_item_id.values()))
    undelivered_urls = {url for url, iid in url_to_item_id.items() if iid in undelivered_ids}
    item_ids = [iid for iid in url_to_item_id.values() if iid in undelivered_ids]

    if weekend_mode_active and all_scored_stories is not None:
        all_scored_stories = [
            (story, sim) for story, sim in all_scored_stories
            if story["url"] in undelivered_urls
        ]
        display_stories = [story for story, _ in all_scored_stories]
    else:
        display_stories = [story for story in matched_stories if story["url"] in undelivered_urls]

    _log(f"Database storage completed in {time.time() - db_start:.1f}s ({len(display_stories)} undelivered)")

    authors_start = time.time()
    notable_authors = storage.get_notable_authors(
        user_id=user_id,
        min_count=config["settings"]["notable_author_threshold"],
    )

    current_authors = {story["by"] for story in display_stories}
    batch_notable = [author for author in notable_authors if author["author_name"] in current_authors]

    followed_users = config.get("settings", {}).get("followed_hn_users", [])
    if followed_users:
        existing_notable_names = {author["author_name"] for author in batch_notable}
        for username in followed_users:
            if username in current_authors and username not in existing_notable_names:
                batch_notable.append({
                    "author_name": username,
                    "story_count": 0,
                    "topics": {},
                })
    _log(f"Notable authors identified in {time.time() - authors_start:.1f}s ({len(batch_notable)} in batch)")

    digest_start = time.time()
    digest_id = storage.insert_digest(
        user_id=user_id,
        item_ids=item_ids,
        sent_at=datetime.now().isoformat(),
    )

    for item_id in item_ids:
        storage.insert_feedback(
            user_id=user_id,
            item_id=item_id,
            action="delivered",
            metadata={"digest_id": digest_id},
        )
    _log(f"Digest recorded in {time.time() - digest_start:.1f}s")

    if ENGAGEMENT_ENABLED and EngagementDetector and display_stories:
        _log("Fetching comment summaries and author karma...")
        comments_start = time.time()
        try:
            db_config = config["storage"]["sqlite"]
            comment_detector = EngagementDetector(db_config["db_path"])
            karma_cache = {}
            for story in display_stories:
                story_id = story.get("id")
                if story_id:
                    try:
                        comments = comment_detector.fetch_story_comments(story_id, max_depth=1)
                        story["comment_summary"] = summarize_comments(
                            comments,
                            story.get("descendants", 0),
                        )
                    except Exception:
                        story["comment_summary"] = None
                author = story.get("by", "")
                if author and author not in karma_cache:
                    karma_cache[author] = comment_detector.fetch_user_karma(author)
                story["author_karma"] = karma_cache.get(author)
            _log(f"Comments and karma fetched in {time.time() - comments_start:.1f}s")
        except Exception as exc:
            _log(f"Warning: Comment/karma fetch failed: {exc}")

    engagement_opportunities = []
    if ENGAGEMENT_ENABLED and EngagementDetector and display_stories:
        _log("Detecting engagement opportunities...")
        engagement_start = time.time()
        try:
            db_config = config["storage"]["sqlite"]
            detector = EngagementDetector(db_config["db_path"])
            engagement_opportunities = detector.detect_opportunities(stories, max_results=5)
            detector.save_opportunities(engagement_opportunities, datetime.now().date().isoformat())

            _log("Syncing user comments...")
            sync_start = time.time()
            detector.sync_user_comments()
            _log(f"User comments synced in {time.time() - sync_start:.1f}s")
            _log(f"Engagement detection completed in {time.time() - engagement_start:.1f}s")
        except Exception as exc:
            _log(f"Warning: Engagement detection failed: {exc}")

    _log(f"Total processing time: {time.time() - start_time:.1f}s")

    return {
        "stories": display_stories,
        "notable_authors": batch_notable,
        "digest_id": digest_id,
        "item_ids": item_ids,
        "engagement_opportunities": engagement_opportunities,
        "all_scored_stories": all_scored_stories,
    }
