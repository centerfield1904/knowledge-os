#!/usr/bin/env python3
"""
Engagement Opportunity Detection for HN Digest
Tracks vb7132's HN comments and surfaces high-value engagement opportunities
"""

import sqlite3
import json
import urllib.request
from datetime import datetime, timedelta
from typing import List, Dict, Optional

HN_API = "https://hacker-news.firebaseio.com/v0"
HN_USERNAME = "vb7132"


class EngagementDetector:
    """Detect and score engagement opportunities from HN stories"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Create engagement tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS engagement_opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_id INTEGER,
                detected_date TEXT,
                opportunity_type TEXT,
                score REAL,
                action_prompt TEXT,
                engaged BOOLEAN DEFAULT 0,
                engagement_date TEXT,
                comment_id INTEGER,
                karma_gained INTEGER,
                UNIQUE(story_id, detected_date)
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_comments (
                comment_id INTEGER PRIMARY KEY,
                story_id INTEGER,
                comment_text TEXT,
                posted_at TEXT,
                synced_at TEXT
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS engagement_stats (
                date TEXT PRIMARY KEY,
                opportunities_detected INTEGER,
                opportunities_engaged INTEGER,
                total_karma_gained INTEGER,
                comments_posted INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def fetch_json(self, url: str) -> Optional[Dict]:
        """Fetch JSON from HN API"""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HNDigest/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                return json.loads(r.read())
        except Exception:
            return None
    
    def fetch_user_karma(self, username: str) -> Optional[int]:
        """Fetch HN karma for a username."""
        user_data = self.fetch_json(f"{HN_API}/user/{username}.json")
        if user_data:
            return user_data.get("karma")
        return None

    def fetch_user_recent_comments(self, max_items: int = 30) -> List[Dict]:
        """Fetch user's recent comments from HN API"""
        user_data = self.fetch_json(f"{HN_API}/user/{HN_USERNAME}.json")
        if not user_data or "submitted" not in user_data:
            return []
        
        comments = []
        for item_id in user_data["submitted"][:max_items]:
            item = self.fetch_json(f"{HN_API}/item/{item_id}.json")
            if item and item.get("type") == "comment":
                comments.append(item)
        
        return comments
    
    def sync_user_comments(self):
        """Sync recent user comments to database"""
        comments = self.fetch_user_recent_comments()
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        for comment in comments:
            comment_id = comment["id"]
            story_id = self._find_story_id(comment)
            
            c.execute('''
                INSERT OR IGNORE INTO user_comments 
                (comment_id, story_id, comment_text, posted_at, synced_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                comment_id,
                story_id,
                comment.get("text", ""),
                datetime.fromtimestamp(comment.get("time", 0)).isoformat(),
                datetime.now().isoformat()
            ))
            
            # Mark opportunity as engaged if it exists
            if story_id:
                c.execute('''
                    UPDATE engagement_opportunities 
                    SET engaged = 1, engagement_date = ?, comment_id = ?
                    WHERE story_id = ? AND engaged = 0
                ''', (datetime.now().isoformat(), comment_id, story_id))
        
        conn.commit()
        conn.close()
        
        return len(comments)
    
    def _find_story_id(self, comment: Dict) -> Optional[int]:
        """Traverse parent chain to find root story ID"""
        current_id = comment.get("parent")
        visited = set()
        
        while current_id and current_id not in visited:
            visited.add(current_id)
            item = self.fetch_json(f"{HN_API}/item/{current_id}.json")
            
            if not item:
                return None
            
            if item.get("type") == "story":
                return current_id
            
            current_id = item.get("parent")
        
        return None
    
    def fetch_story_comments(self, story_id: int, max_depth: int = 1) -> List[Dict]:
        """Fetch top-level comments for a story"""
        story = self.fetch_json(f"{HN_API}/item/{story_id}.json")
        if not story or "kids" not in story:
            return []
        
        comments = []
        for kid_id in story["kids"][:10]:  # Top 10 comments
            comment = self.fetch_json(f"{HN_API}/item/{kid_id}.json")
            if comment:
                comments.append(comment)
        
        return comments
    
    def analyze_comments(self, comments: List[Dict]) -> Dict[str, any]:
        """Analyze comments for engagement signals"""
        if not comments:
            return {"has_questions": False, "has_debate": False, "avg_length": 0}
        
        question_signals = ["?", "how do", "how to", "what about", "why does"]
        debate_signals = ["disagree", "wrong", "actually", "but ", "however"]
        
        has_questions = any(
            any(sig in comment.get("text", "").lower() for sig in question_signals)
            for comment in comments
        )
        
        has_debate = sum(
            1 for comment in comments
            if any(sig in comment.get("text", "").lower() for sig in debate_signals)
        ) >= 2
        
        avg_length = sum(len(comment.get("text", "")) for comment in comments) / len(comments)
        
        return {
            "has_questions": has_questions,
            "has_debate": has_debate,
            "avg_length": avg_length,
            "comment_count": len(comments)
        }
    
    def detect_opportunities(self, stories: List[Dict], max_results: int = 5) -> List[Dict]:
        """
        Find top engagement opportunities from matched stories
        
        Args:
            stories: List of HN story dicts
            max_results: Maximum opportunities to return
            
        Returns:
            List of opportunity dicts with type, story, score, action_prompt
        """
        opportunities = []
        
        for story in stories:
            # Extract story data - handle both formats (knowledge-os and raw HN)
            if 'id' in story:
                story_id = story['id']
                title = story.get('title', '')
                descendants = story.get('descendants', 0)
                score = story.get('score', 0)
                time = story.get('time', datetime.now().timestamp())
            else:
                # Skip if malformed
                continue
            
            age_hours = (datetime.now() - datetime.fromtimestamp(time)).total_seconds() / 3600
            
            # Type 1: Ask HN / Show HN
            if title.startswith(('Ask HN:', 'Show HN:')):
                opportunities.append({
                    'type': 'ask_show',
                    'story': story,
                    'score': self._score_ask_show(story, age_hours),
                    'action_prompt': self._generate_ask_show_prompt(story)
                })
            
            # Type 2: Early engagement (low comment count, recent)
            elif descendants < 10 and age_hours < 6:
                opportunities.append({
                    'type': 'early',
                    'story': story,
                    'score': self._score_early(story, age_hours),
                    'action_prompt': self._generate_early_prompt(story)
                })
            
            # Type 3: Hot debate (50+ comments, active)
            elif descendants > 50 and age_hours < 12:
                opportunities.append({
                    'type': 'debate',
                    'story': story,
                    'score': self._score_debate(story, age_hours),
                    'action_prompt': self._generate_debate_prompt(story)
                })
        
        # Sort by score
        opportunities.sort(key=lambda x: x['score'], reverse=True)
        
        # For top 3, fetch comments and analyze (middle ground approach)
        for opp in opportunities[:3]:
            try:
                comments = self.fetch_story_comments(opp['story']['id'])
                analysis = self.analyze_comments(comments)
                
                # Boost score based on comment analysis
                if analysis['has_questions']:
                    opp['score'] = min(1.0, opp['score'] + 0.15)
                if analysis['has_debate']:
                    opp['score'] = min(1.0, opp['score'] + 0.1)
            except Exception:
                # Continue if comment analysis fails
                pass
        
        # Re-sort after analysis boost
        opportunities.sort(key=lambda x: x['score'], reverse=True)
        return opportunities[:max_results]
    
    def _score_ask_show(self, story: Dict, age_hours: float) -> float:
        """Score Ask HN / Show HN opportunities"""
        base_score = 0.75  # High base - explicit request for feedback
        
        # Boost for low comment count (early engagement)
        descendants = story.get('descendants', 0)
        if descendants == 0:
            comment_boost = 0.15
        elif descendants < 5:
            comment_boost = 0.1
        else:
            comment_boost = 0.05
        
        # Boost for recent (fresher = better visibility)
        time_boost = max(0, 0.1 - (age_hours / 60))  # Decay over 6 hours
        
        return min(1.0, base_score + comment_boost + time_boost)
    
    def _score_early(self, story: Dict, age_hours: float) -> float:
        """Score early engagement opportunities"""
        base_score = 0.55
        
        descendants = story.get('descendants', 0)
        if descendants == 0:
            comment_boost = 0.25
        elif descendants <= 3:
            comment_boost = 0.15
        else:
            comment_boost = 0.1
        
        # High score = likely to get attention
        score_boost = 0.1 if story.get('score', 0) > 50 else 0.05
        
        # Very fresh = better
        time_boost = max(0, 0.1 - (age_hours / 30))
        
        return min(1.0, base_score + comment_boost + score_boost + time_boost)
    
    def _score_debate(self, story: Dict, age_hours: float) -> float:
        """Score debate/discussion opportunities"""
        base_score = 0.45  # Lower base - harder to stand out
        
        descendants = story.get('descendants', 0)
        if descendants > 150:
            activity_boost = 0.25
        elif descendants > 100:
            activity_boost = 0.15
        else:
            activity_boost = 0.1
        
        # Still somewhat fresh
        time_boost = max(0, 0.1 - (age_hours / 60))
        
        return min(1.0, base_score + activity_boost + time_boost)
    
    def _generate_ask_show_prompt(self, story: Dict) -> str:
        """Generate action prompt for Ask/Show HN"""
        descendants = story.get('descendants', 0)
        title = story['title']
        
        if title.startswith('Ask HN:'):
            return f"Direct question. {descendants} comments. Share your systems thinking?"
        else:  # Show HN
            return f"Someone built something. {descendants} comments. Feedback or insights?"
    
    def _generate_early_prompt(self, story: Dict) -> str:
        """Generate action prompt for early engagement"""
        descendants = story.get('descendants', 0)
        age_hours = (datetime.now() - datetime.fromtimestamp(story.get('time', datetime.now().timestamp()))).total_seconds() / 3600
        return f"Early ({descendants} comments, {int(age_hours)}h old). High visibility. Add framework?"
    
    def _generate_debate_prompt(self, story: Dict) -> str:
        """Generate action prompt for debates"""
        descendants = story.get('descendants', 0)
        return f"Active debate ({descendants} comments). Provide clarity or mental model?"
    
    def save_opportunities(self, opportunities: List[Dict], date: str):
        """Save detected opportunities to database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        for opp in opportunities:
            c.execute('''
                INSERT OR REPLACE INTO engagement_opportunities 
                (story_id, detected_date, opportunity_type, score, action_prompt)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                opp['story']['id'],
                date,
                opp['type'],
                opp['score'],
                opp['action_prompt']
            ))
        
        # Update stats
        c.execute('''
            INSERT OR REPLACE INTO engagement_stats 
            (date, opportunities_detected)
            VALUES (?, ?)
        ''', (date, len(opportunities)))
        
        conn.commit()
        conn.close()


def format_engagement_section(opportunities: List[Dict]) -> str:
    """Format opportunities for digest output"""
    if not opportunities:
        return ""
    
    output = "\n🎯 *Engagement Opportunities*\n\n"
    
    emoji_map = {
        'ask_show': '💬',
        'early': '🎯',
        'debate': '🔥'
    }
    
    for i, opp in enumerate(opportunities, 1):
        story = opp['story']
        title = story['title']
        sid = story['id']
        emoji = emoji_map.get(opp['type'], '•')

        output += f"- [ ] {emoji} {title}\n"
        output += f"  → {opp['action_prompt']}\n"
        output += f"  🔗 https://news.ycombinator.com/item?id={sid}\n"
        output += f"  Notes: \n\n"
    
    return output


def generate_weekly_report(db_path: str) -> str:
    """Generate weekly engagement report"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    week_ago = (datetime.now() - timedelta(days=7)).date().isoformat()
    
    c.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN engaged = 1 THEN 1 ELSE 0 END) as engaged
        FROM engagement_opportunities 
        WHERE detected_date >= ?
    ''', (week_ago,))
    
    total, engaged = c.fetchone()
    engaged = engaged or 0
    rate = (engaged / total * 100) if total > 0 else 0
    
    c.execute('''
        SELECT COUNT(*) FROM user_comments
        WHERE posted_at >= ?
    ''', (week_ago,))
    
    comments_count = c.fetchone()[0]
    
    output = f"""📊 *Weekly Engagement Report*

Opportunities detected: {total}
Engaged with: {engaged} ({rate:.1f}%)
Total comments posted: {comments_count}
"""
    
    conn.close()
    return output


if __name__ == "__main__":
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else "hn_digest_v2.db"
    detector = EngagementDetector(db_path)
    
    # Sync recent comments
    synced = detector.sync_user_comments()
    print(f"✅ Synced {synced} recent comments for {HN_USERNAME}")
    
    # Generate weekly report
    print(generate_weekly_report(db_path))
