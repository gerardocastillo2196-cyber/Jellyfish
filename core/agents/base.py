"""core.agents.base — Clase base para todos los agentes de Jellyfish OS.

Define la interfaz común que todo agente Python debe implementar:
- Metadatos estructurados (name, agency, role, expertise)
- Generación dinámica del system prompt
- Hooks pre_execute / post_execute para intervención programática

Referencia de acoplamiento:
    - core/state.py            → load_agent() instancia la clase y llama get_system_prompt()
    - core/project_orchestrator.py → _load_agent_prompt() consulta el registry
    - core/orchestration/task_runner.py → ejecuta pre_execute() y post_execute()
    - core/orchestration/scrum_master.py → lee .expertise para asignar tareas
"""

from typing import Any, Dict, List, Optional


class BaseAgent:
    """Clase base para todos los agentes en Jellyfish OS.

    Los agentes Python reemplazan los archivos .md estáticos, proveyendo:
    1. Metadatos tipados (expertise, agency) para asignación inteligente de tareas.
    2. Generación dinámica del system prompt.
    3. Hooks de ciclo de vida (pre/post ejecución) para validación programática.
    """

    def __init__(
        self,
        name: str,
        role: str,
        agency: str = "default",
        context: str = "",
        tone: str = "Técnico, directo.",
        expertise: Optional[List[str]] = None,
        directives: Optional[List[str]] = None,
        rules: Optional[List[str]] = None,
    ):
        self.name = name
        self.role = role
        self.agency = agency
        self.context = context
        self.tone = tone
        self.expertise: List[str] = expertise or []
        self.directives: List[str] = directives or []
        self.rules: List[str] = rules or []

    # ── Generación del Prompt ──────────────────────────────────

    def get_system_prompt(self) -> str:
        """Construye dinámicamente el prompt de sistema del agente.

        El formato replica la estructura Markdown que el orquestador
        ya espera (# AGENTE, **ROL:**, etc.) para mantener compatibilidad.
        """
        parts = [
            f"# AGENTE: @{self.name.upper()}",
            f"**ROL:** {self.role}",
        ]
        if self.context:
            parts.append(f"**CONTEXTO:** {self.context}")
        parts.append(f"**TONO:** {self.tone}")

        if self.expertise:
            parts.append(f"**EXPERTISE:** {', '.join(self.expertise)}")

        if self.directives:
            parts.append("\n## DIRECTIVAS OPERATIVAS")
            for i, d in enumerate(self.directives, 1):
                parts.append(f"{i}. {d}")

        if self.rules:
            parts.append("\n## REGLAS INQUEBRANTABLES")
            for i, r in enumerate(self.rules, 1):
                parts.append(f"{i}. {r}")

        return "\n".join(parts)

    # ── Hooks de Ciclo de Vida ─────────────────────────────────

    def pre_execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> None:
        """Hook ejecutado ANTES de la llamada al LLM.

        Permite al agente:
        - Inyectar datos dinámicos al contexto de la tarea
        - Validar precondiciones
        - Cargar archivos de referencia adicionales

        Args:
            task: Diccionario con id, task (descripción), agent, output_file.
            context: Diccionario con project_path, system_state proxy, etc.
        """
        pass

    def post_execute(self, response: str, context: Dict[str, Any]) -> str:
        """Hook ejecutado DESPUÉS de recibir la respuesta del LLM.

        Permite al agente:
        - Validar sintaxis del código generado (AST, linting)
        - Ejecutar tests automatizados en sandbox
        - Sanear o reformatear la salida

        Args:
            response: Texto completo de la respuesta del LLM.
            context: Diccionario con project_path, output_file, etc.

        Returns:
            La respuesta procesada (puede ser la misma o modificada).
        """
        return response

    # ── Representación ─────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<Agent @{self.name} agency={self.agency} role={self.role!r}>"
