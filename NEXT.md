# NEXT.md - HN Digest Roadmap

## Immediate (This Week)

- [ ] **Add persona digest preview diagnostics** — The canonical persona renderer now selects directly from scored catalog rows. Add a dry-run query that explains every rejected candidate by persona threshold, source, source-aware cadence window, send-day gating, and exclusive-assignment winner.
- [ ] **Stabilize persona digest volume** — Audit persona `selection` defaults, source coverage, and scoring coverage so each subscribed persona has enough candidates before WhatsApp summaries link to the website.
- [ ] **Add cross-day digest de-dupe at render time** — HN cadence now uses `items.fetched_at`, so a high-scoring HN story can rarely appear across multiple days if it remains in the fetched source set. Add a rendered/delivered item suppression check keyed by `item_id` or URL across recent digest artifacts, with a `--rerun`/debug escape hatch so intentional backfills remain possible.
- [ ] **Make topic scoring local/offline safe** — The launch smoke logs showed repeated Hugging Face DNS retries before scoring completed. Add a model-cache preflight, explicit offline/local-model option, clearer failure message, and a short retry policy so daily runs do not hang on network/model resolution.
- [ ] **Populate modular enrichment data before rendering** — The renderer can show author karma and top-comment blurbs, but the modular path does not reliably populate `authors.metadata_json` or `item_content` yet. Add a separate enrichment step that fills HN author karma, top comments, article summaries, and source annotations without changing ranking.
- [ ] **Improve Scala RSS/Substack adapter quality** — Current Scala ingestion fetches RSS feeds, but it is still basic: source is always `substack`, feed identity lives only in metadata, HTML entities are not decoded, and per-feed frequency is not honored in the Scala path. Add feed/source tags, robust date parsing, HTML text normalization, and fetch metrics.
- [ ] **Separate launch feeds from VB/global scoring noise** — Kintu design feeds are now global catalog inputs, which is correct for catalog freshness but can leak AI/design overlap into Mikey/VB scoring. Add source tags or per-topic source weights so selection can distinguish "design feed item about AI UX" from core AI research content.
- [ ] **Add launch health summary command** — One command should report catalog counts, scored-item counts by topic, candidate counts before/after filters, selected count, empty-digest risk, and last catalog refresh time for `vb`, `mikey`, and `kintu`.
- [x] **Install Scala and verify** — COMPLETE (2026-05-13: Homebrew OpenJDK, SBT, and Scala installed; verified `scala -version`; `sbt test` passes)
- [x] **Split target architecture into four modules** — COMPLETE (2026-05-13: catalog/ingestion, topic scoring, subscriptions/digests, feedback/engagement documented in ARCHITECTURE.md)
- [x] **Add target schema and modular commands** — COMPLETE (2026-05-13: `knowledge_os.schema`, `topic_scoring`, `subscriptions`, `feedback_events`; Scala `knowledgeos.Ingest`)
- [x] **Add Scala unit and integration tests** — COMPLETE (2026-05-13: URL dedupe, author upsert, subscription filtering, digest writes, delivered feedback, and full four-module DB flow)
- [x] **Wire modular runner** — COMPLETE (2026-05-13; revised 2026-05-25: `scripts/run_modular_digest.sh` calls ingestion, persona materialization, scoring, and canonical persona rendering)
- [x] **Add persona-level cadence selection** — COMPLETE (2026-05-27; revised 2026-05-29: persona `selection.cadence` supports daily and weekly source-aware windows; HN uses `items.fetched_at`, Substack/RSS uses `items.published_at`; optional `send_days` gates weekly UX delivery; zero-item digests are allowed)
- [x] **Make Scala ingestion date-aware** — COMPLETE (2026-05-27: `knowledgeos.Ingest --date YYYY-MM-DD` stores date-derived `fetched_at`; modular/catalog runners pass the date through for backfills and auditability)
- [x] **Persona-only website delivery** — COMPLETE (2026-05-25: removed per-user rendered artifacts; WhatsApp summaries now link to the persona-filtered website)
- [x] **Persona-driven multi-user config** — COMPLETE (2026-05-14; revised 2026-05-25: users subscribe to personas; personas own topics and selection defaults)
- [ ] **Bring modular renderer to digest format parity** — Add optional engagement sections and verify the new enrichment step supplies comment summaries and author karma without moving ranking back into Python.
- [x] **Engagement opportunity detection** - COMPLETE (Feb 20: 5 opps/day, username tracking, comment analysis)
- [x] **Update digest format** - COMPLETE (🎯 Engagement Opportunities section added)
- [x] **Engagement tracking schema** - COMPLETE (SQLite tables, auto comment sync)
- [x] **Test full pipeline** — COMPLETE (integration test in tests/test_pipeline_integration.py)
- [x] **Monitor delivery reliability** - Track 7 days of successful 2 PM deliveries
- [ ] **Review match quality** - Are the semantic matches hitting the right content?
- [x] **Add frequency in config option for sources** — COMPLETE (2026-03-05: `frequency` field per source in config; `_source_is_due()` filter in `process_digest.py`; supports daily/weekly/biweekly/monthly/quarterly/list-of-weekdays; all sources still fetched and stored daily)
- [x] **Weekly trending topics analysis** For this page, add them to the sources: substack_tspc.csv — COMPLETE (52 Substack feeds from tspc CSV added to config; YouTube/Instagram/Spotify/LinkedIn/profile-only URLs skipped)
- [x] **Track read content** — COMPLETE (sync_reading_log.py + Read Tracker section in digest)
- [x] **Show yc link** — COMPLETE (HN discussion links + 💬 comment keyword summaries)
- [x] **Add unit tests** — COMPLETE (4 test files in tests/ covering process_digest, storage, engagement, sync_reading_log)
- [x] **Add other sources** — COMPLETE (Substack RSS via fetch_substack.py, config-driven feeds)
- [x] **Fix Substack duplicate stories** — COMPLETE (insert_item returns (item_id, is_new); digest only surfaces new stories; author/topic tracking still runs for all fetched content)
- [x] **Run tests in PR builds** — COMPLETE (2026-03-07: `.github/workflows/tests.yml`; `pytest.ini` with `integration` marker; integration tests deselected in CI with `-m "not integration"`)
- [x] **build a dashboard** — COMPLETE (2026-03-01: Streamlit app; 2026-03-03: 6 tabs; 2026-03-04: split into PM/Engineering modes via sidebar switcher — PM view: Overview + match quality + Browse + Authors; Engg view: Pipeline Health + Stories + Config + Simulator)
- [ ] **Add economist as a source** - New POC: something with images, something that requires login.
- [x] **Per-feed frequency for Substack** — COMPLETE (2026-03-07: feeds accept `{"url": "...", "frequency": "..."}` dicts; `_feed_is_due()` in `fetch_substack.py`; string feeds inherit source-level frequency)
- [x] **Dashboard Config tab: frequency editor** — COMPLETE (2026-03-07: per-feed frequency via dict format in config; dashboard Followed HN Users and Weekend Mode expanders added)
- [x] **Interesting content** — COMPLETE (2026-03-07: Weekend Mode — stricter topic threshold for Best Matches + high-score Interesting Reads section; configurable via dashboard Config tab "Weekend Mode" expander)
- [x] **week summary** — COMPLETE (2026-03-07: `src/knowledge_os/weekly_summary.py` queries last 7 days by topic; `scripts/run_digest_v2.sh --fetch-only` for 6-hour cron; add `0 */6 * * * bash scripts/run_digest_v2.sh --fetch-only` and `0 9 * * 1 venv/bin/python -m knowledge_os.weekly_summary` to crontab)
- [x] **Change what is shown** — COMPLETE (2026-03-07: comment count removed; author HN karma shown as `karma: N`; top comment first sentence shown as 💬 blurb)
- [x] **Option to manually add or remove HN users that I follow** — COMPLETE (2026-03-07: `followed_hn_users` in config; followed users get ⭐ in digest; dashboard Config tab "Followed HN Users" expander)
- [ ] For every comment on HN or substack, assess the objective quality: why it was good or bad

## Short-term (This Month)

### Quality & Tuning
- [ ] **Use local LLM** - For summarization and any other daily operations, use a local LLM, not remote apis
- [ ] **Refine topic embeddings** - Adjust if matches drift from intent
- [ ] **Add topic weights** - Let VB prioritize AI/ML > Parenting > Philosophy, etc.
- [ ] **Threshold tuning** - Current semantic similarity cutoff may need calibration; use per-topic score distributions and rejected-candidate explanations rather than one global cutoff
- [ ] **Feedback mechanism** - Deferred until manual WhatsApp launch produces repeated signal worth automating
- [ ] **Store feedback** - Deferred; do not build link/open tracking until the manual launch proves which signal is useful

### UX
- [ ] **Redesign the dashboard** - make it super user friendly, less clunky. Keep the streamlit version for all the bells and whistles. Create one for external users.
- [ ] **Manage scheduled jobs from the dashboard** — Add a dashboard view for Knowledge OS cron jobs: current schedule, last run status, log tail, enable/disable, run-now, and safe edit controls for the daily VB delivery, catalog refresh, weekly summary, and engagement summary jobs.

### Similar
- [ ] https://www.kerns.ai
- [ ] https://github.com/herol3oy/kiosk24

### Features
- [ ] **Thread continuity** - "You saw Story X yesterday, here's an update/follow-up"
- [ ] **Author highlights** - "Author Y (who wrote Z last week) posted this"
- [ ] **Weekly summary mode** - Option for digest-of-digests
- [ ] **Weekend articles logic** Review the interesting articles logic: update the code with improvements


### Infrastructure
- [ ] **Logging & metrics** - Track story volume, match rates, delivery timing
- [ ] **Backup & recovery** - SQLite backup strategy (daily? weekly?)
- [ ] **Error handling** - Graceful degradation if HN API is down
- [x] **Scala ingestion source parity** - COMPLETE (2026-05-15: Scala catalog ingestion now fetches configured RSS/Substack feeds alongside HN; remaining quality work tracked above)
- [ ] **Separate content enrichment** - Populate `item_content` for comments, extracted article bodies, summaries, and source annotations.

### Interactive Feedback
- [ ] **WhatsApp Business API** — Migrate from Baileys to Business API for inline buttons per story (👍 Like | 📌 Save | 👎 Skip). Callbacks connect to the `feedback` table. `digest_metadata.json` is already exported as a bridge. Button format: `hn_like:{story_id}`, `hn_save:{story_id}`, `hn_skip:{story_id}`.

## Mid-term (3-6 Months)

- [ ] Being able to search through a book that I have read before - but with a question - potential use of SLMs?

### Intelligence Layer
- [ ] **Comment analysis expansion** - Surface high-signal HN comments, not just stories
- [ ] **Trend detection** - "This topic is heating up" signals
- [ ] **Author reputation** - Weight by HN karma, previous quality matches
- [ ] **Engagement quality metrics** - Track karma/replies on VB's comments

### Personalization
- [ ] **Dynamic topic learning** - Learn from engagement patterns
- [ ] **Time-of-day optimization** - Is 2 PM actually best? A/B test timing
- [ ] **Negative filters** - "Never show me X" capabilities
- [ ] **Volume tuning** - Auto-adjust opportunity count based on engagement rate

### Expansion
- [ ] **Multi-source** - Add Reddit, ArXiv, Twitter feeds
- [ ] **Collaborative filtering** - "People with your interests also read..."

## Long-term (6+ Months)

### Meta-Framework
- [ ] **Generalize architecture** - Turn this into a template for any feed curation
- [ ] **API layer** - Expose digest engine for other projects
- [ ] **Knowledge graph integration** - Feed into VB's broader knowledge system

### Engagement Layer
- [ ] **Voice summaries** - TTS versions of digests for commute listening
- [ ] **Interactive mode** - "Tell me more about story #3" capability
- [ ] **Reputation dashboard** - Track HN karma growth, connections made

---

## Decision Log

**2026-02-11** - Initial architecture: semantic matching, SQLite continuity, WhatsApp delivery  
**2026-02-13** - v2 migration: improved storage layer, better topic handling  
**2026-04-30** - Fixed empty digest bug: `get_undelivered_item_ids` replaces `is_new` as the display gate; `--rerun` flag clears archive + stale feedback; `--push` flag makes git push opt-in  
**2026-05-13** - Four-module architecture adopted: catalog, topic scoring, subscriptions/digests, and feedback are independent; Scala owns concurrent ingestion; Python owns ML scoring, config/materialization, persona selection/rendering, and feedback parsing
**2026-05-16** - Launch-readiness review: Kintu source coverage improved with design feeds; Mikey threshold tuned; remaining VB risks are side-effectful dry runs, offline scoring reliability, enrichment gaps, and candidate/filter observability
**2026-05-27** - Persona cadence implemented in canonical renderer: daily/weekly windows, UX weekly on Fridays, zero-item digests, and Scala ingestion `--date` for date-aware backfills. Cadence timestamp choice was revised on 2026-05-29 to be source-aware.
**2026-05-29** - Source-aware persona cadence: Hacker News now uses `items.fetched_at` for daily/weekly cadence windows; Substack/RSS continues to use `items.published_at`. Official HN Firebase API exposes near-real-time top/new/best lists and item timestamps, not a date-addressable historical front-page endpoint, so `--date` remains the logical snapshot date for HN ingest/backfill runs.
**2026-05-30** - Historical HN ingest: added `--historical-hn` to fetch one requested HN submission date through Algolia `search_by_date`; item rows record `items.source_api` (`hackernews_firebase`, `hackernews_algolia`, `rss`) for provider-aware filtering.
**2026-05-30** - Docs/config cleanup: removed stale `config/user.vb.example.json`; canonical user subscriptions live under `configs/users/*.json`. README and ARCHITECTURE now document the modular production path, source-aware cadence, historical HN mode, remote website publish, and send-only WhatsApp delivery wrappers.

---

## Notes

- Keep it lean - this is infrastructure, not a product
- Focus on reliability first, features second
- MVP → iterate philosophy applies here too
- If engagement drops, audit match quality before adding features

---

## Session Log

Dated record of what closed each session. Read by `/week-review` to compute project momentum.

### 2026-05-13
- [x] Install Scala and verify (Homebrew OpenJDK, SBT, Scala; `sbt test` passing)
- [x] Document four-module architecture in ARCHITECTURE.md
- [x] Add target schema and modular commands (`knowledge_os.schema`, `topic_scoring`, `subscriptions`, `feedback_events`; Scala `knowledgeos.Ingest`)
- [x] Add Scala unit and integration tests (URL dedupe, author upsert, subscription filtering, digest writes, delivered feedback, full four-module DB flow)
- [x] Wire modular runner (`scripts/run_modular_digest.sh`)
- [x] Persona website rendering (`knowledge_os.persona_digest` renders canonical persona-marked markdown)

### 2026-05-14
- [x] Persona-driven multi-user config (persona catalog, VB/Kintu/Mikey configs, materializer, website-link delivery)

### 2026-05-21
- [x] Add VS Code workspace setup for the mixed Python/Scala project (`.vscode/settings.json`, recommended extensions, tasks, and debug launch configs)
- [x] Validate Scala ingest debugging through Metals with `knowledgeos.Ingest --db knowledge_os.debug.db --sources config/sources.example.json`
- [x] Confirm catalog ingest run writes to a debug SQLite DB without touching `knowledge_os.db` (136 catalog items upserted in the smoke run)

### 2026-05-30
- [x] Add source-aware persona cadence (`fetched_at` for HN, `published_at` for RSS/Substack)
- [x] Add historical HN backfill mode through Algolia and persist `items.source_api`
- [x] Add fetched-item query filters for score, topic, title text, source, and source API
- [x] Split scheduled operation into 9 AM ingest/render/push and 2 PM send-only WhatsApp delivery
- [x] Update README/ARCHITECTURE/NEXT for the current modular production path and remove stale user config docs
