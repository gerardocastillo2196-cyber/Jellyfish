"""
Jellyfish OS v6 - Workflow Orchestrator Plugin
Orchestrates multi-step workflows for complex tasks
"""

from typing import Dict, List, Callable, Any, Optional
from datetime import datetime
from enum import Enum

from plugins.plugin_core import PluginInterface, PluginMetadata

class WorkflowStatus(Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

class WorkflowStep:
    """Represents a single step in a workflow"""
    
    def __init__(
        self,
        step_id: str,
        name: str,
        action: Callable,
        required_skills: Optional[List[str]] = None,
        retry_count: int = 0,
        timeout_seconds: int = 300
    ):
        self.id = step_id
        self.name = name
        self.action = action
        self.required_skills = required_skills or []
        self.retry_count = retry_count
        self.timeout_seconds = timeout_seconds
        self.status = "pending"
        self.result: Any = None
        self.error: Optional[str] = None
        self.executed_at: Optional[datetime] = None

class Workflow:
    """Represents a multi-step workflow"""
    
    def __init__(self, workflow_id: str, name: str, description: str = ""):
        self.id = workflow_id
        self.name = name
        self.description = description
        self.steps: List[WorkflowStep] = []
        self.status = WorkflowStatus.CREATED
        self.current_step_index = 0
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.context: Dict[str, Any] = {}
    
    def add_step(self, step: WorkflowStep) -> None:
        """Add a step to the workflow"""
        self.steps.append(step)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "steps_count": len(self.steps),
            "current_step": self.current_step_index,
            "context_keys": list(self.context.keys()),
            "created_at": self.created_at.isoformat()
        }

class WorkflowOrchestrator(PluginInterface):
    """Plugin to orchestrate multi-step workflows"""
    
    PLUGIN_METADATA = PluginMetadata(
        name="workflow-orchestrator",
        version="1.0.0",
        description="Orchestrate multi-step workflows for complex tasks",
        author="Jellyfish OS Team",
        capabilities=[
            "workflow_creation",
            "step_management",
            "workflow_execution",
            "context_passing",
            "error_handling"
        ]
    )
    
    def __init__(self):
        super().__init__()
        self.workflows: Dict[str, Workflow] = {}
        self.execution_history: List[Dict] = []
    
    def create_workflow(
        self,
        name: str,
        description: str = "",
        workflow_id: Optional[str] = None
    ) -> Workflow:
        """Create a new workflow"""
        wf_id = workflow_id or f"WF-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        workflow = Workflow(wf_id, name, description)
        self.workflows[wf_id] = workflow
        return workflow
    
    def add_steps(
        self,
        workflow_id: str,
        steps: List[Dict]
    ) -> bool:
        """Add multiple steps to a workflow"""
        if workflow_id not in self.workflows:
            return False
        
        workflow = self.workflows[workflow_id]
        for i, step_def in enumerate(steps):
            step = WorkflowStep(
                step_id=f"{workflow_id}-STEP-{i+1:02d}",
                name=step_def["name"],
                action=step_def.get("action", lambda ctx: ctx),
                required_skills=step_def.get("skills", []),
                retry_count=step_def.get("retry", 0),
                timeout_seconds=step_def.get("timeout", 300)
            )
            workflow.add_step(step)
        
        return True
    
    def execute_workflow(self, workflow_id: str, initial_context: Dict = None) -> Dict:
        """Execute a workflow"""
        if workflow_id not in self.workflows:
            return {"success": False, "error": "Workflow not found"}
        
        workflow = self.workflows[workflow_id]
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now()
        workflow.context = initial_context or {}
        
        results = []
        try:
            for i, step in enumerate(workflow.steps):
                workflow.current_step_index = i
                step.status = "running"
                step.executed_at = datetime.now()
                
                # Execute step action with context
                result = step.action(workflow.context)
                step.result = result
                step.status = "completed"
                results.append({"step": step.name, "result": result})
                
        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            return {"success": False, "error": str(e), "results": results}
        
        workflow.status = WorkflowStatus.COMPLETED
        workflow.completed_at = datetime.now()
        
        return {
            "success": True,
            "workflow_id": workflow_id,
            "steps_completed": len(results),
            "results": results,
            "final_context": workflow.context
        }
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict]:
        """Get workflow status"""
        if workflow_id not in self.workflows:
            return None
        return self.workflows[workflow_id].to_dict()

# Module-level metadata for package import compatibility
PLUGIN_METADATA = {
    "name": "workflow-orchestrator",
    "version": "1.0.0",
    "description": "Orchestrate multi-step workflows for complex tasks",
    "author": "Jellyfish OS Team",
    "capabilities": [
        "workflow_creation",
        "step_management",
        "workflow_execution",
        "context_passing",
        "error_handling"
    ]
}