#!/usr/bin/env python3
"""
Match stories to topics using semantic similarity
"""
import json
import numpy as np
from typing import List, Dict
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

class TopicMatcher:
    def __init__(self, config_path: str = "config.json", config: Dict = None):
        import sys
        import time
        from datetime import datetime
        
        init_start = time.time()
        if config is not None:
            self.config = config
        else:
            with open(config_path) as f:
                self.config = json.load(f)
        
        # Load embedding model
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Loading embedding model (all-MiniLM-L6-v2)...", file=sys.stderr)
        model_start = time.time()
        self.model = SentenceTransformer('all-MiniLM-L6-v2')  # Fast, good quality
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Model loaded in {time.time() - model_start:.1f}s", file=sys.stderr)
        
        # Pre-compute topic embeddings
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Computing topic embeddings...", file=sys.stderr)
        embedding_start = time.time()
        self.topic_embeddings = {}
        for topic in self.config['topics']:
            # Create topic representation from keywords
            topic_text = f"{topic['name']}. " + " ".join(topic['keywords'])
            self.topic_embeddings[topic['name']] = self.model.encode(topic_text)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Topic embeddings computed in {time.time() - embedding_start:.1f}s ({len(self.topic_embeddings)} topics)", file=sys.stderr)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] TopicMatcher initialized in {time.time() - init_start:.1f}s", file=sys.stderr)
    
    def match_stories(self, stories: List[Dict]) -> List[Dict]:
        """Match stories to topics and return filtered/enriched stories"""
        import sys
        import time
        from datetime import datetime
        
        match_start = time.time()
        if not stories:
            return []
        
        # Embed story titles
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Embedding {len(stories)} story titles...", file=sys.stderr)
        embed_start = time.time()
        story_texts = [s['title'] for s in stories]
        story_embeddings = self.model.encode(story_texts)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Story embeddings completed in {time.time() - embed_start:.1f}s", file=sys.stderr)
        
        matched_stories = []
        threshold = self.config['settings']['similarity_threshold']
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Computing similarity scores...", file=sys.stderr)
        similarity_start = time.time()
        for i, story in enumerate(stories):
            story_emb = story_embeddings[i].reshape(1, -1)
            
            # Calculate similarity to each topic
            topic_scores = {}
            for topic_name, topic_emb in self.topic_embeddings.items():
                similarity = cosine_similarity(story_emb, topic_emb.reshape(1, -1))[0][0]
                topic_scores[topic_name] = float(similarity)
            
            # Get best matching topic
            best_topic = max(topic_scores.items(), key=lambda x: x[1])
            
            if best_topic[1] >= threshold:
                story['matched_topic'] = best_topic[0]
                story['topic_score'] = best_topic[1]
                story['all_topic_scores'] = topic_scores
                matched_stories.append(story)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Similarity computation completed in {time.time() - similarity_start:.1f}s", file=sys.stderr)
        
        # Sort by topic score (most relevant first)
        matched_stories.sort(key=lambda x: x['topic_score'], reverse=True)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Story matching completed in {time.time() - match_start:.1f}s ({len(matched_stories)}/{len(stories)} matched)", file=sys.stderr)
        return matched_stories

    def score_all_stories(self, stories: List[Dict]) -> List:
        """Return (story, max_similarity) for every story, with all_topic_scores attached.
        Unlike match_stories(), no threshold filter is applied — all stories are returned."""
        import sys
        if not stories:
            return []
        story_texts = [s['title'] for s in stories]
        story_embeddings = self.model.encode(story_texts)
        result = []
        for i, story in enumerate(stories):
            story_emb = story_embeddings[i].reshape(1, -1)
            topic_scores = {}
            for topic_name, topic_emb in self.topic_embeddings.items():
                similarity = cosine_similarity(story_emb, topic_emb.reshape(1, -1))[0][0]
                topic_scores[topic_name] = float(similarity)
            story['all_topic_scores'] = topic_scores
            max_sim = max(topic_scores.values(), default=0.0)
            result.append((story, max_sim))
        return result

if __name__ == "__main__":
    import sys
    
    # Read stories from stdin or file
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            stories = json.load(f)
    else:
        stories = json.load(sys.stdin)
    
    matcher = TopicMatcher()
    matched = matcher.match_stories(stories)
    
    print(json.dumps(matched, indent=2))
