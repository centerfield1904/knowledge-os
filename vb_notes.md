# VB Notes


## Usage

### Useful db commands

List down materialized topics

```sql
select name from topics;
```

List items by topic and scores

```sql
select t.name as topic, round(s.score, 3) as topic_score, i.source, i.title, coalesce(i.author_name, '') as author, coalesce(i.published_at, i.fetched_at) as item_date, i.url from item_topic_scores s join items i on i.item_id = s.item_id join topics t on t.topic_id = s.topic_id order by s.score desc, item_date desc limit 50;
```

### Ingest and Analyze debug db

```
 # Inspect what ingest wrote
  sqlite3 knowledge_os.debug.db "select source, count(*) from items group by source;"

  # Then materialize VB subscriptions
venv/bin/python -m knowledge_os.personas --db knowledge_os.debug.db --catalog personas/catalog.json --users-dir configs/users

  ~~venv/bin/python -m knowledge_os.personas --db knowledge_os.debug.db --catalog personas/catalog.json --user-config
  configs/users/vb.json~~

  # Move to scoring against the debug DB
venv/bin/python -m knowledge_os.topic_scoring --db knowledge_os.debug.db --config config/topic_scoring.example.json
  
  # Then generate a digest from the debug DB
  sbt "runMain knowledgeos.GenerateDigest --db knowledge_os.debug.db --user vb --max-items 20"

  # Then render it
  venv/bin/python -m knowledge_os.render_digest --db knowledge_os.debug.db --user vb --digest-id 1

```