"""Tests for sync_reading_log.py"""
import pytest
from knowledge_os.sync_reading_log import parse_read_items, _lookup_item_id
from knowledge_os.storage_sqlite import SQLiteStorage


SAMPLE_DIGEST = """\
🦅 *HN Digest* - Afternoon Energy Boost
_3 stories worth your attention_

*AI/ML*
- [x] Cool AI Tool
  ↑200 | 50 comments | by alice
  💬 Discussing: transformers, scaling
  🔗 https://news.ycombinator.com/item?id=1
  Notes: Really impressive demo
- [ ] Rust is Fast
  ↑150 | 30 comments | by bob
  🔗 https://news.ycombinator.com/item?id=2
  Notes:

🎯 *Engagement Opportunities*

- [x] 💬 Show HN: My Project
  → Someone built something. 80 comments.
  🔗 https://news.ycombinator.com/item?id=3
  Notes:
- [ ] 🔥 Hot Debate Topic
  → Active debate (200 comments).
  🔗 https://news.ycombinator.com/item?id=4
  Notes:

_Keep building. The frontier moves forward._
"""

MULTILINE_NOTES = """\
*AI/ML*
- [x] LLM Deep Dive
  ↑126 | 153 comments | by qsi
  🔗 https://news.ycombinator.com/item?id=5
  Notes:

  IMO, the writer is overzealous with their comments.

  > They aren't perfect, but it looks like magic.

  I won't be surprised if the next version outperforms their output.

- [ ] Another Story
  ↑50 | 10 comments | by someone
  Notes:
"""


class TestParseReadItems:
    def test_finds_checked_items(self):
        items = parse_read_items(SAMPLE_DIGEST)
        assert len(items) == 2

    def test_extracts_titles(self):
        items = parse_read_items(SAMPLE_DIGEST)
        titles = [i["title"] for i in items]
        assert "Cool AI Tool" in titles
        assert "Show HN: My Project" in titles

    def test_unchecked_items_skipped(self):
        items = parse_read_items(SAMPLE_DIGEST)
        titles = [i["title"] for i in items]
        assert "Rust is Fast" not in titles
        assert "Hot Debate Topic" not in titles

    def test_extracts_notes(self):
        items = parse_read_items(SAMPLE_DIGEST)
        by_title = {i["title"]: i for i in items}
        assert by_title["Cool AI Tool"]["note"] == "Really impressive demo"
        assert by_title["Show HN: My Project"]["note"] == ""
        assert by_title["Cool AI Tool"]["link"] == "https://news.ycombinator.com/item?id=1"

    def test_multiline_notes(self):
        items = parse_read_items(MULTILINE_NOTES)
        assert len(items) == 1
        assert items[0]["title"] == "LLM Deep Dive"
        assert "overzealous" in items[0]["note"]
        assert "outperforms" in items[0]["note"]

    def test_no_tracker_items(self):
        md = "# Just a heading\nSome text\n"
        assert parse_read_items(md) == []

    def test_empty_input(self):
        assert parse_read_items("") == []

    def test_case_insensitive_checkbox(self):
        md = "- [X] Title Here\n  Notes: \n"
        items = parse_read_items(md)
        assert len(items) == 1
        assert items[0]["title"] == "Title Here"

    def test_emoji_prefix_stripped(self):
        md = "- [x] 📰 Substack Article\n  Notes: Good read\n"
        items = parse_read_items(md)
        assert len(items) == 1
        assert items[0]["title"] == "Substack Article"
        assert items[0]["note"] == "Good read"

    def test_engagement_emoji_stripped(self):
        md = "- [x] 🔥 Hot Take on AI\n  Notes: \n"
        items = parse_read_items(md)
        assert items[0]["title"] == "Hot Take on AI"


class TestLookupItemId:
    def test_prefers_hn_external_id_over_title(self, tmp_path):
        storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
        storage.insert_item(
            url="https://example.com/older",
            title="Duplicate Title",
            source="hackernews",
            author="a",
            score=1,
            fetched_at="2026-01-01",
            published_at="2026-01-01T00:00:00",
            external_id="1",
        )
        expected_id, _ = storage.insert_item(
            url="https://example.com/newer",
            title="Duplicate Title",
            source="hackernews",
            author="b",
            score=1,
            fetched_at="2026-01-02",
            published_at="2026-01-02T00:00:00",
            external_id="2",
        )

        row = _lookup_item_id(storage, {
            "title": "Duplicate Title",
            "note": "",
            "link": "https://news.ycombinator.com/item?id=2",
        })
        assert row["item_id"] == expected_id

    def test_substack_lookup_uses_article_url(self, tmp_path):
        storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
        expected_id, _ = storage.insert_item(
            url="https://example.com/post",
            title="Weekly Note",
            source="substack",
            author="writer",
            score=0,
            fetched_at="2026-01-01",
            published_at="2026-01-01T00:00:00",
        )

        row = _lookup_item_id(storage, {
            "title": "Weekly Note",
            "note": "",
            "link": "https://example.com/post",
        })
        assert row["item_id"] == expected_id
