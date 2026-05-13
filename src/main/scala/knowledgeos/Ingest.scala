package knowledgeos

import java.sql.{Connection, Statement}
import java.time.Instant
import scala.concurrent.{Await, ExecutionContext, Future}
import scala.concurrent.duration.Duration

object Ingest:
  case class Story(
      title: String,
      url: String,
      source: String,
      externalId: Option[String],
      authorName: String,
      score: Int,
      commentCount: Int,
      itemText: Option[String],
      publishedAt: Option[String],
      metadataJson: String
  )

  def main(raw: Array[String]): Unit =
    val args = Args.parse(raw)
    val db = args.getOrElse("db", "knowledge_os.db")
    val configPath = Args.required(args, "sources")
    val config = ujson.read(os.read(os.Path(configPath, os.pwd)))
    val stories = fetchConfiguredSources(config)
    Db.withConnection(db) { conn =>
      conn.setAutoCommit(false)
      try
        stories.foreach(upsertStory(conn, _))
        conn.commit()
      catch
        case ex: Throwable =>
          conn.rollback()
          throw ex
    }
    println(s"Upserted ${stories.size} catalog item(s)")

  def fetchConfiguredSources(config: ujson.Value): Vector[Story] =
    given ExecutionContext = ExecutionContext.global
    val sources = config("sources")
    val futures = Vector.newBuilder[Future[Vector[Story]]]

    sources.obj.get("hackernews").foreach { hn =>
      if hn("enabled").bool then
        val minScore = hn.obj.get("min_score").map(_.num.toInt).getOrElse(50)
        val maxItems = hn.obj.get("max_items").map(_.num.toInt).getOrElse(90)
        futures += Future(fetchHackerNews(minScore, maxItems))
    }

    val result = Future.sequence(futures.result()).map(_.flatten.toVector)
    Await.result(result, Duration.Inf)

  def fetchHackerNews(minScore: Int, maxItems: Int): Vector[Story] =
    val topIds = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json").text()
    val ids = ujson.read(topIds).arr.take(maxItems * 3).map(_.num.toLong)
    given ExecutionContext = ExecutionContext.global
    val futures = ids.map { id =>
      Future {
        val body = requests.get(s"https://hacker-news.firebaseio.com/v0/item/$id.json").text()
        val json = ujson.read(body)
        if json.obj.get("type").exists(_.str == "story") &&
           json.obj.get("score").exists(_.num.toInt >= minScore) &&
           !json.obj.get("deleted").exists(_.bool)
        then
          Some(
            Story(
              title = json.obj.get("title").map(_.str).getOrElse(""),
              url = json.obj.get("url").map(_.str).getOrElse(s"https://news.ycombinator.com/item?id=$id"),
              source = "hackernews",
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
      }
    }
    Await.result(Future.sequence(futures), Duration.Inf).flatten.sortBy(-_.score).take(maxItems).toVector

  def upsertStory(conn: Connection, story: Story): Unit =
    val authorId = upsertAuthor(conn, story.source, story.authorName)
    Db.execute(
      conn,
      """
      INSERT INTO items
        (url, title, source, external_id, author_id, author_name, score, comment_count,
         item_text, fetched_at, published_at, updated_at, metadata_json)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
      ON CONFLICT(url) DO UPDATE SET
        title = excluded.title,
        source = excluded.source,
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
        Instant.now().toString,
        story.publishedAt.orNull,
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
