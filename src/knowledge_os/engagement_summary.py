#!/usr/bin/env python3
"""
Daily Engagement Summary - Reports today's HN engagement activity
Separate from digest, runs at 5 PM for same-day reflection
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from typing import List, Dict

HN_USERNAME = "vb7132"


def generate_daily_summary(db_path: str) -> str:
    """Generate today's engagement summary"""
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    today = datetime.now().date().isoformat()
    week_ago = (datetime.now() - timedelta(days=7)).date().isoformat()
    
    # Today's opportunities
    c.execute('''
        SELECT story_id, opportunity_type, score, action_prompt, engaged, comment_id
        FROM engagement_opportunities
        WHERE detected_date = ?
        ORDER BY score DESC
    ''', (today,))
    
    today_opps = c.fetchall()
    
    if not today_opps:
        return None  # No digest today, skip summary
    
    # Today's comments
    c.execute('''
        SELECT comment_id, story_id, comment_text, posted_at
        FROM user_comments
        WHERE DATE(posted_at) = ?
        ORDER BY posted_at
    ''', (today,))
    
    today_comments = c.fetchall()
    
    # Week stats
    c.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN engaged = 1 THEN 1 ELSE 0 END) as engaged
        FROM engagement_opportunities 
        WHERE detected_date >= ?
    ''', (week_ago,))
    
    week_total, week_engaged = c.fetchone()
    week_engaged = week_engaged or 0
    week_rate = (week_engaged / week_total * 100) if week_total > 0 else 0
    
    conn.close()
    
    # Build summary
    lines = []
    lines.append("📊 *Today's Engagement*")
    lines.append("")
    
    if today_comments:
        lines.append(f"✅ *You engaged:* {len(today_comments)} comment(s) posted\n")
        
        # Group comments by story
        by_story = {}
        for comment_id, story_id, text, posted_at in today_comments:
            if story_id not in by_story:
                by_story[story_id] = []
            by_story[story_id].append({
                'id': comment_id,
                'text': text[:100] + "..." if len(text) > 100 else text,
                'time': datetime.fromisoformat(posted_at).strftime("%H:%M")
            })
        
        for story_id, comments in by_story.items():
            # Find if this was an opportunity
            opp = next((o for o in today_opps if o[0] == story_id), None)
            
            if opp:
                opp_type = {"ask_show": "💬", "early": "🎯", "debate": "🔥"}.get(opp[1], "•")
                lines.append(f"{opp_type} *Story {story_id}* (was in opportunities)")
            else:
                lines.append(f"• *Story {story_id}* (organic engagement)")
            
            for comment in comments:
                lines.append(f"  └ {comment['time']}: {comment['text']}")
                lines.append(f"    https://news.ycombinator.com/item?id={comment['id']}")
            lines.append("")
    else:
        lines.append("⏸️ *No engagement today*")
        lines.append("")
    
    # Opportunities recap
    engaged_count = sum(1 for o in today_opps if o[4] == 1)
    lines.append(f"*Opportunities:* {len(today_opps)} detected, {engaged_count} engaged ({engaged_count/len(today_opps)*100:.0f}%)")
    
    if engaged_count < len(today_opps):
        lines.append("\n*Missed opportunities:*")
        for story_id, opp_type, score, prompt, engaged, _ in today_opps:
            if not engaged:
                emoji = {"ask_show": "💬", "early": "🎯", "debate": "🔥"}.get(opp_type, "•")
                lines.append(f"{emoji} https://news.ycombinator.com/item?id={story_id}")
                lines.append(f"   Score: {score:.2f} · {prompt}")
    
    lines.append("")
    
    # Week trend
    lines.append("*7-Day Trend*")
    lines.append(f"Engagement rate: {week_rate:.1f}% ({week_engaged}/{week_total})")
    
    if week_rate < 15:
        lines.append("💡 Tip: Low engagement - opportunities may be too broad")
    elif week_rate > 50:
        lines.append("💡 Tip: High engagement - consider raising quality bar")
    else:
        lines.append("✅ Healthy engagement rate")
    
    lines.append("")
    lines.append("_Daily reflection · track engagement patterns_")
    
    return "\n".join(lines)


def main():
    """Generate and output daily summary"""
    db_path = sys.argv[1] if len(sys.argv) > 1 else "hn_digest_v2.db"
    
    summary = generate_daily_summary(db_path)
    
    if summary:
        print(summary)
    else:
        print("NO_SUMMARY")  # Signal no digest today

if __name__ == "__main__":
    main()
