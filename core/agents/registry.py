"""core.agents.registry — Registro dinámico de agentes Python para Jellyfish OS.

Escanea la carpeta agents/ en busca de archivos .py que contengan
subclases de BaseAgent, las instancia y las indexa por nombre.

Referencia de acoplamiento:
    - core/state.py            → scan_agencies() llama AgentRegistry.scan()
    - core/state.py            → load_agent() llama AgentRegistry.get()
    - core/project_orchestrator.py → _scan_available_agents() consulta list_agents()
    - core/orchestration/scrum_master.py → itera list_agents() para match_agent_for_task()
"""

import os
import sys
import importlib
import inspect
import logging
from typing import Dict, Optional, Type

from core.agents.base import BaseAgent

logger = logging.getLogger("jellyfish.agents.registry")


class AgentRegistry:
    """Registro centralizado de agentes Python.

    Singleton de clase (atributos de clase) para que sea accesible
    desde cualquier módulo sin necesidad de pasar instancias.
    """

    _registry: Dict[str, Type[BaseAgent]] = {}
    _scanned: bool = False

    @classmethod
    def scan(cls, agents_dir: str) -> int:
        """Escanea la carpeta agents/ y registra clases que hereden de BaseAgent.

        Args:
            agents_dir: Ruta absoluta a la carpeta agents/.

        Returns:
            Número de agentes Python registrados.
        """
        if not os.path.isdir(agents_dir):
            logger.warning("Directorio de agentes no encontrado: %s", agents_dir)
            return 0

        # Agregar al path si no está
        if agents_dir not in sys.path:
            sys.path.insert(0, agents_dir)

        discovered = 0
        for filename in sorted(os.listdir(agents_dir)):
            if not filename.endswith(".py") or filename.startswith("__"):
                continue

            module_name = filename[:-3]

            # Evitar colisiones de nombre con módulos del sistema
            qualified_name = f"_jellyfish_agent_{module_name}"

            try:
                spec = importlib.util.spec_from_file_location(
                    qualified_name,
                    os.path.join(agents_dir, filename),
                )
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[qualified_name] = module
                spec.loader.exec_module(module)

                # Buscar clases que hereden de BaseAgent
                for attr_name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseAgent) and obj is not BaseAgent:
                        # Instanciar para leer el nombre
                        instance = obj()
                        agent_name = instance.name.lower().strip()
                        if agent_name:
                            cls._registry[agent_name] = obj
                            discovered += 1
                            logger.info(
                                "Agente Python registrado: @%s (%s)",
                                agent_name,
                                obj.__name__,
                            )

            except Exception as e:
                logger.error("Error cargando agente Python '%s': %s", module_name, e)

        cls._scanned = True
        return discovered

    @classmethod
    def get(cls, name: str) -> Optional[BaseAgent]:
        """Retorna una instancia del agente por nombre, o None si no existe."""
        agent_cls = cls._registry.get(name.lower().strip())
        if agent_cls:
            return agent_cls()
        return None

    @classmethod
    def has(cls, name: str) -> bool:
        """Verifica si un agente Python está registrado."""
        return name.lower().strip() in cls._registry

    @classmethod
    def list_agents(cls) -> Dict[str, Type[BaseAgent]]:
        """Retorna el diccionario completo de agentes registrados."""
        return dict(cls._registry)

    @classmethod
    def clear(cls) -> None:
        """Limpia el registro (útil para testing)."""
        cls._registry.clear()
        cls._scanned = False
