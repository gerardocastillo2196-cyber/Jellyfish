"""
Jellyfish OS v6 - Skill Loader Plugin
Loads and manages skill files for AI agents (Refactored to Python Classes)
"""

import os
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

from plugins.plugin_core import PluginInterface, PluginMetadata
from core.skills.registry import SkillRegistry

class SkillMetadata:
    """Metadata for a skill (Backward compatible wrapper)"""
    
    def __init__(self, name: str, agency: str, role: str, file_path: str):
        self.name = name
        self.agency = agency
        self.role = role
        self.file_path = file_path
        self.loaded_at: Optional[datetime] = None
        self.content: Optional[str] = None
        self.usage_count = 0
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "agency": self.agency,
            "role": self.role,
            "file_path": self.file_path,
            "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
            "usage_count": self.usage_count
        }

class SkillLoaderPlugin(PluginInterface):
    """Plugin to load and manage skills for AI agents"""
    
    PLUGIN_METADATA = PluginMetadata(
        name="skill-loader",
        version="1.1.0",
        description="Load and manage skill files for AI agents (Python integrated)",
        author="Jellyfish OS Team",
        capabilities=[
            "skill_discovery",
            "skill_loading",
            "skill_search",
            "agency_filtering"
        ]
    )
    
    def __init__(self, skills_base_path: str = "./skills"):
        self.skills_base_path = Path(skills_base_path)
        self.skills: Dict[str, SkillMetadata] = {}
        self.agency_index: Dict[str, List[str]] = {}
        
    def initialize(self, config: Dict[str, Any]) -> None:
        self.proxy = config.get("proxy")
        if self.proxy:
            project_path = self.proxy.get_active_project()
            if project_path:
                self.skills_base_path = Path(project_path) / "skills"
        self.discover_skills()
        
    def discover_skills(self) -> int:
        """Discover skills using SkillRegistry and register in local legacy dictionary"""
        skills_dir = str(self.skills_base_path.absolute())
        SkillRegistry.scan(skills_dir)
        
        discovered = 0
        self.skills.clear()
        self.agency_index.clear()
        
        for name, skill_cls in SkillRegistry.list_skills().items():
            skill = skill_cls()
            meta = SkillMetadata(
                name=skill.name,
                agency=skill.agency,
                role=skill.role,
                file_path=f"skills/{skill.agency.lower()}/{name}.py"
            )
            self.skills[skill.name] = meta
            
            # Index by agency
            if skill.agency not in self.agency_index:
                self.agency_index[skill.agency] = []
            self.agency_index[skill.agency].append(skill.name)
            discovered += 1
            
        return discovered
        
    def load_skill(self, name: str) -> Optional[SkillMetadata]:
        """Load a skill by name"""
        skill_meta = self.skills.get(name)
        if not skill_meta:
            # Try reloading/scanning first
            self.discover_skills()
            skill_meta = self.skills.get(name)
            if not skill_meta:
                return None
        
        skill = SkillRegistry.get(name)
        if skill:
            skill_meta.content = skill.get_instructions()
            skill_meta.loaded_at = datetime.now()
            skill_meta.usage_count += 1
            return skill_meta
        return None
        
    def get_skill_content(self, name: str) -> Optional[str]:
        """Get skill content by name"""
        skill = self.load_skill(name)
        return skill.content if skill else None
        
    def get_skills_by_agency(self, agency: str) -> List[SkillMetadata]:
        """Get all skills for an agency"""
        skill_names = self.agency_index.get(agency, [])
        return [self.skills[name] for name in skill_names if name in self.skills]
        
    def search_skills(self, query: str) -> List[SkillMetadata]:
        """Search skills by name or content"""
        results = []
        query_lower = query.lower()
        for skill in self.skills.values():
            if query_lower in skill.name.lower():
                results.append(skill)
                continue
            
            # Retrieve instruction content to search
            inst = SkillRegistry.get(skill.name)
            if inst and query_lower in inst.get_instructions().lower():
                results.append(skill)
        return results
        
    def get_skill_catalog(self) -> Dict[str, Any]:
        """Get complete catalog of available skills"""
        catalog = {
            "total_skills": len(self.skills),
            "agencies": {},
            "skills": []
        }
        for agency, skill_names in self.agency_index.items():
            catalog["agencies"][agency] = len(skill_names)
        for skill in self.skills.values():
            catalog["skills"].append(skill.to_dict())
        return catalog

    def load_skills_for_task(self, agent_name: str, task_description: str) -> str:
        """Selective skills injection based on keywords and agency"""
        from core.agents.registry import AgentRegistry
        agent_cls = AgentRegistry.get(agent_name)
        agency = agent_cls.agency if agent_cls else "development" if agent_name == "backend_dev" else agent_name
        
        relevant_skills = SkillRegistry.get_skills_for_task(task_description, agency=agency)
        contents = []
        for skill in relevant_skills:
            contents.append(f"### SKILL: {skill.name}\n{skill.get_instructions()}")
        return "\n\n".join(contents)

    def execute(self, method: str, *args, **kwargs) -> Any:
        if method == "load_skills_for_task":
            return self.load_skills_for_task(*args, **kwargs)
        return super().execute(method, *args, **kwargs)


def load_skills(agent_name: str, agency_dir: str) -> str:
    """Helper function to load skill content matching the agent's agency/role"""
    skills_path = os.path.join(agency_dir, "skills")
    loader = SkillLoaderPlugin(skills_path)
    loader.discover_skills()
    
    contents = []
    # If agent_name is backend_dev or development, load development agency skills
    agency_key = "development" if agent_name == "backend_dev" else agent_name
    
    for skill_name, skill_meta in loader.skills.items():
        if agency_key.lower() in skill_meta.agency.lower() or agency_key.lower() in skill_meta.file_path.lower():
            content = loader.get_skill_content(skill_name)
            if content:
                contents.append(content)
                
    return "\n\n".join(contents)

# Module-level metadata for package import compatibility
PLUGIN_METADATA = {
    "name": "skill-loader",
    "version": "1.0.0",
    "description": "Load and manage skill files for AI agents",
    "author": "Jellyfish OS Team",
    "capabilities": [
        "skill_discovery",
        "skill_loading",
        "skill_search",
        "agency_filtering"
    ]
}