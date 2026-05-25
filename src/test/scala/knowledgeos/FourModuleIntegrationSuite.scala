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
        """
      ).foreach(sql => Db.execute(conn, sql))
    }

  test("catalog ingestion composes with scored topic rows") {
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
      val scored = Db.query(
        conn,
        """
        SELECT i.title, t.name, s.score
        FROM item_topic_scores s
        JOIN items i ON i.item_id = s.item_id
        JOIN topics t ON t.topic_id = s.topic_id
        """,
      ) { rs =>
        (rs.getString("title"), rs.getString("name"), rs.getDouble("score"))
      }

      assertEquals(scored, Vector(("Scala ranks digest candidates", "Digest Ranking", 0.92)))
    }
  }
