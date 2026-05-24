"""
Jellyfish OS v6 - Integration Package
Integration and connectivity plugins
"""

from .skill_loader import SkillLoaderPlugin, PLUGIN_METADATA as SKILL_LOADER_METADATA
from .api_integration import APIIntegrationPlugin, APIRouter, PLUGIN_METADATA as API_INTEGRATION_METADATA
from .knowledge_base import KnowledgeBasePlugin, PLUGIN_METADATA as KNOWLEDGE_BASE_METADATA

__all__ = [
    "SkillLoaderPlugin",
    "APIIntegrationPlugin",
    "APIRouter",
    "KnowledgeBasePlugin"
]