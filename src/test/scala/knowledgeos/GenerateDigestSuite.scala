package knowledgeos

import java.nio.file.Files

class GenerateDigestSuite extends munit.FunSuite:
  private def tempDb(): String =
    Files.createTempFile("knowledge-os-digest", ".db").toString

  private def initDigestSchema(db: String): Unit =
    Db.withConnection(db) { conn =>
      Seq(
        """
        CREATE TABLE users (
          user_id INTEGER PRIMARY KEY AUTOINCREMENT,
          identifier TEXT NOT NULL UNIQUE
        )
        """,
        """
        CREATE TABLE topics (
          topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          active INTEGER DEFAULT 1
        )
        """,
        """
        CREATE TABLE items (
          item_id INTEGER PRIMARY KEY AUTOINCREMENT,
          url TEXT NOT NULL UNIQUE,
          title TEXT NOT NULL,
          source TEXT NOT NULL,
          author_name TEXT,
          score INTEGER DEFAULT 0,
          fetched_at TEXT NOT NULL,
          published_at TEXT
        )
        """,
        """
        CREATE TABLE item_topic_scores (
          item_id INTEGER NOT NULL,
          topic_id INTEGER NOT NULL,
          scoring_config_id INTEGER NOT NULL,
          score REAL NOT NULL,
          PRIMARY KEY (item_id, topic_id, scoring_config_id)
        )
        """,
        """
        CREATE TABLE user_topic_subscriptions (
          subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          topic_id INTEGER NOT NULL,
          min_topic_score REAL DEFAULT 0.3,
          author_filter_json TEXT,
          source_filter_json TEXT,
          freshness_days INTEGER DEFAULT 7,
          max_items INTEGER DEFAULT 10,
          suppress_delivered INTEGER DEFAULT 1,
          active INTEGER DEFAULT 1
        )
        """,
        """
        CREATE TABLE digests (
          digest_id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          status TEXT DEFAULT 'generated',
          metadata_json TEXT
        )
        """,
        """
        CREATE TABLE digest_items (
          digest_id INTEGER NOT NULL,
          item_id INTEGER NOT NULL,
          topic_id INTEGER,
          topic_score REAL,
          rank INTEGER NOT NULL,
          selection_reason_json TEXT,
          PRIMARY KEY (digest_id, item_id)
        )
        """,
        """
        CREATE TABLE feedback (
          feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          item_id INTEGER NOT NULL,
          digest_id INTEGER,
          action TEXT NOT NULL,
          metadata_json TEXT
        )
        """
      ).foreach(sql => Db.execute(conn, sql))
    }

  private def seed(db: String): Unit =
    Db.withConnection(db) { conn =>
      Db.execute(conn, "INSERT INTO users (identifier) VALUES ('vb')")
      Db.execute(conn, "INSERT INTO topics (name, active) VALUES ('AI', 1)")
      Db.execute(
        conn,
        """
        INSERT INTO items (url, title, source, author_name, score, fetched_at, published_at)
        VALUES
          ('https://example.com/a', 'High score', 'hackernews', 'alice', 100, '2026-01-01T00:00:00', '2026-01-01T00:00:00'),
          ('https://example.com/b', 'Denied author', 'hackernews', 'bob', 200, '2026-01-01T00:00:00', '2026-01-01T00:00:00'),
          ('https://example.com/c', 'Low topic score', 'hackernews', 'carol', 300, '2026-01-01T00:00:00', '2026-01-01T00:00:00')
        """
      )
      Db.execute(
        conn,
        """
        INSERT INTO item_topic_scores (item_id, topic_id, scoring_config_id, score)
        VALUES (1, 1, 1, 0.9), (2, 1, 1, 0.95), (3, 1, 1, 0.1)
        """
      )
      Db.execute(
        conn,
        """
        INSERT INTO user_topic_subscriptions
          (user_id, topic_id, min_topic_score, author_filter_json, source_filter_json,
           freshness_days, max_items, suppress_delivered, active)
        VALUES
          (1, 1, 0.5, '{"deny":["bob"]}', '["hackernews"]', 9999, 10, 1, 1)
        """
      )
    }

  test("selectCandidates applies score, source, author, and delivered filters") {
    val db = tempDb()
    initDigestSchema(db)
    seed(db)
    Db.withConnection(db) { conn =>
      val first = GenerateDigest.selectCandidates(conn, userId = 1, maxItems = 10)
      assertEquals(first.map(_.title), Vector("High score"))

      Db.execute(conn, "INSERT INTO feedback (user_id, item_id, action) VALUES (1, 1, 'delivered')")
      val second = GenerateDigest.selectCandidates(conn, userId = 1, maxItems = 10)
      assertEquals(second, Vector.empty)
    }
  }

  test("writeDigestItems records ranked membership and delivered feedback") {
    val db = tempDb()
    initDigestSchema(db)
    seed(db)
    Db.withConnection(db) { conn =>
      val digestId = GenerateDigest.createDigest(conn, userId = 1)
      val selected = GenerateDigest.selectCandidates(conn, userId = 1, maxItems = 10)
      GenerateDigest.writeDigestItems(conn, digestId, userId = 1, selected)

      val digestRows = Db.query(conn, "SELECT item_id, rank FROM digest_items WHERE digest_id = ?", Seq(digestId))(
        rs => (rs.getInt("item_id"), rs.getInt("rank"))
      )
      val feedbackRows = Db.query(conn, "SELECT item_id, action FROM feedback WHERE digest_id = ?", Seq(digestId))(
        rs => (rs.getInt("item_id"), rs.getString("action"))
      )

      assertEquals(digestRows, Vector((1, 1)))
      assertEquals(feedbackRows, Vector((1, "delivered")))
    }
  }
