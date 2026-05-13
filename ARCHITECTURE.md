# knowledge-os — Architecture

## Overview

Multi-source digest pipeline with semantic topic matching, engagement detection, read tracking, and a local dashboard.

**Current:** Single-user SQLite
**Future:** Multi-user Postgres (swap via config)

## Core Design Principles

1. **Storage abstraction** - Backend-agnostic interface
2. **Event log pattern** - All user actions tracked as events
3. **Normalized schema** - Clean relational model
4. **Multi-user ready** - User ID throughout
5. **Feedback loop** - Track engagement for future ML

## Schema

### Users
```sql
users (
    user_id: PK,
    identifier: UNIQUE (phone/email),
    settings: JSON,
    created_at
)
```

### Items (Core Content)
```sql
items (
    item_id: PK,
    url: UNIQUE,
    title,
    source: (hackernews|substack),
    author,
    score,
    fetched_at,
    published_at: ISO 8601 — if newer on re-fetch, item re-surfaces in digest,
    embedding_id: (for vector DB integration),
    external_id: HN item ID or Substack URL hash,
    created_at
)
```

### Topics (User Preferences)
```sql
topics (
    topic_id: PK,
    user_id: FK,
    name,
    keywords: JSON,
    weight: (0.0-2.0, default 1.0),
    created_at,
    updated_at,
    UNIQUE(user_id, name)
)
```

### Item-Topic Scores (Matching Results)
```sql
item_topic_scores (
    item_id: FK,
    topic_id: FK,
    score: (0.0-1.0),
    computed_at,
    PRIMARY KEY(item_id, topic_id)
)
```

### Feedback (Event Log)
```sql
feedback (
    feedback_id: PK,
    user_id: FK,
    item_id: FK,
    action: (delivered|clicked|dismissed|saved|shared),
    metadata: JSON,
    created_at
)
```

### Authors (Reputation Tracking)
```sql
authors (
    author_id: PK,
    author_name: UNIQUE,
    story_count,
    total_score,
    topics: JSON (topic -> max_score),
    first_seen,
    last_seen
)
```

### Digests (Delivery Log)
```sql
digests (
    digest_id: PK,
    user_id: FK,
    item_ids: JSON,
    sent_at,
    metadata: JSON (channel, format, etc)
)
```

## Storage Interface

### Abstraction Layer
```python
class StorageInterface(ABC):
    # Items
    @abstractmethod
    def insert_item(...) -> int
    def get_item(item_id) -> Dict
    def get_item_by_url(url) -> Dict
    
    # Topics
    @abstractmethod
    def insert_topic(...) -> int
    def get_topics(user_id) -> List[Dict]
    def update_topic_weight(topic_id, weight)
    
    # Item-Topic Scores
    @abstractmethod
    def insert_item_topic_score(...)
    def get_item_topic_scores(item_id) -> List[Dict]
    
    # Feedback
    @abstractmethod
    def insert_feedback(...)
    def get_feedback(user_id, item_id?) -> List[Dict]
    def get_undelivered_item_ids(item_ids: List[int]) -> Set[int]  # stories not yet delivered
    
    # Authors
    @abstractmethod
    def upsert_author(...)
    def get_notable_authors(user_id, min_count) -> List[Dict]
    
    # Digests
    @abstractmethod
    def insert_digest(...) -> int
    def get_digest_history(user_id) -> List[Dict]
    
    # Users
    @abstractmethod
    def get_or_create_user(...) -> int
```

### Factory Pattern
```python
storage = get_storage(backend="sqlite", db_path="...")
storage = get_storage(backend="postgres", host="...", ...)
```

## Data Flow

```
1. Fetch stories
   fetch_stories.py   → HN API (hackernews source)
   fetch_substack.py  → RSS feeds (substack source)
   Merged             → all_stories.json

2. Process (process_digest.py)
   → Load config
   → Get/create user
   → Initialize topics (if needed)
   → Match stories to topics (sentence-transformer embeddings)
   → Insert items + item-topic scores
   → Update author stats
   → Record digest delivery
   → Fetch comment summaries (engagement.py)
   → Detect engagement opportunities (engagement.py)
   → Generate digest markdown

3. Deliver
   → knos-digest/YYYY-MM-DD.md (archive)
   → WhatsApp via OpenClaw gateway

4. Post-delivery
   → sync_reading_log.py  — mark read items from digest
   → engagement_summary.py — daily engagement reflection
   → dashboard.py (streamlit) — local observability UI
```

## Configuration

**config.json:**
```json
{
  "storage": {
    "backend": "sqlite|postgres",
    "sqlite": { "db_path": "..." },
    "postgres": { "host": "...", ... }
  },
  "user": {
    "identifier": "+919179611575",
    "timezone": "Asia/Calcutta"
  },
  "topics": [ ... ],
  "settings": { ... }
}
```

## Migration Path

### Phase 1: SQLite (Current)
- Single user
- Local storage
- Fast development

### Phase 2: Multi-user SQLite
- Add user management
- Multiple identifier support
- Per-user topics/settings

### Phase 3: Postgres
- Change config: `"backend": "postgres"`
- Implement `storage_postgres.py`
- Add connection pooling
- Optional: pgvector for embeddings

### Phase 4: Scale
- Redis caching layer
- Background workers (Celery)
- Vector DB (Pinecone/Weaviate) for semantic search
- Analytics dashboard ✅ (Streamlit, local)

## Testing

```bash
# Run all tests
venv/bin/python -m pytest tests/ -v

# Test full pipeline
bash scripts/run_digest_v2.sh

# Check database
sqlite3 hn_digest_v2.db "SELECT COUNT(*) FROM items"

# Local dashboard
venv/bin/python -m streamlit run src/knowledge_os/dashboard.py
```

## Monitoring

Track:
- Digest delivery rate
- Items per digest
- Topic match distribution
- Author diversity
- Feedback engagement

---

**Design Goal:** Start simple (SQLite), scale seamlessly (Postgres), optimize later (vector DB + ML).
