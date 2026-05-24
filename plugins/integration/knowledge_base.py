"""
Jellyfish OS v6 - Knowledge Base Plugin
Manages a searchable knowledge base for agents
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import json
import re

class KnowledgeEntry:
    """Represents a single knowledge base entry"""
    
    def __init__(
        self,
        entry_id: str,
        title: str,
        content: str,
        category: str,
        tags: List[str],
        metadata: Optional[Dict] = None
    ):
        self.id = entry_id
        self.title = title
        self.content = content
        self.category = category
        self.tags = tags
        self.metadata = metadata or {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.access_count = 0
        self.related_entries: List[str] = []
    
    def search_score(self, query: str) -> float:
        """Calculate relevance score for a search query"""
        query_lower = query.lower()
        score = 0.0
        
        # Title match (highest weight)
        if query_lower in self.title.lower():
            score += 10.0
        
        # Tag match
        for tag in self.tags:
            if query_lower in tag.lower():
                score += 5.0
        
        # Content match
        content_matches = len(re.findall(query_lower, self.content.lower()))
        score += min(content_matches * 0.5, 5.0)
        
        # Popularity boost
        score += min(self.access_count * 0.1, 2.0)
        
        return score
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "category": self.category,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "access_count": self.access_count
        }

class KnowledgeBasePlugin:
    """Plugin to manage a searchable knowledge base"""
    
    def __init__(self, storage_path: Optional[str] = None):
        self.entries: Dict[str, KnowledgeEntry] = {}
        self.categories: Dict[str, List[str]] = {}
        self.tag_index: Dict[str, List[str]] = {}
        self.storage_path = storage_path
        self.entry_counter = 0
    
    def add_entry(
        self,
        title: str,
        content: str,
        category: str,
        tags: List[str],
        metadata: Optional[Dict] = None
    ) -> KnowledgeEntry:
        """Add a new entry to the knowledge base"""
        self.entry_counter += 1
        entry_id = f"KB-{self.entry_counter:06d}"
        
        entry = KnowledgeEntry(entry_id, title, content, category, tags, metadata)
        self.entries[entry_id] = entry
        
        # Index by category
        if category not in self.categories:
            self.categories[category] = []
        self.categories[category].append(entry_id)
        
        # Index by tags
        for tag in tags:
            if tag not in self.tag_index:
                self.tag_index[tag] = []
            self.tag_index[tag].append(entry_id)
        
        return entry
    
    def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Get an entry by ID"""
        entry = self.entries.get(entry_id)
        if entry:
            entry.access_count += 1
        return entry
    
    def search(
        self,
        query: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """Search the knowledge base"""
        results = []
        candidate_ids = set(self.entries.keys())
        
        # Filter by category
        if category:
            cat_entries = self.categories.get(category, [])
            candidate_ids &= set(cat_entries)
        
        # Filter by tags
        if tags:
            tag_entries = set()
            for tag in tags:
                tag_entries |= set(self.tag_index.get(tag, []))
            candidate_ids &= tag_entries
        
        # Score and rank
        for entry_id in candidate_ids:
            entry = self.entries[entry_id]
            score = entry.search_score(query)
            if score > 0:
                results.append((entry, score))
        
        # Sort by score
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:limit]
    
    def get_by_category(self, category: str) -> List[KnowledgeEntry]:
        """Get all entries in a category"""
        entry_ids = self.categories.get(category, [])
        return [self.entries[eid] for eid in entry_ids if eid in self.entries]
    
    def get_by_tag(self, tag: str) -> List[KnowledgeEntry]:
        """Get all entries with a tag"""
        entry_ids = self.tag_index.get(tag, [])
        return [self.entries[eid] for eid in entry_ids if eid in self.entries]
    
    def update_entry(
        self,
        entry_id: str,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Update an existing entry"""
        entry = self.entries.get(entry_id)
        if not entry:
            return False
        
        if content:
            entry.content = content
        
        if tags:
            entry.tags = tags
        
        entry.updated_at = datetime.now()
        return True
    
    def link_entries(self, entry_id_1: str, entry_id_2: str) -> bool:
        """Link two entries as related"""
        if entry_id_1 not in self.entries or entry_id_2 not in self.entries:
            return False
        
        self.entries[entry_id_1].related_entries.append(entry_id_2)
        self.entries[entry_id_2].related_entries.append(entry_id_1)
        return True
    
    def get_related(self, entry_id: str, limit: int = 5) -> List[KnowledgeEntry]:
        """Get related entries"""
        entry = self.entries.get(entry_id)
        if not entry:
            return []
        
        return [
            self.entries[rid]
            for rid in entry.related_entries[:limit]
            if rid in self.entries
        ]
    
    def get_statistics(self) -> Dict:
        """Get knowledge base statistics"""
        return {
            "total_entries": len(self.entries),
            "categories": len(self.categories),
            "tags": len(self.tag_index),
            "most_accessed": sorted(
                [(e.id, e.title, e.access_count) for e in self.entries.values()],
                key=lambda x: x[2],
                reverse=True
            )[:10],
            "entries_by_category": {
                cat: len(ids)
                for cat, ids in self.categories.items()
            }
        }
    
    def save(self, path: Optional[str] = None) -> bool:
        """Save knowledge base to disk"""
        save_path = path or self.storage_path
        if not save_path:
            return False
        
        data = {
            "entries": {
                eid: {
                    "title": e.title,
                    "content": e.content,
                    "category": e.category,
                    "tags": e.tags,
                    "metadata": e.metadata,
                    "access_count": e.access_count,
                    "related_entries": e.related_entries
                }
                for eid, e in self.entries.items()
            },
            "categories": self.categories,
            "tag_index": self.tag_index,
            "entry_counter": self.entry_counter
        }
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return True
    
    def load(self, path: Optional[str] = None) -> bool:
        """Load knowledge base from disk"""
        load_path = path or self.storage_path
        if not load_path or not Path(load_path).exists():
            return False
        
        with open(load_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for entry_id, entry_data in data["entries"].items():
            entry = KnowledgeEntry(
                entry_id,
                entry_data["title"],
                entry_data["content"],
                entry_data["category"],
                entry_data["tags"],
                entry_data.get("metadata")
            )
            entry.access_count = entry_data.get("access_count", 0)
            entry.related_entries = entry_data.get("related_entries", [])
            self.entries[entry_id] = entry
        
        self.categories = data["categories"]
        self.tag_index = data["tag_index"]
        self.entry_counter = data["entry_counter"]
        
        return True

# Plugin metadata
PLUGIN_METADATA = {
    "name": "knowledge-base",
    "version": "1.0.0",
    "description": "Manage a searchable knowledge base for agents",
    "author": "Jellyfish OS Team",
    "capabilities": [
        "knowledge_storage",
        "semantic_search",
        "category_management",
        "tag_indexing"
    ]
}