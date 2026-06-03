# VB Notes


## Usage

### Pipeline debug commands

e2e pipeline
```bash
 bash scripts/run_modular_digest.sh --db knowledge_os.debug.db --output /tmp/knos-digest
 ```

### Useful db commands

List down materialized topics

```sql
select name from topics;
```

List items by topic and scores

```sql
select t.name as topic, round(s.score, 3) as topic_score, i.source, i.title, coalesce(i.author_name, '') as author, coalesce(i.published_at, i.fetched_at) as item_date, i.url from item_topic_scores s join items i on i.item_id = s.item_id join topics t on t.topic_id = s.topic_id order by s.score desc, item_date desc limit 50;
```

```sql
select t.name as topic, round(s.score, 3) as topic_score, i.source, i.title, i.published_at, i.fetched_at from item_topic_scores s join items i on i.item_id = s.item_id join topics t on t.topic_id = s.topic_id where s.score > 0.3 AND topic = 'AI Research' order by s.score desc, i.published_at desc limit 50;
```

Browse items fetched today, with filters:

```bash
bash scripts/query_fetched_items.sh --limit 50
bash scripts/query_fetched_items.sh --min-score 100
bash scripts/query_fetched_items.sh --topic "AI Research" --min-topic-score 0.3
bash scripts/query_fetched_items.sh --title agent
bash scripts/query_fetched_items.sh --source hackernews --format json
bash scripts/query_fetched_items.sh --source-api hackernews_algolia --date 2026-02-12
bash scripts/query_fetched_items.sh --date 2026-05-28 --topic design --title interface
```

Historical HN backfill uses Algolia instead of today's Firebase top stories. This fetches HN submissions for the requested date, not an exact historical front-page snapshot.

```bash
bash scripts/run_modular_digest.sh --db /tmp/knowledge_os.2026-02-12.db --date 2026-02-12 --historical-hn --overwrite
```

Provider marker:

```sql
select source, source_api, count(*) from items group by source, source_api;
```

### Delivery and WhatsApp ops

Morning cron generates the digest, commits `knos-digest/YYYY-MM-DD.md`, pushes it, and triggers the remote website GitHub Action:

```bash
bash scripts/run_catalog_ingest.sh
bash scripts/run_daily_ingest_and_verify_publish.sh
bash scripts/run_catalog_ingest.sh --date 2026-05-28
```

Daily publish readiness guard:

```bash
bash scripts/check_daily_digest_ready.sh
bash scripts/check_daily_digest_ready.sh --alert-vb
```

Afternoon cron sends from the existing digest without regenerating catalog/digest or rebuilding site. Manas and Mikey wrappers fail closed if the website has not published today's digest. VB is daily; Kintu is Friday weekly, matching `ux_design.send_days`.

```bash
bash scripts/daily_manas_whatsapp_digest.sh
bash scripts/daily_mikey_whatsapp_digest.sh
bash scripts/daily_vb_whatsapp_digest.sh
bash scripts/weekly_kintu_whatsapp_digest.sh
bash scripts/deliver_whatsapp_digest.sh --users vb --skip-digest --skip-site --send
```

Zero-item digests still send a focus message:

```text
Nothing worth noticing surfaced in today's digest.

Use this as a quiet window: stay focused, protect your attention, and spend the time on the work that matters.
```

Baileys session health check:

```bash
node scripts/baileys_send.mjs --login-only --timeout-ms 30000
```

Expected:

```json
{"ok":true,"loginOnly":true,"sessionDir":"/Users/vb/.config/knowledge-os/baileys-auth"}
```

Usually this login stays valid for weeks/months if used daily. Relink only if the command prints a QR, WhatsApp unlinks the device, or `~/.config/knowledge-os/baileys-auth` is deleted/corrupted.

Confirm the linked WhatsApp account without printing secrets:

```bash
node -e "const fs=require('fs'); const c=JSON.parse(fs.readFileSync(process.env.HOME+'/.config/knowledge-os/baileys-auth/creds.json','utf8')); console.log(JSON.stringify({me:c.me, registered:c.registered, platform:c.platform}, null, 2));"
```

If sends get flaky, avoid deleting the whole auth directory first. Clear only stale session cache, then health check:

```bash
rm ~/.config/knowledge-os/baileys-auth/session-*.json
node scripts/baileys_send.mjs --login-only --timeout-ms 30000
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
