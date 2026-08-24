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
          source_api TEXT,
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
        sourceApi = "hackernews_firebase",
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

  test("upsertStory accepts caller-provided ingest date as fetched_at") {
    val db = tempDb()
    initCatalog(db)
    Db.withConnection(db) { conn =>
      val story = Ingest.Story(
        title = "Dated ingest",
        url = "https://example.com/dated",
        source = "hackernews",
        sourceApi = "hackernews_firebase",
        externalId = Some("2"),
        authorName = "alice",
        score = 10,
        commentCount = 2,
        itemText = Some("body"),
        publishedAt = Some("2026-01-01T00:00:00Z"),
        metadataJson = "{}"
      )

      Ingest.upsertStory(conn, story, Ingest.ingestFetchedAt(Some("2026-05-14")))

      val fetchedAt = Db.query(conn, "SELECT fetched_at FROM items WHERE url = ?", Seq(story.url))(
        _.getString("fetched_at")
      )
      assertEquals(fetchedAt, Vector("2026-05-14T00:00:00Z"))
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
    assertEquals(story.sourceApi, "hackernews_firebase")
    assertEquals(story.externalId, Some("123"))
    assertEquals(story.authorName, "alice")
    assertEquals(story.score, 100)
  }

  test("rankedHackerNewsStories preserves HN ranking after score filtering") {
    def story(id: String, score: Int): Ingest.Story =
      Ingest.Story(
        title = s"Story $id",
        url = s"https://example.com/$id",
        source = "hackernews",
        sourceApi = "hackernews_firebase",
        externalId = Some(id),
        authorName = "alice",
        score = score,
        commentCount = 0,
        itemText = None,
        publishedAt = Some("2026-01-01T00:00:00Z"),
        metadataJson = "{}"
      )

    val rankedStories = Vector(
      story("frontpage-rank-1", 80),
      story("frontpage-rank-2", 1000),
      story("frontpage-rank-3", 90)
    )

    val selected = Ingest.rankedHackerNewsStories(rankedStories, maxItems = 2)

    assertEquals(selected.map(_.externalId.get), Vector("frontpage-rank-1", "frontpage-rank-2"))
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
    assertEquals(stories.head.sourceApi, "rss")
    assertEquals(stories.head.authorName, "Design Feed")
    assertEquals(stories.head.publishedAt, Some("2026-05-15T09:00:00Z"))
    assertEquals(stories.head.itemText, Some("Onboarding should earn attention."))
  }

  test("rssStoriesFromXml supports configured Economist source and guid URL fallback") {
    val xml =
      """
      <rss>
        <channel>
          <item>
            <title>World in Brief: Markets move</title>
            <guid isPermaLink="false">https://www.economist.com/the-world-in-brief/2026/08/20/example</guid>
            <pubDate>Thu, 20 Aug 2026 00:00:00 +0000</pubDate>
            <description>The world in brief

            America's government debt passed a large milestone.</description>
            <category>The World in Brief</category>
          </item>
        </channel>
      </rss>
      """
    val feed = Ingest.FeedConfig(
      url = "../economist-newspaper-rss-feed/dist/economist-fulltext.xml",
      name = Some("The Economist"),
      maxItems = 5,
      requestTimeoutMs = 1000,
      retries = 0,
      source = "economist"
    )

    val stories = Ingest.rssStoriesFromXml(xml, feed)
    val story = stories.head
    val metadata = ujson.read(story.metadataJson)

    assertEquals(stories.size, 1)
    assertEquals(story.title, "World in Brief: Markets move")
    assertEquals(story.url, "https://www.economist.com/the-world-in-brief/2026/08/20/example")
    assertEquals(story.source, "economist")
    assertEquals(story.sourceApi, "rss")
    assertEquals(story.authorName, "The Economist")
    assertEquals(story.publishedAt, Some("2026-08-20T00:00:00Z"))
    assert(story.itemText.exists(_.contains("America's government debt passed a large milestone.")))
    assertEquals(metadata("category").str, "The World in Brief")
    assertEquals(metadata("feed_source").str, "economist")
  }

  test("fetchRssFeeds reads generated local XML files") {
    val path = Files.createTempFile("economist-fulltext", ".xml")
    Files.writeString(
      path,
      """
      <rss>
        <channel>
          <item>
            <title>The war on data centres is a bit fake</title>
            <link>https://www.economist.com/business/2026/08/19/the-war-on-data-centres-is-a-bit-fake</link>
            <guid isPermaLink="false">76864362-7902-4951-8044-f586df7a68b4</guid>
            <pubDate>Wed, 19 Aug 2026 21:10:33 +0000</pubDate>
            <description>Developers are exaggerating their plans.</description>
            <category>Business</category>
          </item>
        </channel>
      </rss>
      """
    )
    val feed = Ingest.FeedConfig(
      url = path.toString,
      name = Some("The Economist"),
      maxItems = 5,
      requestTimeoutMs = 1000,
      retries = 0,
      source = "economist"
    )

    val stories = Ingest.fetchRssFeeds(Vector(feed))

    assertEquals(stories.map(_.source), Vector("economist"))
    assertEquals(stories.map(_.title), Vector("The war on data centres is a bit fake"))
    assertEquals(stories.head.externalId, Some("76864362-7902-4951-8044-f586df7a68b4"))
  }

  test("algoliaStoryFromHit normalizes historical HN stories") {
    val hit = ujson.Obj(
      "objectID" -> "123",
      "title" -> "Historical HN story",
      "url" -> "https://example.com/historical",
      "author" -> "alice",
      "points" -> 120,
      "num_comments" -> 12,
      "story_text" -> "body",
      "created_at_i" -> 1770000000
    )

    val story = Ingest.algoliaStoryFromHit(hit, minScore = 50).get

    assertEquals(story.title, "Historical HN story")
    assertEquals(story.source, "hackernews")
    assertEquals(story.sourceApi, "hackernews_algolia")
    assertEquals(story.externalId, Some("123"))
    assertEquals(story.score, 120)
    assertEquals(story.commentCount, 12)
    assertEquals(story.publishedAt, Some("2026-02-02T02:40:00Z"))
  }

  test("algoliaStoryFromHit filters low score historical HN stories") {
    val hit = ujson.Obj(
      "objectID" -> "123",
      "title" -> "Too quiet historically",
      "points" -> 10,
      "created_at_i" -> 1770000000
    )

    assertEquals(Ingest.algoliaStoryFromHit(hit, minScore = 50), None)
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
