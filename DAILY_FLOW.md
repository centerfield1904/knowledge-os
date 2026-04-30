# Daily Flow: Digest + Engagement Summary

**Two separate messages at different times for different purposes**

---

## Message 1: HN Digest (2:00 PM)

**Purpose:** Discover today's HN opportunities  
**Frequency:** Daily  
**Format:**

```
🦅 *HN Digest* - Afternoon Energy Boost
_7 stories worth your attention_

*AI/ML/LLMs*
• Cord: Coordinating Trees of AI Agents
  ↑87 by gfortaine
  https://www.june.kim/cord

🎯 *Engagement Opportunities*

💬 Show HN: Native macOS HN client
   → Someone built something. 148 comments. Feedback?
   https://news.ycombinator.com/item?id=47088166

_Keep building. The frontier moves forward._
```

**What it shows:**
- 📚 Stories matched to your topics (AI/ML, Data Science, etc.)
- 🎯 5 engagement opportunities (Ask/Show HN, early, debates)
- ⭐ Notable authors you're tracking

**When skipped:**
- Never (always runs daily)
- Shows "quiet day" if no matches

---

## Message 2: Engagement Summary (5:00 PM or 9:00 AM next day)

**Purpose:** Reflect on today's HN engagement
**Frequency:** Only when digest ran and engagement occurred
**Format:**

```
📊 *Today's Engagement*

✅ *You engaged:* 4 comment(s) posted

💬 *Story 47088166* (was in opportunities)
  └ 15:13: This seems like a common problem...
    https://news.ycombinator.com/item?id=47099090
  └ 15:14: This feature is very useful :)
    https://news.ycombinator.com/item?id=47099101
  └ 15:43: This is fantastic. The app is simple...
    https://news.ycombinator.com/item?id=47099300
  └ 15:44: A link to my experiment: https://...
    https://news.ycombinator.com/item?id=47099309

*Opportunities:* 5 detected, 1 engaged (20%)

*Missed opportunities:*
💬 https://news.ycombinator.com/item?id=47094149
   Score: 1.00 · Someone built something. Feedback?
🔥 https://news.ycombinator.com/item?id=47094192
   Score: 0.85 · Active debate. Clarity?

*7-Day Trend*
Engagement rate: 7.7% (1/13)
💡 Tip: Low engagement - opportunities may be too broad

_Daily reflection · track engagement patterns_
```

**What it shows:**
- ✅ Comments you posted yesterday (time, snippet, link)
- 📊 Which stories were digest opportunities vs organic
- 📉 Missed opportunities with scores
- 📈 7-day engagement trend + tips

**When skipped:**
- No digest ran today
- No engagement today (0 comments)

---

## Why Separate?

### Different Purposes
- **Summary (PM/next AM):** Reflection, learning, calibration
- **Digest (2 PM):** Discovery, action, opportunities

### Different Frequencies
- **Summary:** Only when you engage (0-3x/week)
- **Digest:** Every day (7x/week)

### Different Timing
- **Summary:** After engagement window (5 PM same day or 9 AM next day)
- **Digest:** 2 PM catches stories while hot

### Different Actions
- **Summary:** Review, reflect, adjust strategy
- **Digest:** Read, engage, contribute

---

## Sample Weekly Flow

### Monday
- **2 PM:** Digest arrives, 5 opportunities
- **Action:** Engage with 1 Ask HN
- **5 PM:** Summary shows today's engagement (20% rate)

### Tuesday
- **2 PM:** Digest arrives, 5 opportunities
- **Action:** Skip, nothing interesting

### Wednesday
- **2 PM:** Digest arrives, 5 opportunities
- **Action:** Engage with 2 debates
- **5 PM:** Summary shows today's engagement (40% rate)

### Thursday
- **2 PM:** Digest arrives, 5 opportunities
- **Action:** Engage with 1 Show HN
- **5 PM:** Summary shows today's engagement

### Friday
- **2 PM:** Digest arrives, 5 opportunities
- **Action:** Engage with 1 early thread
- **5 PM:** Summary shows today's engagement

### Saturday
- **2 PM:** Digest arrives, 5 opportunities
- **Reflection:** 4/7 days engaged, 7/35 opportunities (20%)

---

## Benefits of Separation

### Morning Summary Benefits:
- ✅ Immediate feedback loop (see yesterday's impact)
- ✅ Calibrate engagement strategy before today's digest
- ✅ Track patterns (which opportunities you engage with)
- ✅ Builds reflection habit
- ✅ No clutter in main digest

### Afternoon Digest Benefits:
- ✅ Focused on discovery (not distracted by stats)
- ✅ Catches stories while hot (afternoon = engagement window)
- ✅ Clean, actionable format
- ✅ Independent of engagement tracking

---

## Message Comparison

| Aspect | Engagement Summary | HN Digest |
|--------|-------------------|-----------|
| **Time** | 5:00 PM (same day) | 2:00 PM |
| **Focus** | Past (today so far) | Present (today) |
| **Purpose** | Reflection | Discovery |
| **Frequency** | Conditional | Daily |
| **Tone** | Analytical | Motivational |
| **Length** | Short (stats) | Medium (stories) |
| **Action** | Adjust strategy | Engage with HN |

---

## File Locations

**Summary:**
- Generator: `engagement_summary.py`
- Wrapper: `scripts/send_engagement_summary.sh`
- Cron: 5 PM daily (isolated session)

**Digest:**
- Generator: `process_digest.py`
- Wrapper: `scripts/daily_digest.sh` → `run_digest_v2.sh`
- Cron: 2 PM daily (isolated session)
- Archive: `knos-digest/YYYY-MM-DD.md`

**Shared:**
- Database: `hn_digest_v2.db`
- Engagement tracker: `engagement.py`

---

## Configuration

### Enable/Disable Summary

**Enable (recommended):**
```bash
# Add 9 AM cron job via OpenClaw
# See ENGAGEMENT_SUMMARY_PLAN.md for details
```

**Disable:**
```bash
# Remove cron job
# Digest continues unaffected
```

### Adjust Timing

**Same-day summary:**
- 5 PM: Standard (recommended) — 3h window after digest
- 6 PM: Later if you need more time to engage

**Next-morning summary (alternative):**
- 9 AM: Morning sets tone for day
- Tradeoff: delayed feedback vs fresh start

---

## Implementation Status

### Completed ✅
- Summary generator (`engagement_summary.py`)
- Delivery wrapper (`scripts/send_engagement_summary.sh`)
- Testing with real data (Feb 21 engagement)
- Documentation (this file)

### To Do 🔲
- Add 9 AM cron job
- Test full delivery to WhatsApp
- Monitor for 7 days
- Iterate based on feedback

---

_Morning reflection + afternoon discovery = balanced engagement strategy_
