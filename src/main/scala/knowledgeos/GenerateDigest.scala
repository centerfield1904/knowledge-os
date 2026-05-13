package knowledgeos

import java.sql.{Connection, ResultSet, Statement}

object GenerateDigest:
  case class Candidate(
      itemId: Int,
      topicId: Int,
      topicScore: Double,
      title: String,
      url: String,
      source: String,
      authorName: String,
      itemScore: Int,
      publishedAt: String
  )

  def main(raw: Array[String]): Unit =
    val args = Args.parse(raw)
    val db = args.getOrElse("db", "knowledge_os.db")
    val user = Args.required(args, "user")
    val maxItems = args.get("max-items").map(_.toInt).getOrElse(20)

    Db.withConnection(db) { conn =>
      conn.setAutoCommit(false)
      try
        val userId = userIdFor(conn, user)
        val digestId = createDigest(conn, userId)
        val selected = selectCandidates(conn, userId, maxItems)
        writeDigestItems(conn, digestId, userId, selected)
        conn.commit()
        println(renderSelectionJson(digestId, selected))
      catch
        case ex: Throwable =>
          conn.rollback()
          throw ex
    }

  def userIdFor(conn: Connection, identifier: String): Int =
    Db.query(conn, "SELECT user_id FROM users WHERE identifier = ?", Seq(identifier))(_.getInt("user_id"))
      .headOption
      .getOrElse(throw new IllegalArgumentException(s"Unknown user: $identifier"))

  def createDigest(conn: Connection, userId: Int): Int =
    val ps = conn.prepareStatement(
      "INSERT INTO digests (user_id, status, metadata_json) VALUES (?, 'generated', '{}')",
      Statement.RETURN_GENERATED_KEYS
    )
    try
      ps.setInt(1, userId)
      ps.executeUpdate()
      val keys = ps.getGeneratedKeys
      keys.next()
      keys.getInt(1)
    finally ps.close()

  def selectCandidates(conn: Connection, userId: Int, maxItems: Int): Vector[Candidate] =
    Db.query(
      conn,
      """
      SELECT
          i.item_id,
          t.topic_id,
          s.score AS topic_score,
          i.title,
          i.url,
          i.source,
          COALESCE(i.author_name, '') AS author_name,
          COALESCE(i.score, 0) AS item_score,
          COALESCE(i.published_at, i.fetched_at) AS published_at,
          sub.max_items
      FROM user_topic_subscriptions sub
      JOIN topics t ON t.topic_id = sub.topic_id
      JOIN item_topic_scores s ON s.topic_id = t.topic_id
      JOIN items i ON i.item_id = s.item_id
      WHERE sub.user_id = ?
        AND sub.active = 1
        AND t.active = 1
        AND s.score >= sub.min_topic_score
        AND (
          sub.freshness_days IS NULL OR
          datetime(COALESCE(i.published_at, i.fetched_at)) >= datetime('now', '-' || sub.freshness_days || ' days')
        )
        AND (
          sub.source_filter_json IS NULL OR
          sub.source_filter_json = '' OR
          EXISTS (
            SELECT 1 FROM json_each(sub.source_filter_json)
            WHERE json_each.value = i.source
          )
        )
        AND (
          sub.author_filter_json IS NULL OR
          json_array_length(json_extract(sub.author_filter_json, '$.allow')) IS NULL OR
          json_array_length(json_extract(sub.author_filter_json, '$.allow')) = 0 OR
          EXISTS (
            SELECT 1 FROM json_each(json_extract(sub.author_filter_json, '$.allow'))
            WHERE json_each.value = COALESCE(i.author_name, '')
          )
        )
        AND NOT EXISTS (
          SELECT 1 FROM json_each(json_extract(COALESCE(sub.author_filter_json, '{"deny":[]}'), '$.deny'))
          WHERE json_each.value = COALESCE(i.author_name, '')
        )
        AND (
          sub.suppress_delivered = 0 OR
          NOT EXISTS (
            SELECT 1 FROM feedback f
            WHERE f.user_id = sub.user_id
              AND f.item_id = i.item_id
              AND f.action = 'delivered'
          )
        )
      ORDER BY s.score DESC, COALESCE(i.score, 0) DESC, datetime(COALESCE(i.published_at, i.fetched_at)) DESC
      LIMIT ?
      """,
      Seq(userId, maxItems),
    ) { rs =>
      Candidate(
        itemId = rs.getInt("item_id"),
        topicId = rs.getInt("topic_id"),
        topicScore = rs.getDouble("topic_score"),
        title = rs.getString("title"),
        url = rs.getString("url"),
        source = rs.getString("source"),
        authorName = rs.getString("author_name"),
        itemScore = rs.getInt("item_score"),
        publishedAt = rs.getString("published_at")
      )
    }.distinctBy(_.itemId).take(maxItems)

  def writeDigestItems(conn: Connection, digestId: Int, userId: Int, selected: Vector[Candidate]): Unit =
    selected.zipWithIndex.foreach { case (candidate, idx) =>
      val rank = idx + 1
      Db.execute(
        conn,
        """
        INSERT INTO digest_items
          (digest_id, item_id, topic_id, topic_score, rank, selection_reason_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        Seq(
          digestId,
          candidate.itemId,
          candidate.topicId,
          candidate.topicScore,
          rank,
          ujson.Obj("rank" -> rank, "topic_score" -> candidate.topicScore).render()
        )
      )
      Db.execute(
        conn,
        """
        INSERT INTO feedback (user_id, item_id, digest_id, action, metadata_json)
        VALUES (?, ?, ?, 'delivered', ?)
        """,
        Seq(userId, candidate.itemId, digestId, ujson.Obj("rank" -> rank).render())
      )
    }

  def renderSelectionJson(digestId: Int, selected: Vector[Candidate]): String =
    ujson.Obj(
      "digest_id" -> digestId,
      "items" -> selected.zipWithIndex.map { case (candidate, idx) =>
        ujson.Obj(
          "rank" -> (idx + 1),
          "item_id" -> candidate.itemId,
          "topic_id" -> candidate.topicId,
          "topic_score" -> candidate.topicScore,
          "title" -> candidate.title,
          "url" -> candidate.url,
          "source" -> candidate.source,
          "author_name" -> candidate.authorName,
          "item_score" -> candidate.itemScore,
          "published_at" -> candidate.publishedAt
        )
      }
    ).render()
