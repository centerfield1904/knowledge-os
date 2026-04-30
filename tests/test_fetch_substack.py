"""Tests for fetch_substack.py"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from knowledge_os.fetch_substack import _stable_id, fetch_feed, fetch_all_feeds, _feed_is_due


class TestStableId:
    def test_deterministic(self):
        assert _stable_id("https://example.com/a") == _stable_id("https://example.com/a")

    def test_different_urls_different_ids(self):
        assert _stable_id("https://a.com") != _stable_id("https://b.com")

    def test_positive_int(self):
        assert _stable_id("https://example.com") > 0


class TestFetchFeed:
    def _make_feed(self, entries):
        feed = MagicMock()
        feed.feed.get.return_value = "Test Blog"
        feed.entries = entries
        return feed

    def _make_entry(self, title="Post", link="https://example.com/post",
                    author="Writer", summary="Summary text"):
        entry = {
            "title": title,
            "link": link,
            "author": author,
            "summary": summary,
            "published_parsed": (2026, 2, 27, 10, 0, 0, 0, 0, 0),
        }
        # Make it behave like a feedparser entry (dict-like with .get)
        return type("Entry", (), {"get": lambda self, k, d=None: entry.get(k, d)})()

    @patch("knowledge_os.fetch_substack.feedparser")
    def test_basic_fetch(self, mock_fp):
        entry = self._make_entry()
        mock_fp.parse.return_value = self._make_feed([entry])

        stories = fetch_feed("https://test.substack.com/feed")
        assert len(stories) == 1
        assert stories[0]["title"] == "Post"
        assert stories[0]["source"] == "substack"
        assert stories[0]["score"] == 0
        assert stories[0]["descendants"] == 0
        assert "published_at" in stories[0]
        assert stories[0]["published_at"]  # non-empty

    @patch("knowledge_os.fetch_substack.feedparser")
    def test_max_items_respected(self, mock_fp):
        entries = [self._make_entry(link=f"https://example.com/{i}") for i in range(20)]
        mock_fp.parse.return_value = self._make_feed(entries)

        stories = fetch_feed("https://test.substack.com/feed", max_items=3)
        assert len(stories) == 3

    @patch("knowledge_os.fetch_substack.feedparser")
    def test_entry_without_link_skipped(self, mock_fp):
        entry = self._make_entry(link="")
        mock_fp.parse.return_value = self._make_feed([entry])

        stories = fetch_feed("https://test.substack.com/feed")
        assert len(stories) == 0


class TestFetchAllFeeds:
    def test_disabled_returns_empty(self):
        config = {"sources": {"substack": {"enabled": False, "feeds": ["https://x.com/feed"]}}}
        assert fetch_all_feeds(config) == []

    def test_no_sources_key_returns_empty(self):
        config = {}
        assert fetch_all_feeds(config) == []

    @patch("knowledge_os.fetch_substack.fetch_feed")
    def test_merges_multiple_feeds(self, mock_fetch):
        mock_fetch.return_value = [{"id": 1, "title": "Post"}]
        config = {
            "sources": {
                "substack": {
                    "enabled": True,
                    "feeds": ["https://a.substack.com/feed", "https://b.substack.com/feed"],
                    "max_items": 5,
                }
            }
        }
        result = fetch_all_feeds(config)
        assert len(result) == 2
        assert mock_fetch.call_count == 2

    @patch("knowledge_os.fetch_substack.fetch_feed")
    def test_failed_feed_continues(self, mock_fetch):
        mock_fetch.side_effect = [Exception("Network error"), [{"id": 2, "title": "OK"}]]
        config = {
            "sources": {
                "substack": {
                    "enabled": True,
                    "feeds": ["https://bad.com/feed", "https://good.com/feed"],
                    "max_items": 5,
                }
            }
        }
        result = fetch_all_feeds(config)
        assert len(result) == 1


class TestFeedIsDue:
    def test_daily_always_true(self):
        assert _feed_is_due("daily", datetime(2026, 3, 7)) is True

    def test_none_always_true(self):
        assert _feed_is_due(None, datetime(2026, 3, 7)) is True

    def test_weekly_true_on_monday(self):
        assert _feed_is_due("weekly", datetime(2026, 3, 2)) is True  # Monday

    def test_weekly_false_on_saturday(self):
        assert _feed_is_due("weekly", datetime(2026, 3, 7)) is False  # Saturday

    def test_list_matches_day(self):
        assert _feed_is_due(["mon", "wed", "fri"], datetime(2026, 3, 2)) is True

    def test_list_no_match(self):
        assert _feed_is_due(["mon", "wed"], datetime(2026, 3, 7)) is False  # Saturday


class TestFetchAllFeedsPerFeedFrequency:
    @patch("knowledge_os.fetch_substack.fetch_feed")
    def test_dict_feed_fetched(self, mock_fetch):
        mock_fetch.return_value = [{"id": 1, "title": "Post"}]
        config = {
            "sources": {
                "substack": {
                    "enabled": True,
                    "feeds": [{"url": "https://a.substack.com/feed", "frequency": "daily"}],
                    "max_items": 5,
                }
            }
        }
        result = fetch_all_feeds(config)
        assert len(result) == 1
        mock_fetch.assert_called_once_with("https://a.substack.com/feed", max_items=5)

    @patch("knowledge_os.fetch_substack.fetch_feed")
    @patch("knowledge_os.fetch_substack._feed_is_due", return_value=False)
    def test_skipped_when_not_due(self, mock_due, mock_fetch):
        config = {
            "sources": {
                "substack": {
                    "enabled": True,
                    "feeds": [{"url": "https://a.substack.com/feed", "frequency": "weekly"}],
                    "max_items": 5,
                }
            }
        }
        result = fetch_all_feeds(config)
        assert result == []
        mock_fetch.assert_not_called()
