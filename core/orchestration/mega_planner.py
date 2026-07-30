"""core/orchestration/mega_planner.py

Sprint 14 — Mega-Agente Planificador: Consolida la cascada de 5-9 llamadas LLM
(Translator → CEO → PO refinamiento → PO backlog → Scrum Master) en exactamente
2 llamadas al LLM:

    Llamada 1: Pregunta única de clarificación (si el input es vago)
    Llamada 2: Generación del JSON maestro de planificación completo

Los artefactos físicos (BACKLOG.json, BACKLOG.md, ARCHITECTURE.md,
SPRINT_BOARD.md, SPRINT_BOARD.json) se generan con Python puro sin consumir
cuota adicional del LLM.

Ahorro de cuota estimado: ~85% (de 5-9 RPM → 1-2 RPM por ejecución de /auto).
"""

import os
import re
import json
import time
import logging
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from core.tui import tui_engine, TaskProgress
from core.state import estimate_tokens
from core.llm_engine import _call_llm_silent

logger = logging.getLogger("jellyfish.orchestration.mega_planner")
console = Console()

# Roles de gestión que NO deben asignarse a tareas de ejecución
_MANAGEMENT_ROLES = {"product_owner", "scrum_master", "template", "researcher"}

# ── Prompt Maestro ─────────────────────────────────────────────────────────────

_MEGA_PLANNER_CLARIFICATION_SYSTEM = """\
Eres el Comité Ejecutivo de Jellyfish OS: Product Owner, Scrum Master, Arquitecto y CEO fusionados en un único agente planificador experto.

Tu misión en ESTE MOMENTO es evaluar la idea del usuario y hacer UNA SOLA pregunta de clarificación que permita completar la arquitectura y la planificación técnica con precisión.

REGLAS ESTRICTAS:
1. Formula EXACTAMENTE UNA pregunta. No más. Sé directo y específico.
2. La pregunta debe apuntar al GAP de información más importante para decidir el stack tecnológico o la arquitectura de datos.
3. Si la idea ya tiene suficiente detalle para planificar sin ambigüedades (stack mencionado, plataforma, tipo de app), responde únicamente con la palabra: READY
4. NO respondas con saludos, introducciones ni explicaciones. Ve directo a la pregunta o a READY.
"""

_MEGA_PLANNER_GENERATION_SYSTEM = """\
Eres el Comité Ejecutivo de Jellyfish OS: Product Owner, Scrum Master, Arquitecto y CEO fusionados en un único agente planificador de élite.

Tu misión es generar en UNA SOLA RESPUESTA el plan técnico maestro completo del proyecto en formato JSON puro, absolutamente correcto y válido.

═══════════════════════════════════════════════════════════════
REGLAS ESTRUCTURALES ABSOLUTAS (violación = salida inválida)
═══════════════════════════════════════════════════════════════

REGLA 1 — MÁXIMO 15 ÉPICAS:
El campo backlog.user_stories debe contener como máximo 15 épicas (macro-historias de alto nivel). PROHIBIDO generar micro-tareas o más de 15 historias.

REGLA 2 — SPRINT 0 OBLIGATORIO Y SIEMPRE PRIMERO:
La primera historia DEBE ser siempre:
  id: "US-000"
  titulo: "Sprint 0: Infraestructura, Gestor de Dependencias y Entorno Base"
  prioridad: "Must-have"
  contenido: gestor de dependencias (package.json / requirements.txt / build.gradle / go.mod), Dockerfile, docker-compose.yml y punto de entrada principal (server.js, main.py, App.tsx, etc.)
  NINGUNA historia de lógica de negocio o UI puede preceder al Sprint 0.

REGLA 3 — SPRINT_BOARD COMPLETO:
Cada épica del backlog DEBE generar al menos UNA tarea en sprint_board.tareas.
Cada tarea DEBE tener su us_id mapeando a la épica correspondiente.

REGLA 4 — JSON PURO:
Tu respuesta debe comenzar directamente con { y terminar con }.
PROHIBIDO: texto narrativo, explicaciones, comentarios, bloques ```json```.

═══════════════════════════════════════════════════════════════
ESQUEMA JSON OBLIGATORIO (todos los campos son requeridos)
═══════════════════════════════════════════════════════════════

{
  "intent_analysis": {
    "clasificacion": "NEW_PROJECT | ADD_FEATURE | FIX_BUG | REFACTOR",
    "dominio": "descripción del dominio de negocio",
    "stack_recomendado": "resumen del stack tecnológico elegido",
    "equipo_requerido": ["backend_dev", "frontend_dev", "devops_engineer", "qa_engineer"]
  },
  "architecture": {
    "resumen": "descripción concisa de la arquitectura elegida",
    "stack": {
      "backend": "tecnología backend (ej: FastAPI + PostgreSQL)",
      "frontend": "tecnología frontend si aplica (ej: React + TypeScript)",
      "mobile": "tecnología móvil si aplica (ej: Kotlin + Jetpack Compose)",
      "infra": "infraestructura (ej: Docker + Nginx)"
    },
    "decisiones": [
      "Decisión arquitectónica 1",
      "Decisión arquitectónica 2"
    ],
    "patrones": [
      "Patrón de diseño aplicado 1"
    ]
  },
  "backlog": {
    "proyecto": "Nombre del proyecto",
    "vision": "Visión general del producto en 2-3 oraciones",
    "user_stories": [
      {
        "id": "US-000",
        "titulo": "Sprint 0: Infraestructura, Gestor de Dependencias y Entorno Base",
        "como": "DevOps Engineer / Arquitecto Principal",
        "quiero": "configurar el gestor de dependencias, contenedorización Docker y punto de entrada del proyecto",
        "para": "garantizar un andamiaje 100% ejecutable, compilable y desplegable antes de codificar lógica de negocio",
        "prioridad": "Must-have",
        "estimacion": "S",
        "criterios_aceptacion": [
          "Dado un proyecto nuevo, cuando se ejecute el Sprint 0, entonces debe existir el gestor de dependencias del stack elegido.",
          "Dado el entorno de contenedores, entonces deben crearse Dockerfile y docker-compose.yml validados y funcionales.",
          "Dado el punto de entrada principal, debe existir el archivo base con imports y scaffolding mínimo."
        ],
        "contexto_rag_necesario": ["Dockerfile", "docker-compose.yml", "package.json"],
        "definition_of_done": [
          "Compilación y sintaxis libre de errores verificada",
          "Gestor de dependencias e infraestructura Docker inicializados"
        ]
      }
    ]
  },
  "sprint_board": {
    "tareas": [
      {
        "id": "T-001",
        "us_id": "US-000",
        "task": "[US-000] Crear Dockerfile, docker-compose.yml y punto de entrada principal",
        "agent": "devops_engineer",
        "estimacion": "S",
        "output_file": "Dockerfile",
        "dependencias": []
      }
    ]
  }
}
"""


class MegaPlannerPhase:
    """Fase de Planificación Unificada del pipeline /auto.

    Reemplaza la cascada: Translator → CEO → PO (refinamiento + backlog) → Scrum Master.
    Flujo de 2 llamadas LLM máximo:
        1. Clarificación (1 pregunta → respuesta del usuario o Enter = fallback automático)
        2. Generación del JSON maestro completo
    Todos los artefactos se escriben localmente con Python puro.
    """

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    # ── Utilidades de Escritura de Artefactos (Python puro, sin cuota) ─────────

    def _build_md_backlog(self, backlog: dict) -> str:
        """Convierte el dict del backlog en Markdown formateado."""
        md = f"# Backlog: {backlog.get('proyecto', 'Proyecto')}\n\n"
        md += f"**Visión:** {backlog.get('vision', '')}\n\n"
        md += "## Historias de Usuario\n\n"
        for us in backlog.get("user_stories", []):
            md += f"### {us.get('id')}: {us.get('titulo')}\n"
            md += f"- **Como:** {us.get('como', '')}\n"
            md += f"- **Quiero:** {us.get('quiero', '')}\n"
            md += f"- **Para:** {us.get('para', '')}\n"
            md += f"- **Prioridad (MoSCoW):** {us.get('prioridad', 'Must-have')}\n"
            md += f"- **Estimación:** {us.get('estimacion', 'M')}\n"
            md += "\n#### Criterios de Aceptación\n"
            for ca in us.get("criterios_aceptacion", []):
                md += f"- {ca}\n"
            md += "\n#### Contexto RAG\n"
            for rag in us.get("contexto_rag_necesario", []):
                md += f"- `{rag}`\n"
            md += "\n#### Definition of Done\n"
            for dod in us.get("definition_of_done", []):
                md += f"- {dod}\n"
            md += "\n---\n\n"
        return md

    def _build_architecture_md(self, plan: dict) -> str:
        """Genera ARCHITECTURE.md desde el dict del plan maestro."""
        arch = plan.get("architecture", {})
        intent = plan.get("intent_analysis", {})
        stack = arch.get("stack", {})
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        md = f"# ARCHITECTURE.md\n\n"
        md += f"*Auto-generado por Jellyfish OS Mega-Agente Planificador — {now}*\n\n"
        md += f"## Dominio y Clasificación\n\n"
        md += f"- **Clasificación:** {intent.get('clasificacion', 'NEW_PROJECT')}\n"
        md += f"- **Dominio:** {intent.get('dominio', '')}\n"
        md += f"- **Stack Recomendado:** {intent.get('stack_recomendado', '')}\n\n"
        md += f"## Resumen Arquitectónico\n\n{arch.get('resumen', '')}\n\n"
        md += "## Stack Tecnológico\n\n"
        md += "| Capa | Tecnología |\n|---|---|\n"
        for layer, tech in stack.items():
            if tech:
                md += f"| {layer.capitalize()} | {tech} |\n"
        md += "\n"
        md += "## Decisiones Arquitectónicas\n\n"
        for dec in arch.get("decisiones", []):
            md += f"- {dec}\n"
        md += "\n## Patrones de Diseño\n\n"
        for pat in arch.get("patrones", []):
            md += f"- {pat}\n"
        md += "\n## Equipo Requerido\n\n"
        for ag in intent.get("equipo_requerido", []):
            md += f"- @{ag}\n"
        return md

    def _build_sprint_board_md(self, sprint_board: dict, board_filename: str = "SPRINT_BOARD.md") -> str:
        """Genera el Markdown del Sprint Board desde el dict del plan maestro."""
        tareas = sprint_board.get("tareas", [])
        md = f"# Sprint Board\n\n"
        md += f"*Auto-generado por Jellyfish OS Mega-Agente Planificador — {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"
        md += "## 📋 POR HACER (TODO)\n\n"
        md += "| ID | Tarea | Asignado | Estimación | Entregable | Dependencias |\n"
        md += "|---|---|---|---|---|---|\n"
        for t in tareas:
            deps = ", ".join(t.get("dependencias", [])) if t.get("dependencias") else "Ninguna"
            agent = t.get("agent", "autodetect").replace("@", "")
            md += (
                f"| {t.get('id', '')} | {t.get('task', '')} | @{agent} "
                f"| {t.get('estimacion', 'M')} | {t.get('output_file', '')} | {deps} |\n"
            )
        md += "\n## ⏳ EN PROCESO (IN PROGRESS)\n\n"
        md += "## ✅ HECHO (DONE)\n\n"

        # Sección de especificaciones técnicas detalladas
        md += "---\n\n### 📋 Especificaciones de Tareas y Criterios de Aceptación Técnicos\n\n"
        for t in tareas:
            md += f"#### {t.get('id', '')}: {t.get('task', '')}\n"
            md += f"- **Agente:** @{t.get('agent', 'autodetect')}\n"
            md += f"- **Entregable:** `{t.get('output_file', '')}`\n"
            deps = t.get("dependencias", [])
            md += f"- **Dependencias:** {', '.join(deps) if deps else 'Ninguna'}\n"
            md += f"- **Historia asociada:** {t.get('us_id', '')}\n\n"
        return md

    def _tasks_as_json_list(self, sprint_board: dict) -> list[dict]:
        """Convierte las tareas del sprint_board al formato que espera el TaskRunner."""
        result = []
        for t in sprint_board.get("tareas", []):
            agent_raw = t.get("agent", "autodetect").strip().lstrip("@")
            deps_raw = t.get("dependencias", [])
            # Normalizar dependencias a lista de strings
            if isinstance(deps_raw, str):
                deps_raw = [d.strip() for d in deps_raw.split(",") if d.strip() and d.strip().lower() != "ninguna"]
            else:
                deps_raw = [str(d) for d in deps_raw if str(d).lower() not in ("", "ninguna")]
            result.append({
                "id": t.get("id", ""),
                "task": t.get("task", ""),
                "agent": agent_raw,
                "estimate": t.get("estimacion", "M"),
                "output_file": t.get("output_file", ""),
                "dependencies": deps_raw,
                "status": "TODO",
            })
        return result

    def _ensure_sprint_0(self, backlog: dict) -> dict:
        """Garantiza determinísticamente que US-000 (Sprint 0) sea la primera historia."""
        stories = backlog.get("user_stories", [])
        has_s0 = any(
            us.get("id") in ("US-000", "US-00") or
            "sprint 0" in str(us.get("titulo", "")).lower() or
            "infraestructura" in str(us.get("titulo", "")).lower()
            for us in stories
        )
        if not has_s0:
            logger.info("MegaPlanner: Inyectando Sprint 0 (US-000) determinísticamente.")
            stories.insert(0, {
                "id": "US-000",
                "titulo": "Sprint 0: Infraestructura, Gestor de Dependencias y Entorno Base",
                "como": "DevOps Engineer / Arquitecto Principal",
                "quiero": "configurar el gestor de dependencias, contenedorización Docker y punto de entrada del proyecto",
                "para": "garantizar un andamiaje 100% ejecutable, compilable y desplegable antes de codificar lógica de negocio",
                "prioridad": "Must-have",
                "estimacion": "S",
                "criterios_aceptacion": [
                    "Dado un proyecto nuevo, cuando se ejecute el Sprint 0, entonces debe existir el gestor de dependencias del stack elegido.",
                    "Dado el entorno de contenedores, entonces deben crearse Dockerfile y docker-compose.yml validados.",
                    "Dado el punto de entrada principal, debe existir el archivo base con imports y scaffolding mínimo.",
                ],
                "contexto_rag_necesario": ["Dockerfile", "docker-compose.yml", "package.json"],
                "definition_of_done": [
                    "Compilación y sintaxis libre de errores verificada",
                    "Gestor de dependencias e infraestructura Docker inicializados",
                ],
            })
        backlog["user_stories"] = stories
        return backlog

    def _enforce_epics_limit(self, backlog: dict) -> dict:
        """Trunca el backlog a máximo 15 épicas preservando siempre US-000."""
        stories = backlog.get("user_stories", [])
        if len(stories) > 15:
            logger.warning("MegaPlanner: Backlog con %d épicas → truncando a 15.", len(stories))
            backlog["user_stories"] = stories[:15]
        return backlog

    def _extract_json(self, text: str) -> dict:
        """Extrae de forma robusta el primer bloque JSON {...} del texto del LLM."""
        if not text:
            raise ValueError("Respuesta vacía del LLM.")
        # Limpiar bloques de código markdown
        cleaned = re.sub(r"```(?:json)?", "", text).strip()
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if not match:
            raise ValueError("No se encontró ningún bloque JSON en la respuesta.")
        json_str = match.group(1).strip()
        # Intentar parseo directo
        try:
            return json.loads(json_str)
        except Exception:
            pass
        # Reparar trailing commas
        try:
            sanitized = re.sub(r",\s*([\}\]])", r"\1", json_str)
            return json.loads(sanitized)
        except Exception:
            pass
        # Último intento — propaga excepción original
        return json.loads(json_str)

    # ── Escritura de Artefactos (sin cuota) ────────────────────────────────────

    def write_artifacts(self, plan: dict) -> bool:
        """Escribe todos los artefactos físicos del proyecto usando Python puro.

        Genera: BACKLOG.json, BACKLOG.md, ARCHITECTURE.md, SPRINT_BOARD.md, SPRINT_BOARD.json
        No realiza ninguna llamada al LLM.
        """
        try:
            backlog = plan.get("backlog", {})
            sprint_board = plan.get("sprint_board", {})
            board_filename = getattr(self.orchestrator, "board_filename", "SPRINT_BOARD.md")

            # 1. BACKLOG.json
            backlog = self._ensure_sprint_0(backlog)
            backlog = self._enforce_epics_limit(backlog)
            self.orchestrator._write_project_file(
                "BACKLOG.json", json.dumps(backlog, indent=2, ensure_ascii=False)
            )
            console.print("       [dim]✓ BACKLOG.json generado[/dim]")

            # 2. BACKLOG.md
            md_backlog = self._build_md_backlog(backlog)
            self.orchestrator._write_project_file("BACKLOG.md", md_backlog)
            console.print("       [dim]✓ BACKLOG.md generado[/dim]")

            # 3. ARCHITECTURE.md
            arch_md = self._build_architecture_md(plan)
            self.orchestrator._write_project_file("ARCHITECTURE.md", arch_md)
            console.print("       [dim]✓ ARCHITECTURE.md generado[/dim]")

            # 4. Sprint Board Markdown + JSON
            # Resolver asignaciones @autodetect programáticamente (0 tokens)
            tasks_list = self._tasks_as_json_list(sprint_board)
            from core.orchestration.scrum_master import _resolve_agent_assignments
            active_agency = getattr(self.orchestrator.state, "active_agency", "")
            resolved = _resolve_agent_assignments(tasks_list, active_agency)
            if resolved:
                console.print(f"       [dim]✓ {resolved} asignación(es) @autodetect resueltas programáticamente[/dim]")
                # Reflejar las resoluciones en sprint_board
                for i, t in enumerate(sprint_board.get("tareas", [])):
                    if i < len(tasks_list):
                        t["agent"] = tasks_list[i]["agent"]

            board_md = self._build_sprint_board_md(sprint_board, board_filename)
            self.orchestrator._write_project_file(board_filename, board_md)
            console.print(f"       [dim]✓ {board_filename} generado[/dim]")

            json_board_filename = board_filename.replace(".md", ".json")
            self.orchestrator._write_project_file(
                json_board_filename, json.dumps(tasks_list, indent=2, ensure_ascii=False)
            )
            console.print(f"       [dim]✓ {json_board_filename} generado[/dim]")

            return True

        except Exception as e:
            logger.error("MegaPlanner: Error escribiendo artefactos: %s", e, exc_info=True)
            console.print(f"[red]❌ Error al escribir artefactos del Mega-Planner: {e}[/red]")
            return False

    # ── Flujo Principal ─────────────────────────────────────────────────────────

    def run(self, user_idea: str) -> bool:
        """Ejecuta la fase de planificación unificada con máximo 2 llamadas al LLM.

        Flujo:
            1. Llamada LLM opcional: pregunta de clarificación → espera input del usuario
               (Enter en blanco = fallback automático a estándares de la industria)
            2. Llamada LLM obligatoria: generación del JSON maestro completo
            3. Python puro: escritura de todos los artefactos físicos (sin cuota)
        """
        console.print("\n━━━ FASE ÚNICA: 🧠 Mega-Agente Planificador ━━━")
        console.print("[dim]   Consolidando planificación en máximo 2 llamadas al LLM...[/dim]")
        t0 = time.perf_counter()

        # ── Llamada 1: Clarificación (opcional) ────────────────────────────────
        clarification_context = user_idea
        clarification_messages = [
            {"role": "system", "content": _MEGA_PLANNER_CLARIFICATION_SYSTEM},
            {"role": "user", "content": f"Idea del proyecto:\n{user_idea}"},
        ]

        with TaskProgress(tui_engine, "mega_planner_clarify", "Mega-Planner: Evaluando requerimientos..."):
            clarification_response = _call_llm_silent(
                self.orchestrator.state,
                clarification_messages,
                agent_name="product_owner",  # Planificador → Gemini (enrutamiento híbrido)
                timeout=120.0,
                temperature=0.3,
            )

        needs_clarification = (
            clarification_response
            and clarification_response.strip().upper() not in ("READY", "READY.", "READY!")
            and len(clarification_response.strip()) > 5
        )

        if needs_clarification:
            # Mostrar la pregunta al usuario
            console.print()
            console.print(Panel(
                f"[bold cyan]{clarification_response.strip()}[/bold cyan]",
                title="[bold yellow]🧠 Mega-Agente Planificador (Clarificación)[/bold yellow]",
                border_style="cyan"
            ))
            console.print(
                "[dim]💡 Presiona Enter en blanco para asumir automáticamente los estándares de la industria.[/dim]"
            )
            console.print()

            try:
                user_clarification = input("✍ Responde (o Enter para omitir) > ").strip()
            except (KeyboardInterrupt, EOFError):
                user_clarification = ""

            if user_clarification:
                clarification_context = (
                    f"IDEA ORIGINAL DEL USUARIO:\n{user_idea}\n\n"
                    f"ACLARACIÓN DEL USUARIO:\n{user_clarification}"
                )
                console.print("[green]✓ Aclaración integrada al contexto de planificación.[/green]")
            else:
                clarification_context = (
                    f"IDEA ORIGINAL DEL USUARIO:\n{user_idea}\n\n"
                    "[FALLBACK AUTOMÁTICO]: El usuario no proporcionó información adicional. "
                    "Asume automáticamente los estándares de la industria más apropiados para este tipo de proyecto "
                    "(ej: React Native/Flutter para móvil, FastAPI/Node.js para backend, "
                    "PostgreSQL para BD, Docker para infraestructura). "
                    "Procede a generar el plan técnico completo sin detenerte."
                )
                console.print("[yellow]⚡ Fallback automático: asumiendo estándares de la industria.[/yellow]")
        else:
            console.print("[green]✓ Requerimientos suficientes. Generando plan maestro directamente.[/green]")

        # ── Llamada 2: Generación del JSON Maestro ─────────────────────────────
        # Cargar capacidades del entorno si existen (sin cuota, solo lectura de archivo)
        env_context = ""
        cap_path = os.path.join(self.orchestrator.project_path, "env_capabilities.json")
        if os.path.isfile(cap_path):
            try:
                with open(cap_path, "r", encoding="utf-8") as f:
                    caps = json.load(f)
                env_lines = [f"  - {k}: {v}" for k, v in caps.items() if v and v != "No disponible"]
                if env_lines:
                    env_context = (
                        "\n\n[CAPACIDADES REALES DEL ENTORNO HOST]\n"
                        "Adapta las versiones y herramientas del stack a estas capacidades instaladas:\n"
                        + "\n".join(env_lines)
                    )
            except Exception:
                pass

        # Cargar catálogo de agentes disponibles para informar al Mega-Agente
        from core.project_orchestrator import _scan_available_agents
        available_agents = _scan_available_agents(self.orchestrator.state)
        agents_catalog = ", ".join(
            f"@{a['name']}" for a in available_agents
            if a.get("name", "").lower() not in _MANAGEMENT_ROLES
        )

        generation_system = (
            _MEGA_PLANNER_GENERATION_SYSTEM
            + f"\n\nAGENTES EJECUTORES DISPONIBLES (usa SOLO estos nombres en sprint_board.tareas.agent):\n{agents_catalog}"
            + env_context
        )

        generation_messages = [
            {"role": "system", "content": generation_system},
            {"role": "user", "content": (
                f"CONTEXTO DEL PROYECTO:\n{clarification_context}\n\n"
                "Genera el JSON maestro completo de planificación siguiendo exactamente el esquema definido."
            )},
        ]

        MAX_GENERATION_RETRIES = 3
        plan = None
        last_error = None
        current_response = None

        for attempt in range(1, MAX_GENERATION_RETRIES + 1):
            task_label = f"Mega-Planner: Generando plan maestro (intento {attempt}/{MAX_GENERATION_RETRIES})..."
            with TaskProgress(tui_engine, f"mega_planner_gen_{attempt}", task_label):
                if attempt == 1:
                    current_response = _call_llm_silent(
                        self.orchestrator.state,
                        generation_messages,
                        agent_name="product_owner",
                        json_mode=True,
                        timeout=300.0,
                        temperature=0.2,
                    )
                else:
                    # Reintentar con corrección de JSON
                    correction_messages = [
                        {"role": "system", "content": generation_system},
                        {"role": "user", "content": (
                            f"CONTEXTO DEL PROYECTO:\n{clarification_context}\n\n"
                            "Genera el JSON maestro completo de planificación siguiendo exactamente el esquema definido."
                        )},
                        {"role": "assistant", "content": current_response or ""},
                        {"role": "user", "content": (
                            f"ERROR DE PARSEO JSON EN EL INTENTO ANTERIOR:\n{last_error}\n\n"
                            "Corrige el JSON. Devuelve ÚNICAMENTE la estructura JSON pura y válida. "
                            "Tu respuesta debe comenzar con { y terminar con }. Sin texto adicional."
                        )},
                    ]
                    current_response = _call_llm_silent(
                        self.orchestrator.state,
                        correction_messages,
                        agent_name="product_owner",
                        json_mode=True,
                        timeout=300.0,
                        temperature=0.1,
                    )

            if not current_response:
                last_error = "El LLM retornó una respuesta vacía."
                logger.warning("MegaPlanner: Intento %d/%d → respuesta vacía.", attempt, MAX_GENERATION_RETRIES)
                continue

            try:
                parsed = self._extract_json(current_response)
                # Validar estructura mínima
                if not isinstance(parsed, dict):
                    raise ValueError("La respuesta JSON no es un objeto dict.")
                if "backlog" not in parsed:
                    raise ValueError("El JSON maestro no contiene el campo 'backlog'.")
                if "user_stories" not in parsed.get("backlog", {}):
                    raise ValueError("El campo 'backlog' no contiene 'user_stories'.")
                if "sprint_board" not in parsed:
                    raise ValueError("El JSON maestro no contiene el campo 'sprint_board'.")
                plan = parsed
                break
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "MegaPlanner: Error parseando JSON en intento %d/%d: %s",
                    attempt, MAX_GENERATION_RETRIES, e
                )
                if attempt < MAX_GENERATION_RETRIES:
                    console.print(
                        f"[yellow]⚠ Intento {attempt}/{MAX_GENERATION_RETRIES}: "
                        f"Error de parseo JSON. Solicitando corrección...[/yellow]"
                    )

        elapsed = time.perf_counter() - t0

        if plan is None:
            console.print(
                f"\n[bold red]🚨 HARD CRASH: Mega-Agente no pudo generar el plan maestro "
                f"tras {MAX_GENERATION_RETRIES} intentos.[/bold red]"
            )
            console.print(f"[red]Último error: {last_error}[/red]")
            self.orchestrator.metrics.append({
                "fase": "🧠 Mega-Planner",
                "detalle": f"HARD CRASH ({(last_error or '')[:40]}...)",
                "tiempo": elapsed,
                "status": "❌",
            })
            # Activar pausa de Sentinel para intervención manual
            self.orchestrator.state.set_pipeline_status("PIPELINE_PAUSED", {
                "task_id": "MEGA-PLAN-001",
                "agent_name": "mega_planner",
                "error_log": (
                    f"HARD CRASH MegaPlanner: Imposible parsear JSON maestro tras "
                    f"{MAX_GENERATION_RETRIES} intentos.\n"
                    f"Salida LLM:\n{current_response}\nError: {last_error}"
                ),
                "task_desc": "Generar plan maestro de planificación JSON",
                "output_file": "BACKLOG.json",
            })
            return False

        # ── Fase Local: Escritura de Artefactos (sin cuota) ────────────────────
        console.print("\n[dim]   📁 Generando artefactos del proyecto (Python puro, sin cuota)...[/dim]")
        if not self.write_artifacts(plan):
            return False

        # ── Mostrar resumen del Backlog al usuario y pedir aprobación ───────────
        backlog = plan.get("backlog", {})
        md_backlog = self._build_md_backlog(backlog)

        stories = backlog.get("user_stories", [])
        unique_agents = set(
            t.get("agent", "").replace("@", "")
            for t in plan.get("sprint_board", {}).get("tareas", [])
        )
        tasks_count = len(plan.get("sprint_board", {}).get("tareas", []))

        console.print(f"\n[bold green]📋 Plan Maestro de {backlog.get('proyecto', 'Proyecto')} generado:[/bold green]")
        console.print(f"   - Épicas: {len(stories)} historias de usuario")
        console.print(f"   - Sprint Board: {tasks_count} tareas técnicas")
        console.print(f"   - Equipo: {', '.join(f'@{a}' for a in sorted(unique_agents) if a)}")
        console.print(f"   - Arquitectura: {plan.get('intent_analysis', {}).get('stack_recomendado', '')}")
        console.print()
        console.print(Markdown(md_backlog))
        console.print("-" * 60)

        try:
            approval = input(
                "\n✍ Escribe comentarios para ajustar el plan, o responde 'y'/'aprobado' para continuar > "
            ).strip()
        except (KeyboardInterrupt, EOFError):
            approval = "y"

        if approval.lower() not in ("y", "aprobado", "aprobar", "ok", "si", "sí", "confirmar", "listo", "ready", ""):
            # El usuario tiene comentarios — incorporarlos pero NO hacemos otra llamada al LLM aquí
            # Se guarda el comentario en DAILY.md para que el Task Runner tenga contexto
            daily_note = (
                f"\n\n## Feedback del Usuario sobre el Plan Maestro\n\n"
                f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"**Comentario:** {approval}\n"
            )
            try:
                daily_path = os.path.join(self.orchestrator.project_path, "DAILY.md")
                with open(daily_path, "a", encoding="utf-8") as f:
                    f.write(daily_note)
                console.print(
                    "[yellow]📝 Comentario registrado en DAILY.md. "
                    "El Task Runner lo tendrá en cuenta durante la ejecución.[/yellow]"
                )
            except Exception:
                pass

        console.print("✓ Plan Maestro aprobado. Iniciando ejecución del sprint.\n")

        # ── Métricas ───────────────────────────────────────────────────────────
        total_tokens = estimate_tokens(current_response or "")
        self.orchestrator.metrics.append({
            "fase": "🧠 Mega-Agente Planificador",
            "detalle": (
                f"~{total_tokens:,} tokens → "
                f"BACKLOG.json + ARCHITECTURE.md + {getattr(self.orchestrator, 'board_filename', 'SPRINT_BOARD.md')}"
            ),
            "tiempo": elapsed,
            "status": "✅",
        })

        return True
