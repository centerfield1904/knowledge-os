## HN Engagement Plan - knowledge-os

**Username:** vb7132  
**Goal:** Strategic HN presence through high-signal contributions  
**Volume:** 5 opportunities/day, engage with 1-2/week (20-40% rate)  
**Status:** ✅ Complete, ready for testing

---

## Implementation Summary

### ✅ Complete (Feb 20, 2026)

**Engagement detection**  
- Finds Ask/Show HN, early threads (<10 comments), hot debates (50+)  
- Scores by recency, comment count, activity level  
- Top 3 get comment analysis (questions, debate signals)

**Automatic comment tracking (vb7132)**  
- Syncs recent comments from HN API daily  
- Traces parent chain to find story ID  
- Auto-marks opportunities as "engaged"  
- No manual tracking required

**Database integration**  
- Tables: engagement_opportunities, user_comments, engagement_stats  
- SQLite @ hn_digest_v2.db  
- Tracks history, calculates engagement rate

**Digest integration**  
- "🎯 Engagement Opportunities" section in daily digest  
- 5 opportunities per day (adjustable)  
- Formatted for WhatsApp with emoji, prompts, links

---

## Opportunity Types (5 per day)

### 1. 💬 Ask HN / Show HN (Score: 0.75+)
**Why:** Direct request for feedback, high appreciation  
**Action:** Share systems thinking or relevant experience  
**Example:** "Ask HN: Best practices for knowledge graphs in production?"

### 2. 🎯 Early Engagement (<10 comments, <6h old) (Score: 0.55+)
**Why:** High visibility, OP responsiveness, conversation shaping  
**Action:** Add framework or mental model early  
**Example:** "2 comments, 3h old. Add architectural perspective?"

### 3. 🔥 Hot Debate (50+ comments, active) (Score: 0.45+)
**Why:** Framework-bringer role, clarify confusion  
**Action:** Provide systems perspective to resolve debate  
**Example:** "Active debate (87 comments). People confusing X vs Y. Clarify?"

---

## Comment Analysis (Top 3 Opportunities)

For the highest-scored 3 opportunities, system:
- Fetches top-level comments from HN API
- Detects unanswered questions
- Identifies debate patterns
- Boosts score if questions/debates present

**Signals:**
- Questions: "?", "how do", "what about", "why does"
- Debate: "disagree", "wrong", "actually", "but", "however"

**Score boost:**
- Has questions: +0.15
- Has debate: +0.10

---

## Daily Workflow

**2:00 PM** - Digest arrives with 5 opportunities  
**2:00-2:05** - Scan engagement section  
**Pick 1** - Quality > quantity (not obligatory)  
**Draft comment** - 5 minutes, add genuine value  
**Post within 2h** - While story is hot  
**Done** - System auto-tracks your comment next sync

---

## Testing & Deployment

### Test engagement module
```bash
cd /Users/vb/.openclaw/workspace/knowledge-os
scripts/test_engagement.sh
```

### Test full digest pipeline
```bash
scripts/run_digest_v2.sh
```

### Check engagement stats
```bash
venv/bin/python -m knowledge_os.engagement
```

Output:
```
✅ Synced N comments for vb7132
📊 Weekly Engagement Report

Opportunities detected: 35
Engaged with: 8 (22.9%)
Total comments posted: 8
```

### Manual weekly report (Mondays)
```bash
venv/bin/python -m knowledge_os.engagement
```

---

## Scoring Formula

```python
# Ask/Show HN
score = 0.75 + comment_boost(0-0.15) + time_boost(0-0.1)

# Early Engagement  
score = 0.55 + comment_boost(0-0.25) + score_boost(0-0.1) + time_boost(0-0.1)

# Hot Debate
score = 0.45 + activity_boost(0-0.25) + time_boost(0-0.1)

# Comment Analysis Boost (top 3 only)
if has_questions: score += 0.15
if has_debate: score += 0.10
```

**Result:** Top 5 scored opportunities delivered

---

## Success Metrics (30-Day Target)

Review: March 20, 2026

| Metric | Target | Why |
|--------|--------|-----|
| Opportunities/week | 30-35 (5/day) | Consistent flow |
| Engagement rate | 20-40% (6-14/week) | Quality filter |
| Avg karma/comment | 3+ | Signal quality |
| Replies/comment | 1+ | Conversation starter |
| Time to engage | <2h | Catch while hot |
| High-karma connects | 3-5 authors | Network building |

---

## Engagement Templates

### Ask HN
> "I dealt with [problem] when [context]. What worked: [framework]. Key trade-off: [nuance]."

### Show HN  
> "Interesting approach to [goal]. Have you considered [perspective]? I explored this in [related context], found [insight]."

### Debates
> "This thread is circling [confusion]. Useful frame: [mental model]. It explains why [clarification]."

---

## What NOT to Do

❌ Comment just to comment (lowers signal)  
❌ Self-promote without value-add  
❌ Engage in low-quality debates  
❌ Chase karma (chase insight)  
❌ Respond to every opportunity  
❌ Force engagement when nothing resonates

✅ Skip days if no high-quality opportunities  
✅ Provide frameworks, not opinions  
✅ Build relationships, not just thread count  
✅ Quality > quantity always  
✅ Lead with insight, link when genuinely relevant

---

## Files

**Core:**
- `src/knowledge_os/engagement.py` — Detection, tracking, comment sync
- `src/knowledge_os/engagement_summary.py` — Daily reflection report
- `src/knowledge_os/process_digest.py` — Main pipeline (integration point)
- `hn_digest_v2.db` — SQLite storage

**Observability:**
- `src/knowledge_os/dashboard.py` — Streamlit UI (`venv/bin/python -m streamlit run src/knowledge_os/dashboard.py`)

**Documentation:**
- `ENGAGEMENT_PLAN.md` — This file
- `ENGAGEMENT.md` — Full strategy
- Historical integration notes were removed during cleanup; `engagement.py` is the source of truth
- `NEXT.md` — Roadmap

**Testing:**
- `tests/test_engagement.py` — Unit tests

---

## Architecture Decisions (VB Confirmed)

✅ **5 opportunities per day** (up from 3 in original plan)  
✅ **Username tracking (vb7132)** - auto-sync comments  
✅ **Comment analysis (middle ground)** - top 3 opportunities only  
❌ **Blog post integration** - not implemented (removed from plan)

---

## Next Steps

1. ✅ **Run test:** `scripts/test_engagement.sh`
2. ✅ **Review output:** Check digest format, opportunities
3. ✅ **Adjust if needed:** Scoring, volume, prompts
4. ✅ **Go live:** Daily digest at 2 PM (running since Feb 20)
5. **Engage with 1:** Test the workflow this week
6. **Weekly review:** Check stats via dashboard or `venv/bin/python -m knowledge_os.engagement`

---

## Iteration Strategy

**Week 1:** Observe which opportunities you engage with  
**Week 2:** Adjust scoring based on patterns  
**Week 3:** Refine action prompts for clarity  
**Week 4:** Review 30-day metrics, decide on volume

**If engagement rate < 15%:** Opportunities too broad → tighten filters  
**If engagement rate > 50%:** Opportunities too easy → raise bar

---

_Built for leverage: automated detection, frictionless engagement, reputation compounding._
