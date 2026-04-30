#!/usr/bin/env python3
"""
Fetch top stories from Hacker News
"""
import requests
import json
from datetime import datetime
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

HN_TOP_STORIES = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"

def fetch_story(story_id: int) -> Dict:
    """Fetch individual story details with timeout"""
    try:
        response = requests.get(HN_ITEM.format(story_id), timeout=5)
        return response.json()
    except Exception as e:
        return None

def fetch_top_stories(max_stories: int = 30, min_score: int = 50) -> List[Dict]:
    """Fetch top stories from HN using concurrent requests"""
    # Get top story IDs
    response = requests.get(HN_TOP_STORIES, timeout=5)
    # Only fetch 3x the target to reduce API calls
    story_ids = response.json()[:max_stories * 3]
    
    stories = []
    
    # Fetch stories concurrently
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_id = {executor.submit(fetch_story, sid): sid for sid in story_ids}
        
        for future in as_completed(future_to_id):
            if len(stories) >= max_stories:
                # Cancel remaining futures
                for f in future_to_id:
                    f.cancel()
                break
                
            story = future.result()
            
            if not story:
                continue
                
            # Filter by score and type
            if (story.get('type') == 'story' and 
                story.get('score', 0) >= min_score and
                not story.get('deleted', False)):
                
                stories.append({
                    'id': story['id'],
                    'title': story.get('title', ''),
                    'url': story.get('url', f"https://news.ycombinator.com/item?id={story['id']}"),
                    'score': story.get('score', 0),
                    'by': story.get('by', 'unknown'),
                    'time': story.get('time', 0),
                    'descendants': story.get('descendants', 0),  # comment count
                    'text': story.get('text', ''),
                    'fetched_at': datetime.now().isoformat(),
                    'published_at': datetime.utcfromtimestamp(story['time']).isoformat() if story.get('time') else datetime.now().isoformat(),
                })
    
    # Sort by score
    stories.sort(key=lambda x: x['score'], reverse=True)
    return stories[:max_stories]

if __name__ == "__main__":
    stories = fetch_top_stories()
    print(json.dumps(stories, indent=2))
