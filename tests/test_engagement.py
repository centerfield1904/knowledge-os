"""Tests for engagement detection module"""
import pytest
import tempfile
import os
from datetime import datetime
from knowledge_os.engagement import EngagementDetector, format_engagement_section


@pytest.fixture
def detector(tmp_path):
    """Create EngagementDetector with a temp DB"""
    db_path = str(tmp_path / "test_engagement.db")
    return EngagementDetector(db_path)


def _make_story(story_id=1, title="Test Story", score=100, descendants=5,
                age_hours=2, **kwargs):
    """Helper to create a story dict"""
    time_val = datetime.now().timestamp() - (age_hours * 3600)
    defaults = {
        "id": story_id,
        "title": title,
        "score": score,
        "descendants": descendants,
        "time": time_val,
        "by": "testuser",
        "url": f"https://example.com/{story_id}",
    }
    defaults.update(kwargs)
    return defaults


class TestEngagementDetector:
    def test_init_creates_tables(self, detector):
        """DB tables should be created on init"""
        import sqlite3
        conn = sqlite3.connect(detector.db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in c.fetchall()}
        conn.close()
        assert "engagement_opportunities" in tables
        assert "user_comments" in tables
        assert "engagement_stats" in tables

    def test_detect_ask_hn(self, detector):
        stories = [_make_story(title="Ask HN: Best languages?", descendants=3)]
        opps = detector.detect_opportunities(stories)
        assert len(opps) == 1
        assert opps[0]["type"] == "ask_show"

    def test_detect_show_hn(self, detector):
        stories = [_make_story(title="Show HN: My new tool", descendants=2)]
        opps = detector.detect_opportunities(stories)
        assert len(opps) == 1
        assert opps[0]["type"] == "ask_show"

    def test_detect_early(self, detector):
        stories = [_make_story(title="New Framework Released",
                               descendants=3, age_hours=1)]
        opps = detector.detect_opportunities(stories)
        assert len(opps) == 1
        assert opps[0]["type"] == "early"

    def test_detect_debate(self, detector):
        stories = [_make_story(title="Language X vs Y",
                               descendants=80, age_hours=4)]
        opps = detector.detect_opportunities(stories)
        assert len(opps) == 1
        assert opps[0]["type"] == "debate"

    def test_no_opportunity_for_old_story(self, detector):
        stories = [_make_story(descendants=20, age_hours=24)]
        opps = detector.detect_opportunities(stories)
        assert len(opps) == 0

    def test_max_results(self, detector):
        stories = [
            _make_story(story_id=i, title=f"Ask HN: Q{i}?", descendants=1)
            for i in range(10)
        ]
        opps = detector.detect_opportunities(stories, max_results=3)
        assert len(opps) <= 3

    def test_sorted_by_score(self, detector):
        stories = [
            _make_story(story_id=1, title="Ask HN: Hot?", descendants=0, age_hours=1),
            _make_story(story_id=2, title="Old debate", descendants=80, age_hours=11),
        ]
        opps = detector.detect_opportunities(stories)
        scores = [o["score"] for o in opps]
        assert scores == sorted(scores, reverse=True)

    def test_save_opportunities(self, detector):
        stories = [_make_story(title="Ask HN: Test?")]
        opps = detector.detect_opportunities(stories)
        detector.save_opportunities(opps, "2026-02-25")

        import sqlite3
        conn = sqlite3.connect(detector.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM engagement_opportunities")
        assert c.fetchone()[0] == len(opps)
        conn.close()


class TestFormatEngagementSection:
    def test_empty(self):
        assert format_engagement_section([]) == ""

    def test_basic_format(self):
        opps = [{
            "type": "ask_show",
            "story": {"id": 123, "title": "Ask HN: Testing?"},
            "score": 0.9,
            "action_prompt": "Share your thoughts!",
        }]
        result = format_engagement_section(opps)
        assert "Engagement Opportunities" in result
        assert "Ask HN: Testing?" in result
        assert "Share your thoughts!" in result
        assert "123" in result
        assert "- [ ]" in result
        assert "Notes: " in result

    def test_emoji_mapping(self):
        types_emojis = [("ask_show", "💬"), ("early", "🎯"), ("debate", "🔥")]
        for opp_type, emoji in types_emojis:
            opps = [{
                "type": opp_type,
                "story": {"id": 1, "title": "T"},
                "score": 0.5,
                "action_prompt": "Go",
            }]
            assert emoji in format_engagement_section(opps)
