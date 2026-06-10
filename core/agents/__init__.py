"""core.agents — Sistema de agentes basados en clases Python para Jellyfish OS.

Provee la clase base BaseAgent, el registro dinámico AgentRegistry
y el sandbox de ejecución para hooks post_execute.
"""

from core.agents.base import BaseAgent
from core.agents.registry import AgentRegistry

__all__ = ["BaseAgent", "AgentRegistry"]
