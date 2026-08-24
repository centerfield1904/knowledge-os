package knowledgeos

import java.sql.Connection
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths}
import java.time.{Instant, LocalDate, ZoneOffset}
import scala.concurrent.{Await, ExecutionContext, Future}
import scala.concurrent.duration.Duration
import scala.util.Try
import scala.util.control.NonFatal
import scala.xml.{Node, XML}

object Ingest:
  private def log(message: String): Unit =
    val ts = Instant.now().toString
    Console.err.println(s"[$ts] [ingest] $message")

  case class Story(
      title: String,
      url: String,
      source: String,
      sourceApi: String,
      externalId: Option[String],
      authorName: String,
      score: Int,
      commentCount: Int,
      itemText: Option[String],
      publishedAt: Option[String],
      metadataJson: String
  )

  case class HackerNewsFetchConfig(
      minScore: Int,
      maxItems: Int,
      concurrency: Int,
      throttleMs: Int,
      requestTimeoutMs: Int,
      retries: Int
  )

  case class FeedConfig(
      url: String,
      name: Option[String],
      maxItems: Int,
      requestTimeoutMs: Int,
      retries: Int,
      source: String = "substack",
      sourceApi: String = "rss"
  )

  def main(raw: Array[String]): Unit =
    val args = Args.parse(raw)
    val db = args.getOrElse("db", "knowledge_os.db")
    val configPath = Args.required(args, "sources")
    val ingestDate = args.get("date").map(value => LocalDate.parse(value.trim))
    val historicalHn = args.get("historical-hn").exists(_.toBoolean)
    if historicalHn && ingestDate.isEmpty then
      throw new IllegalArgumentException("--historical-hn requires --date YYYY-MM-DD")
    val fetchedAt = ingestFetchedAt(args.get("date"))
    log(s"Loading source config from $configPath")
    val config = ujson.read(os.read(os.Path(configPath, os.pwd)))
    val stories = fetchConfiguredSources(config, historicalHnDate = if historicalHn then ingestDate else None)
    log(s"Fetched ${stories.size} catalog item(s); writing to $db")
    Db.withConnection(db) { conn =>
      conn.setAutoCommit(false)
      try
        initCatalogSchema(conn)
        stories.foreach(upsertStory(conn, _, fetchedAt))
        conn.commit()
        log(s"Committed ${stories.size} catalog item(s)")
      catch
        case ex: Throwable =>
          conn.rollback()
          log(s"Rolled back catalog write after failure: ${ex.getMessage}")
          throw ex
    }
    println(s"Upserted ${stories.size} catalog item(s)")

  def ingestFetchedAt(date: Option[String]): String =
    date match
      case Some(value) if value.trim.nonEmpty =>
        LocalDate.parse(value.trim).atStartOfDay(ZoneOffset.UTC).toInstant.toString
      case _ => Instant.now().toString

  def fetchConfiguredSources(config: ujson.Value, historicalHnDate: Option[LocalDate] = None): Vector[Story] =
    given ExecutionContext = ExecutionContext.global
    val sources = config("sources")
    val futures = Vector.newBuilder[Future[Vector[Story]]]

    sources.obj.get("hackernews").foreach { hn =>
      if hn("enabled").bool then
        val fetchConfig = HackerNewsFetchConfig(
          minScore = hn.obj.get("min_score").map(_.num.toInt).getOrElse(50),
          maxItems = hn.obj.get("max_items").map(_.num.toInt).getOrElse(90),
          concurrency = hn.obj.get("concurrency").map(_.num.toInt).getOrElse(8),
          throttleMs = hn.obj.get("throttle_ms").map(_.num.toInt).getOrElse(150),
          requestTimeoutMs = hn.obj.get("request_timeout_ms").map(_.num.toInt).getOrElse(10000),
          retries = hn.obj.get("retries").map(_.num.toInt).getOrElse(1)
        )
        log(
          s"Configured Hacker News fetch: maxItems=${fetchConfig.maxItems}, minScore=${fetchConfig.minScore}, " +
            s"concurrency=${fetchConfig.concurrency}, throttleMs=${fetchConfig.throttleMs}, " +
            s"timeoutMs=${fetchConfig.requestTimeoutMs}, retries=${fetchConfig.retries}"
        )
        futures += Future {
          historicalHnDate match
            case Some(date) => fetchHistoricalHackerNews(date, fetchConfig)
            case None => fetchHackerNews(fetchConfig)
        }
    }

    sources.obj.get("substack").foreach { substack =>
      if substack("enabled").bool then
        val feeds = configuredRssFeeds(substack, defaultSource = "substack", defaultSourceApi = "rss")
        log(s"Configured Substack/RSS fetch: feeds=${feeds.size}")
        futures += Future(fetchRssFeeds(feeds))
    }

    sources.obj.get("economist").foreach { economist =>
      if economist("enabled").bool then
        val feeds = configuredRssFeeds(economist, defaultSource = "economist", defaultSourceApi = "rss")
        log(s"Configured Economist RSS fetch: feeds=${feeds.size}")
        futures += Future(fetchRssFeeds(feeds))
    }

    val result = Future.sequence(futures.result()).map(_.flatten.toVector)
    Await.result(result, Duration.Inf)

  private def configuredRssFeeds(
      sourceConfig: ujson.Value,
      defaultSource: String,
      defaultSourceApi: String
  ): Vector[FeedConfig] =
    val maxItems = sourceConfig.obj.get("max_items_per_feed")
      .orElse(sourceConfig.obj.get("max_items"))
      .map(_.num.toInt)
      .getOrElse(10)
    val requestTimeoutMs = sourceConfig.obj.get("request_timeout_ms").map(_.num.toInt).getOrElse(15000)
    val retries = sourceConfig.obj.get("retries").map(_.num.toInt).getOrElse(1)
    val source = stringField(sourceConfig, "source").getOrElse(defaultSource)
    val sourceApi = sourceApiField(sourceConfig, defaultSourceApi)

    sourceConfig.obj.get("feeds").map(_.arr.toVector).getOrElse(Vector.empty).flatMap {
      case feed if feed.isInstanceOf[ujson.Str] =>
        Some(FeedConfig(feed.str, None, maxItems, requestTimeoutMs, retries, source, sourceApi))
      case feed if feed.isInstanceOf[ujson.Obj] =>
        feed.obj.get("url").map { url =>
          FeedConfig(
            url = url.str,
            name = stringField(feed, "name"),
            maxItems = feed.obj.get("max_items").map(_.num.toInt).getOrElse(maxItems),
            requestTimeoutMs = feed.obj.get("request_timeout_ms").map(_.num.toInt).getOrElse(requestTimeoutMs),
            retries = feed.obj.get("retries").map(_.num.toInt).getOrElse(retries),
            source = stringField(feed, "source").getOrElse(source),
            sourceApi = sourceApiField(feed, sourceApi)
          )
        }
      case _ => None
    }

  private def sourceApiField(value: ujson.Value, defaultSourceApi: String): String =
    stringField(value, "source_api").orElse(stringField(value, "sourceApi")).getOrElse(defaultSourceApi)

  def initCatalogSchema(conn: Connection): Unit =
    Db.execute(
      conn,
      """
      CREATE TABLE IF NOT EXISTS authors (
        author_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        external_author_id TEXT,
        author_name TEXT NOT NULL,
        profile_url TEXT,
        story_count INTEGER DEFAULT 0,
        total_score REAL DEFAULT 0.0,
        metadata_json TEXT,
        first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
        last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source, author_name)
      )
      """
    )
    Db.execute(
      conn,
      """
      CREATE TABLE IF NOT EXISTS items (
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
        metadata_json TEXT,
        FOREIGN KEY (author_id) REFERENCES authors(author_id)
      )
      """
    )
    Db.execute(
      conn,
      """
      CREATE TABLE IF NOT EXISTS item_content (
        content_id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        content_type TEXT NOT NULL,
        content_text TEXT NOT NULL,
        source TEXT,
        metadata_json TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (item_id) REFERENCES items(item_id),
        UNIQUE(item_id, content_type, source)
      )
      """
    )
    Db.execute(conn, "CREATE INDEX IF NOT EXISTS idx_items_url ON items(url)")
    Db.execute(conn, "CREATE INDEX IF NOT EXISTS idx_items_source_external ON items(source, external_id)")
    ensureColumn(conn, "items", "source_api", "source_api TEXT")
    Db.execute(
      conn,
      """
      UPDATE items
      SET source_api = CASE
        WHEN source = 'hackernews' THEN 'hackernews_firebase'
        WHEN source = 'substack' THEN 'rss'
        WHEN source = 'economist' THEN 'rss'
        ELSE source
      END
      WHERE source_api IS NULL OR source_api = ''
      """
    )
    Db.execute(conn, "CREATE INDEX IF NOT EXISTS idx_items_source_api ON items(source_api)")
    Db.execute(conn, "CREATE INDEX IF NOT EXISTS idx_item_content_item_type ON item_content(item_id, content_type)")

  private def ensureColumn(conn: Connection, table: String, column: String, ddl: String): Unit =
    val columns = Db.query(conn, s"PRAGMA table_info($table)")(_.getString("name")).toSet
    if !columns.contains(column) then
      Db.execute(conn, s"ALTER TABLE $table ADD COLUMN $ddl")

  def fetchHackerNews(minScore: Int, maxItems: Int): Vector[Story] =
    fetchHackerNews(
      HackerNewsFetchConfig(
        minScore = minScore,
        maxItems = maxItems,
        concurrency = 8,
        throttleMs = 150,
        requestTimeoutMs = 10000,
        retries = 1
      )
    )

  def fetchHackerNews(config: HackerNewsFetchConfig): Vector[Story] =
    log("Fetching Hacker News top story IDs")
    val topIds = requests
      .get(
        "https://hacker-news.firebaseio.com/v0/topstories.json",
        readTimeout = config.requestTimeoutMs,
        connectTimeout = config.requestTimeoutMs,
      )
      .text()
    val ids = ujson.read(topIds).arr.take(config.maxItems * 3).map(_.num.toLong)
    log(s"Fetching ${ids.size} Hacker News item payload(s) in batches of ${math.max(config.concurrency, 1)}")
    given ExecutionContext = ExecutionContext.global
    val batchSize = math.max(config.concurrency, 1)
    var batchNumber = 0
    val stories = ids.grouped(batchSize).flatMap { batch =>
      batchNumber += 1
      val futures = batch.map(id => Future(fetchHackerNewsItem(id, config))).toVector
      val fetched = Await.result(Future.sequence(futures), Duration.Inf).flatten
      log(s"Hacker News batch $batchNumber fetched ${fetched.size}/${batch.size} matching item(s)")
      if config.throttleMs > 0 then Thread.sleep(config.throttleMs.toLong)
      fetched
    }
    val result = rankedHackerNewsStories(stories, config.maxItems)
    log(s"Hacker News fetch produced ${result.size} item(s) after filtering")
    result

  def rankedHackerNewsStories(stories: IterableOnce[Story], maxItems: Int): Vector[Story] =
    stories.iterator.take(maxItems).toVector

  def fetchHistoricalHackerNews(date: LocalDate, config: HackerNewsFetchConfig): Vector[Story] =
    val start = date.atStartOfDay(ZoneOffset.UTC).toEpochSecond
    val end = date.plusDays(1).atStartOfDay(ZoneOffset.UTC).toEpochSecond
    val hitsPerPage = math.min(100, math.max(1, config.maxItems))
    val numericFilters = s"created_at_i>=$start,created_at_i<$end,points>=${config.minScore}"
    log(
      s"Fetching historical Hacker News stories from Algolia: date=$date, " +
        s"minScore=${config.minScore}, maxItems=${config.maxItems}"
    )

    val stories = Vector.newBuilder[Story]
    var storyCount = 0
    var page = 0
    var nbPages = 1
    while page < nbPages && storyCount < config.maxItems do
      val url = algoliaSearchUrl(
        "tags" -> "story",
        "numericFilters" -> numericFilters,
        "hitsPerPage" -> hitsPerPage.toString,
        "page" -> page.toString,
      )
      val body = retry(config.retries) {
        requests
          .get(url, readTimeout = config.requestTimeoutMs, connectTimeout = config.requestTimeoutMs)
          .text()
      }.getOrElse("")
      if body.nonEmpty then
        val json = ujson.read(body)
        nbPages = json.obj.get("nbPages").flatMap(value => Try(value.num.toInt).toOption).getOrElse(page + 1)
        val hits = json.obj.get("hits").map(_.arr.toVector).getOrElse(Vector.empty)
        val parsed = hits.flatMap(hit => algoliaStoryFromHit(hit, config.minScore))
        log(s"Algolia HN page $page fetched ${parsed.size}/${hits.size} matching story item(s)")
        parsed.foreach { story =>
          if storyCount < config.maxItems then
            stories += story
            storyCount += 1
        }
      page += 1
      if config.throttleMs > 0 && page < nbPages then Thread.sleep(config.throttleMs.toLong)

    val result = stories.result().sortBy(story => (-story.score, story.publishedAt.getOrElse(""), story.title)).take(config.maxItems)
    log(s"Historical Hacker News Algolia fetch produced ${result.size} item(s)")
    result

  private def algoliaSearchUrl(params: (String, String)*): String =
    val query = params
      .map { case (key, value) =>
        val encodedKey = URLEncoder.encode(key, StandardCharsets.UTF_8.name())
        val encodedValue = URLEncoder.encode(value, StandardCharsets.UTF_8.name())
        s"$encodedKey=$encodedValue"
      }
      .mkString("&")
    s"https://hn.algolia.com/api/v1/search_by_date?$query"

  def algoliaStoryFromHit(hit: ujson.Value, minScore: Int): Option[Story] =
    val objectId = stringField(hit, "objectID")
    val title = stringField(hit, "title").orElse(stringField(hit, "story_title")).getOrElse("")
    val score = intField(hit, "points").getOrElse(0)
    if objectId.isEmpty || title.trim.isEmpty || score < minScore then None
    else
      val id = objectId.get
      val createdAt = intField(hit, "created_at_i")
        .map(ts => Instant.ofEpochSecond(ts.toLong).toString)
        .orElse(stringField(hit, "created_at"))
      Some(
        Story(
          title = title,
          url = stringField(hit, "url")
            .orElse(stringField(hit, "story_url"))
            .getOrElse(s"https://news.ycombinator.com/item?id=$id"),
          source = "hackernews",
          sourceApi = "hackernews_algolia",
          externalId = Some(id),
          authorName = stringField(hit, "author").getOrElse("unknown"),
          score = score,
          commentCount = intField(hit, "num_comments").getOrElse(0),
          itemText = stringField(hit, "story_text"),
          publishedAt = createdAt,
          metadataJson = ujson.Obj(
            "source_api" -> "hackernews_algolia",
            "provider" -> "algolia",
            "raw" -> hit,
          ).render()
        )
      )

  private def stringField(value: ujson.Value, key: String): Option[String] =
    value.obj.get(key).flatMap {
      case ujson.Str(raw) if raw.trim.nonEmpty => Some(raw.trim)
      case _ => None
    }

  private def intField(value: ujson.Value, key: String): Option[Int] =
    value.obj.get(key).flatMap(raw => Try(raw.num.toInt).toOption)

  def fetchHackerNewsItem(id: Long, config: HackerNewsFetchConfig): Option[Story] =
    retry(config.retries) {
      val body = requests
        .get(
          s"https://hacker-news.firebaseio.com/v0/item/$id.json",
          readTimeout = config.requestTimeoutMs,
          connectTimeout = config.requestTimeoutMs,
        )
        .text()
      hackerNewsStoryFromJson(id, ujson.read(body), config.minScore)
    }.flatten

  def hackerNewsStoryFromJson(id: Long, json: ujson.Value, minScore: Int): Option[Story] =
    if json.obj.get("type").exists(_.str == "story") &&
       json.obj.get("score").exists(_.num.toInt >= minScore) &&
       !json.obj.get("deleted").exists(_.bool)
    then
      Some(
        Story(
          title = json.obj.get("title").map(_.str).getOrElse(""),
          url = json.obj.get("url").map(_.str).getOrElse(s"https://news.ycombinator.com/item?id=$id"),
          source = "hackernews",
          sourceApi = "hackernews_firebase",
          externalId = Some(id.toString),
          authorName = json.obj.get("by").map(_.str).getOrElse("unknown"),
          score = json.obj.get("score").map(_.num.toInt).getOrElse(0),
          commentCount = json.obj.get("descendants").map(_.num.toInt).getOrElse(0),
          itemText = json.obj.get("text").map(_.str),
          publishedAt = json.obj.get("time").map(ts => Instant.ofEpochSecond(ts.num.toLong).toString),
          metadataJson = json.render()
        )
      )
    else None

  def retry[A](retries: Int)(block: => A): Option[A] =
    var remaining = math.max(retries, 0)
    while true do
      try return Some(block)
      catch
        case NonFatal(ex) =>
          if remaining <= 0 then
            Console.err.println(s"[warn] Skipping fetch after failure: ${ex.getMessage}")
            return None
          remaining -= 1
          Thread.sleep(250L)
    None

  def fetchRssFeeds(feeds: Vector[FeedConfig]): Vector[Story] =
    feeds.flatMap { feed =>
      retry(feed.retries) {
        log(s"Fetching feed ${feed.url}")
        val body = fetchFeedText(feed)
        val stories = rssStoriesFromXml(body, feed)
        log(s"Feed ${feed.url} produced ${stories.size} item(s)")
        stories
      }.getOrElse(Vector.empty)
    }

  private def fetchFeedText(feed: FeedConfig): String =
    val rawUrl = feed.url.trim
    if rawUrl.startsWith("http://") || rawUrl.startsWith("https://") then
      requests
        .get(rawUrl, readTimeout = feed.requestTimeoutMs, connectTimeout = feed.requestTimeoutMs)
        .text()
    else
      val path =
        if rawUrl.startsWith("file://") then Paths.get(java.net.URI.create(rawUrl))
        else Paths.get(rawUrl)
      val resolved = if path.isAbsolute then path else Paths.get("").toAbsolutePath.resolve(path).normalize()
      Files.readString(resolved, StandardCharsets.UTF_8)

  def rssStoriesFromXml(xmlText: String, feed: FeedConfig): Vector[Story] =
    val root = XML.loadString(xmlText)
    val entries = (root \\ "item").toVector match
      case Vector() => (root \\ "entry").toVector
      case items => items

    entries.take(feed.maxItems).flatMap { entry =>
      val title = text(entry, "title")
      val url = rssEntryUrl(entry)
      if title.isEmpty || url.isEmpty then None
      else
        val guid = text(entry, "guid")
        val author = firstNonEmpty(
          text(entry, "author"),
          text(entry, "creator"),
          text(entry, "dc:creator"),
          feed.name.getOrElse(hostFromUrl(feed.url))
        )
        val publishedAt = firstNonEmpty(
          text(entry, "pubDate"),
          text(entry, "published"),
          text(entry, "updated")
        )
        val summary = firstNonEmpty(
          text(entry, "description"),
          text(entry, "summary"),
          text(entry, "content"),
          text(entry, "content:encoded")
        )
        val category = text(entry, "category")
        Some(
          Story(
            title = normalizeWhitespace(title),
            url = url,
            source = feed.source,
            sourceApi = feed.sourceApi,
            externalId = Some(firstNonEmpty(guid, url)),
            authorName = normalizeWhitespace(author),
            score = 0,
            commentCount = 0,
            itemText = Some(stripHtml(summary)).filter(_.nonEmpty),
            publishedAt = Some(normalizeFeedDate(publishedAt)).filter(_.nonEmpty),
            metadataJson = ujson.Obj(
              "feed_url" -> feed.url,
              "feed_name" -> feed.name.getOrElse(hostFromUrl(feed.url)),
              "feed_source" -> feed.source,
              "category" -> category,
              "raw_published_at" -> publishedAt
            ).render()
          )
        )
    }

  private def text(node: Node, label: String): String =
    val direct = (node \ label).headOption.map(_.text.trim).getOrElse("")
    if direct.nonEmpty then direct
    else
      val suffix = label.stripPrefix("dc:").stripPrefix("content:")
      node.child.collectFirst {
        case child: Node if child.label == suffix || child.label == label => child.text.trim
      }.getOrElse("")

  private def rssEntryUrl(entry: Node): String =
    val linkText = text(entry, "link")
    if linkText.nonEmpty then linkText
    else
      (entry \ "link")
        .flatMap(node => node.attribute("href").map(_.text))
        .headOption
        .getOrElse {
          val guid = text(entry, "guid")
          if guid.startsWith("http://") || guid.startsWith("https://") then guid else ""
        }

  private def firstNonEmpty(values: String*): String =
    values.find(_.trim.nonEmpty).map(_.trim).getOrElse("")

  private def stripHtml(value: String): String =
    normalizeWhitespace(value.replaceAll("<[^>]+>", " "))

  private def normalizeWhitespace(value: String): String =
    value.replaceAll("\\s+", " ").trim

  private def normalizeFeedDate(value: String): String =
    val trimmed = value.trim
    if trimmed.isEmpty then ""
    else
      try Instant.parse(trimmed).toString
      catch
        case _: Throwable =>
          try java.time.ZonedDateTime.parse(trimmed, java.time.format.DateTimeFormatter.RFC_1123_DATE_TIME).toInstant.toString
          catch case _: Throwable => trimmed

  private def hostFromUrl(url: String): String =
    try Option(java.net.URI(url).getHost).getOrElse("unknown").stripPrefix("www.")
    catch case _: Throwable => "unknown"

  def upsertStory(conn: Connection, story: Story): Unit =
    upsertStory(conn, story, Instant.now().toString)

  def upsertStory(conn: Connection, story: Story, fetchedAt: String): Unit =
    val authorId = upsertAuthor(conn, story.source, story.authorName)
    Db.execute(
      conn,
      """
      INSERT INTO items
        (url, title, source, external_id, author_id, author_name, score, comment_count,
         item_text, fetched_at, published_at, source_api, updated_at, metadata_json)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
      ON CONFLICT(url) DO UPDATE SET
        title = excluded.title,
        source = excluded.source,
        source_api = excluded.source_api,
        external_id = COALESCE(excluded.external_id, items.external_id),
        author_id = excluded.author_id,
        author_name = excluded.author_name,
        score = excluded.score,
        comment_count = excluded.comment_count,
        item_text = excluded.item_text,
        fetched_at = excluded.fetched_at,
        published_at = COALESCE(excluded.published_at, items.published_at),
        updated_at = CURRENT_TIMESTAMP,
        metadata_json = excluded.metadata_json
      """,
      Seq(
        story.url,
        story.title,
        story.source,
        story.externalId.orNull,
        authorId,
        story.authorName,
        story.score,
        story.commentCount,
        story.itemText.orNull,
        fetchedAt,
        story.publishedAt.orNull,
        story.sourceApi,
        story.metadataJson
      )
    )

  def upsertAuthor(conn: Connection, source: String, authorName: String): Int =
    Db.execute(
      conn,
      """
      INSERT INTO authors (source, author_name, story_count, first_seen, last_seen)
      VALUES (?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
      ON CONFLICT(source, author_name) DO UPDATE SET last_seen = CURRENT_TIMESTAMP
      """,
      Seq(source, authorName)
    )
    Db.query(conn, "SELECT author_id FROM authors WHERE source = ? AND author_name = ?", Seq(source, authorName))(
      _.getInt("author_id")
    ).head
