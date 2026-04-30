# Knowledge OS - Planned Features

## High Priority

### WhatsApp Business API Integration for Interactive Feedback
**Status:** Planned  
**Context:** 2026-03-10

**Current State:**
- Using WhatsApp Web (Baileys) via OpenClaw
- No inline button support (Business API feature)
- Simple reply format as workaround: `1,3 👍  2 📌  4,5 skip`

**Target State:**
- Migrate to WhatsApp Business API
- Inline buttons on each story in digest
- Button options: 👍 Like | 📌 Save | 👎 Skip
- Instant feedback without typing

**Technical Notes:**
- The old feedback-button prototype was removed during cleanup.
- Current feedback/read tracking flows through `sync_reading_log.py` and the main `feedback` table in `hn_digest_v2.db`.
- `digest_metadata.json` is still exported by `process_digest.py` as a lightweight bridge for future interactive feedback.
- Button callback format: `hn_like:{story_id}`, `hn_save:{story_id}`, `hn_skip:{story_id}`
- Feedback patterns used to tune semantic matching weights

**Dependencies:**
- WhatsApp Business API account setup
- OpenClaw WhatsApp Business channel support (or custom integration)
- Business phone number (separate from personal)

**Implementation Path:**
1. Setup WhatsApp Business API account
2. Integrate with OpenClaw (check if supported or build plugin)
3. Add a new Business API sender/callback module
4. Test button delivery and callback handling
5. Connect callbacks to the main SQLite feedback event log

**References:**
- WhatsApp Business API Docs: https://developers.facebook.com/docs/whatsapp/
- OpenClaw WhatsApp channel: `~/.nvm/versions/node/v22.22.0/lib/node_modules/openclaw/docs/channels/whatsapp.md`

---

## Medium Priority

### Feedback Analytics Dashboard
**Status:** Planned

Show patterns from feedback data:
- Most liked topics/authors
- Skip patterns (what to reduce)
- Saved stories for reading queue
- Engagement trends over time

**Files:**
- Build analytics on top of the main `feedback` table in `hn_digest_v2.db`
- Add either a dashboard panel or a simple CLI report

---

## Low Priority

### Multi-Source Digest Expansion
**Status:** In Progress (Substack already added)

Add more high-quality sources beyond HN:
- ✅ Substack feeds (done)
- Reddit (r/MachineLearning, r/datascience)
- Lobsters
- Product Hunt
- ArXiv (AI/ML papers)

---

## Backlog

### Smart Scheduling
Detect optimal delivery time based on engagement patterns

### Thread Tracking
Follow HN comment threads on stories you engaged with

### Author Profiles
Build knowledge graph of HN authors you track

---

_Add new planned features above this line with date and context_
