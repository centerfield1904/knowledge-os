#!/usr/bin/env python3
"""
Storage interface abstraction for HN digest system
Supports SQLite (current) and Postgres (future)
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime
import json

class StorageInterface(ABC):
    """Abstract storage interface"""
    
    @abstractmethod
    def init_schema(self):
        """Initialize database schema"""
        pass
    
    # Items
    @abstractmethod
    def insert_item(self, url: str, title: str, source: str, author: str,
                   score: int, fetched_at: str, published_at: str = '',
                   embedding_id: Optional[str] = None,
                   external_id: Optional[str] = None) -> Tuple[int, bool]:
        """Insert item and return (item_id, is_new).
        is_new=True if newly inserted OR if published_at is newer than stored."""
        pass
    
    @abstractmethod
    def get_item(self, item_id: int) -> Optional[Dict]:
        """Get item by ID"""
        pass
    
    @abstractmethod
    def get_item_by_url(self, url: str) -> Optional[Dict]:
        """Get item by URL"""
        pass
    
    # Topics
    @abstractmethod
    def insert_topic(self, user_id: int, name: str, keywords: List[str], weight: float = 1.0) -> int:
        """Insert topic and return topic_id"""
        pass
    
    @abstractmethod
    def get_topics(self, user_id: int) -> List[Dict]:
        """Get all topics for user"""
        pass
    
    @abstractmethod
    def update_topic_weight(self, topic_id: int, weight: float):
        """Update topic weight"""
        pass
    
    # Item-Topic scores
    @abstractmethod
    def insert_item_topic_score(self, item_id: int, topic_id: int, score: float):
        """Record item-topic similarity score"""
        pass
    
    @abstractmethod
    def get_item_topic_scores(self, item_id: int) -> List[Dict]:
        """Get all topic scores for an item"""
        pass
    
    # Feedback
    @abstractmethod
    def insert_feedback(self, user_id: int, item_id: int, action: str, 
                       metadata: Optional[Dict] = None):
        """Record user feedback event"""
        pass
    
    @abstractmethod
    def get_feedback(self, user_id: int, item_id: Optional[int] = None) -> List[Dict]:
        """Get feedback history"""
        pass

    @abstractmethod
    def get_undelivered_item_ids(self, item_ids: List[int]) -> Set[int]:
        """Return the subset of item_ids that have never been delivered in a digest."""
        pass
    
    # Authors
    @abstractmethod
    def upsert_author(self, user_id: int, author_name: str, item_id: int,
                      topic_scores: Dict[str, float]):
        """Insert or update author stats"""
        pass
    
    @abstractmethod
    def get_notable_authors(self, user_id: int, min_count: int = 3) -> List[Dict]:
        """Get authors who frequently post in user's topics"""
        pass
    
    # Digests
    @abstractmethod
    def insert_digest(self, user_id: int, item_ids: List[int], sent_at: str) -> int:
        """Record digest delivery"""
        pass
    
    @abstractmethod
    def get_digest_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get digest history"""
        pass
    
    # Users
    @abstractmethod
    def get_or_create_user(self, identifier: str, settings: Optional[Dict] = None) -> int:
        """Get or create user, return user_id"""
        pass


def get_storage(backend: str = "sqlite", **kwargs) -> StorageInterface:
    """Factory function to get storage implementation"""
    if backend == "sqlite":
        from .storage_sqlite import SQLiteStorage
        return SQLiteStorage(**kwargs)
    elif backend == "postgres":
        from .storage_postgres import PostgresStorage
        return PostgresStorage(**kwargs)
    else:
        raise ValueError(f"Unknown storage backend: {backend}")
