"""
Jellyfish OS v6 - Skill Loader Plugin
Loads and manages skill files for AI agents
"""

import os
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

class SkillMetadata:
    """Metadata for a skill"""
    
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

class SkillLoaderPlugin:
    """Plugin to load and manage skills for AI agents"""
    
    def __init__(self, skills_base_path: str = "./skills"):
        self.skills_base_path = Path(skills_base_path)
        self.skills: Dict[str, SkillMetadata] = {}
        self.agency_index: Dict[str, List[str]] = {}
        self.tag_index: Dict[str, List[str]] = {}
    
    def discover_skills(self) -> int:
        """Discover all skill files in the skills directory"""
        discovered = 0
        
        for md_file in self.skills_base_path.rglob("*.md"):
            try:
                skill = self._parse_skill_file(md_file)
                if skill:
                    self.skills[skill.name] = skill
                    
                    # Index by agency
                    if skill.agency not in self.agency_index:
                        self.agency_index[skill.agency] = []
                    self.agency_index[skill.agency].append(skill.name)
                    
                    discovered += 1
                    
            except Exception as e:
                print(f"Error parsing {md_file}: {e}")
        
        return discovered
    
    def _parse_skill_file(self, file_path: Path) -> Optional[SkillMetadata]:
        """Parse a skill markdown file and extract metadata"""
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            
            name = file_path.stem.replace("_", " ").title()
            agency = "Unknown"
            role = "Unknown"
            
            # Parse frontmatter-like header
            for line in lines[:20]:
                if line.startswith("**Agencia:**"):
                    agency = line.split("**Agencia:**")[1].strip()
                elif line.startswith("**Rol Sugerido:**"):
                    role = line.split("**Rol Sugerido:**")[1].strip()
                elif line.startswith("# "):
                    name = line[2:].strip()
                    break
            
            skill = SkillMetadata(name, agency, role, str(file_path))
            return skill
            
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return None
    
    def load_skill(self, name: str) -> Optional[SkillMetadata]:
        """Load a skill by name"""
        skill = self.skills.get(name)
        if not skill:
            return None
        
        try:
            skill.content = Path(skill.file_path).read_text(encoding="utf-8")
            skill.loaded_at = datetime.now()
            skill.usage_count += 1
            return skill
        except Exception as e:
            print(f"Error loading skill {name}: {e}")
            return None
    
    def get_skill_content(self, name: str) -> Optional[str]:
        """Get skill content by name (loads if needed)"""
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
            # Check name
            if query_lower in skill.name.lower():
                results.append(skill)
                continue
            
            # Check if loaded and search content
            if skill.content and query_lower in skill.content.lower():
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

# Plugin metadata
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

def load_skills(agent_name: str, agency_dir: str) -> str:
    """Helper function to load skill content matching the agent's agency/role"""
    skills_path = os.path.join(agency_dir, "skills")
    loader = SkillLoaderPlugin(skills_path)
    loader.discover_skills()
    
    contents = []
    # If agent_name is backend_dev or development, load development agency skills
    agency_key = "development" if agent_name == "backend_dev" else agent_name
    
    for skill in loader.skills.values():
        if agency_key.lower() in skill.agency.lower() or agency_key.lower() in skill.file_path.lower():
            content = loader.get_skill_content(skill.name)
            if content:
                contents.append(content)
                
    return "\n\n".join(contents)