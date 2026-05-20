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

  test("initCatalogSchema creates required tables for an empty database") {
    val db = tempDb()
    Db.withConnection(db) { conn =>
      Ingest.initCatalogSchema(conn)
      val tables = Db.query(
        conn,
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name IN ('authors', 'items', 'item_content')
        ORDER BY name
        """
      )(_.getString("name"))

      assertEquals(tables, Vector("authors", "item_content", "items"))
    }
  }

  test("hackerNewsStoryFromJson filters low score items") {
    val json = ujson.Obj(
      "type" -> "story",
      "title" -> "Too quiet",
      "url" -> "https://example.com/quiet",
      "by" -> "alice",
      "score" -> 10,
      "descendants" -> 1,
      "time" -> 1770000000
    )

    assertEquals(Ingest.hackerNewsStoryFromJson(1, json, minScore = 50), None)
  }

  test("hackerNewsStoryFromJson normalizes valid stories") {
    val json = ujson.Obj(
      "type" -> "story",
      "title" -> "Useful story",
      "url" -> "https://example.com/useful",
      "by" -> "alice",
      "score" -> 100,
      "descendants" -> 5,
      "text" -> "body",
      "time" -> 1770000000
    )

    val story = Ingest.hackerNewsStoryFromJson(123, json, minScore = 50).get

    assertEquals(story.title, "Useful story")
    assertEquals(story.externalId, Some("123"))
    assertEquals(story.authorName, "alice")
    assertEquals(story.score, 100)
  }

  test("rssStoriesFromXml normalizes feed items") {
    val xml =
      """
      <rss>
        <channel>
          <item>
            <title>Designing useful onboarding</title>
            <link>https://example.com/onboarding</link>
            <author>Design Feed</author>
            <pubDate>Fri, 15 May 2026 09:00:00 GMT</pubDate>
            <description><![CDATA[<p>Onboarding should earn attention.</p>]]></description>
          </item>
        </channel>
      </rss>
      """
    val feed = Ingest.FeedConfig(
      url = "https://example.com/feed",
      name = Some("Example Design"),
      maxItems = 5,
      requestTimeoutMs = 1000,
      retries = 0
    )

    val stories = Ingest.rssStoriesFromXml(xml, feed)

    assertEquals(stories.size, 1)
    assertEquals(stories.head.title, "Designing useful onboarding")
    assertEquals(stories.head.url, "https://example.com/onboarding")
    assertEquals(stories.head.source, "substack")
    assertEquals(stories.head.authorName, "Design Feed")
    assertEquals(stories.head.publishedAt, Some("2026-05-15T09:00:00Z"))
    assertEquals(stories.head.itemText, Some("Onboarding should earn attention."))
  }

  test("retry returns None after failures instead of throwing") {
    var attempts = 0
    val result = Ingest.retry(retries = 1) {
      attempts += 1
      throw new RuntimeException("temporary failure")
    }

    assertEquals(result, None)
    assertEquals(attempts, 2)
  }
