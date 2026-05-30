# knowledge-os

Multi-source digest pipeline that fetches stories from HN and Substack RSS, matches to user topics via semantic similarity, detects engagement opportunities, and delivers daily digests.

## Commands

```bash
# Run production morning ingest/render and push the digest artifact
bash scripts/run_catalog_ingest.sh

# Run modular ingest/render locally without publishing
bash scripts/run_modular_digest.sh --db knowledge_os.db --date "$(date +%F)" --overwrite

# Send from the existing rendered digest artifact
bash scripts/daily_vb_whatsapp_digest.sh
bash scripts/weekly_kintu_whatsapp_digest.sh

# Run tests
venv/bin/python -m pytest tests/ -v

# Sync reading log from a digest file
venv/bin/python -m knowledge_os.sync_reading_log knos-digest/YYYY-MM-DD.md

# Run engagement summary
venv/bin/python -m knowledge_os.engagement_summary

# Run local dashboard
venv/bin/python -m streamlit run src/knowledge_os/dashboard.py
```

## Environment

- **Package manager:** Always use `uv` — never bare `pip` or `pip3`
  - Install: `uv pip install <pkg> --python venv/bin/python`
- **Python:** Always use `venv/bin/python`, never system python
- **Database:** SQLite at `knowledge_os.db` for the modular path; legacy v2 may still use `hn_digest_v2.db`. Never DROP or DELETE without WHERE.
- **Tests:** pytest with `tmp_path` fixtures for DB isolation (not `:memory:` — connections don't persist across `_get_conn()` calls)

## Architecture

```
knowledgeos.Ingest ─→ items/authors/item_content
                          ↓
topic_scoring.py ───→ item_topic_scores
                          ↓
personas.py ────────→ users/user_topic_subscriptions
                          ↓
persona_digest.py ──→ knos-digest/YYYY-MM-DD.md
                          ↓
whatsapp_delivery.py / baileys_send.mjs
```

- `config/sources.example.json` — catalog ingestion source config
- `config/topic_scoring.example.json` — ML topic scoring config
- `personas/catalog.json` — canonical persona topic and selection config
- `configs/users/*.json` — user persona subscriptions
- `src/main/scala/knowledgeos/Ingest.scala` — Scala catalog ingestion; HN Firebase for current runs, HN Algolia for `--historical-hn`, RSS for Substack feeds
- `persona_digest.py` — source-aware persona selection/rendering; HN cadence uses `fetched_at`, RSS/Substack uses `published_at`
- `storage_interface.py` — abstract base; `storage_sqlite.py` implements it
- `match_topics.py` — sentence-transformers semantic matching (heavy import, avoid in tests)
- `dashboard.py` — local Streamlit app with PM/Engineering mode switcher (sidebar radio); PM view: Overview (metrics + match quality), Browse, Authors; Engg view: Pipeline Health, Stories, Config, Simulator; reads DB and config directly, never writes to DB (except Config tab)

## Learning Goals

I'm an engineer using this project to build product management skills. When PM mode is active:
- Ask what problem a feature solves and for whom before discussing implementation
- Frame tradeoffs as user value vs effort, not technical complexity
- Surface: "What does success look like?" before writing code
- Reference pm/PRODUCT_STRATEGY.md for product context; pm/PM_NOTEBOOK.md for learning notes

## Code Conventions

- Config loading: modular code uses `config/sources.example.json`, `config/topic_scoring.example.json`, `personas/catalog.json`, and `configs/users/*.json`; legacy v2 uses `config.json`
- DB access in modular code: prefer explicit SQLite connections and helpers in `schema.py`/`query_pipeline.py`; legacy code goes through `storage_interface.get_storage()`
- DB access in `engagement.py`: uses raw `sqlite3` directly (separate schema)
- Errors/warnings: `print(..., file=sys.stderr)` — stdout is reserved for pipeline output
- Digest artifact: `knos-digest/YYYY-MM-DD.md`; the morning wrapper commits and pushes the latest file when it changes
- `published_at` stores the source-native publication/submission timestamp; `fetched_at` stores the logical catalog snapshot date; `source_api` records the concrete provider
- Persona cadence is source-aware: HN uses `fetched_at`; RSS/Substack uses `published_at`
- Legacy archive naming: `archive/YYYY-MM-DD_{stories,digest}.{json,txt}`
- HN username `vb7132` is hardcoded in `engagement.py` and `engagement_summary.py`
- WhatsApp digest links: `persona_url()` in `persona_digest.py` appends `&date=YYYY-MM-DD` derived from the digest filename stem (only when it matches a real date), so an old message reopens that day's items, not the latest site export; the site page (`bvaibhav-info/src/app/knos-digest/page.tsx`) reads the `date` param (`latest`/`all`/`YYYY-MM-DD`)

## Testing

- All tests in `tests/` — run with `venv/bin/python -m pytest tests/ -v`
- Use `tmp_path` fixture for SQLite (not `:memory:`)
- Don't import `match_topics` or `sentence_transformers` in tests — they load heavy ML models
- Test pure functions directly; mock network calls
