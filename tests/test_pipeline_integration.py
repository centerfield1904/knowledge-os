"""Integration test for the full digest pipeline (process_stories + generate_digest_text)"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

pytestmark = pytest.mark.integration


@pytest.fixture
def config(tmp_path):
    db_path = str(tmp_path / "test.db")
    return {
        "storage": {
            "backend": "sqlite",
            "sqlite": {"db_path": db_path}
        },
        "user": {"identifier": "+910000000000", "timezone": "Asia/Calcutta"},
        "topics": [
            {"name": "AI/ML/LLMs", "keywords": ["AI", "machine learning"], "weight": 1.0},
            {"name": "Philosophy", "keywords": ["philosophy", "thinking"], "weight": 1.0},
        ],
        "settings": {
            "max_stories": 30,
            "min_score": 50,
            "max_age_days": 7,
            "similarity_threshold": 0.3,
            "digest_time": "14:00",
            "track_authors": True,
            "track_continuity": True,
            "notable_author_threshold": 3,
        },
    }


@pytest.fixture
def sample_stories():
    now = datetime.now().isoformat()
    return [
        {
            "id": 1001,
            "title": "New Transformer Architecture Beats GPT-5",
            "url": "https://example.com/transformers",
            "score": 250,
            "by": "airesearcher",
            "time": 1700000000,
            "descendants": 80,
            "text": "",
            "fetched_at": now,
            "published_at": now,
        },
        {
            "id": 1002,
            "title": "Stoicism and Software Engineering",
            "url": "https://example.com/stoicism",
            "score": 120,
            "by": "phildev",
            "time": 1700000100,
            "descendants": 30,
            "text": "",
            "fetched_at": now,
            "published_at": now,
        },
    ]


def _fake_match_stories(stories):
    """Simulate TopicMatcher.match_stories — assigns topics without sentence-transformers."""
    result = []
    for story in stories:
        s = dict(story)
        if "AI" in story["title"] or "Transformer" in story["title"] or "GPT" in story["title"]:
            s["matched_topic"] = "AI/ML/LLMs"
            s["all_topic_scores"] = {"AI/ML/LLMs": 0.85, "Philosophy": 0.1}
        else:
            s["matched_topic"] = "Philosophy"
            s["all_topic_scores"] = {"AI/ML/LLMs": 0.1, "Philosophy": 0.75}
        result.append(s)
    return result


class TestPipelineIntegration:
    """End-to-end test of process_stories → generate_digest_text."""

    def test_full_pipeline(self, config, sample_stories):
        mock_matcher = MagicMock()
        mock_matcher.match_stories.side_effect = _fake_match_stories

        mock_detector = MagicMock()
        mock_detector.fetch_story_comments.return_value = [
            {"text": "<p>Great analysis of transformer scaling. Impressive results.</p>"}
        ]
        mock_detector.fetch_user_karma.return_value = 1234
        mock_detector.detect_opportunities.return_value = []
        mock_detector.save_opportunities.return_value = None
        mock_detector.sync_user_comments.return_value = None

        with patch("knowledge_os.digest_pipeline.TopicMatcher", return_value=mock_matcher), \
             patch("knowledge_os.digest_pipeline.EngagementDetector", return_value=mock_detector), \
             patch("knowledge_os.digest_pipeline.ENGAGEMENT_ENABLED", True):

            from knowledge_os.digest_context import build_digest_context
            from knowledge_os.digest_pipeline import process_stories
            from knowledge_os.process_digest import generate_digest_text

            result = process_stories(sample_stories, build_digest_context(config))

            # Stories stored and returned
            assert len(result["stories"]) == 2
            assert len(result["item_ids"]) == 2
            assert result["digest_id"] >= 1

            # Generate digest text
            digest = generate_digest_text(result)

            # Topic sections present
            assert "*AI/ML/LLMs*" in digest
            assert "*Philosophy*" in digest

            # Story titles appear
            assert "New Transformer Architecture Beats GPT-5" in digest
            assert "Stoicism and Software Engineering" in digest

            # HN links (not article URLs)
            assert "news.ycombinator.com/item?id=1001" in digest
            assert "news.ycombinator.com/item?id=1002" in digest

            # Inline checkboxes (no separate read tracker)
            assert "- [ ] New Transformer Architecture" in digest
            assert "## 📖 Read Tracker" not in digest

    def test_stories_persisted_in_db(self, config, sample_stories):
        """Verify that stories are actually written to the SQLite DB."""
        mock_matcher = MagicMock()
        mock_matcher.match_stories.side_effect = _fake_match_stories

        with patch("knowledge_os.digest_pipeline.TopicMatcher", return_value=mock_matcher), \
             patch("knowledge_os.digest_pipeline.ENGAGEMENT_ENABLED", False):

            from knowledge_os.digest_context import build_digest_context
            from knowledge_os.digest_pipeline import process_stories
            from knowledge_os.storage_sqlite import SQLiteStorage

            result = process_stories(sample_stories, build_digest_context(config))

            # Verify via direct DB read
            storage = SQLiteStorage(db_path=config["storage"]["sqlite"]["db_path"])
            for item_id in result["item_ids"]:
                item = storage.get_item(item_id)
                assert item is not None
                assert item["source"] == "hackernews"

    def test_feedback_recorded(self, config, sample_stories):
        """Verify 'delivered' feedback is recorded for each story."""
        mock_matcher = MagicMock()
        mock_matcher.match_stories.side_effect = _fake_match_stories

        with patch("knowledge_os.digest_pipeline.TopicMatcher", return_value=mock_matcher), \
             patch("knowledge_os.digest_pipeline.ENGAGEMENT_ENABLED", False):

            from knowledge_os.digest_context import build_digest_context
            from knowledge_os.digest_pipeline import process_stories
            from knowledge_os.storage_sqlite import SQLiteStorage

            result = process_stories(sample_stories, build_digest_context(config))

            storage = SQLiteStorage(db_path=config["storage"]["sqlite"]["db_path"])
            user_id = storage.get_or_create_user(config["user"]["identifier"])
            feedback = storage.get_feedback(user_id)
            delivered = [f for f in feedback if f["action"] == "delivered"]
            assert len(delivered) == len(result["item_ids"])

    def test_empty_stories(self, config):
        """Pipeline handles empty story list gracefully."""
        mock_matcher = MagicMock()
        mock_matcher.match_stories.return_value = []

        with patch("knowledge_os.digest_pipeline.TopicMatcher", return_value=mock_matcher), \
             patch("knowledge_os.digest_pipeline.ENGAGEMENT_ENABLED", False):

            from knowledge_os.digest_context import build_digest_context
            from knowledge_os.digest_pipeline import process_stories
            from knowledge_os.process_digest import generate_digest_text

            result = process_stories([], build_digest_context(config))
            assert result["stories"] == []
            assert result["item_ids"] == []

            digest = generate_digest_text(result)
            assert "Quiet day" in digest

    def test_age_filter_drops_old_stories(self, config):
        """Stories older than max_age_days are excluded before matching."""
        mock_matcher = MagicMock()
        mock_matcher.match_stories.side_effect = _fake_match_stories

        old_story = {
            "id": 2001,
            "title": "New Transformer Architecture from 2020",
            "url": "https://example.com/old",
            "score": 300,
            "by": "oldposter",
            "time": 1577836800,
            "descendants": 0,
            "text": "",
            "fetched_at": datetime.now().isoformat(),
            "published_at": "2020-01-01T00:00:00",
        }

        with patch("knowledge_os.digest_pipeline.TopicMatcher", return_value=mock_matcher), \
             patch("knowledge_os.digest_pipeline.ENGAGEMENT_ENABLED", False):

            from knowledge_os.digest_context import build_digest_context
            from knowledge_os.digest_pipeline import process_stories

            result = process_stories([old_story], build_digest_context(config))
            # Old story should be filtered before matching — matcher never called
            mock_matcher.match_stories.assert_called_once_with([])
            assert result["stories"] == []

    def test_weekend_mode_only_surfaces_new_scored_stories(self, config, sample_stories):
        config["settings"]["weekend_mode"] = {
            "enabled": True,
            "similarity_threshold": 0.45,
            "max_top_matches": 10,
            "interesting_reads_count": 10,
            "interesting_min_score": 100,
        }

        matched = dict(sample_stories[0])
        matched["matched_topic"] = "AI/ML/LLMs"
        matched["all_topic_scores"] = {"AI/ML/LLMs": 0.85, "Philosophy": 0.1}

        interesting = dict(sample_stories[1])
        interesting["all_topic_scores"] = {"AI/ML/LLMs": 0.2, "Philosophy": 0.25}

        mock_matcher = MagicMock()
        mock_matcher.match_stories.return_value = [matched]
        mock_matcher.score_all_stories.return_value = [(matched, 0.85), (interesting, 0.25)]

        with patch("knowledge_os.digest_pipeline.TopicMatcher", return_value=mock_matcher), \
             patch("knowledge_os.digest_pipeline.ENGAGEMENT_ENABLED", False), \
             patch("knowledge_os.digest_pipeline.is_weekend", return_value=True):

            from knowledge_os.digest_context import build_digest_context
            from knowledge_os.digest_pipeline import process_stories

            first = process_stories(sample_stories, build_digest_context(config))
            assert [story["title"] for story in first["stories"]] == [
                "New Transformer Architecture Beats GPT-5",
                "Stoicism and Software Engineering",
            ]
            assert len(first["item_ids"]) == 2

            second = process_stories(sample_stories, build_digest_context(config))
            assert second["stories"] == []
            assert second["item_ids"] == []
