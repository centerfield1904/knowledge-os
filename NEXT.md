# NEXT.md - HN Digest Roadmap

## Immediate (This Week)

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
- [ ] **Threshold tuning** - Current semantic similarity cutoff may need calibration
- [ ] **Feedback mechanism** - via whatsapp
- [ ] **Store feedback** - store the feedback as: opening links, links engaged with, linked stored in the memo db

### UX
- [ ] **Redesign the dashboard** - make it super user friendly, less clunky. Keep the streamlit version for all the bells and whistles. Create one for external users.

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

---

## Notes

- Keep it lean - this is infrastructure, not a product
- Focus on reliability first, features second
- MVP → iterate philosophy applies here too
- If engagement drops, audit match quality before adding features
