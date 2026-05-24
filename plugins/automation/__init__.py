"""
Jellyfish OS v6 - Automation Package
Workflow and task automation plugins
"""

from .task_tracker import TaskTrackerPlugin, TaskStatus, PLUGIN_METADATA as TASK_TRACKER_METADATA
from .workflow_orchestrator import WorkflowOrchestrator, Workflow, WorkflowStep, PLUGIN_METADATA as WORKFLOW_ORCHESTRATOR_METADATA

__all__ = [
    "TaskTrackerPlugin",
    "TaskStatus",
    "WorkflowOrchestrator",
    "Workflow",
    "WorkflowStep"
]