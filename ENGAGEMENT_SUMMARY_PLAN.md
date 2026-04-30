# Engagement Summary Plan

**Purpose:** Daily reflection on today's HN engagement, separate from main digest

---

## Design Philosophy

**Separation Principles:**
1. **Different timing** - Summary at 5 PM, digest at 2 PM
2. **Different purpose** - Reflection vs discovery
3. **Different frequency** - Only on days you engage
4. **Optional** - Can be disabled without affecting digest

---

## Delivery Options

### Option 1: Same-Day Evening (Recommended) ✅
**Time:** 5:00 PM daily  
**Trigger:** Automatic cron job  
**Delivery:** Separate WhatsApp message

**Pros:**
- Same-day feedback (immediate reflection)
- 3 hours after digest (time to engage)
- End-of-workday natural break
- Can skip if no engagement today
- Clear separation from digest

**Cons:**
- Another scheduled message (but same day)

**Implementation:**
```bash
# Cron: 0 17 * * *
python3 engagement_summary.py > summary.txt
# Send to WhatsApp if not "NO_SUMMARY"
```

---

### Option 2: Next Morning (Alternative)
**Time:** 9:00 AM next day  
**Trigger:** Automatic cron job  
**Delivery:** Separate WhatsApp message

**Pros:**
- Morning reflection sets tone for day
- Separate day = very clear separation

**Cons:**
- Delayed feedback (less immediate)
- Can't adjust same-day engagement

---

### Option 3: Late Evening (Not Recommended)
**Time:** 9:00 PM  
**Trigger:** Automatic cron job  
**Delivery:** Separate WhatsApp message

**Pros:**
- End-of-day reflection

**Cons:**
- Too late, might be ignored
- Less actionable

---

## Recommended Approach: Option 1 (5 PM Same Day)

**Schedule:**
- **2:00 PM:** HN Digest (today's opportunities)
- **5:00 PM:** Engagement summary (today's activity so far)

**Rationale:**
- Same-day reflection is more immediate
- 3-hour window allows engagement + tracking
- Natural end-of-workday break
- Can still engage after seeing summary
- Builds same-day feedback loop

---

## Summary Format

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
   Score: 0.72 · Someone built something. Feedback?
🔥 https://news.ycombinator.com/item?id=47094192
   Score: 0.68 · Active debate. Provide clarity?

*7-Day Trend*
Engagement rate: 7.7% (1/13)
💡 Tip: Low engagement - opportunities may be too broad

_Daily reflection · track engagement patterns_
```

---

## What Gets Tracked

### Yesterday's Activity
- **Comments posted:** Count, timestamps, snippets
- **Stories engaged:** Which were opportunities vs organic
- **Opportunities:** Total detected, engagement rate
- **Missed chances:** Stories you didn't engage with

### 7-Day Trend
- **Engagement rate:** % of opportunities engaged
- **Feedback:** Tips based on rate (too high/low/just right)

---

## Implementation Steps

### 1. Create Summary Script ✅
`engagement_summary.py` (created above)

### 2. Create Delivery Wrapper ✅
```bash
#!/bin/bash
# scripts/send_engagement_summary.sh

cd "$(dirname "$0")"

SUMMARY=$(python3 engagement_summary.py)

if [ "$SUMMARY" != "NO_SUMMARY" ]; then
    echo "$SUMMARY"
fi
```

### 3. Add Cron Job (5 PM) ✅
```json
{
  "name": "Engagement Summary - 5 PM Daily",
  "schedule": {
    "kind": "cron",
    "expr": "0 17 * * *",
    "tz": "Asia/Calcutta"
  },
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "message": "Generate today's engagement summary. Run: bash /Users/vb/.openclaw/workspace/knowledge-os/scripts/send_engagement_summary.sh\n\nIf output is not empty, send to +919179611575 via WhatsApp.",
    "timeoutSeconds": 60
  }
}
```

### 4. Test Manually ✅
```bash
cd /Users/vb/.openclaw/workspace/knowledge-os
venv/bin/python -m knowledge_os.engagement_summary
```

---

## File Structure

```
knowledge-os/
├── engagement_summary.py       # Summary generator
├── scripts/send_engagement_summary.sh  # Delivery wrapper
├── engagement.py               # Main engagement module
├── process_digest.py           # Digest pipeline
├── dashboard.py                # Local Streamlit observability UI
└── hn_digest_v2.db            # Shared database
```

**Separation:**
- Different scripts
- Different cron jobs
- Different delivery times
- Same database (shared state)

---

## Configuration

### Enable/Disable Summary

**Disable:**
```bash
# Remove cron job
cron remove <job-id>
```

**Enable:**
```bash
# Add cron job (see step 3)
```

**Adjust timing:**
```json
"expr": "0 17 * * *"  # 5 PM (recommended)
"expr": "0 18 * * *"  # 6 PM
"expr": "0 21 * * *"  # 9 PM
```

---

## Skip Logic

**Summary only sent when:**
- ✅ Digest ran today (opportunities detected)
- ✅ At least one opportunity OR comment from today
- ❌ Skip if no digest today
- ❌ Skip if no activity today

**Rationale:** Don't send empty summaries

---

## Sample Daily Flow

**Saturday 2 PM:**
- Receive digest with 5 opportunities
- Engage with 1 (comment on Show HN at 3:30 PM)

**Saturday 5 PM:**
- Receive engagement summary
- See: 1 engaged, 4 missed
- Reflect: "I only engaged 20% - were the others not interesting?"
- Still have evening to engage if something resonates

**Sunday 2 PM:**
- Receive digest with 5 new opportunities
- Better calibrated from yesterday's reflection

---

## Metrics to Track

### Daily Summary Should Show:
1. **Activity:** Comment count, timestamps
2. **Quality:** Which opportunities you engaged
3. **Missed chances:** What you skipped
4. **Trends:** 7-day engagement rate
5. **Feedback:** Actionable tips

### What NOT to Show:
- Story titles (too verbose, just IDs + links)
- Full comment text (just snippets)
- Karma/replies (check manually on HN)
- Author stats (irrelevant for reflection)

---

## Future Enhancements

### Phase 2 (Later)
- **Comment karma tracking:** Fetch karma for each comment
- **Reply detection:** Did your comments get replies?
- **Engagement quality score:** Not just count, but impact
- **Pattern recognition:** Which opportunity types you engage with most

### Phase 3 (Much Later)
- **Weekly digest:** Aggregate of 7 daily summaries
- **Streak tracking:** "5 days in a row with engagement"
- **Comparative analysis:** This week vs last week

---

## Testing Plan

### 1. Test Summary Generation
```bash
python3 engagement_summary.py
```

**Expected:** Summary of today's activity (if any)

### 2. Test Skip Logic
```bash
# On day with no digest
python3 engagement_summary.py
```

**Expected:** "NO_SUMMARY"

### 3. Test Delivery
```bash
bash scripts/send_engagement_summary.sh
```

**Expected:** Summary text or nothing

### 4. Test Cron Job
- Add job at 5 PM
- Wait for delivery
- Verify WhatsApp message received

---

## Decision Confirmed ✅

**Using:**
- ✅ 5 PM same-day summary
- ✅ Skip days with no digest/engagement
- ✅ Current detail level (concise but informative)
- ✅ Show all missed opportunities (usually 4-5)

**Rationale:**
- Same-day reflection is more immediate
- 3-hour window allows engagement + tracking
- Skipping empty days reduces noise
- Concise format scans quickly
- Seeing all missed helps calibrate interest

---

_Builds reflection habit · separate from discovery · actionable feedback_
