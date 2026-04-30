"""Tests for SQLite storage with temp file DB"""
import pytest
from knowledge_os.storage_sqlite import SQLiteStorage


@pytest.fixture
def storage(tmp_path):
    """Create a SQLite storage instance with a temp file"""
    return SQLiteStorage(db_path=str(tmp_path / "test.db"))


@pytest.fixture
def user_id(storage):
    """Create a test user and return user_id"""
    return storage.get_or_create_user("test@example.com")


class TestUsers:
    def test_create_user(self, storage):
        uid = storage.get_or_create_user("alice@test.com")
        assert uid >= 1

    def test_get_existing_user(self, storage):
        uid1 = storage.get_or_create_user("bob@test.com")
        uid2 = storage.get_or_create_user("bob@test.com")
        assert uid1 == uid2

    def test_different_users_different_ids(self, storage):
        uid1 = storage.get_or_create_user("a@test.com")
        uid2 = storage.get_or_create_user("b@test.com")
        assert uid1 != uid2


class TestItems:
    def test_insert_and_get(self, storage):
        item_id, is_new = storage.insert_item(
            url="https://example.com/1",
            title="Test Story",
            source="hackernews",
            author="pg",
            score=100,
            fetched_at="2026-01-01T00:00:00",
            published_at="2026-01-01T12:00:00",
        )
        assert is_new is True
        item = storage.get_item(item_id)
        assert item is not None
        assert item["title"] == "Test Story"
        assert item["score"] == 100

    def test_get_by_url(self, storage):
        url = "https://example.com/unique"
        storage.insert_item(url=url, title="T", source="hn", author="a",
                           score=1, fetched_at="2026-01-01", published_at="2026-01-01T12:00:00")
        item = storage.get_item_by_url(url)
        assert item is not None
        assert item["url"] == url

    def test_get_nonexistent(self, storage):
        assert storage.get_item(9999) is None

    def test_get_by_url_nonexistent(self, storage):
        assert storage.get_item_by_url("https://nope.com") is None

    def test_duplicate_url_returns_existing_id(self, storage):
        id1, is_new1 = storage.insert_item(url="https://dup.com", title="A", source="hn",
                                           author="a", score=1, fetched_at="2026-01-01",
                                           published_at="2026-01-01T12:00:00")
        id2, is_new2 = storage.insert_item(url="https://dup.com", title="B", source="hn",
                                           author="b", score=2, fetched_at="2026-01-02",
                                           published_at="2026-01-01T12:00:00")
        assert is_new1 is True
        assert is_new2 is False
        assert id1 == id2

    def test_is_new_flag(self, storage):
        _, is_new1 = storage.insert_item(url="https://new.com", title="N", source="hn",
                                         author="a", score=1, fetched_at="2026-01-01",
                                         published_at="2026-01-01T12:00:00")
        _, is_new2 = storage.insert_item(url="https://new.com", title="N", source="hn",
                                         author="a", score=1, fetched_at="2026-01-01",
                                         published_at="2026-01-01T12:00:00")
        assert is_new1 is True
        assert is_new2 is False

    def test_republish_resurfaces(self, storage):
        _, is_new1 = storage.insert_item(url="https://up.com", title="V1", source="hn",
                                         author="a", score=1, fetched_at="2026-01-01",
                                         published_at="2026-01-01T00:00:00")
        _, is_new2 = storage.insert_item(url="https://up.com", title="V2", source="hn",
                                         author="a", score=1, fetched_at="2026-01-02",
                                         published_at="2026-01-02T00:00:00")
        _, is_new3 = storage.insert_item(url="https://up.com", title="V2", source="hn",
                                         author="a", score=1, fetched_at="2026-01-03",
                                         published_at="2026-01-02T00:00:00")
        assert is_new1 is True   # first insert
        assert is_new2 is True   # newer published_at → re-surface
        assert is_new3 is False  # same published_at → skip

    def test_external_id_persisted(self, storage):
        item_id, _ = storage.insert_item(
            url="https://example.com/hn",
            title="HN Story",
            source="hackernews",
            author="pg",
            score=100,
            fetched_at="2026-01-01T00:00:00",
            published_at="2026-01-01T12:00:00",
            external_id="12345",
        )
        item = storage.get_item(item_id)
        assert item["external_id"] == "12345"


class TestTopics:
    def test_insert_and_get(self, storage, user_id):
        tid = storage.insert_topic(user_id, "AI/ML", ["machine learning", "AI"], weight=1.5)
        topics = storage.get_topics(user_id)
        assert len(topics) == 1
        assert topics[0]["name"] == "AI/ML"
        assert topics[0]["weight"] == 1.5
        assert "machine learning" in topics[0]["keywords"]

    def test_update_weight(self, storage, user_id):
        tid = storage.insert_topic(user_id, "Rust", ["rust", "systems"])
        storage.update_topic_weight(tid, 2.0)
        topics = storage.get_topics(user_id)
        assert topics[0]["weight"] == 2.0

    def test_topics_per_user(self, storage):
        u1 = storage.get_or_create_user("u1")
        u2 = storage.get_or_create_user("u2")
        storage.insert_topic(u1, "Topic A", ["a"])
        storage.insert_topic(u2, "Topic B", ["b"])
        assert len(storage.get_topics(u1)) == 1
        assert storage.get_topics(u1)[0]["name"] == "Topic A"


class TestFeedback:
    def test_insert_and_get(self, storage, user_id):
        item_id, _ = storage.insert_item(url="https://fb.com", title="FB",
                                         source="hn", author="a", score=1,
                                         fetched_at="2026-01-01",
                                         published_at="2026-01-01T12:00:00")
        storage.insert_feedback(user_id, item_id, "read",
                               metadata={"note": "interesting"})
        fb = storage.get_feedback(user_id, item_id)
        assert len(fb) == 1
        assert fb[0]["action"] == "read"
        assert fb[0]["metadata"]["note"] == "interesting"

    def test_multiple_feedback(self, storage, user_id):
        item_id, _ = storage.insert_item(url="https://multi.com", title="M",
                                         source="hn", author="a", score=1,
                                         fetched_at="2026-01-01",
                                         published_at="2026-01-01T12:00:00")
        storage.insert_feedback(user_id, item_id, "delivered")
        storage.insert_feedback(user_id, item_id, "read")
        fb = storage.get_feedback(user_id, item_id)
        assert len(fb) == 2

    def test_get_all_user_feedback(self, storage, user_id):
        for i in range(3):
            iid, _ = storage.insert_item(url=f"https://all{i}.com", title=f"T{i}",
                                         source="hn", author="a", score=1,
                                         fetched_at="2026-01-01",
                                         published_at="2026-01-01T12:00:00")
            storage.insert_feedback(user_id, iid, "delivered")
        fb = storage.get_feedback(user_id)
        assert len(fb) == 3

    def test_get_undelivered_item_ids(self, storage, user_id):
        id1, _ = storage.insert_item(url="https://ud1.com", title="U1",
                                     source="hn", author="a", score=1,
                                     fetched_at="2026-01-01",
                                     published_at="2026-01-01T12:00:00")
        id2, _ = storage.insert_item(url="https://ud2.com", title="U2",
                                     source="hn", author="a", score=1,
                                     fetched_at="2026-01-01",
                                     published_at="2026-01-01T12:00:00")
        id3, _ = storage.insert_item(url="https://ud3.com", title="U3",
                                     source="hn", author="a", score=1,
                                     fetched_at="2026-01-01",
                                     published_at="2026-01-01T12:00:00")
        storage.insert_feedback(user_id, id1, "delivered")
        # id2 has only a non-delivery action — still counts as undelivered
        storage.insert_feedback(user_id, id2, "read")
        # id3 has no feedback at all

        result = storage.get_undelivered_item_ids([id1, id2, id3])
        assert id1 not in result
        assert id2 in result
        assert id3 in result

    def test_get_undelivered_empty_input(self, storage):
        assert storage.get_undelivered_item_ids([]) == set()


class TestAuthors:
    def test_upsert_new(self, storage):
        user_id = storage.get_or_create_user("u1")
        storage.upsert_author(user_id, "newauthor", item_id=1,
                             topic_scores={"AI/ML": 0.9})
        authors = storage.get_notable_authors(user_id=user_id, min_count=1)
        assert len(authors) == 1
        assert authors[0]["author_name"] == "newauthor"

    def test_upsert_increments(self, storage):
        user_id = storage.get_or_create_user("u1")
        storage.upsert_author(user_id, "repeat", item_id=1,
                             topic_scores={"AI/ML": 0.5})
        storage.upsert_author(user_id, "repeat", item_id=2,
                             topic_scores={"AI/ML": 0.8})
        authors = storage.get_notable_authors(user_id=user_id, min_count=1)
        author = [a for a in authors if a["author_name"] == "repeat"][0]
        assert author["story_count"] == 2

    def test_duplicate_item_no_inflate(self, storage):
        """Same item_id called multiple times should not inflate story_count."""
        user_id = storage.get_or_create_user("u1")
        storage.upsert_author(user_id, "dup", item_id=1, topic_scores={"AI/ML": 0.5})
        storage.upsert_author(user_id, "dup", item_id=1, topic_scores={"AI/ML": 0.5})
        storage.upsert_author(user_id, "dup", item_id=1, topic_scores={"AI/ML": 0.5})
        authors = storage.get_notable_authors(user_id=user_id, min_count=1)
        author = [a for a in authors if a["author_name"] == "dup"][0]
        assert author["story_count"] == 1

    def test_notable_threshold(self, storage):
        user_id = storage.get_or_create_user("u1")
        storage.upsert_author(user_id, "once", item_id=1, topic_scores={"X": 0.5})
        # Default min_count=3 should filter this out
        assert storage.get_notable_authors(user_id=user_id, min_count=3) == []

    def test_authors_are_isolated_per_user(self, storage):
        user1 = storage.get_or_create_user("u1")
        user2 = storage.get_or_create_user("u2")
        storage.upsert_author(user1, "sharedauthor", item_id=1, topic_scores={"AI/ML": 0.9})
        assert storage.get_notable_authors(user_id=user1, min_count=1)
        assert storage.get_notable_authors(user_id=user2, min_count=1) == []


class TestDigests:
    def test_insert_and_get(self, storage, user_id):
        did = storage.insert_digest(user_id, [1, 2, 3], "2026-01-01T12:00:00")
        history = storage.get_digest_history(user_id)
        assert len(history) == 1
        assert history[0]["item_ids"] == [1, 2, 3]

    def test_history_ordering(self, storage, user_id):
        storage.insert_digest(user_id, [1], "2026-01-01T00:00:00")
        storage.insert_digest(user_id, [2], "2026-01-02T00:00:00")
        history = storage.get_digest_history(user_id)
        assert history[0]["item_ids"] == [2]  # most recent first

    def test_history_limit(self, storage, user_id):
        for i in range(15):
            storage.insert_digest(user_id, [i], f"2026-01-{i+1:02d}T00:00:00")
        history = storage.get_digest_history(user_id, limit=5)
        assert len(history) == 5
