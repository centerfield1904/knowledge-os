ThisBuild / scalaVersion := "3.5.2"

lazy val root = (project in file("."))
  .settings(
    name := "knowledge-os-scala",
    libraryDependencies ++= Seq(
      "org.xerial" % "sqlite-jdbc" % "3.46.1.3",
      "com.lihaoyi" %% "ujson" % "4.0.2",
      "com.lihaoyi" %% "os-lib" % "0.11.3",
      "com.lihaoyi" %% "requests" % "0.9.0",
      "org.scalameta" %% "munit" % "1.0.2" % Test
    )
  )
