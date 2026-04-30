#!/usr/bin/env python3
"""
Simple feedback extractor from knos-digest markdown files
Standalone script with minimal dependencies
"""
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "hn_feedback.db"

def init_db():
    """Initialize feedback database"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS feedback
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  story_id TEXT,
                  story_title TEXT,
                  story_url TEXT,
                  story_score INTEGER,
                  story_author TEXT,
                  action TEXT,
                  timestamp TEXT,
                  digest_date TEXT,
                  notes TEXT)''')
    
    conn.commit()
    return conn

def parse_digest(filepath):
    """Extract stories with feedback from digest markdown"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    stories = []
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Look for checkbox lines
        checkbox_match = re.match(r'^- \[([ x])\]\s*(.+)$', line)
        if checkbox_match:
            checked = checkbox_match.group(1) == 'x'
            title = re.sub(r'^(📰|💬|🔥)\s*', '', checkbox_match.group(2)).strip()
            
            # Extract metadata from following lines
            story_id = None
            url = None
            author = None
            score = None
            notes = ''
            
            i += 1
            while i < len(lines) and not lines[i].startswith('- ['):
                curr = lines[i].strip()
                
                # Stop at section headers
                if curr.startswith('*') or curr.startswith('🎯') or curr.startswith('_Keep'):
                    break
                
                # Parse metadata
                meta_match = re.search(r'↑(\d+).*by\s+(\w+)', curr)
                if meta_match:
                    score = int(meta_match.group(1))
                    author = meta_match.group(2)
                
                # Parse URL
                url_match = re.search(r'🔗\s+(https?://[^\s]+)', curr)
                if url_match:
                    url = url_match.group(1)
                    id_match = re.search(r'item\?id=(\d+)', url)
                    if id_match:
                        story_id = id_match.group(1)
                
                # Parse notes
                if curr.startswith('Notes:'):
                    notes_lines = [curr[6:].strip()]
                    i += 1
                    while i < len(lines):
                        next_line = lines[i].strip()
                        if next_line.startswith('- [') or next_line.startswith('*') or next_line.startswith('🎯'):
                            i -= 1
                            break
                        if next_line:
                            notes_lines.append(next_line)
                        i += 1
                    notes = '\n'.join(notes_lines).strip()
                    break
                
                i += 1
            
            if story_id:
                action = 'save' if (checked and notes) else ('like' if checked else 'skip')
                stories.append({
                    'story_id': story_id,
                    'title': title,
                    'url': url,
                    'score': score,
                    'author': author,
                    'action': action,
                    'notes': notes
                })
        
        i += 1
    
    return stories

def process_digests(days_back=30):
    """Process all digest files"""
    knos_dir = PROJECT_ROOT / 'knos-digest'
    md_files = sorted(knos_dir.glob('*.md'))
    
    cutoff = datetime.now() - timedelta(days=days_back)
    
    conn = init_db()
    c = conn.cursor()
    
    stats = {'processed': 0, 'recorded': 0, 'like': 0, 'save': 0, 'skip': 0}
    
    for md_file in md_files:
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', md_file.stem)
        if not date_match:
            continue
        
        digest_date = date_match.group(1)
        
        try:
            file_date = datetime.strptime(digest_date, '%Y-%m-%d')
            if file_date < cutoff:
                continue
        except:
            continue
        
        stories = parse_digest(md_file)
        stats['processed'] += 1
        
        for story in stories:
            # Check if already recorded
            c.execute("SELECT id FROM feedback WHERE story_id = ? AND digest_date = ?",
                     (story['story_id'], digest_date))
            if c.fetchone():
                continue
            
            # Insert feedback
            c.execute('''INSERT INTO feedback 
                        (story_id, story_title, story_url, story_score, story_author,
                         action, timestamp, digest_date, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (story['story_id'], story['title'], story['url'], story['score'],
                      story['author'], story['action'], datetime.now().isoformat(),
                      digest_date, story['notes']))
            
            stats['recorded'] += 1
            stats[story['action']] += 1
    
    conn.commit()
    conn.close()
    
    return stats

if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    
    print(f"🔍 Scanning digests (last {days} days)...")
    stats = process_digests(days)
    
    print(f"\n✅ Results:")
    print(f"   Files processed: {stats['processed']}")
    print(f"   Feedback recorded: {stats['recorded']}")
    print(f"\n📊 Breakdown:")
    print(f"   👍 like: {stats['like']}")
    print(f"   📌 save: {stats['save']}")
    print(f"   👎 skip: {stats['skip']}")
    print(f"\n💾 Stored in: hn_feedback.db")
