"""Tests for process_digest.py pure functions"""
import pytest
from datetime import datetime, timedelta
from knowledge_os.process_digest import (
    _extract_first_sentence,
    _extract_keywords,
    _filter_by_age,
    _is_weekend,
    _apply_weekend_mode,
    _source_is_due,
    summarize_comments,
    generate_digest_text,
)


# --- _extract_first_sentence ---

class TestExtractFirstSentence:
    def test_plain_sentence(self):
        assert _extract_first_sentence("Hello world. More text here.") == "Hello world."

    def test_html_tags_stripped(self):
        result = _extract_first_sentence("<p>Hello <b>world</b>. More.</p>")
        assert "<" not in result
        assert "Hello" in result

    def test_html_entities_decoded(self):
        result = _extract_first_sentence("A &amp; B are great. Next.")
        assert result == "A & B are great."

    def test_empty_string(self):
        assert _extract_first_sentence("") == ""

    def test_no_sentence_boundary(self):
        text = "This is a comment without ending punctuation"
        result = _extract_first_sentence(text)
        assert result == text

    def test_long_text_truncated(self):
        text = "A" * 200
        result = _extract_first_sentence(text)
        assert len(result) <= 120

    def test_exclamation_boundary(self):
        assert _extract_first_sentence("Wow! That's great.") == "Wow!"

    def test_question_boundary(self):
        assert _extract_first_sentence("Really? I doubt it.") == "Really?"


# --- _extract_keywords ---

class TestExtractKeywords:
    def test_basic_extraction(self):
        sentences = ["Rust programming language", "Rust compiler performance"]
        stop_words = {"this", "that", "with"}
        result = _extract_keywords(sentences, stop_words)
        assert "rust" in result

    def test_stop_words_filtered(self):
        sentences = ["This is about using things really well"]
        stop_words = {"this", "about", "using", "things", "really", "well"}
        result = _extract_keywords(sentences, stop_words)
        assert "this" not in result
        assert "about" not in result

    def test_short_words_ignored(self):
        """Words shorter than 4 chars are excluded by the regex"""
        sentences = ["Go is a fun and new language"]
        result = _extract_keywords(sentences, set())
        assert "fun" not in result  # 3 chars
        assert "language" in result

    def test_empty_input(self):
        assert _extract_keywords([], set()) == []

    def test_returns_max_five(self):
        sentences = ["alpha bravo charlie delta echo foxtrot golf hotel india juliet"]
        result = _extract_keywords(sentences, set())
        assert len(result) <= 5

    def test_frequency_ordering(self):
        sentences = ["python python python", "python rust rust", "rust golang"]
        result = _extract_keywords(sentences, set())
        assert result[0] == "python"


# --- _filter_by_age ---

class TestFilterByAge:
    def _story(self, published_at):
        return {"title": "T", "published_at": published_at}

    def test_recent_story_passes(self):
        s = self._story(datetime.now().isoformat())
        assert _filter_by_age([s], 7) == [s]

    def test_old_story_filtered(self):
        s = self._story("2020-01-01T00:00:00")
        assert _filter_by_age([s], 7) == []

    def test_no_published_at_passes(self):
        s = {"title": "no date"}
        assert _filter_by_age([s], 7) == [s]

    def test_empty_published_at_passes(self):
        s = self._story("")
        assert _filter_by_age([s], 7) == [s]

    def test_invalid_date_passes(self):
        s = self._story("not-a-date")
        assert _filter_by_age([s], 7) == [s]

    def test_within_boundary_passes(self):
        s = self._story((datetime.now() - timedelta(days=6)).isoformat())
        assert _filter_by_age([s], 7) == [s]

    def test_outside_boundary_filtered(self):
        s = self._story((datetime.now() - timedelta(days=8)).isoformat())
        assert _filter_by_age([s], 7) == []

    def test_mixed_keeps_only_recent(self):
        recent = self._story(datetime.now().isoformat())
        old = self._story("2020-01-01T00:00:00")
        no_date = {"title": "no date"}
        result = _filter_by_age([recent, old, no_date], 7)
        assert result == [recent, no_date]

    def test_empty_list(self):
        assert _filter_by_age([], 7) == []


# --- _source_is_due ---

class TestSourceIsDue:
    def _monday_even(self):
        # A Monday with an even ISO week number
        # ISO week 2 of 2023 starts Mon Jan 9 2023
        return datetime(2023, 1, 9)  # weekday=0, isoweek=2

    def _monday_odd(self):
        # ISO week 1 of 2023: Mon Jan 2 2023
        return datetime(2023, 1, 2)  # weekday=0, isoweek=1

    def _tuesday(self):
        return datetime(2023, 1, 10)  # Tuesday

    def test_daily_always_true(self):
        assert _source_is_due("daily", datetime(2023, 6, 15)) is True

    def test_none_always_true(self):
        assert _source_is_due(None, datetime(2023, 6, 15)) is True

    def test_empty_string_always_true(self):
        assert _source_is_due("", datetime(2023, 6, 15)) is True

    def test_weekly_true_on_monday(self):
        assert _source_is_due("weekly", self._monday_even()) is True

    def test_weekly_false_on_tuesday(self):
        assert _source_is_due("weekly", self._tuesday()) is False

    def test_biweekly_true_monday_even_week(self):
        assert _source_is_due("biweekly", self._monday_even()) is True

    def test_biweekly_false_monday_odd_week(self):
        assert _source_is_due("biweekly", self._monday_odd()) is False

    def test_biweekly_false_non_monday(self):
        assert _source_is_due("biweekly", self._tuesday()) is False

    def test_monthly_true_on_first(self):
        assert _source_is_due("monthly", datetime(2023, 3, 1)) is True

    def test_monthly_false_on_second(self):
        assert _source_is_due("monthly", datetime(2023, 3, 2)) is False

    def test_quarterly_true_jan_1(self):
        assert _source_is_due("quarterly", datetime(2023, 1, 1)) is True

    def test_quarterly_true_apr_1(self):
        assert _source_is_due("quarterly", datetime(2023, 4, 1)) is True

    def test_quarterly_true_jul_1(self):
        assert _source_is_due("quarterly", datetime(2023, 7, 1)) is True

    def test_quarterly_true_oct_1(self):
        assert _source_is_due("quarterly", datetime(2023, 10, 1)) is True

    def test_quarterly_false_jan_2(self):
        assert _source_is_due("quarterly", datetime(2023, 1, 2)) is False

    def test_quarterly_false_feb_1(self):
        assert _source_is_due("quarterly", datetime(2023, 2, 1)) is False

    def test_list_true_on_matching_day(self):
        monday = datetime(2023, 1, 9)  # Monday
        assert _source_is_due(["mon", "wed", "fri"], monday) is True

    def test_list_false_on_non_matching_day(self):
        tuesday = datetime(2023, 1, 10)  # Tuesday
        assert _source_is_due(["mon", "wed", "fri"], tuesday) is False

    def test_list_case_insensitive(self):
        monday = datetime(2023, 1, 9)
        assert _source_is_due(["Mon", "WED"], monday) is True

    def test_unknown_frequency_defaults_true(self):
        assert _source_is_due("fortnightly", datetime(2023, 6, 15)) is True


# --- summarize_comments ---

class TestSummarizeComments:
    def test_empty_comments(self):
        assert summarize_comments([]) is None

    def test_empty_comments_with_descendants(self):
        assert summarize_comments([], descendants=42) == "42 comments"

    def test_comments_with_text(self):
        comments = [
            {"text": "<p>Python performance is impressive. Very cool.</p>"},
            {"text": "<p>Python async support matters. Great work.</p>"},
        ]
        result = summarize_comments(comments)
        assert result is not None
        assert "impressive" in result  # first sentence of top comment

    def test_comments_no_text(self):
        comments = [{"text": ""}, {"text": ""}]
        result = summarize_comments(comments, descendants=10)
        assert result == "10 comments"

    def test_comments_returns_top_comment_sentence(self):
        comments = [{"text": "Short thought. More after."}]
        result = summarize_comments(comments)
        assert result == "Short thought."


# --- generate_digest_text ---

class TestGenerateDigestText:
    def _make_story(self, title="Test Story", score=100, topic="AI/ML", **kwargs):
        defaults = {
            "title": title,
            "score": score,
            "matched_topic": topic,
            "by": "testuser",
            "id": 12345,
            "url": "https://example.com",
            "descendants": 50,
            "all_topic_scores": {topic: 0.9},
            "comment_summary": None,
        }
        defaults.update(kwargs)
        return defaults

    def test_empty_stories(self):
        result = generate_digest_text({"stories": [], "notable_authors": []})
        assert "Quiet day" in result

    def test_basic_digest_format(self):
        story = self._make_story()
        result = generate_digest_text({
            "stories": [story],
            "notable_authors": [],
            "engagement_opportunities": [],
        })
        assert "HN Digest" in result
        assert "Test Story" in result
        assert "↑100" in result
        assert "https://news.ycombinator.com/item?id=12345" in result

    def test_comment_summary_included(self):
        story = self._make_story(comment_summary="Discussing: rust, wasm, perf")
        result = generate_digest_text({
            "stories": [story],
            "notable_authors": [],
            "engagement_opportunities": [],
        })
        assert "Discussing: rust, wasm, perf" in result

    def test_notable_author_star(self):
        story = self._make_story(by="notable_dev")
        result = generate_digest_text({
            "stories": [story],
            "notable_authors": [
                {"author_name": "notable_dev", "story_count": 5, "topics": {"AI/ML": 0.9}}
            ],
            "engagement_opportunities": [],
        })
        assert "⭐" in result

    def test_inline_checkbox_on_stories(self):
        story = self._make_story()
        result = generate_digest_text({
            "stories": [story],
            "notable_authors": [],
            "engagement_opportunities": [],
        })
        assert "- [ ] Test Story" in result
        assert "  Notes: " in result
        # No separate read tracker section
        assert "## 📖 Read Tracker" not in result

    def test_no_separate_read_tracker(self):
        story = self._make_story(title="Main Story")
        eng_story = self._make_story(title="Engagement Story", id=99999)
        result = generate_digest_text({
            "stories": [story],
            "notable_authors": [],
            "engagement_opportunities": [{"story": eng_story, "type": "early",
                                          "score": 0.8, "action_prompt": "Go!"}],
        })
        assert "- [ ] Main Story" in result
        assert "## 📖 Read Tracker" not in result

    def test_weekend_sections_renders_two_sections(self):
        story = self._make_story()
        interesting = self._make_story(title="Viral HN Post", score=500, topic="Other", id=99999,
                                       url="https://example.com/viral")
        result = {
            "stories": [story, interesting],
            "notable_authors": [],
            "engagement_opportunities": [],
        }
        config = {"settings": {"weekend_mode": {"digest_title": "Weekend Reads"}}}
        output = generate_digest_text(result, config=config, weekend_sections=([story], [interesting]))
        assert "Weekend Reads" in output
        assert "Best Matches" in output
        assert "Interesting Reads" in output
        assert "Test Story" in output
        assert "Viral HN Post" in output

    def test_multiple_topics_grouped(self):
        s1 = self._make_story(title="AI thing", topic="AI/ML")
        s2 = self._make_story(title="Rust thing", topic="Systems", id=99999,
                              url="https://example.com/2")
        result = generate_digest_text({
            "stories": [s1, s2],
            "notable_authors": [],
            "engagement_opportunities": [],
        })
        assert "*AI/ML*" in result
        assert "*Systems*" in result


# --- _is_weekend ---

class TestIsWeekend:
    def test_saturday_is_weekend(self):
        assert _is_weekend(datetime(2026, 3, 7)) is True  # Saturday

    def test_sunday_is_weekend(self):
        assert _is_weekend(datetime(2026, 3, 8)) is True  # Sunday

    def test_thursday_is_not_weekend(self):
        assert _is_weekend(datetime(2026, 3, 5)) is False  # Thursday

    def test_monday_is_not_weekend(self):
        assert _is_weekend(datetime(2026, 3, 2)) is False  # Monday

    def test_friday_is_not_weekend(self):
        assert _is_weekend(datetime(2026, 3, 6)) is False  # Friday


# --- _apply_weekend_mode ---

class TestApplyWeekendMode:
    _config = {
        "settings": {
            "weekend_mode": {
                "similarity_threshold": 0.45,
                "max_top_matches": 10,
                "interesting_reads_count": 10,
                "interesting_min_score": 100,
            }
        }
    }

    def _story(self, url, score, title="T"):
        return {"url": url, "score": score, "title": title, "by": "u", "source": "hackernews"}

    def test_splits_by_threshold(self):
        high = self._story("http://a.com", 300)
        low = self._story("http://b.com", 200)
        scored = [(high, 0.6), (low, 0.2)]
        top, interesting = _apply_weekend_mode(scored, self._config)
        assert high in top
        assert low not in top
        assert low in interesting

    def test_top_matches_sorted_by_score(self):
        s1 = self._story("http://a.com", 100)
        s2 = self._story("http://b.com", 500)
        scored = [(s1, 0.9), (s2, 0.8)]
        top, _ = _apply_weekend_mode(scored, self._config)
        assert top[0] == s2  # higher score first

    def test_interesting_excludes_top_matches(self):
        s1 = self._story("http://a.com", 300)
        s2 = self._story("http://b.com", 200)
        scored = [(s1, 0.7), (s2, 0.1)]
        top, interesting = _apply_weekend_mode(scored, self._config)
        urls_in_top = {s["url"] for s in top}
        for s in interesting:
            assert s["url"] not in urls_in_top

    def test_interesting_min_score_filter(self):
        low_score = self._story("http://c.com", 50)
        scored = [(low_score, 0.1)]
        _, interesting = _apply_weekend_mode(scored, self._config)
        assert low_score not in interesting  # score < 100

    def test_interesting_sorted_by_score(self):
        s1 = self._story("http://a.com", 150)
        s2 = self._story("http://b.com", 400)
        scored = [(s1, 0.1), (s2, 0.2)]
        _, interesting = _apply_weekend_mode(scored, self._config)
        assert interesting[0] == s2

    def test_respects_max_top_matches(self):
        stories = [self._story(f"http://{i}.com", 100 + i) for i in range(20)]
        scored = [(s, 0.9) for s in stories]
        top, _ = _apply_weekend_mode(scored, self._config)
        assert len(top) <= 10

    def test_respects_interesting_reads_count(self):
        stories = [self._story(f"http://{i}.com", 200 + i) for i in range(20)]
        scored = [(s, 0.1) for s in stories]
        _, interesting = _apply_weekend_mode(scored, self._config)
        assert len(interesting) <= 10
