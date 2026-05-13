package knowledgeos

import java.sql.{Connection, DriverManager, PreparedStatement, ResultSet}

object Db:
  def connect(path: String): Connection =
    Class.forName("org.sqlite.JDBC")
    val conn = DriverManager.getConnection(s"jdbc:sqlite:$path")
    conn.createStatement().execute("PRAGMA foreign_keys = ON")
    conn

  def withConnection[A](path: String)(f: Connection => A): A =
    val conn = connect(path)
    try f(conn)
    finally conn.close()

  extension (ps: PreparedStatement)
    def bind(values: Seq[Any]): PreparedStatement =
      values.zipWithIndex.foreach { case (value, idx) =>
        val pos = idx + 1
        value match
          case null => ps.setObject(pos, null)
          case v: Int => ps.setInt(pos, v)
          case v: Long => ps.setLong(pos, v)
          case v: Double => ps.setDouble(pos, v)
          case v: Boolean => ps.setInt(pos, if v then 1 else 0)
          case v => ps.setString(pos, v.toString)
      }
      ps

  def query[A](conn: Connection, sql: String, values: Seq[Any] = Seq.empty)(row: ResultSet => A): Vector[A] =
    val ps = conn.prepareStatement(sql).bind(values)
    try
      val rs = ps.executeQuery()
      val out = Vector.newBuilder[A]
      while rs.next() do out += row(rs)
      out.result()
    finally ps.close()

  def execute(conn: Connection, sql: String, values: Seq[Any] = Seq.empty): Int =
    val ps = conn.prepareStatement(sql).bind(values)
    try ps.executeUpdate()
    finally ps.close()
