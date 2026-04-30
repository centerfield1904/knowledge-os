#!/usr/bin/env python3
"""
Weekly trending topics summary.
Queries the last 7 days of stored stories and surfaces what dominated by topic.
"""
import sqlite3
import sys
from datetime import datetime, timedelta


def generate_weekly_summary(db_path: str = "hn_digest_v2.db") -> str:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    week_ago = (datetime.now() - timedelta(days=7)).isoformat()

    c.execute('''
        SELECT i.title, i.score, i.author, i.source, i.fetched_at,
               its.score AS topic_score, t.name AS topic_name
        FROM items i
        JOIN item_topic_scores its ON i.item_id = its.item_id
        JOIN topics t ON its.topic_id = t.topic_id
        WHERE i.fetched_at >= ? AND its.score >= 0.3
        ORDER BY its.score DESC
    ''', (week_ago,))

    rows = c.fetchall()
    conn.close()

    if not rows:
        return "No matched stories in the last 7 days."

    # Deduplicate: keep highest topic_score per (title, topic)
    seen = {}
    for row in rows:
        key = (row['title'], row['topic_name'])
        if key not in seen or row['topic_score'] > seen[key]['topic_score']:
            seen[key] = dict(row)

    # Group by topic
    by_topic = {}
    for entry in seen.values():
        topic = entry['topic_name']
        by_topic.setdefault(topic, []).append(entry)

    # Sort topics by story count desc
    sorted_topics = sorted(by_topic.items(), key=lambda x: len(x[1]), reverse=True)

    today = datetime.now().strftime("%a, %b %-d")
    lines = [f"*Weekly Summary* — week ending {today}",
             f"_{sum(len(v) for v in by_topic.values())} matched stories across {len(by_topic)} topics_",
             ""]

    for topic, stories in sorted_topics:
        lines.append(f"*{topic}* — {len(stories)} stories")
        top = sorted(stories, key=lambda s: s.get('score') or 0, reverse=True)[:3]
        for s in top:
            icon = "📰 " if s['source'] == 'substack' else ""
            score_str = f" ↑{s['score']}" if s.get('score') else ""
            lines.append(f"  • {icon}{s['title']}{score_str}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "hn_digest_v2.db"
    print(generate_weekly_summary(db_path))
