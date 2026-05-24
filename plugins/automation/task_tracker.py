"""
Jellyfish OS v6 - Task Tracker Plugin
Tracks tasks, subtasks, and progress for agent workflows
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"

class Task:
    """Represents a single task"""
    
    def __init__(self, title: str, task_id: str, parent_id: Optional[str] = None):
        self.id = task_id
        self.title = title
        self.parent_id = parent_id
        self.status = TaskStatus.PENDING
        self.subtasks: List[Task] = []
        self.notes: List[str] = []
        self.created_at = datetime.now()
        self.completed_at: Optional[datetime] = None
        self.metadata: Dict[str, Any] = {}
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "parent_id": self.parent_id,
            "status": self.status.value,
            "subtasks_count": len(self.subtasks),
            "completed_subtasks": sum(1 for s in self.subtasks if s.status == TaskStatus.COMPLETED),
            "notes_count": len(self.notes),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

class TaskTrackerPlugin:
    """Plugin to track tasks and progress"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.task_counter = 0
    
    def create_task(self, title: str, parent_id: Optional[str] = None) -> Task:
        """Create a new task"""
        self.task_counter += 1
        task = Task(title, f"TASK-{self.task_counter:04d}", parent_id)
        self.tasks[task.id] = task
        
        # Link to parent if exists
        if parent_id and parent_id in self.tasks:
            self.tasks[parent_id].subtasks.append(task)
        
        return task
    
    def update_status(self, task_id: str, status: TaskStatus) -> bool:
        """Update task status"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.status = status
        
        if status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now()
        
        return True
    
    def add_note(self, task_id: str, note: str) -> bool:
        """Add a note to a task"""
        if task_id not in self.tasks:
            return False
        
        self.tasks[task_id].notes.append(note)
        return True
    
    def get_task_tree(self, root_id: Optional[str] = None) -> Dict:
        """Get hierarchical task tree"""
        if root_id:
            return self._build_tree(self.tasks[root_id])
        
        # Return all root tasks
        roots = [t for t in self.tasks.values() if t.parent_id is None]
        return {
            "tasks": [self._build_tree(t) for t in roots],
            "summary": self.get_summary()
        }
    
    def _build_tree(self, task: Task) -> Dict:
        """Build tree structure for a task"""
        node = task.to_dict()
        if task.subtasks:
            node["children"] = [self._build_tree(s) for s in task.subtasks]
        return node
    
    def get_summary(self) -> Dict:
        """Get summary statistics"""
        status_counts = {s.value: 0 for s in TaskStatus}
        for task in self.tasks.values():
            status_counts[task.status.value] += 1
        
        total_completion = 0
        if self.tasks:
            completed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
            total_completion = (completed / len(self.tasks)) * 100
        
        return {
            "total_tasks": len(self.tasks),
            "by_status": status_counts,
            "completion_percentage": round(total_completion, 2)
        }

# Plugin metadata
PLUGIN_METADATA = {
    "name": "task-tracker",
    "version": "1.0.0",
    "description": "Track tasks, subtasks, and progress",
    "author": "Jellyfish OS Team",
    "capabilities": [
        "task_creation",
        "progress_tracking",
        "hierarchy_management",
        "note_taking"
    ]
}