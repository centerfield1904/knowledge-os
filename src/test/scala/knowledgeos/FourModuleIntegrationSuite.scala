package knowledgeos

import java.nio.file.Files

class FourModuleIntegrationSuite extends munit.FunSuite:
  private def tempDb(): String =
    Files.createTempFile("knowledge-os-four-module", ".db").toString

  private def initTargetSchema(db: String): Unit =
    Db.withConnection(db) { conn =>
      Seq(
        """
        CREATE TABLE authors (
          author_id INTEGER PRIMARY KEY AUTOINCREMENT,
          source TEXT NOT NULL,
          author_name TEXT NOT NULL,
          story_count INTEGER DEFAULT 0,
          first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
          last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(source, author_name)
        )
        """,
        """
        CREATE TABLE items (
          item_id INTEGER PRIMARY KEY AUTOINCREMENT,
          url TEXT NOT NULL UNIQUE,
          title TEXT NOT NULL,
          source TEXT NOT NULL,
          external_id TEXT,
          author_id INTEGER,
          author_name TEXT,
          score INTEGER DEFAULT 0,
          comment_count INTEGER DEFAULT 0,
          item_text TEXT,
          fetched_at TEXT NOT NULL,
          published_at TEXT,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          metadata_json TEXT
        )
        """,
        """
        CREATE TABLE item_content (
          content_id INTEGER PRIMARY KEY AUTOINCREMENT,
          item_id INTEGER NOT NULL,
          content_type TEXT NOT NULL,
          content_text TEXT,
          metadata_json TEXT,
          fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
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
        CREATE TABLE topic_scoring_configs (
          scoring_config_id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          config_json TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE item_topic_scores (
          item_id INTEGER NOT NULL,
          topic_id INTEGER NOT NULL,
          scoring_config_id INTEGER NOT NULL,
          score REAL NOT NULL,
          scored_at TEXT DEFAULT CURRENT_TIMESTAMP,
          evidence_json TEXT,
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

  test("catalog scoring subscriptions and engagement compose through the target schema") {
    val db = tempDb()
    initTargetSchema(db)

    Db.withConnection(db) { conn =>
      Ingest.upsertStory(
        conn,
        Ingest.Story(
          title = "Scala ranks digest candidates",
          url = "https://example.com/scala-ranking",
          source = "hackernews",
          externalId = Some("42"),
          authorName = "alice",
          score = 120,
          commentCount = 8,
          itemText = Some("Selection and ranking are latency-sensitive."),
          publishedAt = Some("2026-05-13T00:00:00Z"),
          metadataJson = """{"source":"test"}"""
        )
      )
      Db.execute(
        conn,
        """
        INSERT INTO item_content (item_id, content_type, content_text, metadata_json)
        VALUES (1, 'comments', 'Readers discuss concurrency and ranking.', '{}')
        """
      )
      Db.execute(conn, "INSERT INTO users (identifier) VALUES ('vb')")
      Db.execute(conn, "INSERT INTO topics (name, active) VALUES ('Digest Ranking', 1)")
      Db.execute(
        conn,
        """
        INSERT INTO topic_scoring_configs (name, config_json)
        VALUES ('comment-aware-v1', '{"content_fields":["title","item_text","comments"]}')
        """
      )
      Db.execute(
        conn,
        """
        INSERT INTO item_topic_scores
          (item_id, topic_id, scoring_config_id, score, evidence_json)
        VALUES (1, 1, 1, 0.92, '{"matched_content":["comments"]}')
        """
      )
      Db.execute(
        conn,
        """
        INSERT INTO user_topic_subscriptions
          (user_id, topic_id, min_topic_score, author_filter_json, source_filter_json,
           freshness_days, max_items, suppress_delivered, active)
        VALUES (1, 1, 0.7, '{"deny":[]}', '["hackernews"]', 30, 5, 1, 1)
        """
      )

      val digestId = GenerateDigest.createDigest(conn, userId = 1)
      val selected = GenerateDigest.selectCandidates(conn, userId = 1, maxItems = 5)
      GenerateDigest.writeDigestItems(conn, digestId, userId = 1, selected)

      assertEquals(selected.map(_.title), Vector("Scala ranks digest candidates"))
      assertEquals(selected.map(_.topicScore), Vector(0.92))

      val digestRows = Db.query(conn, "SELECT item_id, topic_id, rank FROM digest_items WHERE digest_id = ?", Seq(digestId))(
        rs => (rs.getInt("item_id"), rs.getInt("topic_id"), rs.getInt("rank"))
      )
      val delivered = Db.query(conn, "SELECT action FROM feedback WHERE digest_id = ?", Seq(digestId))(
        _.getString("action")
      )

      assertEquals(digestRows, Vector((1, 1, 1)))
      assertEquals(delivered, Vector("delivered"))
    }
  }
