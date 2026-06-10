"""core.skills.base — Clase base para habilidades de agentes en Jellyfish OS.

Define la interfaz que toda skill Python debe implementar:
- Metadatos (name, agency, keywords) para filtrado selectivo
- Esquema Pydantic opcional (input_schema) para Function Calling tipado
- Generación de instrucciones textuales para inyección al prompt del LLM
- Método execute() para acciones programáticas

Referencia de acoplamiento:
    - core/skills/registry.py → escanea y registra subclases de BaseSkill
    - core/orchestration/task_runner.py → llama matches_task() para filtrado
    - core/state.py → refresh_static_context() inyecta get_instructions()
    - plugins/integration/skill_loader.py → itera el registry para cargar skills
"""

from typing import Any, Dict, List, Optional, Type


class BaseSkill:
    """Clase base para habilidades (skills) de agentes en Jellyfish OS.

    Las skills Python reemplazan los archivos .md estáticos, proveyendo:
    1. Keywords para inyección selectiva (ahorro de tokens).
    2. Esquemas tipados con Pydantic para validación de entrada.
    3. Ejecución programática vía execute().
    """

    # Nombre legible de la skill
    name: str = ""

    # Agencia a la que pertenece (Development, DevOps, Frontend, etc.)
    agency: str = "default"

    # Rol de agente sugerido para esta skill
    role: str = "default"

    # Keywords que activan esta skill cuando aparecen en la descripción de la tarea.
    # Si está vacío, la skill se inyecta siempre (skill genérica de la agencia).
    keywords: List[str] = []

    # Esquema Pydantic de entrada para execute() (opcional).
    # Cuando está definido, permite usar Function Calling nativo
    # de OpenAI/Anthropic en el futuro.
    input_schema: Optional[Type] = None  # Type[BaseModel] cuando pydantic esté disponible

    def get_instructions(self) -> str:
        """Devuelve las directrices de texto que se inyectan en el prompt del LLM.

        Este texto reemplaza al contenido del archivo .md original.
        Debe ser Markdown limpio y conciso.
        """
        raise NotImplementedError(
            f"La skill '{self.__class__.__name__}' debe implementar get_instructions()."
        )

    def execute(self, params=None, **kwargs) -> Any:
        """Ejecuta una acción programática asociada a esta habilidad.

        Este método es OPCIONAL. Las skills que solo proveen instrucciones
        de texto no necesitan implementarlo.

        Args:
            params: Instancia del input_schema si está definido, o None.
            **kwargs: Argumentos adicionales de contexto.

        Returns:
            Resultado de la ejecución (string, dict, etc.)
        """
        pass

    def matches_task(self, task_description: str) -> bool:
        """Determina si esta skill es relevante para la tarea descrita.

        Lógica:
        - Si no tiene keywords → siempre relevante (skill genérica).
        - Si tiene keywords → al menos una debe aparecer en la descripción.

        Args:
            task_description: Texto descriptivo de la tarea del sprint.

        Returns:
            True si la skill debe inyectarse para esta tarea.
        """
        if not self.keywords:
            return True
        task_lower = task_description.lower()
        return any(kw.lower() in task_lower for kw in self.keywords)

    def __repr__(self) -> str:
        return f"<Skill '{self.name}' agency={self.agency} keywords={self.keywords}>"
