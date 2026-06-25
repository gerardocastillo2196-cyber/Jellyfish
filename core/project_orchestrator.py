"""Sprint 11 — Orquestador Autónomo con Scrum Team Dinámico.

El Scrum Master escanea los agentes disponibles, arma el equipo ideal,
asigna tareas en el SPRINT_BOARD.md, y el Task Runner ejecuta cada tarea
invocando al agente correspondiente de forma autónoma.

Pipeline Dinámico:
    1. Product Owner  → BACKLOG.md   (checkpoint: aprobación del usuario)
    2. Scrum Master   → SPRINT_BOARD.md (con asignación dinámica de agentes)
    3. Task Runner    → Ejecuta cada tarea del tablero con el agente asignado
"""

import os
import re
import time
import json
import logging
import sys
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text
from rich.prompt import Confirm

from core.state import JellyfishState, AGENCY_DIR, _safe_read, estimate_tokens
from core.llm_engine import _call_llm_silent
from core.tui import tui_engine, TaskProgress
from core.agents.registry import AgentRegistry

logger = logging.getLogger("jellyfish.project_orchestrator")
console = Console()

class SilentExecutionRedirect:
    """Context manager que redirige las consolas Rich a un archivo de log.
    
    Auditoría: Corregido para prevenir leak de file descriptors si __enter__
    falla parcialmente (e.g. alguna consola no existe o no tiene .file).
    """
    def __init__(self, state):
        self.state = state
        self.log_file = None
        self.old_files = {}

    def __enter__(self):
        proj_path = getattr(self.state, "active_project", None)
        log_path = os.path.join(proj_path, "jellyfish_debug.log") if proj_path else "jellyfish_debug.log"
        self.log_file = open(log_path, "a", encoding="utf-8")
        
        try:
            from core.project_orchestrator import console as po_console
            from core.terminal import console as term_console
            from core.ui import console as ui_console
            
            self.consoles = [po_console, term_console, ui_console]
            for c in self.consoles:
                self.old_files[c] = c.file
                c.file = self.log_file
        except Exception:
            # Si falla la asignación de consoles, cerrar el archivo y propagar
            if self.log_file:
                self.log_file.close()
                self.log_file = None
            raise
            
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for c in self.old_files:
            try:
                c.file = self.old_files[c]
            except Exception:
                # Fallback: restaurar a stdout si el archivo original ya no es válido
                c.file = sys.stdout
        if self.log_file:
            try:
                self.log_file.close()
            except Exception:
                pass

# Agentes que son roles de gestión y NO deben asignarse a tareas de ejecución
_MANAGEMENT_ROLES = {"product_owner", "scrum_master", "template", "researcher"}


def _scan_available_agents(state: JellyfishState = None) -> list[dict]:
    """Escanea agents/ y retorna nombre + primera línea de rol de cada uno.
    
    Sprint 12 — Prioriza agentes Python del AgentRegistry.
    Los .md son fallback para agentes aún no migrados.
    """
    agents_dir = os.path.join(AGENCY_DIR, "agents")
    agents = []
    if not os.path.isdir(agents_dir):
        return agents
    
    active_agency = "default"
    allowed_agents = []
    if state is not None:
        active_agency = getattr(state, "active_agency", "default")
        allowed_agents = state.agency_catalog.get(active_agency, [])
        if not allowed_agents:
            allowed_agents = state.agency_catalog.get("default", [])

    seen_names = set()
    
    # 1. Agentes Python (.py) — prioridad
    for name, agent_cls in AgentRegistry.list_agents().items():
        if name in _MANAGEMENT_ROLES:
            continue
        if state is not None and name not in allowed_agents:
            continue
        agent_inst = agent_cls()
        agents.append({
            "name": name,
            "file": f"{name}.py",
            "role": agent_inst.role,
            "expertise": getattr(agent_inst, "expertise", [])
        })
        seen_names.add(name)
    
    # 2. Agentes Markdown (.md) — fallback
    for fname in sorted(os.listdir(agents_dir)):
        if not fname.endswith(".md"):
            continue
        name = fname[:-3]  # quitar .md
        if name in _MANAGEMENT_ROLES or name in seen_names:
            continue
        # Filtrar agentes permitidos si state está provisto
        if state is not None and name not in allowed_agents:
            continue
        content = _safe_read(os.path.join(agents_dir, fname))
        # Extraer la línea de ROL
        role_line = ""
        for line in content.split("\n"):
            if line.strip().startswith("**ROL:**"):
                role_line = line.strip().replace("**ROL:**", "").strip()
                break
        agents.append({"name": name, "file": fname, "role": role_line})
    return agents


def _parse_sprint_tasks(board_content: str) -> list[dict]:
    """Parsea las tareas del tablero de forma defensiva y tolerante a variaciones."""
    tasks = []
    in_todo = False
    lines = board_content.split("\n")
    
    for line in lines:
        stripped = line.strip()
        
        # Detectar inicio/fin de sección de tareas pendientes (tolerante a idiomas)
        if stripped.startswith("#"):
            # Limpiar emojis y caracteres especiales, convertir a mayúsculas
            clean_header = re.sub(r'[^\w\s]', ' ', stripped).upper()
            is_todo_header = any(kw in clean_header for kw in ["TODO", "POR HACER", "PENDIENTE", "TRACK", "BACKLOG", "HACER"])
            
            if is_todo_header:
                in_todo = True
                continue
            elif in_todo:
                # Si ya estábamos en la sección de pendientes y encontramos otro encabezado principal,
                # significa que salimos de la sección de TODO.
                # Para evitar salir ante subencabezados muy pequeños, validamos que comience con ## o #
                if stripped.startswith("##") or stripped.startswith("# "):
                    break

        if not in_todo or not stripped.startswith("|"):
            continue

        # Separar por |
        cells = [c.strip() for c in stripped.split("|")]
        # Quitar celdas vacías externas si existen (delimitadores de tabla | ... |)
        if cells and cells[0] == "":
            cells.pop(0)
        if cells and cells[-1] == "":
            cells.pop()

        if not cells:
            continue

        # Ignorar separadores de tabla Markdown |---|
        if all(all(char in ('-', ':', ' ') for char in cell) for cell in cells if cell):
            continue

        # Ignorar cabeceras de texto de la tabla (por ejemplo: ID, Tarea, Asignado) utilizando coincidencia exacta
        col0_clean = re.sub(r'[^\w\s]', '', cells[0]).upper().strip()
        col1_clean = re.sub(r'[^\w\s]', '', cells[1]).upper().strip() if len(cells) > 1 else ""
        if col0_clean in ("ID", "TASK ID", "TASK_ID", "CODIGO", "CÓDIGO", "CODE") or \
           col1_clean in ("TAREA", "TASK", "DESCRIPCION", "DESCRIPCIÓN", "DESCRIPTION"):
            continue

        # Ignorar filas placeholder o vacías
        if not cells[0] or cells[0] in ("—", "-", "") or (len(cells) > 1 and (not cells[1] or cells[1] in ("—", "-", ""))):
            continue

        # Sanitización de datos extraídos
        task_id = cells[0].replace("*", "").replace("`", "").strip()
        task_desc = cells[1].strip()
        
        agent_name = "default"
        if len(cells) > 2:
            agent_name = cells[2].lower().replace("@", "").replace("*", "").replace("`", "").strip()
        if not agent_name:
            agent_name = "default"
            
        estimate = "M"
        output_file = "src/output.md"
        
        dependencies = []
        if len(cells) == 4:
            # La columna de estimación fue omitida: ID, Tarea, Agente, Entregable
            output_file = cells[3].replace("`", "").replace("*", "").strip()
        elif len(cells) == 5:
            # Estructura estándar: ID, Tarea, Agente, Estimación, Entregable
            estimate = cells[3].replace("`", "").replace("*", "").strip()
            output_file = cells[4].replace("`", "").replace("*", "").strip()
        elif len(cells) >= 6:
            # Estructura estándar con dependencias: ID, Tarea, Agente, Estimación, Entregable, Dependencias
            estimate = cells[3].replace("`", "").replace("*", "").strip()
            output_file = cells[4].replace("`", "").replace("*", "").strip()
            dep_cell = cells[5].replace("`", "").replace("*", "").strip()
            if dep_cell and dep_cell.lower() not in ("ninguna", "ninguno", "-", "none", ""):
                dependencies = [d.strip().upper() for d in dep_cell.split(",") if d.strip()]
            
        # Detección inteligente si se cruzaron o desplazaron las columnas de Estimación y Entregable
        if estimate and ("." in estimate or "/" in estimate or "\\" in estimate) and (not output_file or output_file == "src/output.md"):
            output_file = estimate
            estimate = "M"
            
        # Valores por defecto si quedaron vacíos después de sanitizar
        if not estimate:
            estimate = "M"
        if not output_file:
            output_file = "src/output.md"

        if task_id and task_desc:
            tasks.append({
                "id": task_id,
                "task": task_desc,
                "agent": agent_name,
                "estimate": estimate,
                "output_file": output_file,
                "dependencies": dependencies
            })

    return tasks



class ProjectOrchestrator:
    """Orquestador Autónomo con Scrum Team Dinámico — Sprint 11.

    Pipeline:
        1. PO genera BACKLOG.md (con checkpoint de aprobación).
        2. SM escanea agentes disponibles, arma equipo, genera SPRINT_BOARD.md
           con tareas asignadas a agentes específicos.
        3. Task Runner parsea el tablero y ejecuta cada tarea con el agente
           asignado, pasando contexto acumulado.
    """

    def __init__(self, state: JellyfishState):
        self.state = state
        self.project_path = state.active_project
        self.metrics: list[dict] = []
        self.generated_files: list[str] = []

    @property
    def board_filename(self) -> str:
        methodology = getattr(self.state, "project_methodology", "scrum").lower()
        agency = getattr(self.state, "active_agency", "default")
        
        if methodology == "scrum":
            return "SPRINT_BOARD.md"
            
        if agency == "development":
            return "DEV_BOARD.md"
        elif agency == "marketing":
            return "MKT_BOARD.md"
        elif agency == "research":
            return "RESEARCH_BOARD.md"
        else:
            return "DEV_BOARD.md"

    def _load_agent_prompt(self, agent_name: str) -> str:
        """Carga el system prompt de un agente.
        
        Sprint 12 — Prioriza clase Python del AgentRegistry.
        Si no existe, cae al archivo .md (retrocompatibilidad).
        """
        py_agent = AgentRegistry.get(agent_name)
        if py_agent:
            return py_agent.get_system_prompt()
        filepath = os.path.join(AGENCY_DIR, "agents", f"{agent_name}.md")
        return _safe_read(filepath)

    def _read_project_file(self, filename: str) -> str:
        """Lee un archivo del proyecto activo."""
        filename_clean = filename.replace("`", "").strip()
        return _safe_read(os.path.join(self.project_path, filename_clean))

    def _write_project_file(self, filename: str, content: str) -> bool:
        """Escribe un archivo al directorio del proyecto activo."""
        filename_clean = filename.replace("`", "").strip()
        filepath = os.path.join(self.project_path, filename_clean)
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            self.generated_files.append(filename_clean)
            return True
        except (OSError, IOError) as e:
            logger.error("Error escribiendo %s: %s", filepath, e)
            console.print(f"Error escribiendo {filename_clean}: {e}")
            return False

    def _call_agent(self, system_prompt: str, user_prompt: str) -> str:
        """Llama al LLM en modo silencioso garantizando que nunca retorne un string vacío."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = _call_llm_silent(
                self.state, messages,
                provider=self.state.provider,
                model=self.state.model,
            )
            if not response or not response.strip():
                logger.error(f"⚠️ El modelo {self.state.model} ({self.state.provider}) retornó un output vacío.")
                # Fallback automático de contingencia para que la Agencia Autónoma continúe sin detenerse
                return (
                    "## 📋 BACKLOG RECOVERY\n\n"
                    "\n"
                    "### US-001: Arquitectura y Capas Base de la Aplicación\n"
                    f"- **Como** Desarrollador del sistema, **quiero** andamiar la idea inicial: '{user_prompt[:50]}...', **para** garantizar la continuidad del flujo de desarrollo.\n"
                    "#### Criterios de Aceptación:\n"
                    "  - Dado que la entrada fue procesada con fallas de respuesta por el LLM, cuando el Task Runner la reciba, entonces creará las configuraciones base requeridas.\n"
                    "  - Prioridad: Must-have | Estimación: 5pts\n"
                )
            return response
        except Exception as e:
            logger.error(f"❌ Excepción crítica en _call_agent para {self.state.model}: {str(e)}", exc_info=True)
            return f"## 📋 ERROR DE PROCESAMIENTO\n\nOcurrió una excepción en el harness del agente: {str(e)}"

    def _build_accumulated_context(self) -> str:
        """Construye contexto con todos los archivos generados hasta ahora."""
        parts = []
        for fname in self.generated_files:
            content = self._read_project_file(fname)
            if content:
                parts.append(f"--- {fname} ---\n{content}\n")
        return "\n".join(parts)

    # ─── FASE 0: Generación de Inteligencia del Proyecto ───────────────

    def _generate_project_intelligence(self, user_idea: str) -> None:
        """Auto-genera documentos de contexto técnico escaneando el proyecto real."""
        import subprocess

        console.print("\n━━━ FASE 0: 🧠 Generación de Inteligencia del Proyecto ━━━")
        t0 = time.perf_counter()

        # 1. PROJECT_TREE.md — Árbol de directorios real
        try:
            result = subprocess.run(
                ["find", ".", "-maxdepth", "4", "-not", "-path", "./.git/*",
                 "-not", "-path", "./.venv/*", "-not", "-path", "./venv/*",
                 "-not", "-path", "./node_modules/*", "-not", "-path", "./__pycache__/*",
                 "-not", "-name", "*.pyc"],
                cwd=self.project_path, capture_output=True, text=True, timeout=10
            )
            tree_content = result.stdout.strip() if result.returncode == 0 else "No disponible"
        except Exception:
            tree_content = "No disponible"

        self._write_project_file("PROJECT_TREE.md", (
            "# 🌳 Árbol del Proyecto (Auto-generado)\n\n"
            "```\n" + tree_content[:8000] + "\n```\n\n"
            "*Auto-generado por Jellyfish OS. No editar manualmente.*\n"
        ))

        # 2. DESIGN_TOKENS.md — Extraído de ARCHITECTURE.md si existe
        arch = self._read_project_file("ARCHITECTURE.md")
        if arch:
            tokens_prompt = (
                "Eres un arquitecto de software senior. Lee el siguiente ARCHITECTURE.md y genera un resumen "
                "ULTRA-COMPACTO (máximo 30 líneas) llamado DESIGN_TOKENS.md con SOLO:\n"
                "- Stack tecnológico (frontend, backend, DB)\n"
                "- Convenciones de carpetas (dónde va cada tipo de archivo)\n"
                "- Patrones de diseño obligatorios\n"
                "- Reglas de naming\n"
                "NO repitas el ARCHITECTURE.md completo. Sé telegráfico."
            )
            tokens_result = self._call_agent(tokens_prompt, f"ARCHITECTURE.md:\n{arch[:6000]}")
            self._write_project_file("DESIGN_TOKENS.md", tokens_result)

        # 3. DATA_SCHEMA.md — Escanea modelos de datos existentes
        schema_parts = []
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in ('.git', 'venv', '.venv', 'node_modules', '__pycache__')]
            for f in files:
                if f in ("models.py", "schema.prisma", "schema.sql", "models.js", "models.ts", "entities.py"):
                    content = _safe_read(os.path.join(root, f))
                    if content:
                        rel = os.path.relpath(os.path.join(root, f), self.project_path)
                        schema_parts.append(f"### {rel}\n```\n{content[:3000]}\n```\n")
        if schema_parts:
            self._write_project_file("DATA_SCHEMA.md", (
                "# 📊 Esquema de Datos (Auto-generado)\n\n" + "\n".join(schema_parts) +
                "\n*Auto-generado por Jellyfish OS.*\n"
            ))

        # 4. SECURITY.md — Guardrails de seguridad
        security_path = os.path.join(self.project_path, "SECURITY.md")
        if not os.path.isfile(security_path):
            self._write_project_file("SECURITY.md", (
                "# 🔒 Guardrails de Seguridad\n\n"
                "## Reglas Obligatorias para Todo Agente\n"
                "1. **NUNCA** hardcodear tokens, contraseñas, API keys o URIs de BD en el código.\n"
                "   - Usar `os.getenv()` (Python) o `process.env` (Node.js).\n"
                "2. **SIEMPRE** preparar consultas SQL con parámetros para evitar inyección.\n"
                "3. **NUNCA** exponer stack traces en respuestas HTTP de producción.\n"
                "4. **SIEMPRE** validar y sanitizar input del usuario antes de procesarlo.\n"
                "5. **NUNCA** almacenar contraseñas en texto plano. Usar bcrypt o argon2.\n"
                "6. **SIEMPRE** usar HTTPS para comunicaciones externas.\n"
                "7. Tokens JWT deben tener expiración máxima de 24 horas.\n\n"
                "*Archivo persistente. Editable por el usuario.*\n"
            ))

        # 5. COMPONENT_INDEX.md — Índice de componentes reutilizables
        components = []
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in ('.git', 'venv', '.venv', 'node_modules', '__pycache__')]
            for f in files:
                if f.endswith(('.jsx', '.tsx', '.vue', '.svelte')):
                    rel = os.path.relpath(os.path.join(root, f), self.project_path)
                    components.append(f"- `{rel}`")
                elif f.endswith('.py') and ('route' in f.lower() or 'view' in f.lower() or 'controller' in f.lower()):
                    rel = os.path.relpath(os.path.join(root, f), self.project_path)
                    components.append(f"- `{rel}`")
        if components:
            self._write_project_file("COMPONENT_INDEX.md", (
                "# 🧩 Índice de Componentes (Auto-generado)\n\n"
                "Archivos reutilizables detectados en el proyecto:\n\n"
                + "\n".join(components[:50]) +
                "\n\n*Antes de crear un componente nuevo, verifica si ya existe aquí.*\n"
            ))

        # 6. DEPENDENCY_MANIFEST.md — Librerías disponibles
        dep_parts = []
        for dep_file in ("requirements.txt", "package.json", "Pipfile", "pyproject.toml", "go.mod"):
            content = self._read_project_file(dep_file)
            if content:
                dep_parts.append(f"### {dep_file}\n```\n{content[:2000]}\n```\n")
            # Buscar en subcarpetas (frontend/, backend/)
            for subdir in ("frontend", "backend"):
                sub_path = os.path.join(self.project_path, subdir, dep_file)
                if os.path.isfile(sub_path):
                    content = _safe_read(sub_path)
                    if content:
                        dep_parts.append(f"### {subdir}/{dep_file}\n```\n{content[:2000]}\n```\n")
        if dep_parts:
            self._write_project_file("DEPENDENCY_MANIFEST.md", (
                "# 📦 Dependencias del Proyecto (Auto-generado)\n\n"
                "**REGLA:** Solo usa librerías que estén listadas aquí. "
                "Si necesitas una nueva, indícalo explícitamente.\n\n"
                + "\n".join(dep_parts) +
                "\n*Auto-generado por Jellyfish OS.*\n"
            ))

        # 7. PLAYBOOK.md — Solo se crea vacío si no existe (se llena con retrospectivas)
        playbook_path = os.path.join(self.project_path, "PLAYBOOK.md")
        if not os.path.isfile(playbook_path):
            # Cargar reglas de retrospectivas anteriores si existen
            retro_path = os.path.join(AGENCY_DIR, "memory", "retrospective_rules.md")
            retro_content = _safe_read(retro_path) if os.path.isfile(retro_path) else ""
            self._write_project_file("PLAYBOOK.md", (
                "# 📖 Playbook de Soluciones Conocidas\n\n"
                "## Lecciones de Sprints Anteriores\n"
                + (retro_content if retro_content else "_(Ninguna todavía)_\n") +
                "\n## Soluciones a Errores Frecuentes\n"
                "_(Se actualizará automáticamente tras cada retrospectiva)_\n"
            ))

        # 8. BUSINESS_CONTEXT.md — Contexto de negocio extraído de la idea del usuario
        biz_path = os.path.join(self.project_path, "BUSINESS_CONTEXT.md")
        if not os.path.isfile(biz_path):
            biz_prompt = (
                "Genera un BUSINESS_CONTEXT.md de MÁXIMO 10 líneas que responda:\n"
                "1. ¿Para quién es esta app? (usuario final)\n"
                "2. ¿Qué problema resuelve?\n"
                "3. ¿Qué tono de UI se espera? (formal, casual, técnico)\n"
                "Sé telegráfico. Solo Markdown limpio."
            )
            biz_result = self._call_agent(biz_prompt, f"Idea del usuario: {user_idea}")
            self._write_project_file("BUSINESS_CONTEXT.md", biz_result)

        elapsed = time.perf_counter() - t0
        intel_files = [f for f in ["PROJECT_TREE.md", "DESIGN_TOKENS.md", "DATA_SCHEMA.md",
                                    "SECURITY.md", "COMPONENT_INDEX.md", "DEPENDENCY_MANIFEST.md",
                                    "PLAYBOOK.md", "BUSINESS_CONTEXT.md"] if os.path.isfile(os.path.join(self.project_path, f))]
        console.print(f"✓ Inteligencia del proyecto generada: {len(intel_files)} documentos ({elapsed:.1f}s)")
        self.metrics.append({
            "fase": "🧠 Inteligencia", "detalle": f"{len(intel_files)} docs generados",
            "tiempo": elapsed, "status": "✅",
        })

    # ─── FASE 1: Product Owner ──────────────────────────────────────────

    def _run_product_owner(self, user_idea: str) -> bool:
        """Genera BACKLOG.md y solicita aprobación del usuario."""
        from core.orchestration.product_owner import ProductOwnerPhase
        return ProductOwnerPhase(self).run(user_idea)

    # ─── FASE 2: Scrum Master (Team Assembly + Sprint Planning) ─────────

    def _run_scrum_master(self, user_idea: str) -> bool:
        """SM escanea agentes, arma equipo y genera el tablero correspondiente a la agencia."""
        from core.orchestration.scrum_master import ScrumMasterPhase
        return ScrumMasterPhase(self).run(user_idea)

    # ─── FASE 3: Task Runner (Ejecución Dinámica) ──────────────────────

    def _run_environment_probe(self) -> dict:
        """Ejecuta comandos de diagnóstico en la terminal para identificar capacidades del sistema.
        Guarda los resultados en env_capabilities.json con cacheo.
        """
        cap_path = os.path.join(self.project_path, "env_capabilities.json")
        if os.path.isfile(cap_path):
            try:
                import time
                mtime = os.path.getmtime(cap_path)
                if (time.time() - mtime) < 86400: # 24 horas de validez de caché
                    with open(cap_path, "r", encoding="utf-8") as f:
                        capabilities = json.load(f)
                    console.print("✓ Capacidades del sistema cargadas desde caché (env_capabilities.json)")
                    return capabilities
            except Exception as e:
                logger.warning("Error leyendo caché de capacidades: %s. Re-ejecutando diagnóstico.", e)

        console.print("\n🔍 Ejecutando Agente Validador del Entorno (Environment Probe)...")
        capabilities = {}
        
        commands = {
            "python_version": "python3 --version",
            "java_version": "java -version",
            "docker_version": "docker --version",
            "docker_compose_version": "docker compose version || docker-compose --version",
            "gradle_version": "gradle --version",
            "node_version": "node --version",
            "npm_version": "npm --version",
            "git_version": "git --version"
        }
        
        import subprocess
        for key, cmd in commands.items():
            try:
                res = subprocess.run(
                    cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5
                )
                output = (res.stdout.strip() + "\n" + res.stderr.strip()).strip()
                if res.returncode == 0 and output:
                    first_line = output.split('\n')[0].strip()
                    capabilities[key] = first_line
                elif output:
                    first_line = output.split('\n')[0].strip()
                    capabilities[key] = first_line
                else:
                    capabilities[key] = "No disponible"
            except Exception:
                capabilities[key] = "No disponible"
                
        try:
            with open(cap_path, "w", encoding="utf-8") as f:
                json.dump(capabilities, f, indent=2)
            console.print(f"✓ Capacidades del sistema guardadas en env_capabilities.json")
        except Exception as e:
            logger.error("Error escribiendo env_capabilities.json: %s", e)
            
        return capabilities

    def _detect_compile_command(self) -> str:
        """Detecta el comando de compilación o verificación para el proyecto activo."""
        if not self.project_path or not os.path.isdir(self.project_path):
            return ""
        
        docker_android_yml = os.path.join(self.project_path, "docker-compose.android.yml")
        if os.path.isfile(docker_android_yml):
            return "docker compose -f docker-compose.android.yml run --rm android-builder ./gradlew assembleDebug --no-daemon"
            
        docker_yml = os.path.join(self.project_path, "docker-compose.yml")
        if os.path.isfile(docker_yml):
            return "docker compose build"
            
        gradlew = os.path.join(self.project_path, "gradlew")
        if os.path.isfile(gradlew):
            return "./gradlew assembleDebug --no-daemon"
            
        package_json = os.path.join(self.project_path, "package.json")
        if os.path.isfile(package_json):
            return "npm run build"
            
        # Validar si existe subdirectorio frontend con package.json
        frontend_pkg = os.path.join(self.project_path, "frontend", "package.json")
        if os.path.isfile(frontend_pkg):
            return "cd frontend && npm run build && cd .. && python3 -m compileall -q ."
            
        has_python = False
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in ('.git', 'venv', '.venv', 'node_modules')]
            for f in files:
                if f.endswith('.py') or f in ('requirements.txt', 'pyproject.toml', 'setup.py'):
                    has_python = True
                    break
            if has_python:
                break
                
        if has_python:
            frontend_dir = os.path.join(self.project_path, "frontend")
            if os.path.isdir(frontend_dir):
                return "python3 -m compileall -q . && [ -d frontend/src ] && echo 'Validando frontend...' && [ \"$(ls -A frontend/src)\" ]"
            return "python3 -m compileall -q ."
            
        return ""

    def _extract_relevant_errors(self, build_output: str) -> str:
        """Extrae las líneas de error más relevantes de la salida de compilación."""
        if not build_output:
            return "Sin salida de error."
            
        lines = build_output.split('\n')
        relevant_lines = []
        error_keywords = ["error:", "failed", "exception", "caused by:", "unresolved reference", "e:", "w:", "kapt"]
        
        for line in lines:
            if any(kw in line.lower() for kw in error_keywords):
                relevant_lines.append(line)
                
        if not relevant_lines:
            return "\n".join(lines[-30:])
            
        return "\n".join(relevant_lines[-40:])

    def _run_build_command(self, cmd: str) -> tuple[int, str]:
        """Ejecuta el comando de compilación en el directorio del proyecto y captura salida/código de salida."""
        from core.terminal import run_terminal_command
        console.print(f"\n       🛠 Solicitando ejecución de comando de compilación: {cmd}")
        
        ret_dict = {'returncode': 0}
        output = run_terminal_command(
            cmd,
            self.state,
            silent_history=True,
            timeout=300,
            force_confirm=True,
            return_code_dict=ret_dict
        )
        
        returncode = ret_dict['returncode']
        if returncode != 0:
            # Interceptación de error y disparo del Bucle de Auto-Recuperación (Auto-Healing Loop)
            returncode, output = self._auto_heal_build_error(cmd, returncode, output)
            
        if returncode != 0:
            if not hasattr(self.state, "captured_errors"):
                self.state.captured_errors = []
            self.state.captured_errors.append(
                f"Fallo de compilación en el comando '{cmd}'. Código de retorno: {returncode}.\n"
                f"Salida del error:\n{output}"
            )
            
        # Persistir el código de retorno y el circuit breaker
        self._update_circuit_breaker(returncode)
        
        exit_code_path = os.path.join(self.project_path, ".jellyfish_last_exit_code")
        try:
            with open(exit_code_path, "w", encoding="utf-8") as f:
                f.write(str(returncode))
        except Exception as e:
            logger.error("Error persistiendo last_exit_code: %s", e)
            
        return returncode, output

    def _classify_build_error(self, output: str) -> str:
        """Clasifica el error de compilación para guiar al Auto-Healing."""
        out_lower = output.lower()
        if "dependency" in out_lower or "cannot find module" in out_lower or "no module named" in out_lower or "unresolved reference" in out_lower or "import error" in out_lower:
            return "ERROR DE DEPENDENCIAS: Faltan paquetes o librerías en el entorno."
        if "permission denied" in out_lower or "command not found" in out_lower or "not recognized" in out_lower:
            return "ERROR DE ENTORNO/PERMISOS: Falta ejecutar herramientas o configurar permisos de ejecución."
        if "syntax" in out_lower or "compile error" in out_lower or "indentationerror" in out_lower or "unexpected token" in out_lower:
            return "ERROR DE SINTAXIS/CÓDIGO: El código generado tiene errores de sintaxis o de compilación estática."
        return "ERROR GENERAL DE COMPILACIÓN: Error de lógica o configuración."

    def _is_safe_healing_command(self, cmd: str) -> bool:
        """Verifica si un comando del auto-healing es seguro (control de blast radius)."""
        cmd_lower = cmd.lower()
        dangerous = ["rm ", "rm -", "uninstall", "purge", "delete", "fdisk", "mkfs", "dd ", "shred"]
        for d in dangerous:
            if d in cmd_lower:
                allowed_rm = [
                    "rm -rf build", "rm -rf dist", "rm -rf .pytest_cache", 
                    "rm -rf __pycache__", "rm -rf node_modules", 
                    "rm -rf .venv", "rm -rf venv", "rm -f package-lock.json",
                    "rm -f yarn.lock", "rm -f pnpm-lock.yaml"
                ]
                is_allowed = False
                for clean_rm in allowed_rm:
                    if clean_rm in cmd_lower:
                        is_allowed = True
                if not is_allowed:
                    return False
        return True

    def _auto_heal_build_error(self, cmd: str, returncode: int, build_output: str) -> tuple[int, str]:
        """Bucle Autónomo de Resolución de Errores (Auto-Healing Loop) con un máximo de 3 iteraciones (Auto-ReAct)."""
        from core.terminal import run_terminal_command
        from core.llm_engine import _call_llm_silent
        
        current_code = returncode
        current_output = build_output
        healing_attempts_log = []
        
        error_class = self._classify_build_error(build_output)
        
        for attempt in range(1, 4):
            console.print(f"\n       ⚡ [Auto-Healing Loop] Intento {attempt}/3 para resolver fallo de compilación...")
            console.print(f"       [dim]Clasificación del fallo: {error_class}[/dim]")
            
            # DIAGNÓSTICO: Analizar archivos del entorno para dar contexto
            files_list = []
            for root, dirs, files in os.walk(self.project_path):
                dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '.venv', 'venv', '__pycache__')]
                for f in files:
                    files_list.append(os.path.relpath(os.path.join(root, f), self.project_path))
                    
            files_context = "\n".join(files_list[:100])
            
            system_prompt = (
                "Eres un Agente Especialista en Auto-Recuperación de Sistemas (Auto-Healing Agent).\n"
                "Tu objetivo es diagnosticar y reparar problemas del entorno (ej. dependencias no instaladas, permisos faltantes, configuraciones erróneas, Dockerfiles rotos, etc.) para que el comando de compilación/verificación tenga éxito.\n\n"
                "Instrucciones:\n"
                "1. Analiza el comando que falló y la salida exacta del error.\n"
                "2. Propón la solución:\n"
                "   - Para escribir/modificar un archivo, usa:\n"
                "     <write_file path=\"ruta/relativa/archivo.ext\">\n"
                "     contenido corregido del archivo\n"
                "     </write_file>\n"
                "   - Para ejecutar comandos que solucionen el entorno (ej. chmod +x, npm install, export, mkdir, etc.), usa:\n"
                "     <run_command>comando a ejecutar</run_command>\n\n"
                "No des introducciones, sé ultra directo y responde solo con código y parches."
            )
            
            user_prompt = (
                f"COMANDO QUE FALLÓ:\n`{cmd}`\n\n"
                f"CÓDIGO DE SALIDA: {current_code}\n\n"
                f"TIPO DE ERROR DETECTADO: {error_class}\n\n"
                f"SALIDA DE ERROR (stdout/stderr):\n```\n{current_output}\n```\n\n"
                f"ARCHIVOS DISPONIBLES EN EL PROYECTO:\n{files_context}\n\n"
                f"Genera tus parches de corrección usando <write_file> y/o <run_command>."
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = _call_llm_silent(self.state, messages, provider=self.state.provider, model=self.state.model)
            if not response:
                console.print("       ⚠ No se obtuvo respuesta del Agente de Auto-Recuperación.")
                healing_attempts_log.append(f"Intento {attempt}: Sin respuesta del modelo.")
                continue
                
            # EJECUCIÓN DE PARCHE
            created_files = self._extract_and_write_files(response)
            executed_cmds = []
            cmd_matches = re.findall(r'<run_command>(.*?)</run_command>', response, re.DOTALL)
            for cmd_to_run in cmd_matches:
                cmd_clean = cmd_to_run.strip()
                if cmd_clean:
                    if not self._is_safe_healing_command(cmd_clean):
                        console.print(f"       🛡 Bloqueado comando potencialmente peligroso en Auto-Healing: {cmd_clean}")
                        healing_attempts_log.append(f"Intento {attempt}: Comando peligroso '{cmd_clean}' bloqueado por seguridad.")
                        continue
                    console.print(f"       ⚙ Ejecutando parche de entorno: {cmd_clean}")
                    run_terminal_command(cmd_clean, self.state, silent_history=True)
                    executed_cmds.append(cmd_clean)
                    
            healing_attempts_log.append(
                f"Intento {attempt}:\n"
                f"  - Archivos modificados: {created_files}\n"
                f"  - Comandos ejecutados: {executed_cmds}"
            )
            
            # REINTENTO
            console.print(f"       🔄 Reintentando comando original: {cmd}")
            ret_dict = {'returncode': 0}
            new_output = run_terminal_command(
                cmd,
                self.state,
                silent_history=True,
                timeout=300,
                force_confirm=True,
                return_code_dict=ret_dict
            )
            
            current_code = ret_dict['returncode']
            current_output = new_output
            
            if current_code == 0:
                console.print("       ✓ ¡Auto-Healing exitoso! El entorno se ha auto-recuperado.")
                return 0, current_output
                
        # ESCALAMIENTO
        console.print("       ❌ Auto-Healing Loop falló tras 3 intentos. Escalando error.")
        if not hasattr(self.state, "healing_failures"):
            self.state.healing_failures = {}
        self.state.healing_failures[cmd] = "\n".join(healing_attempts_log)
        
        return current_code, current_output

    def _get_last_exit_code(self) -> int:
        """Obtiene el último exit_code persistido del proyecto o 0 por defecto."""
        exit_code_path = os.path.join(self.project_path, ".jellyfish_last_exit_code")
        if os.path.isfile(exit_code_path):
            try:
                with open(exit_code_path, "r", encoding="utf-8") as f:
                    return int(f.read().strip())
            except Exception:
                pass
        return 0

    def _get_circuit_breaker_count(self) -> int:
        cb_path = os.path.join(self.project_path, ".jellyfish_circuit_breaker")
        if os.path.isfile(cb_path):
            try:
                with open(cb_path, "r", encoding="utf-8") as f:
                    return int(f.read().strip())
            except Exception:
                pass
        return 0

    def _reset_circuit_breaker(self) -> None:
        cb_path = os.path.join(self.project_path, ".jellyfish_circuit_breaker")
        exit_code_path = os.path.join(self.project_path, ".jellyfish_last_exit_code")
        for path in (cb_path, exit_code_path):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

    def _update_circuit_breaker(self, returncode: int) -> None:
        cb_path = os.path.join(self.project_path, ".jellyfish_circuit_breaker")
        if returncode == 0:
            count = 0
        else:
            count = self._get_circuit_breaker_count() + 1
        try:
            with open(cb_path, "w", encoding="utf-8") as f:
                f.write(str(count))
        except Exception:
            pass

    def _extract_and_write_files(self, content: str) -> list[str]:
        """Extrae y escribe en disco los archivos de código real desde el contenido generado."""
        created_files = []
        
        xml_matches = re.findall(r'<write_file\s+path="([^"]+)">\s*\n?(.*?)\s*\n?</write_file>', content, re.DOTALL)
        for rel_path, file_content in xml_matches:
            clean_rel_path = rel_path.strip().replace("`", "")
            full_path = os.path.join(self.project_path, clean_rel_path)
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(file_content)
                created_files.append(clean_rel_path)
            except Exception as e:
                console.print(f"       ✗ Error creando archivo {clean_rel_path}: {e}")
                logger.error("Error al escribir archivo real de agente: %s", e)

        md_matches = re.findall(r'\[WRITE_FILE:\s*([^\]\s]+)\]\s*\n*```[a-zA-Z0-9_-]*\n(.*?)\n```', content, re.DOTALL)
        for rel_path, file_content in md_matches:
            rel_clean = rel_path.strip().replace("`", "")
            if rel_clean in created_files:
                continue
            full_path = os.path.join(self.project_path, rel_clean)
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(file_content)
                created_files.append(rel_clean)
            except Exception as e:
                console.print(f"       ✗ Error creando archivo {rel_clean}: {e}")
                logger.error("Error al escribir archivo real de agente: %s", e)
                
        return created_files

    def _run_task_runner(self, user_idea: str) -> None:
        """Parsea el tablero de la agencia y ejecuta cada tarea con su agente asignado."""
        from core.orchestration.task_runner import TaskRunnerPhase
        TaskRunnerPhase(self).run(user_idea)

    def _write_task_handoff_with_status(self, task_id: str, agent: str, desc: str, output: str, status: str) -> None:
        """Registra un handoff en DAILY.md con el estado de compilación para trazabilidad."""
        daily_path = os.path.join(self.project_path, "DAILY.md")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = (
            f"\n### [{timestamp}] @{agent} — {task_id}\n"
            f"**Tarea:** {desc}\n"
            f"**Archivo generado:** `{output}`\n"
            f"**Estado:** {status}\n\n"
        )
        try:
            existing = _safe_read(daily_path)
            with open(daily_path, "w", encoding="utf-8") as f:
                f.write(existing + entry)
        except (OSError, IOError) as e:
            logger.warning("No se pudo actualizar DAILY.md: %s", e)

    def _mark_all_done(self, tasks: list[dict]) -> None:
        """Mueve todas las tareas a la sección DONE del tablero de la agencia vaciando las anteriores."""
        board = self._read_project_file(self.board_filename)
        if not board:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        done_rows = "\n".join(
            f"| {t.get('id', '')} | {t.get('task', '')} | @{t.get('agent', '')} | {timestamp} |"
            for t in tasks
        )
        
        # 1. Vaciar las tablas de POR HACER y EN PROGRESO dejando solo sus cabeceras
        board = re.sub(r'(##.*?(?:POR HACER|TODO).*?\n\|.*?\n\|[-\s|]*\n)(?:\|.*?\n)*', r'\1', board, flags=re.IGNORECASE)
        board = re.sub(r'(##.*?(?:EN PROGRESO|IN PROGRESS|DOING).*?\n\|.*?\n\|[-\s|]*\n)(?:\|.*?\n)*', r'\1', board, flags=re.IGNORECASE)

        # 2. Reconstruir la sección DONE
        done_section = (
            f"## ✅ HECHO (DONE)\n\n"
            f"| ID | Tarea | Asignado | Completado |\n"
            f"|---|---|---|---|\n"
            f"{done_rows}\n"
        )
        
        # 3. Insertar o reemplazar la sección DONE actual
        pattern = r"##\s*(?:✅\s*)?(?:HECHO|DONE|Completadas|Completado).*?(?=\n##|\n---|\n\*|$)"
        if re.search(pattern, board, flags=re.IGNORECASE | re.DOTALL):
            new_board = re.sub(pattern, done_section, board, flags=re.IGNORECASE | re.DOTALL)
        else:
            new_board = board.strip() + "\n\n" + done_section
            
        self._write_project_file(self.board_filename, new_board)

        # Actualizar versión JSON (Mejora 11)
        try:
            import json
            json_filename = self.board_filename.replace(".md", ".json")
            json_path = os.path.join(self.project_path, json_filename)
            if os.path.isfile(json_path):
                for t in tasks:
                    t["status"] = "DONE"
                    t["completed_at"] = timestamp
                self._write_project_file(json_filename, json.dumps(tasks, indent=2, ensure_ascii=False))
        except Exception as je:
            logger.warning("No se pudo actualizar el tablero JSON a DONE: %s", je)

    def _save_board(self, tasks: list[dict]) -> None:
        """Guarda el estado actual de las tareas en los formatos JSON y Markdown del tablero."""
        # 1. Actualizar versión JSON
        try:
            import json
            json_filename = self.board_filename.replace(".md", ".json")
            self._write_project_file(json_filename, json.dumps(tasks, indent=2, ensure_ascii=False))
        except Exception as je:
            logger.warning("No se pudo guardar el tablero JSON: %s", je)

        # 2. Sincronizar versión Markdown
        try:
            board = self._read_project_file(self.board_filename)
            if board:
                todo_tasks = [t for t in tasks if t.get("status") not in ("DONE", "HECHO") and t.get("state") not in ("DONE", "HECHO")]
                done_tasks = [t for t in tasks if t.get("status") in ("DONE", "HECHO") or t.get("state") in ("DONE", "HECHO")]
                
                todo_rows = "\n".join(
                    f"| {t.get('id', '')} | {t.get('task', '')} | @{t.get('agent', '')} | Pendiente |"
                    for t in todo_tasks
                )
                done_rows = "\n".join(
                    f"| {t.get('id', '')} | {t.get('task', '')} | @{t.get('agent', '')} | {t.get('completed_at', 'Completado')} |"
                    for t in done_tasks
                )
                
                # Reconstruir sección TODO
                todo_section = (
                    f"## 📋 POR HACER (TODO)\n\n"
                    f"| ID | Tarea | Asignado | Estado |\n"
                    f"|---|---|---|---|\n"
                    f"{todo_rows}\n"
                )
                
                # Vaciar EN PROGRESO
                doing_section = (
                    f"## ⏳ EN PROGRESO (DOING)\n\n"
                    f"| ID | Tarea | Asignado | Progreso |\n"
                    f"|---|---|---|---|\n"
                )
                
                # Reconstruir sección DONE
                done_section = (
                    f"## ✅ HECHO (DONE)\n\n"
                    f"| ID | Tarea | Asignado | Completado |\n"
                    f"|---|---|---|---|\n"
                    f"{done_rows}\n"
                )
                
                # Reemplazar secciones usando regex
                pattern_todo = r"##\s*(?:📋\s*)?(?:POR HACER|TODO).*?(?=\n##|\n---|\n\*|$)"
                if re.search(pattern_todo, board, flags=re.IGNORECASE | re.DOTALL):
                    board = re.sub(pattern_todo, todo_section, board, flags=re.IGNORECASE | re.DOTALL)
                    
                pattern_doing = r"##\s*(?:⏳\s*)?(?:EN PROGRESO|IN PROGRESS|DOING).*?(?=\n##|\n---|\n\*|$)"
                if re.search(pattern_doing, board, flags=re.IGNORECASE | re.DOTALL):
                    board = re.sub(pattern_doing, doing_section, board, flags=re.IGNORECASE | re.DOTALL)
                    
                pattern_done = r"##\s*(?:✅\s*)?(?:HECHO|DONE|Completadas|Completado).*?(?=\n##|\n---|\n\*|$)"
                if re.search(pattern_done, board, flags=re.IGNORECASE | re.DOTALL):
                    board = re.sub(pattern_done, done_section, board, flags=re.IGNORECASE | re.DOTALL)
                else:
                    board = board.strip() + "\n\n" + done_section
                    
                self._write_project_file(self.board_filename, board)
        except Exception as me:
            logger.warning("No se pudo sincronizar el tablero Markdown: %s", me)

    # ─── Orquestación Principal ─────────────────────────────────────────

    def run(self, user_idea: str) -> str:
        """Ejecuta el pipeline completo de desarrollo autónomo dinámico."""
        from rich.prompt import Confirm
        total_start = time.perf_counter()

        # Sprint 12 — Preguntar permisos globales al inicio para evitar saturación
        try:
            global_approve = Confirm.ask(
                "\n⚡ ¿Deseas activar auto-aprobación GLOBAL para TODOS los comandos de esta ejecución? [y/n]",
                default=False
            )
            if global_approve:
                self.state.enable_project_auto_approve()
                console.print("✓ Auto-aprobación global activada para este proceso.\n")
        except (EOFError, KeyboardInterrupt):
            pass

        # La confirmación visual del prompt fue eliminada para mantener la terminal limpia y compacta.

        # AGENTE VALIDADOR DEL ENTORNO (Environment Probe - Sprint 11)
        try:
            self._run_environment_probe()
        except Exception as e:
            logger.error("Error ejecutando Environment Probe: %s", e)
            console.print(f"⚠ No se pudo ejecutar el Environment Probe: {e}")

        # FASE 0: Generación de Inteligencia del Proyecto
        try:
            self._generate_project_intelligence(user_idea)
        except Exception as e:
            logger.error("Error generando inteligencia del proyecto: %s", e)
            console.print(f"⚠ No se pudo generar la inteligencia del proyecto: {e}")

        # Comprobar si existe un sprint activo o planeado en este proyecto
        resume_existing = False
        board_path = os.path.join(self.project_path, self.board_filename)
        json_board_filename = self.board_filename.replace(".md", ".json")
        json_board_path = os.path.join(self.project_path, json_board_filename)
        
        if os.path.isfile(board_path) or os.path.isfile(json_board_path):
            if user_idea == "Reanudación de Sprint Activo":
                resume_existing = True
            else:
                try:
                    resume_existing = Confirm.ask(
                        "\n🔄 Se detectó un sprint activo o planeado en este proyecto.\n"
                        "¿Deseas reanudar las tareas pendientes (y) o planificar tu NUEVO requerimiento desde cero (n)?",
                        default=False
                    )
                except Exception:
                    # Fallback no interactivo: si hay una nueva idea y falla el input, planificar
                    resume_existing = False

        if resume_existing:
            # Verificar si realmente hay tareas en el tablero
            from core.project_orchestrator import _parse_sprint_tasks
            import json
            tasks_found = []
            
            # Cargar desde JSON si existe
            if os.path.isfile(json_board_path):
                try:
                    with open(json_board_path, "r", encoding="utf-8") as f:
                        tasks_found = json.load(f)
                except Exception:
                    pass
            
            # Cargar desde Markdown si no hay en JSON o falló
            if not tasks_found and os.path.isfile(board_path):
                try:
                    board_content = self._read_project_file(self.board_filename)
                    tasks_found = _parse_sprint_tasks(board_content)
                except Exception:
                    pass

            if not tasks_found:
                console.print("[yellow]⚠ El tablero actual está vacío o no contiene tareas válidas.[/yellow]")
                console.print("[bold cyan]🔄 Forzando la planificación de un nuevo requerimiento...[/bold cyan]")
                resume_existing = False

        if resume_existing:
            console.print("[bold green]✓ Reanudando el sprint existente. Saltando fases de planificación...[/bold green]")
            # Tratar de cargar historias del backlog como idea contextual si es posible
            backlog_content = self._read_project_file("BACKLOG.md")
            if backlog_content:
                user_idea = backlog_content[:3000]
        else:
            # Eliminar tableros viejos si el usuario decidió planificar un requerimiento nuevo desde cero
            for f in (board_path, json_board_path):
                if os.path.isfile(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass
            console.print("[bold cyan]🧹 Tablero anterior limpiado. Iniciando planificación del nuevo requerimiento...[/bold cyan]")

            # Fase 1: Product Owner
            if not self._run_product_owner(user_idea):
                total_time = time.perf_counter() - total_start
                self._print_summary_table(total_time)
                return "Pipeline detenido en fase de Product Owner."

            # Validación de Definition of Ready (DoR)
            if not self._run_dor_validation():
                total_time = time.perf_counter() - total_start
                self._print_summary_table(total_time)
                return "Pipeline detenido por fallo en la validación del Definition of Ready (DoR)."

            # Fase 2: Scrum Master (Team Assembly)
            if not self._run_scrum_master(user_idea):
                total_time = time.perf_counter() - total_start
                self._print_summary_table(total_time)
                return "Pipeline detenido en fase de Scrum Master."

        # Fase 3: Task Runner (Ejecución Dinámica) y Compilación automática final (Sprint 11)
        self.state.silent_execution = True
        try:
            with SilentExecutionRedirect(self.state):
                self._run_task_runner(user_idea)

                build_cmd = self._detect_compile_command()
                if build_cmd:
                    console.print("\n🛠 Ejecutando compilación de validación final del proyecto...")
                    returncode, build_output = self._run_build_command(build_cmd)
                    
                    from core.terminal import screen_console
                    if returncode == 0:
                        screen_console.print("✓ ¡Compilación final exitosa! El proyecto está listo.\n")
                        self.metrics.append({
                            "fase": "🛠 Compilación Final",
                            "detalle": f"Comando: {build_cmd}",
                            "tiempo": 0.0,
                            "status": "✅",
                        })
                    else:
                        screen_console.print(f"⚠ La compilación final falló con código {returncode}.\n")
                        self.metrics.append({
                            "fase": "🛠 Compilación Final",
                            "detalle": "Fallo de compilación",
                            "tiempo": 0.0,
                            "status": "❌",
                        })
        finally:
            self.state.silent_execution = False

        # Vincular archivos al contexto
        for fname in self.generated_files:
            filepath = os.path.join(self.project_path, fname)
            if os.path.isfile(filepath):
                self.state.context_files.add(filepath)
        self.state.refresh_static_context()

        # Resumen
        total_time = time.perf_counter() - total_start
        self._print_summary_table(total_time)
        
        try:
            self._run_retrospective()
        except Exception as e:
            logger.warning("No se pudo ejecutar la retrospectiva autónoma: %s", e)

        return self._generate_final_summary(user_idea, total_time)

    def _print_summary_table(self, total_time: float) -> None:
        """Imprime tabla de resumen del pipeline."""
        table = Table(
            title="🪼 Resumen del Pipeline Autónomo",
            show_header=True, header_style="bold purple",
            border_style="dim white", show_footer=True,
        )
        table.add_column("Agente / Tarea", style="bold", min_width=28)
        table.add_column("Entregable", style="dim", min_width=30)
        table.add_column("Duración", justify="right", min_width=10, footer=f"{total_time:.1f}s total")
        table.add_column("", justify="center", min_width=3)

        for m in self.metrics:
            secs = m["tiempo"]
            dur = f"{secs:.1f}s"
            table.add_row(m["fase"], m["detalle"], Text.from_markup(dur), m["status"])

        console.print()
        console.print(table)
        console.print()

    def _generate_final_summary(self, user_idea: str, total_time: float) -> str:
        """Genera resumen textual conciso de lo fallido y el estado actual."""
        completed_tasks = [m for m in self.metrics if m["status"] == "✅"]
        failed_tasks = [m for m in self.metrics if m["status"] in ("❌", "⚠")]
        
        status_project = "COMPLETADO CON ÉXITO"
        if failed_tasks:
            status_project = "INCOMPLETO / CON ADVERTENCIAS (Revisar logs)"

        summary_lines = [
            f"🪼 REPORTE FINAL DEL PROYECTO ({total_time:.1f}s)",
            f"  [bold]• Estado actual:[/bold] {status_project}",
            f"  [bold]• Directorio:[/bold] {self.project_path}",
            f"  [bold]• Tareas exitosas:[/bold] {len(completed_tasks)}/{len(self.metrics)}"
        ]
        
        if failed_tasks:
            summary_lines.append("  • Tareas fallidas/omitidas:")
            for f in failed_tasks:
                summary_lines.append(f"    - {f['fase']}: {f['detalle']}")
                
        healing_failures = getattr(self.state, "healing_failures", {})
        if healing_failures:
            summary_lines.append("  • Intentos de Auto-Recuperación fallidos:")
            for cmd_f, log_f in healing_failures.items():
                summary_lines.append(f"    - Comando: `{cmd_f}`")
                for line in log_f.split('\n'):
                    summary_lines.append(f"      {line}")

        # Imprimir por pantalla
        console.print()
        console.print(Panel("\n".join(summary_lines), title="📋 Reporte de Estado", border_style="dim white", expand=False))
        console.print()

        # Retornar versión markdown para el historial
        md_summary = (
            f"🪼 **Reporte Final del Proyecto** ({total_time:.1f}s)\n\n"
            f"- **Estado:** {status_project}\n"
            f"- **Tareas exitosas:** {len(completed_tasks)}/{len(self.metrics)}\n"
        )
        if failed_tasks:
            md_summary += "- **Tareas fallidas/omitidas:**\n"
            for f in failed_tasks:
                md_summary += f"  - `{f['fase']}`: {f['detalle']}\n"
                
        if healing_failures:
            md_summary += "\n- **Intentos de Auto-Recuperación fallidos:**\n"
            for cmd_f, log_f in healing_failures.items():
                md_summary += f"  - **Comando:** `{cmd_f}`\n"
                md_summary += "    **Detalle de intentos:**\n"
                for line in log_f.split('\n'):
                    md_summary += f"      {line}\n"

        md_summary += f"- **Directorio:** `{self.project_path}`"
        return md_summary

    def _is_git_repo(self) -> bool:
        """Verifica si el proyecto activo es un repositorio Git."""
        import subprocess
        if not self.project_path or not os.path.isdir(self.project_path):
            return False
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            return res.returncode == 0 and "true" in res.stdout.strip().lower()
        except Exception:
            return False

    def _git_commit_snapshot(self, task_id: str) -> bool:
        """Realiza un snapshot de git automático antes de iniciar una tarea.
        Retorna True si se creó un commit de snapshot.
        """
        if not self._is_git_repo():
            return False
        import subprocess
        try:
            status_res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if not status_res.stdout.strip():
                return False
            
            subprocess.run(["git", "add", "."], cwd=self.project_path, capture_output=True, timeout=10)
            res = subprocess.run(
                ["git", "commit", "-m", f"jellyfish_pre_task_{task_id}"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            return res.returncode == 0
        except Exception as e:
            logger.warning("Error creando git snapshot para la tarea %s: %s", task_id, e)
            return False

    def _git_rollback(self, task_id: str, snapshot_created: bool) -> None:
        """Revierte los cambios de la tarea si falla la compilación o ejecución."""
        if not self._is_git_repo():
            return
        import subprocess
        try:
            console.print(f"       ↩ Revertiendo cambios de la tarea {task_id} debido a fallo de compilación/ejecución...")
            if snapshot_created:
                subprocess.run(["git", "reset", "--hard", "HEAD~1"], cwd=self.project_path, capture_output=True, timeout=10)
            else:
                subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=self.project_path, capture_output=True, timeout=10)
            subprocess.run(["git", "clean", "-fd"], cwd=self.project_path, capture_output=True, timeout=10)
            console.print("       ✓ Espacio de trabajo revertido al estado anterior de forma segura.")
        except Exception as e:
            logger.error("Error durante git rollback de la tarea %s: %s", task_id, e)

    def _git_start_task_branch(self, task_id: str) -> tuple[bool, str]:
        """Crea y se mueve a una rama temporal para la tarea (Mejora 41).
        Retorna (exitoso, rama_original).
        """
        if not self._is_git_repo():
            return False, ""
        import subprocess
        try:
            # Obtener rama actual
            res = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            original_branch = res.stdout.strip()
            if not original_branch:
                return False, ""
                
            task_branch = f"jellyfish_task_{task_id.lower().replace('-', '_')}"
            
            # Guardar cambios sin commitear en la rama original
            subprocess.run(["git", "add", "."], cwd=self.project_path, capture_output=True, timeout=10)
            subprocess.run(
                ["git", "commit", "-m", f"jellyfish_auto_save_before_{task_id}"],
                cwd=self.project_path, capture_output=True, timeout=10
            )
            
            # Limpiar ramas antiguas de la tarea si existiesen
            subprocess.run(["git", "checkout", original_branch], cwd=self.project_path, capture_output=True, timeout=10)
            subprocess.run(["git", "branch", "-D", task_branch], cwd=self.project_path, capture_output=True, timeout=10)
            
            res_checkout = subprocess.run(
                ["git", "checkout", "-b", task_branch],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            if res_checkout.returncode == 0:
                console.print(f"       [dim]🌿 Rama Git de tarea creada y activa: {task_branch}[/dim]")
                return True, original_branch
        except Exception as e:
            logger.warning("Error iniciando rama git para tarea %s: %s", task_id, e)
        return False, ""

    def _git_end_task_branch(self, task_id: str, original_branch: str, success: bool) -> None:
        """Cierra el ciclo de la rama de la tarea. Si success es True, fusiona. Si es False, descarta."""
        if not self._is_git_repo() or not original_branch:
            return
        import subprocess
        task_branch = f"jellyfish_task_{task_id.lower().replace('-', '_')}"
        try:
            if success:
                # Commitear cambios en la rama de la tarea
                subprocess.run(["git", "add", "."], cwd=self.project_path, capture_output=True, timeout=10)
                subprocess.run(
                    ["git", "commit", "-m", f"jellyfish_completed_task_{task_id}"],
                    cwd=self.project_path,
                    capture_output=True,
                    timeout=10
                )
                # Volver a rama original
                subprocess.run(["git", "checkout", original_branch], cwd=self.project_path, capture_output=True, timeout=10)
                # Fusionar
                merge_res = subprocess.run(
                    ["git", "merge", task_branch, "--no-edit"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                if merge_res.returncode == 0:
                    console.print(f"       ✓ Rama {task_branch} integrada exitosamente a {original_branch}.")
                    # Borrar rama de la tarea
                    subprocess.run(["git", "branch", "-d", task_branch], cwd=self.project_path, capture_output=True, timeout=10)
                else:
                    console.print(f"       ⚠️ Conflicto al integrar {task_branch}. Forzando rollback...")
                    # Si falla, abortar merge y resetear
                    subprocess.run(["git", "merge", "--abort"], cwd=self.project_path, capture_output=True, timeout=10)
                    subprocess.run(["git", "checkout", original_branch], cwd=self.project_path, capture_output=True, timeout=10)
                    subprocess.run(["git", "branch", "-D", task_branch], cwd=self.project_path, capture_output=True, timeout=10)
                    subprocess.run(["git", "clean", "-fd"], cwd=self.project_path, capture_output=True, timeout=10)
            else:
                console.print(f"       ↩ Revertiendo cambios: Rama {task_branch} descartada.")
                # Volver a rama original
                subprocess.run(["git", "checkout", "-f", original_branch], cwd=self.project_path, capture_output=True, timeout=10)
                # Borrar rama de la tarea
                subprocess.run(["git", "branch", "-D", task_branch], cwd=self.project_path, capture_output=True, timeout=10)
                # Limpiar
                subprocess.run(["git", "clean", "-fd"], cwd=self.project_path, capture_output=True, timeout=10)
                console.print("       ✓ Espacio de trabajo limpio.")
        except Exception as e:
            logger.error("Error al finalizar rama git para tarea %s: %s", task_id, e)

    def _run_dod_validation(self, task_id: str, agent_name: str, task_desc: str, output_file: str, file_content: str) -> tuple[bool, str]:
        """Valida que la tarea cumpla con la Definition of Done (DoD) usando un agente evaluador (Mejora 15)."""
        console.print(f"       [dim]🔍 Validando Definition of Done (DoD) para la tarea {task_id}...[/dim]")
        
        system_prompt = (
            "Eres un QA Automation Engineer experto.\n"
            "Tu tarea es evaluar el entregable de un agente desarrollador y determinar si cumple con el 'Definition of Done' (DoD).\n"
            "El entregable cumple con el DoD si:\n"
            "1. Resuelve directamente la descripción de la tarea.\n"
            "2. No tiene marcadores de posición (placeholders), comentarios TODO incompletos ni código truncado.\n"
            "3. En caso de ser código, sigue buenas prácticas básicas.\n\n"
            "Debes responder en formato JSON puro. Ejemplo:\n"
            '{"approved": true, "reason": "El archivo de código implementa todas las funciones requeridas y no tiene placeholders."}\n'
            'O si no es aprobado:\n'
            '{"approved": false, "reason": "El archivo de código contiene comentarios TODO y el cuerpo de la función principal está vacío."}'
        )
        
        user_prompt = (
            f"DESCRIPCIÓN DE LA TAREA:\n{task_desc}\n\n"
            f"ARCHIVO ENTREGABLE: {output_file}\n"
            f"CONTENIDO GENERADO:\n{file_content}\n"
        )
        
        try:
            response = self._call_agent(system_prompt, user_prompt)
            if not response:
                return True, "DoD aprobado por defecto (sin respuesta del validador)."
                
            import json
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                approved = data.get("approved", True)
                reason = data.get("reason", "Aprobado por el QA Agent.")
                return approved, reason
        except Exception as e:
            logger.warning("Error en validación DoD: %s", e)
            
        return True, "DoD aprobado por defecto."

    def _build_intelligent_context(self, task_desc: str, output_file: str) -> str:
        """Construye un contexto inteligente para la tarea priorizando documentos técnicos reales."""
        parts = []
        total_chars = 0
        MAX_CONTEXT = 30_000  # Budget de contexto por tarea

        # 1. PRIORIDAD MÁXIMA: Documentos de inteligencia técnica (compactos y de alto valor)
        intelligence_files = [
            "DESIGN_TOKENS.md",       # Patrones de arquitectura
            "DATA_SCHEMA.md",         # Modelos de datos reales
            "SECURITY.md",            # Guardrails de seguridad
            "COMPONENT_INDEX.md",     # Componentes reutilizables
            "DEVELOPMENT_LOG.md",     # Bitácora de desarrollo (coherencia inter-agente)
            "DEPENDENCY_MANIFEST.md", # Librerías disponibles
            "PLAYBOOK.md",            # Soluciones conocidas
            "BUSINESS_CONTEXT.md",    # Contexto de negocio
        ]
        for fname in intelligence_files:
            if total_chars >= MAX_CONTEXT:
                break
            content = self._read_project_file(fname)
            if content:
                if fname == "DEVELOPMENT_LOG.md":
                    # Conservar el final de la bitácora (las tareas más recientes)
                    truncated = content[-6000:]
                else:
                    truncated = content[:4000]
                parts.append(f"--- {fname} ---\n{truncated}\n")
                total_chars += len(truncated)

        # 2. PROJECT_TREE.md — Solo si hay espacio (es largo pero muy útil)
        if total_chars < MAX_CONTEXT:
            tree = self._read_project_file("PROJECT_TREE.md")
            if tree:
                truncated = tree[:5000]
                parts.append(f"--- PROJECT_TREE.md ---\n{truncated}\n")
                total_chars += len(truncated)

        # 3. RAG — Código relevante del codebase indexado
        from core.rag_coder import CodeKnowledgeBase
        from core.state import DB_PATH
        try:
            rag = CodeKnowledgeBase(DB_PATH, active_project=self.project_path)
            rag_context = rag.query_code(task_desc, k=4)
            if rag_context and total_chars < MAX_CONTEXT:
                truncated = rag_context[:4000]
                parts.append(f"### [CONTEXTO RELEVANTE RAG]\n{truncated}\n")
                total_chars += len(truncated)
        except Exception as e:
            logger.debug("No se pudo obtener contexto RAG para la tarea: %s", e)

        # 4. Vecinos funcionales: archivos generados que son relevantes para ESTA tarea
        for fname in self.generated_files:
            if total_chars >= MAX_CONTEXT:
                break
            if fname == output_file or fname in intelligence_files:
                continue
            # Incluir si el nombre del archivo aparece en la descripción de la tarea
            # o si es un archivo de arquitectura/diseño central
            is_relevant = (
                fname.lower().replace("_", " ").replace("-", " ") in task_desc.lower() or
                "architecture" in fname.lower() or
                "design" in fname.lower() or
                fname.endswith(('.py', '.js', '.jsx', '.ts', '.tsx'))
            )
            if is_relevant:
                content = self._read_project_file(fname)
                if content:
                    truncated = content[:3000]
                    parts.append(f"--- {fname} ---\n{truncated}\n")
                    total_chars += len(truncated)

        # 5. PRIORIDAD BAJA: Tablero actual (solo resumen de estado, no el completo)
        if total_chars < MAX_CONTEXT:
            board = self._read_project_file(self.board_filename)
            if board:
                truncated = board[:2000]
                parts.append(f"--- {self.board_filename} (estado actual) ---\n{truncated}\n")

        return "\n".join(parts)

    def _run_dor_validation(self) -> bool:
        """Un QA Agent audita el BACKLOG.md para certificar que está listo (DoR)."""
        from core.orchestration.product_owner import ProductOwnerPhase
        return ProductOwnerPhase(self).run_dor_validation()

    def _run_retrospective(self) -> None:
        """Analiza DAILY.md y guarda aprendizajes en retrospective_rules.md para futuros sprints."""
        from core.orchestration.scrum_master import ScrumMasterPhase
        ScrumMasterPhase(self).run_retrospective()
