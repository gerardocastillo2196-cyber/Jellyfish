"""
Jellyfish OS v6 - Agent Context Plugin
Adds context management capabilities to AI agents
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from plugins.plugin_core import PluginInterface, PluginMetadata

class AgentContextPlugin(PluginInterface):
    """Plugin to manage agent conversation context and history"""
    
    PLUGIN_METADATA = PluginMetadata(
        name="agent-context",
        version="1.0.0",
        description="Context management for AI agents",
        author="Jellyfish OS Team",
        capabilities=[
            "context_management",
            "memory_storage",
            "context_search"
        ]
    )
    
    def __init__(self):
        super().__init__()
        self.context_stack: List[Dict[str, Any]] = []
        self.max_context_size = 10
        self.agent_memory: Dict[str, Any] = {}
        
    def push_context(self, context_type: str, data: Dict[str, Any]) -> None:
        """Push a new context frame onto the stack"""
        context_frame = {
            "type": context_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "id": len(self.context_stack)
        }
        self.context_stack.append(context_frame)
        
        # Maintain max size
        if len(self.context_stack) > self.max_context_size:
            self.context_stack.pop(0)
    
    def get_recent_context(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get the n most recent context frames"""
        return self.context_stack[-n:]
    
    def search_context(self, keyword: str) -> List[Dict[str, Any]]:
        """Search context history for keyword"""
        results = []
        for frame in self.context_stack:
            if keyword.lower() in json.dumps(frame.get("data", {})).lower():
                results.append(frame)
        return results
    
    def store_memory(self, key: str, value: Any) -> None:
        """Store persistent memory for the agent"""
        self.agent_memory[key] = {
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
    
    def recall_memory(self, key: str) -> Optional[Any]:
        """Recall stored memory"""
        memory = self.agent_memory.get(key)
        return memory["value"] if memory else None
    
    def get_context_summary(self) -> str:
        """Generate a summary of current context"""
        if not self.context_stack:
            return "No context available"
        
        recent = self.get_recent_context(3)
        summary_parts = []
        
        for frame in recent:
            summary_parts.append(
                f"[{frame['type']}] {json.dumps(frame['data'])[:100]}"
            )
        
        return " | ".join(summary_parts)

# Module-level metadata for package import compatibility
PLUGIN_METADATA = {
    "name": "agent-context",
    "version": "1.0.0",
    "description": "Context management for AI agents",
    "author": "Jellyfish OS Team",
    "capabilities": [
        "context_management",
        "memory_storage",
        "context_search"
    ]
}