# NEXT.md - HN Digest Roadmap

## Immediate (This Week)

- [ ] **Add launch health summary command** — Add one read-only command that reports catalog counts by source/API, last refresh time, scored counts by topic, candidates before/after filters and de-dupe, selection totals, explicit drop reasons, per-user content risk, ingest start/completion and manual/automatic provenance, and scheduled/actual WhatsApp delivery with receipt evidence. The diagnostics must use the renderer's selection path so preview and production cannot drift.
- [ ] **Add personally curated weekly summary workflow** — Aggregate each Mon–Sun daily archive into an editable checkbox draft, finalize only manually selected items into a shared weekly edition without daily read-tracking checkboxes, expose it as the website Weekly view, and publish a WhatsApp-ready `?view=weekly&w=YYYY-Www` link on Monday.
- [ ] **Verify cron-safe GitHub token dispatch** — `scripts/run_catalog_ingest.sh` now loads `~/.config/knowledge-os/cron.env` and uses `GH_TOKEN` for `gh workflow run`. Create a fine-grained PAT, install it locally with `chmod 600`, and confirm the next 9 AM cron writes `website_workflow_status=triggered`.
- [x] **Add gap-day recovery helper** — COMPLETE (2026-08-20: added a read-only gap summary command and a shell wrapper that loops the existing date-aware ingest/render/publish commands; no new ingest path required)
- [ ] **Audit recipient-local digest dates** — Mikey now uses `America/Los_Angeles` for `--date`; verify any future non-IST recipients compute digest date in their own delivery timezone rather than the Mac's timezone.
- [ ] **Stabilize persona digest volume** — Audit persona `selection` defaults, source coverage, and scoring coverage so each subscribed persona has enough candidates before WhatsApp summaries link to the website.
- [ ] **Add cross-day digest de-dupe at render time** — HN cadence now uses `items.fetched_at`, so a high-scoring HN story can rarely appear across multiple days if it remains in the fetched source set. Add a rendered/delivered item suppression check keyed by `item_id` or URL across recent digest artifacts, with a `--rerun`/debug escape hatch so intentional backfills remain possible.
- [ ] **Make topic scoring local/offline safe** — The launch smoke logs showed repeated Hugging Face DNS retries before scoring completed. Add a model-cache preflight, explicit offline/local-model option, clearer failure message, and a short retry policy so daily runs do not hang on network/model resolution.
- [ ] **Populate modular enrichment data before rendering** — The renderer can show author karma and top-comment blurbs, but the modular path does not reliably populate `authors.metadata_json` or `item_content` yet. Add a separate enrichment step that fills HN author karma, top comments, article summaries, and source annotations without changing ranking.
- [ ] **Improve Scala RSS/Substack adapter quality** — Current Scala ingestion fetches RSS feeds, but it is still basic: source is always `substack`, feed identity lives only in metadata, HTML entities are not decoded, and per-feed frequency is not honored in the Scala path. Add feed/source tags, robust date parsing, HTML text normalization, and fetch metrics.
- [ ] **Separate launch feeds from VB/global scoring noise** — Kintu design feeds are now global catalog inputs, which is correct for catalog freshness but can leak AI/design overlap into Mikey/VB scoring. Add source tags or per-topic source weights so selection can distinguish "design feed item about AI UX" from core AI research content.
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
- [x] **Test full pipeline** — COMPLETE (legacy integration tests removed with the v2 digest path; current coverage focuses on modular schema, persona rendering, queries, WhatsApp delivery, and Scala ingestion)
- [x] **Monitor delivery reliability** - Track 7 days of successful 2 PM deliveries
- [ ] **Review match quality** - Are the semantic matches hitting the right content?
- [x] **Add cadence controls** — COMPLETE (current persona `selection.cadence` and `send_days` control daily/weekly delivery behavior)
- [x] **Weekly trending topics analysis** For this page, add them to the sources: substack_tspc.csv — COMPLETE (52 Substack feeds from tspc CSV added to config; YouTube/Instagram/Spotify/LinkedIn/profile-only URLs skipped)
- [x] **Track read content** — COMPLETE historically; current feedback ingestion keeps markdown checked-item parsing in `feedback_events.py`
- [x] **Show yc link** — COMPLETE (HN discussion links + 💬 comment keyword summaries)
- [x] **Add unit tests** — COMPLETE (current tests cover modular schema, persona rendering, queries, storage/read parsing helpers, engagement, and WhatsApp delivery)
- [x] **Add other sources** — COMPLETE (Substack/RSS via Scala catalog ingestion)
- [x] **Fix Substack duplicate stories** — COMPLETE (insert_item returns (item_id, is_new); digest only surfaces new stories; author/topic tracking still runs for all fetched content)
- [x] **Run tests in PR builds** — COMPLETE (2026-03-07: `.github/workflows/tests.yml`; `pytest.ini` with `integration` marker; integration tests deselected in CI with `-m "not integration"`)
- [x] **build a dashboard** — COMPLETE historically; old Streamlit dashboard removed with the v2 digest path
- [x] **Add economist as a source** - COMPLETE (2026-08-24: source-aware RSS ingestion reads the generated full-text Economist XML, stores items as `source = economist`, and lets broad personas select the source; login/browser scraping remains outside the production path)
- [x] **Per-feed frequency for Substack** — COMPLETE historically; superseded by modular source/persona cadence
- [x] **Dashboard Config tab: frequency editor** — REMOVED with old Streamlit dashboard
- [x] **Interesting content** — COMPLETE historically; current persona renderer uses thresholded persona selection
- [x] **week summary** — REMOVED with the v2 digest path
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
- [ ] **Build an ops view if needed** — If cron visibility becomes painful, create a small status page or CLI around current schedules, last run markers, log tails, and last website workflow run.
- [ ] **Add host-awake/missed-cron monitoring** — Cron cannot log a run that never starts because the Mac is asleep. Add a host-level wake policy for the 9 AM IST ingest window, or an external marker monitor that alerts if `ingest-YYYY-MM-DD.env` is missing after 9:15 IST.

### Similar
- [ ] https://www.kerns.ai
- [ ] https://github.com/herol3oy/kiosk24
- [ ] https://www.signalbloom.ai/

### Features
- [ ] **Thread continuity** - "You saw Story X yesterday, here's an update/follow-up"
- [ ] **Author highlights** - "Author Y (who wrote Z last week) posted this"
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
**2026-06-23** - Weekly editions use manual curation through an editable draft, with a shared Mon–Sun edition finalized and sent on Monday. Launch health was selected as the next operational reliability item before expanding the weekly workflow.
**2026-08-20** - Gap recovery uses the existing date-aware ingest/render/publish commands. The new helper layer is intentionally limited to reporting missing days and looping those existing commands.
**2026-08-24** - Economist is a first-class catalog source via the source-aware RSS adapter. The production config reads `../economist-newspaper-rss-feed/dist/economist-fulltext.xml` and stores rows as `source = economist`, `source_api = rss`.

---

## Notes

- Keep it lean - this is infrastructure, not a product
- Focus on reliability first, features second
- MVP → iterate philosophy applies here too
- If engagement drops, audit match quality before adding features
- Create one scheduled delivery script that reads cadence, timezone, recipient, and persona settings from `configs/`. Cron should only trigger the scheduler; it should not encode one cron entry per user.
- Harden the daily publish path so `10:30 IST` readiness does not depend on a single best-effort GitHub scheduled run:
  - Keep explicit local dispatch as the primary path using cron-safe `GH_TOKEN`; website publish readiness is still verified through the public JSON.
  - Add retry/backoff around readiness polling before alerting VB.
  - Add a more frequent `bvaibhav-info` fallback publish schedule during the `09:15-10:30 IST` window.
  - Move the publish trigger closer to the repository boundary long term: either a GitHub Action in `knowledge-os` dispatches `bvaibhav-info`, or the website workflow reacts to `knowledge-os` digest pushes without relying on the Mac.

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
