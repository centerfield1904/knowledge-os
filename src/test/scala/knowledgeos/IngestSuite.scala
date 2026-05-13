package knowledgeos

import java.nio.file.Files

class IngestSuite extends munit.FunSuite:
  private def tempDb(): String =
    Files.createTempFile("knowledge-os-ingest", ".db").toString

  private def initCatalog(db: String): Unit =
    Db.withConnection(db) { conn =>
      Db.execute(
        conn,
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
        """
      )
      Db.execute(
        conn,
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
        """
      )
    }

  test("upsertStory dedupes items by URL and updates catalog fields") {
    val db = tempDb()
    initCatalog(db)
    Db.withConnection(db) { conn =>
      val first = Ingest.Story(
        title = "Old title",
        url = "https://example.com/story",
        source = "hackernews",
        externalId = Some("1"),
        authorName = "alice",
        score = 10,
        commentCount = 2,
        itemText = Some("body"),
        publishedAt = Some("2026-01-01T00:00:00Z"),
        metadataJson = "{}"
      )
      val second = first.copy(title = "New title", score = 42, commentCount = 5)

      Ingest.upsertStory(conn, first)
      Ingest.upsertStory(conn, second)

      val itemRows = Db.query(conn, "SELECT title, score, comment_count FROM items WHERE url = ?", Seq(first.url))(
        rs => (rs.getString("title"), rs.getInt("score"), rs.getInt("comment_count"))
      )
      val authorRows = Db.query(conn, "SELECT author_name FROM authors WHERE source = ?", Seq("hackernews"))(
        _.getString("author_name")
      )

      assertEquals(itemRows, Vector(("New title", 42, 5)))
      assertEquals(authorRows, Vector("alice"))
    }
  }
