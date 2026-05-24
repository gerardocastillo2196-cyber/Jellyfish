"""
Jellyfish OS v6 - Plugins Package
Plugin system for agent extensibility
"""

from .plugin_core import (
    PluginInterface,
    PluginMetadata,
    PluginRegistry,
    PluginManager,
    PLUGIN_SYSTEM_METADATA
)

from .utility import AgentContextPlugin, OutputFormatter, MetricsCollectorPlugin
from .automation import TaskTrackerPlugin, WorkflowOrchestrator
from .integration import SkillLoaderPlugin, APIIntegrationPlugin, KnowledgeBasePlugin

__all__ = [
    # Core
    "PluginInterface",
    "PluginMetadata",
    "PluginRegistry",
    "PluginManager",
    "PLUGIN_SYSTEM_METADATA",
    # Utility
    "AgentContextPlugin",
    "OutputFormatter",
    "MetricsCollectorPlugin",
    # Automation
    "TaskTrackerPlugin",
    "WorkflowOrchestrator",
    # Integration
    "SkillLoaderPlugin",
    "APIIntegrationPlugin",
    "KnowledgeBasePlugin"
]

def get_all_plugin_metadata():
    """Get metadata for all available plugins"""
    return [
        # Utility plugins
        {"name": "agent-context", "version": "1.0.0"},
        {"name": "output-formatter", "version": "1.0.0"},
        {"name": "metrics-collector", "version": "1.0.0"},
        # Automation plugins
        {"name": "task-tracker", "version": "1.0.0"},
        {"name": "workflow-orchestrator", "version": "1.0.0"},
        # Integration plugins
        {"name": "skill-loader", "version": "1.0.0"},
        {"name": "api-integration", "version": "1.0.0"},
        {"name": "knowledge-base", "version": "1.0.0"}
    ]