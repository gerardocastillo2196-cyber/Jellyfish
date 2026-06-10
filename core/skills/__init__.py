"""core.skills — Sistema de habilidades basadas en clases Python para Jellyfish OS.

Provee la clase base BaseSkill y el registro dinámico SkillRegistry.
"""

from core.skills.base import BaseSkill
from core.skills.registry import SkillRegistry

__all__ = ["BaseSkill", "SkillRegistry"]
