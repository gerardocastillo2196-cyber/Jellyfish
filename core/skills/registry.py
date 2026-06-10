"""core.skills.registry — Registro dinámico de skills Python para Jellyfish OS.

Escanea recursivamente la carpeta skills/ (y sus subdirectorios)
en busca de archivos .py que contengan subclases de BaseSkill.

Referencia de acoplamiento:
    - core/state.py → refresh_static_context() usa SkillRegistry para inyectar skills
    - core/orchestration/task_runner.py → filtra skills por keywords vía matches_task()
    - plugins/integration/skill_loader.py → consulta el registry
"""

import os
import sys
import importlib.util
import inspect
import logging
from typing import Dict, List, Optional, Type

from core.skills.base import BaseSkill

logger = logging.getLogger("jellyfish.skills.registry")


class SkillRegistry:
    """Registro centralizado de skills Python.

    Escanea recursivamente subdirectorios (development/, devops/, frontend/, etc.)
    para mantener la misma estructura organizativa que los .md originales.
    """

    _registry: Dict[str, Type[BaseSkill]] = {}
    _scanned: bool = False

    @classmethod
    def scan(cls, skills_dir: str) -> int:
        """Escanea recursivamente skills_dir/ y registra clases BaseSkill.

        Args:
            skills_dir: Ruta absoluta a la carpeta skills/.

        Returns:
            Número de skills Python registradas.
        """
        if not os.path.isdir(skills_dir):
            logger.warning("Directorio de skills no encontrado: %s", skills_dir)
            return 0

        discovered = 0

        for root, _, files in os.walk(skills_dir):
            for filename in sorted(files):
                if not filename.endswith(".py") or filename.startswith("__"):
                    continue

                filepath = os.path.join(root, filename)
                module_name = filename[:-3]

                # Nombre cualificado único para evitar colisiones
                relative = os.path.relpath(filepath, skills_dir)
                qualified = f"_jellyfish_skill_{relative.replace(os.sep, '_')[:-3]}"

                try:
                    spec = importlib.util.spec_from_file_location(
                        qualified, filepath
                    )
                    if spec is None or spec.loader is None:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[qualified] = module
                    spec.loader.exec_module(module)

                    for attr_name, obj in inspect.getmembers(module, inspect.isclass):
                        if (
                            issubclass(obj, BaseSkill)
                            and obj is not BaseSkill
                            and obj.name  # Debe tener nombre definido
                        ):
                            cls._registry[obj.name.lower()] = obj
                            discovered += 1
                            logger.info(
                                "Skill Python registrada: '%s' (%s)",
                                obj.name,
                                obj.__name__,
                            )

                except Exception as e:
                    logger.error(
                        "Error cargando skill Python '%s': %s", filepath, e
                    )

        cls._scanned = True
        return discovered

    @classmethod
    def get(cls, name: str) -> Optional[BaseSkill]:
        """Retorna una instancia de la skill por nombre, o None."""
        skill_cls = cls._registry.get(name.lower().strip())
        if skill_cls:
            return skill_cls()
        return None

    @classmethod
    def has(cls, name: str) -> bool:
        """Verifica si una skill Python está registrada."""
        return name.lower().strip() in cls._registry

    @classmethod
    def list_skills(cls) -> Dict[str, Type[BaseSkill]]:
        """Retorna el diccionario completo de skills registradas."""
        return dict(cls._registry)

    @classmethod
    def get_skills_for_task(
        cls, task_description: str, agency: str = ""
    ) -> List[BaseSkill]:
        """Retorna las instancias de skills relevantes para una tarea.

        Aplica filtrado por:
        1. Agencia del agente (si se provee).
        2. Keywords de la skill vs descripción de la tarea.

        Args:
            task_description: Texto descriptivo de la tarea.
            agency: Agencia del agente asignado (opcional).

        Returns:
            Lista de instancias de BaseSkill relevantes.
        """
        relevant = []
        for skill_cls in cls._registry.values():
            skill = skill_cls()
            # Filtrar por agencia si se especifica
            if agency and agency.lower() not in skill.agency.lower():
                continue
            # Filtrar por keywords
            if skill.matches_task(task_description):
                relevant.append(skill)
        return relevant

    @classmethod
    def clear(cls) -> None:
        """Limpia el registro (útil para testing)."""
        cls._registry.clear()
        cls._scanned = False
