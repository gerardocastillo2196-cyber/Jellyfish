"""core.agents.base — Clase base para todos los agentes de Jellyfish OS.

Define la interfaz común que todo agente Python debe implementar:
- Metadatos estructurados (name, agency, role, expertise)
- Generación dinámica del system prompt
- Hooks pre_execute / post_execute para intervención programática
- Emparejamiento programático agente↔tarea via matches_task()

Referencia de acoplamiento:
    - core/state.py            → load_agent() instancia la clase y llama get_system_prompt()
    - core/project_orchestrator.py → _load_agent_prompt() consulta el registry
    - core/orchestration/task_runner.py → ejecuta pre_execute() y post_execute()
    - core/orchestration/scrum_master.py → lee .expertise para asignar tareas
"""

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BaseAgent(BaseModel):
    """Clase base para todos los agentes en Jellyfish OS.

    Los agentes Python reemplazan los archivos .md estáticos, proveyendo:
    1. Metadatos tipados (expertise, agency) para asignación inteligente de tareas.
    2. Generación dinámica del system prompt.
    3. Hooks de ciclo de vida (pre/post ejecución) para validación programática.
    4. Emparejamiento programático agente↔tarea sin consumir tokens del LLM.

    Retrocompatibilidad:
        Todos los agentes existentes usan super().__init__(name=..., role=..., ...)
        y Pydantic v2 acepta keyword arguments de forma idéntica al constructor
        clásico de Python. No se requiere modificar ningún archivo de agente.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = ""
    role: str = ""
    agency: str = "default"
    context: str = ""
    tone: str = "Técnico, directo."
    expertise: List[str] = Field(default_factory=list)
    directives: List[str] = Field(default_factory=list)
    rules: List[str] = Field(default_factory=list)

    # ── Emparejamiento Programático ────────────────────────────

    def matches_task(self, task_description: str) -> float:
        """Calcula un puntaje de afinidad agente↔tarea en Python puro.

        Compara las palabras de la descripción de la tarea contra
        las keywords de expertise y directivas del agente.
        Retorna un float entre 0.0 (sin afinidad) y 1.0+.

        Esto reemplaza la necesidad de que el LLM decida qué agente
        es el más adecuado para cada tarea, ahorrando tokens.

        El algoritmo da peso doble a coincidencias directas con
        expertise (alta señal) vs palabras extraídas de directivas
        (señal complementaria). Se normaliza por la cantidad de
        palabras de la tarea cubiertas para premiar al agente que
        cubre más aspectos de la descripción.

        Args:
            task_description: Texto descriptivo de la tarea del sprint.

        Returns:
            Float >= 0.0 indicando la afinidad (mayor = mejor).
        """
        task_words = set(re.findall(r'\w{3,}', task_description.lower()))
        if not task_words:
            return 0.0

        # Expertise: coincidencias directas de alta señal (peso 2x)
        expertise_words = set()
        for kw in self.expertise:
            # Soportar expertise multi-palabra como "base de datos"
            expertise_words.update(re.findall(r'\w{3,}', kw.lower()))

        # Directivas: palabras complementarias (peso 1x)
        directive_words: set[str] = set()
        for d in self.directives:
            directive_words.update(re.findall(r'\w{4,}', d.lower()))
        # Evitar duplicar lo que ya está en expertise
        directive_words -= expertise_words

        # Calcular puntaje ponderado
        expertise_hits = len(task_words & expertise_words)
        directive_hits = len(task_words & directive_words)
        weighted_score = (expertise_hits * 2.0) + (directive_hits * 1.0)

        # Normalizar por cantidad de palabras en la tarea
        return weighted_score / len(task_words)

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
            parts.append(f"{len(self.rules) + 1}. Si recibes un token compacto del 'Idioma Jellyfish' (ej. [DB:CONFIG]), ejecuta la acción asociada directamente sin solicitar explicación ni razonamiento verboso.")
        else:
            parts.append("\n## REGLAS INQUEBRANTABLES")
            parts.append("1. Si recibes un token compacto del 'Idioma Jellyfish' (ej. [DB:CONFIG]), ejecuta la acción asociada directamente sin solicitar explicación ni razonamiento verboso.")

        return "\n".join(parts)

    # ── Suscripción a Eventos (FASE 3 Blackboard) ───────────────

    def subscribe_to_blackboard(self, state) -> None:
        """Suscribe el agente a variables de interés en el Blackboard global."""
        if hasattr(state, "blackboard"):
            for var in self.get_subscribed_variables():
                state.blackboard.subscribe(var, self.handle_blackboard_update)

    def get_subscribed_variables(self) -> List[str]:
        """Define qué variables del Blackboard le interesan a este agente.
        
        Por ejemplo, retornar ['technical_decision'] para reaccionar a ella.
        """
        return []

    def handle_blackboard_update(self, key: str, value: Any) -> None:
        """Callback invocado automáticamente cuando cambia una variable suscrita."""
        pass

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

    def execute_local_microtask_loop(self, state, epic_task: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Ejecuta el bucle de micro-tasking local para agentes desarrolladores/ejecutores.
        
        1. Desglosa la Épica en 3-5 micro-tareas técnicas usando el modelo local (Ollama).
        2. Itera secuencialmente sobre cada micro-tarea localmente.
        3. Acumula y construye el código incrementalmente.
        4. Retorna el resultado consolidado final.
        """
        import json
        import re
        import logging
        from core.llm_engine import _call_llm_silent, resolve_hybrid_agent_routing

        logger = logging.getLogger(f"jellyfish.agent.{self.name}")
        task_desc = epic_task.get("task", "")
        output_file = epic_task.get("output_file", "")
        accumulated_context = context.get("accumulated_context", "")

        provider_name, model_name = resolve_hybrid_agent_routing(state, self.name)

        # 1. Prompt de desglose de micro-tareas
        prompt_breakdown = (
            f"Como agente @{self.name}, tu tarea principal es implementar la Épica: '{task_desc}'.\n"
            f"Archivo de salida esperado: '{output_file}'.\n\n"
            "Desglosa esta Épica en una lista JSON de 3 a 5 micro-tareas técnicas secuenciales y específicas.\n"
            "Formato esperado obligatorio JSON:\n"
            '{\n  "micro_tasks": [\n    "1. Crear estructura base de clases/modelos",\n    "2. Implementar funciones/lógica principal",\n    "3. Añadir validaciones y exportaciones"\n  ]\n}'
        )

        sys_prompt = self.get_system_prompt()
        messages_breakdown = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt_breakdown}
        ]

        raw_breakdown = _call_llm_silent(state, messages_breakdown, agent_name=self.name, provider=provider_name, model=model_name, json_mode=True)
        
        micro_tasks = []
        if raw_breakdown:
            try:
                match = re.search(r'(\{.*\}|\[.*\])', raw_breakdown, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    if isinstance(data, dict):
                        micro_tasks = data.get("micro_tasks", [])
                    elif isinstance(data, list):
                        micro_tasks = data
            except Exception:
                pass

        if not micro_tasks:
            micro_tasks = [
                f"1. Estructura e interfaces base para {output_file}",
                f"2. Lógica de negocio y handlers para {task_desc}",
                f"3. Validaciones, exportaciones e integración en {output_file}"
            ]

        logger.info("Agente @%s desglosó Épica '%s' en %d micro-tareas locales.", self.name, epic_task.get("id"), len(micro_tasks))

        # 2. Bucle iterativo sobre micro-tareas acumulando código
        accumulated_code = ""
        for i, micro in enumerate(micro_tasks, 1):
            logger.info("Agente @%s ejecutando micro-tarea [%d/%d] en Ollama: %s", self.name, i, len(micro_tasks), micro)
            
            user_msg = (
                f"ÉPICA PADRE: {task_desc}\n"
                f"ARCHIVO DE SALIDA: {output_file}\n"
                f"CONTEXTO DEL PROYECTO ACUMULADO:\n{accumulated_context}\n\n"
                f"CÓDIGO GENERADO HASTA AHORA PARA {output_file}:\n```\n{accumulated_code}\n```\n\n"
                f"MICRO-TAREA ACTUAL [{i}/{len(micro_tasks)}]: {micro}\n\n"
                "Genera o actualiza el código completo para resolver esta micro-tarea. Devuelve el código completo actualizado dentro de un bloque ```."
            )
            
            msgs = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg}
            ]
            
            sub_res = _call_llm_silent(state, msgs, agent_name=self.name, provider=provider_name, model=model_name)
            if sub_res and sub_res.strip():
                matches = re.findall(r'```(?:\w+)?\n(.*?)\n```', sub_res, re.DOTALL)
                if matches:
                    accumulated_code = matches[-1].strip()
                else:
                    accumulated_code = sub_res.strip()

        return accumulated_code

    # ── Representación ─────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<Agent @{self.name} agency={self.agency} role={self.role!r}>"

