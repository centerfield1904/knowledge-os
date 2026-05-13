package knowledgeos

object Args:
  def parse(raw: Array[String]): Map[String, String] =
    def loop(rest: List[String], acc: Map[String, String]): Map[String, String] =
      rest match
        case Nil => acc
        case key :: value :: tail if key.startsWith("--") =>
          loop(tail, acc + (key.drop(2) -> value))
        case key :: tail if key.startsWith("--") =>
          loop(tail, acc + (key.drop(2) -> "true"))
        case _ :: tail => loop(tail, acc)
    loop(raw.toList, Map.empty)

  def required(args: Map[String, String], name: String): String =
    args.getOrElse(name, throw new IllegalArgumentException(s"Missing --$name"))
