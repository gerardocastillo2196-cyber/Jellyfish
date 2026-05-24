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

logger = logging.getLogger("jellyfish.project_orchestrator")
console = Console()

class SilentExecutionRedirect:
    def __init__(self, state):
        self.state = state
        self.log_file = None
        self.old_files = {}

    def __enter__(self):
        proj_path = getattr(self.state, "active_project", None)
        log_path = os.path.join(proj_path, "jellyfish_debug.log") if proj_path else "jellyfish_debug.log"
        self.log_file = open(log_path, "a", encoding="utf-8")
        
        from core.project_orchestrator import console as po_console
        from core.terminal import console as term_console
        from core.ui import console as ui_console
        
        self.consoles = [po_console, term_console, ui_console]
        for c in self.consoles:
            self.old_files[c] = c.file
            c.file = self.log_file
            
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for c in self.consoles:
            c.file = self.old_files.get(c, sys.stdout)
        if self.log_file:
            self.log_file.close()

# Agentes que son roles de gestión y NO deben asignarse a tareas de ejecución
_MANAGEMENT_ROLES = {"product_owner", "scrum_master", "template", "researcher"}


def _scan_available_agents(state: JellyfishState = None) -> list[dict]:
    """Escanea agents/ y retorna nombre + primera línea de rol de cada uno, filtrados por la agencia activa si está provisto."""
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

    for fname in sorted(os.listdir(agents_dir)):
        if not fname.endswith(".md"):
            continue
        name = fname[:-3]  # quitar .md
        if name in _MANAGEMENT_ROLES:
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
    """Parsea las tareas TODO del SPRINT_BOARD.md.

    Retorna lista de dicts con keys: id, task, agent, estimate, output_file.
    """
    tasks = []
    in_todo = False

    for line in board_content.split("\n"):
        stripped = line.strip()

        # Detectar inicio de sección TODO
        if "TODO" in stripped.upper() and ("##" in stripped or "POR HACER" in stripped.upper()):
            in_todo = True
            continue

        # Detectar fin de sección TODO (otra sección ##)
        if in_todo and stripped.startswith("##"):
            break

        if not in_todo:
            continue

        if not stripped.startswith("|"):
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

        # Saltar separadores de tabla (ej: |---|---|...)
        if all(all(char in ('-', ':', ' ') for char in cell) for cell in cells if cell):
            continue

        # Saltar cabecera de la tabla
        if cells[0].upper() in ("ID", "TASK ID", "TASK_ID", "CÓDIGO", "CODIGO") or cells[1].upper() in ("TAREA", "TASK", "DESCRIPCIÓN", "DESCRIPCION"):
            continue

        # Ignorar filas placeholder
        if cells[0] == "—" or cells[1] == "—" or not cells[0] or not cells[1]:
            continue

        task_data = {
            "id": cells[0],
            "task": cells[1],
            "agent": cells[2].lower().replace("@", "").strip() if len(cells) > 2 else "default",
            "estimate": cells[3] if len(cells) > 3 else "",
            "output_file": cells[4] if len(cells) > 4 else "",
        }

        # Solo agregar si tiene tarea real
        if task_data["task"] and task_data["id"]:
            tasks.append(task_data)

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
        agency = getattr(self.state, "active_agency", "default")
        if agency == "development":
            return "DEV_BOARD.md"
        elif agency == "marketing":
            return "MKT_BOARD.md"
        elif agency == "research":
            return "RESEARCH_BOARD.md"
        elif agency == "default":
            return "SPRINT_BOARD.md"
        else:
            return "DEV_BOARD.md"

    def _load_agent_prompt(self, agent_name: str) -> str:
        """Carga el system prompt de un agente desde su archivo .md."""
        filepath = os.path.join(AGENCY_DIR, "agents", f"{agent_name}.md")
        return _safe_read(filepath)

    def _read_project_file(self, filename: str) -> str:
        """Lee un archivo del proyecto activo."""
        return _safe_read(os.path.join(self.project_path, filename))

    def _write_project_file(self, filename: str, content: str) -> bool:
        """Escribe un archivo al directorio del proyecto activo."""
        filepath = os.path.join(self.project_path, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            self.generated_files.append(filename)
            return True
        except (OSError, IOError) as e:
            logger.error("Error escribiendo %s: %s", filepath, e)
            console.print(f"[red]Error escribiendo {filename}: {e}[/red]")
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

    # ─── FASE 1: Product Owner ──────────────────────────────────────────

    def _run_product_owner(self, user_idea: str) -> bool:
        """Genera BACKLOG.md y solicita aprobación del usuario."""
        console.print("\n[bold cyan]━━━ FASE 1: 📝 Product Owner ━━━[/bold cyan]")
        t0 = time.perf_counter()

        agent_prompt = self._load_agent_prompt("product_owner")
        system = (
            f"{agent_prompt}\n\n"
            "[INSTRUCCIONES ESPECÍFICAS]\n"
            "Tu ÚNICO entregable es el contenido completo del archivo BACKLOG.md. "
            "Genera SOLAMENTE Markdown listo para guardar. NO incluyas explicaciones externas.\n"
            "Incluye:\n"
            "- Título del proyecto y visión general\n"
            "- Al menos 5 historias de usuario: 'Como [rol], quiero [acción] para [beneficio]'\n"
            "- Criterios de aceptación en formato Gherkin\n"
            "- Prioridades MoSCoW y estimación de puntos de historia\n"
        )
        with TaskProgress(tui_engine, "auto_po", "Product Owner: Redactando backlog..."):
            result = self._call_agent(system, f"IDEA DEL PROYECTO:\n{user_idea}")

        elapsed = time.perf_counter() - t0

        if not result:
            self.metrics.append({"fase": "📝 Product Owner", "detalle": "ERROR", "tiempo": elapsed, "status": "❌"})
            console.print("[red]✗ Product Owner no produjo resultado.[/red]")
            return False

        self._write_project_file("BACKLOG.md", result)
        tokens = estimate_tokens(result)
        console.print(f"[green]✓ BACKLOG.md[/green] [dim]({tokens:,} tokens · {elapsed:.1f}s)[/dim]")
        self.metrics.append({"fase": "📝 Product Owner", "detalle": f"~{tokens:,} tokens → BACKLOG.md", "tiempo": elapsed, "status": "✅"})

        # Checkpoint
        preview = result[:2000] + ("\n..." if len(result) > 2000 else "")
        console.print(Panel(Markdown(preview), title="[bold cyan]📋 Preview: BACKLOG.md[/bold cyan]", border_style="cyan", padding=(1, 2)))

        try:
            approved = Confirm.ask("\n[bold yellow]¿Aprobar backlog y continuar?[/bold yellow]", default=True)
        except (EOFError, KeyboardInterrupt):
            approved = False

        if not approved:
            console.print("[yellow]Pipeline detenido. Edita BACKLOG.md y re-ejecuta /auto.[/yellow]")
            return False

        console.print("[bold green]✓ Backlog aprobado.[/bold green]\n")
        return True

    # ─── FASE 2: Scrum Master (Team Assembly + Sprint Planning) ─────────

    def _run_scrum_master(self, user_idea: str) -> bool:
        """SM escanea agentes, arma equipo y genera el tablero correspondiente a la agencia."""
        console.print(f"\n[bold cyan]━━━ FASE 2: 📋 Scrum Master (Team Assembly - Agencia: {self.state.active_agency.upper()}) ━━━[/bold cyan]")
        t0 = time.perf_counter()

        # Escanear agentes disponibles
        available_agents = _scan_available_agents(self.state)
        agents_catalog = "\n".join(
            f"  - @{a['name']}: {a['role']}" for a in available_agents
        )
        console.print(f"[dim]   Agentes disponibles en la agencia '{self.state.active_agency}': {len(available_agents)}[/dim]")

        backlog = self._read_project_file("BACKLOG.md")
        agent_prompt = self._load_agent_prompt("scrum_master")

        system = (
            f"{agent_prompt}\n\n"
            "[INSTRUCCIONES ESPECÍFICAS PARA ESTA TAREA]\n"
            f"Tu ÚNICO entregable es el contenido completo del archivo {self.board_filename}.\n"
            "Genera SOLAMENTE Markdown listo para guardar.\n\n"
            "EQUIPO DISPONIBLE (solo puedes asignar tareas a estos agentes):\n"
            f"{agents_catalog}\n\n"
            "REGLAS DE ASIGNACIÓN:\n"
            "1. Analiza las historias del BACKLOG.md y decide qué agentes se necesitan.\n"
            "2. Desglosa cada historia en tareas técnicas concretas.\n"
            "3. Asigna cada tarea al agente más adecuado usando EXACTAMENTE su @nombre.\n"
            "4. Define un archivo de entregable para cada tarea (ej: ARCHITECTURE.md, API_DESIGN.md).\n"
            f"5. TRASPASOS INTER-AGENCIA (HANDOFFS): Si una tarea técnica excede las capacidades de tu agencia actual (agencia activa: '{self.state.active_agency}'), "
            "puedes definir como 'Entregable' un archivo que servirá de insumo para otra agencia (ej: un COPY_LANDING.md generado por MKT para que DEV lo consuma).\n\n"
            f"FORMATO OBLIGATORIO del tablero (la tabla TODO DEBE tener exactamente 5 columnas en {self.board_filename}):\n"
            "```\n"
            "## 📋 POR HACER (TODO)\n"
            "| ID | Tarea | Asignado | Estimación | Entregable |\n"
            "|---|---|---|---|---|\n"
            "| T-001 | Diseñar la arquitectura del sistema | @arquitecto_software | 5pts | ARCHITECTURE.md |\n"
            "| T-002 | Implementar modelos de datos | @backend_dev | 3pts | IMPLEMENTATION_PLAN.md |\n"
            "```\n\n"
            "IMPORTANTE:\n"
            "- La columna 'Asignado' DEBE ser exactamente un @nombre de la lista de agentes.\n"
            "- La columna 'Entregable' DEBE ser un nombre de archivo .md válido.\n"
            "- Ordena las tareas en el orden lógico de ejecución.\n"
            "- Incluye también secciones IN PROGRESS (vacía) y DONE (vacía).\n"
        )

        user_prompt = (
            f"IDEA ORIGINAL:\n{user_idea}\n\n"
            f"BACKLOG.md:\n{backlog}\n\n"
            f"Genera el {self.board_filename} asignando tareas a los agentes del equipo."
        )

        with TaskProgress(tui_engine, "auto_sm", "Scrum Master: Armando equipo y planificando sprint..."):
            result = self._call_agent(system, user_prompt)

        elapsed = time.perf_counter() - t0

        if not result:
            self.metrics.append({"fase": "📋 Scrum Master", "detalle": "ERROR", "tiempo": elapsed, "status": "❌"})
            console.print("[red]✗ Scrum Master no produjo resultado.[/red]")
            return False

        self._write_project_file(self.board_filename, result)
        tokens = estimate_tokens(result)

        # Mostrar equipo seleccionado
        tasks = _parse_sprint_tasks(result)
        if not tasks:
            self.metrics.append({"fase": "📋 Scrum Master", "detalle": "ERROR — No se encontraron tareas", "tiempo": elapsed, "status": "❌"})
            console.print(f"[red]❌ Error: El Scrum Master no pudo generar tareas válidas en {self.board_filename}.[/red]")
            return False

        unique_agents = set(t["agent"] for t in tasks)
        console.print(f"[green]✓ {self.board_filename}[/green] [dim]({tokens:,} tokens · {elapsed:.1f}s)[/dim]")
        console.print(f"[dim]   Equipo seleccionado: {', '.join(f'@{a}' for a in sorted(unique_agents))}[/dim]")
        console.print(f"[dim]   Tareas planificadas: {len(tasks)}[/dim]")
        return True

    # ─── FASE 3: Task Runner (Ejecución Dinámica) ──────────────────────

    def _run_environment_probe(self) -> dict:
        """Ejecuta comandos de diagnóstico en la terminal para identificar capacidades del sistema.
        Guarda los resultados en env_capabilities.json.
        """
        console.print("\n[bold cyan]🔍 Ejecutando Agente Validador del Entorno (Environment Probe)...[/bold cyan]")
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
                
        cap_path = os.path.join(self.project_path, "env_capabilities.json")
        try:
            with open(cap_path, "w", encoding="utf-8") as f:
                json.dump(capabilities, f, indent=2)
            console.print(f"[green]✓ Capacidades del sistema guardadas en env_capabilities.json[/green]")
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
        console.print(f"\n       [yellow]🛠 Solicitando ejecución de comando de compilación: {cmd}[/yellow]")
        
        ret_dict = {'returncode': 0}
        output = run_terminal_command(
            cmd,
            self.state,
            silent_history=True,
            timeout=300,
            force_confirm=True,
            return_code_dict=ret_dict
        )
        return ret_dict['returncode'], output

    def _extract_and_write_files(self, content: str) -> list[str]:
        """Extrae y escribe en disco los archivos de código real desde el contenido generado."""
        created_files = []
        
        xml_matches = re.findall(r'<write_file\s+path="([^"]+)">\s*\n?(.*?)\s*\n?</write_file>', content, re.DOTALL)
        for rel_path, file_content in xml_matches:
            full_path = os.path.join(self.project_path, rel_path.strip())
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(file_content)
                created_files.append(rel_path.strip())
            except Exception as e:
                console.print(f"[red]       ✗ Error creando archivo {rel_path}: {e}[/red]")
                logger.error("Error al escribir archivo real de agente: %s", e)

        md_matches = re.findall(r'\[WRITE_FILE:\s*([^\]\s]+)\]\s*\n*```[a-zA-Z0-9_-]*\n(.*?)\n```', content, re.DOTALL)
        for rel_path, file_content in md_matches:
            rel_clean = rel_path.strip()
            if rel_clean in created_files:
                continue
            full_path = os.path.join(self.project_path, rel_clean)
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(file_content)
                created_files.append(rel_clean)
            except Exception as e:
                console.print(f"[red]       ✗ Error creando archivo {rel_clean}: {e}[/red]")
                logger.error("Error al escribir archivo real de agente: %s", e)
                
        return created_files

    def _run_task_runner(self, user_idea: str) -> None:
        """Parsea el tablero de la agencia y ejecuta cada tarea con su agente asignado."""
        board = self._read_project_file(self.board_filename)
        tasks = _parse_sprint_tasks(board)

        if not tasks:
            console.print(f"[yellow]⚠ No se encontraron tareas en el tablero {self.board_filename}.[/yellow]")
            return

        console.print(
            f"\n[bold cyan]━━━ FASE 3: 🚀 Task Runner — {len(tasks)} tareas ━━━[/bold cyan]\n"
        )

        for i, task in enumerate(tasks):
            task_num = i + 1
            agent_name = task["agent"]
            task_desc = task["task"]
            output_file = task.get("output_file", "").strip()
            task_id_str = task.get("id", f"T-{task_num:03d}")

            if not output_file or output_file == "—":
                output_file = f"TASK_{task_id_str.replace('-', '_')}.md"

            console.print(
                f"[bold white]  [{task_num}/{len(tasks)}] {task_id_str}:[/bold white] "
                f"{task_desc[:60]}{'...' if len(task_desc) > 60 else ''}"
            )
            console.print(f"[dim]       → @{agent_name} → {output_file}[/dim]")

            t0 = time.perf_counter()

            agent_prompt = self._load_agent_prompt(agent_name)
            if not agent_prompt:
                agent_prompt = f"Eres @{agent_name}, un especialista técnico del equipo de desarrollo."

            accumulated = self._build_accumulated_context()

            system = (
                f"{agent_prompt}\n\n"
                f"[TAREA ASIGNADA POR EL SCRUM MASTER]\n"
                f"ID: {task_id_str}\n"
                f"Descripción: {task_desc}\n"
                f"Tu entregable: Genera el contenido COMPLETO del archivo {output_file}.\n"
                f"Genera Markdown listo para guardar. Sé técnico, detallado y profesional.\n\n"
                f"[REGLA CRÍTICA DE SEPARACIÓN DE CÓDIGO Y DOCUMENTACIÓN]\n"
                f"Si la tarea requiere crear o modificar archivos de código real, scripts, andamiajes o configuraciones en el disco del proyecto, "
                f"debes especificar cada uno de ellos dentro de tu entregable utilizando etiquetas con la ruta del archivo. "
                f"Puedes usar cualquiera de los siguientes dos formatos:\n\n"
                f"Formato 1 (Estructura XML):\n"
                f"<write_file path=\"ruta/relativa/archivo.ext\">\n"
                f"contenido del archivo real aquí...\n"
                f"</write_file>\n\n"
                f"Formato 2 (Anotación Markdown):\n"
                f"[WRITE_FILE: ruta/relativa/archivo.ext]\n"
                f"```lenguaje\n"
                f"contenido del archivo real aquí...\n"
                f"```\n\n"
                f"Puedes incluir múltiples archivos si es necesario. El Task Runner los extraerá y creará automáticamente en el disco. "
                f"Asegúrate de que las rutas relativas sean correctas a partir de la raíz del proyecto."
            )

            user_prompt = (
                f"IDEA ORIGINAL DEL USUARIO:\n{user_idea}\n\n"
                f"DOCUMENTOS PREVIOS DEL PROYECTO:\n{accumulated}\n\n"
                f"TAREA: {task_desc}\n"
                f"Genera el contenido completo de {output_file}."
            )

            # Cargar capacidades del entorno
            capabilities_str = ""
            cap_path = os.path.join(self.project_path, "env_capabilities.json")
            if os.path.isfile(cap_path):
                capabilities_str = _safe_read(cap_path)

            env_capabilities_prompt = ""
            if capabilities_str:
                env_capabilities_prompt = (
                    f"\n\n[ENTORNO REAL DEL HOST / CONTENEDORES]\n"
                    f"Tu código debe ser 100% compatible con las siguientes herramientas y versiones reales del entorno:\n"
                    f"```json\n{capabilities_str}\n```\n"
                    f"Asegúrate de alinear las versiones de Gradle, Kotlin, Python, Room, etc., a estas capacidades. "
                    f"No propongas herramientas ni configuraciones incompatibles con estas versiones."
                )

            system = system + env_capabilities_prompt

            # Lazo de compilación y depuración (Compile & Debug Loop) - Sprint 11
            max_attempts = 3
            build_cmd = self._detect_compile_command()
            
            # [MODIFICACIÓN] Definir la estructura base de los mensajes de forma inmutable para la tarea actual
            base_messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt}
            ]
            
            last_task_result = ""
            success_task = False
            task_elapsed = 0.0
            
            short_desc = f"Tarea {task_id_str}: {task_desc[:50]}..."
            with TaskProgress(tui_engine, f"auto_task_{i}", short_desc, agent=agent_name) as progress:
                for attempt in range(1, max_attempts + 1):
                    attempt_t0 = time.perf_counter()
                    if attempt > 1:
                        console.print(f"       [bold yellow]🔄 Reintento {attempt}/{max_attempts} de compilación y corrección...[/bold yellow]")
                    
                    # [MODIFICACIÓN CORE] Clonar la lista base en una variable temporal para evitar contaminación de contexto
                    current_messages = list(base_messages)
                    if attempt > 1:
                        current_messages.append({"role": "assistant", "content": last_task_result})
                        current_messages.append({"role": "user", "content": feedback})
                    
                    task_result = _call_llm_silent(
                        self.state, current_messages,
                        provider=self.state.provider,
                        model=self.state.model
                    )
                    
                    attempt_elapsed = time.perf_counter() - attempt_t0
                    task_elapsed += attempt_elapsed
                    
                    if not task_result:
                        console.print(f"[red]       ✗ Sin respuesta de @{agent_name}[/red]")
                        if attempt == max_attempts:
                            progress.fail()
                        continue
                        
                    # Preservar el último resultado por si la compilación vuelve a fallar
                    last_task_result = task_result
                    
                    # Guardar entregable en disco e interactuar con archivos reales
                    self._write_project_file(output_file, task_result)
                    created_files = self._extract_and_write_files(task_result)
                    if created_files:
                        console.print("       [bold green]⚒ Archivos reales creados/actualizados en el disco:[/bold green]")
                        for f_path in created_files:
                            console.print(f"         [green]- {f_path}[/green]")
                            
                    if not build_cmd:
                        console.print("       [dim]ℹ No se detectó comando de compilación para este proyecto. Completando tarea.[/dim]")
                        success_task = True
                        break
                        
                    returncode, build_output = self._run_build_command(build_cmd)
                    if returncode == 0:
                        console.print("       [bold green]✓ ¡Compilación exitosa! Tarea validada con éxito.[/bold green]")
                        success_task = True
                        break
                    else:
                        if attempt < max_attempts:
                            error_lines = self._extract_relevant_errors(build_output)
                            console.print(f"       [bold red]⚠ La compilación falló (código {returncode}). Preparando feedback limpio...[/bold red]")
                            
                            # Definir la retroalimentación limpia para la siguiente iteración aislada
                            feedback = (
                                f"Tu código falló en la compilación con el siguiente error. Analiza las dependencias, corrígelo e itera:\n"
                                f"```\n{error_lines}\n```\n"
                                f"Corrige los archivos correspondientes y vuelve a generarlos utilizando las etiquetas <write_file> o [WRITE_FILE: ...]."
                            )
                        else:
                            console.print(f"       [bold red]❌ Se alcanzó el límite de {max_attempts} intentos. La compilación sigue fallando.[/bold red]")
                            success_task = False
                            progress.fail()

                if success_task and task_result:
                    tokens = estimate_tokens(task_result)
                    progress.set_tokens(tokens)

            if not task_result:
                self.metrics.append({
                    "fase": f"@{agent_name} ({task_id_str})",
                    "detalle": f"ERROR — {task_desc[:30]}",
                    "tiempo": task_elapsed,
                    "status": "❌",
                })
                continue

            tokens = estimate_tokens(task_result)
            status_symbol = "✅" if success_task else "⚠"
            status_text = "Completado con éxito" if success_task else "Completado con advertencias (fallo de compilación)"
            
            console.print(f"[green]       {status_symbol} {output_file}[/green] [dim]({tokens:,} tokens · {task_elapsed:.1f}s total)[/dim]")

            self.metrics.append({
                "fase": f"@{agent_name} ({task_id_str})",
                "detalle": f"~{tokens:,} tokens → {output_file}",
                "tiempo": task_elapsed,
                "status": status_symbol,
            })

            # Actualizar DAILY.md con handoff
            self._write_task_handoff_with_status(task_id_str, agent_name, task_desc, output_file, status_text)

        # Actualizar tablero: mover todo a DONE
        self._mark_all_done(tasks)

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
        """Mueve todas las tareas a la sección DONE del tablero de la agencia."""
        board = self._read_project_file(self.board_filename)
        if not board:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d")
        done_rows = "\n".join(
            f"| {t['id']} | {t['task']} | @{t['agent']} | {timestamp} |"
            for t in tasks
        )
        # Reemplazar la sección DONE
        done_section = (
            f"## ✅ HECHO (DONE)\n\n"
            f"| ID | Tarea | Asignado | Completado |\n"
            f"|---|---|---|---|\n"
            f"{done_rows}\n"
        )
        # Intentar reemplazar la sección DONE existente
        pattern = r"##\s*✅.*?DONE.*?\n.*?(?=\n##|\n---|\n\*|$)"
        new_board = re.sub(pattern, done_section, board, flags=re.DOTALL)
        if new_board == board:
            new_board = board + "\n" + done_section
        self._write_project_file(self.board_filename, new_board)

    # ─── Orquestación Principal ─────────────────────────────────────────

    def run(self, user_idea: str) -> str:
        """Ejecuta el pipeline completo de desarrollo autónomo dinámico."""
        total_start = time.perf_counter()

        # Header
        console.print()
        console.print(Panel(
            f"[bold white]{user_idea}[/bold white]",
            title=f"[bold purple]🪼 JELLYFISH — AGENCIA AUTÓNOMA ({self.state.active_agency.upper()})[/bold purple]",
            subtitle="[dim]PO → SM (Team Assembly) → Task Runner[/dim]",
            border_style="purple",
            padding=(1, 2),
        ))

        # AGENTE VALIDADOR DEL ENTORNO (Environment Probe - Sprint 11)
        try:
            self._run_environment_probe()
        except Exception as e:
            logger.error("Error ejecutando Environment Probe: %s", e)
            console.print(f"[yellow]⚠ No se pudo ejecutar el Environment Probe: {e}[/yellow]")

        # Fase 1: Product Owner
        if not self._run_product_owner(user_idea):
            total_time = time.perf_counter() - total_start
            self._print_summary_table(total_time)
            return "Pipeline detenido en fase de Product Owner."

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
                        screen_console.print("[bold green]✓ ¡Compilación final exitosa! El proyecto está listo.[/bold green]\n")
                        self.metrics.append({
                            "fase": "🛠 Compilación Final",
                            "detalle": f"Comando: {build_cmd}",
                            "tiempo": 0.0,
                            "status": "✅",
                        })
                    else:
                        screen_console.print(f"[bold red]⚠ La compilación final falló con código {returncode}.[/bold red]\n")
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
        return self._generate_final_summary(user_idea, total_time)

    def _print_summary_table(self, total_time: float) -> None:
        """Imprime tabla de resumen del pipeline."""
        table = Table(
            title="🪼 Resumen del Pipeline Autónomo",
            show_header=True, header_style="bold purple",
            border_style="bright_black", show_footer=True,
        )
        table.add_column("Agente / Tarea", style="bold", min_width=28)
        table.add_column("Entregable", style="dim", min_width=30)
        table.add_column("Duración", justify="right", min_width=10, footer=f"{total_time:.1f}s total")
        table.add_column("", justify="center", min_width=3)

        for m in self.metrics:
            secs = m["tiempo"]
            if secs < 10:
                dur = f"[green]{secs:.1f}s[/green]"
            elif secs < 60:
                dur = f"[yellow]{secs:.1f}s[/yellow]"
            else:
                dur = f"[red]{secs:.1f}s[/red]"
            table.add_row(m["fase"], m["detalle"], Text.from_markup(dur), m["status"])

        console.print()
        console.print(table)
        console.print()

    def _generate_final_summary(self, user_idea: str, total_time: float) -> str:
        """Genera resumen textual para el historial."""
        completed = sum(1 for m in self.metrics if m["status"] == "✅")
        summary = (
            f"🪼 **Pipeline Autónomo Completado** ({total_time:.0f}s)\n\n"
            f"**Proyecto:** {os.path.basename(self.project_path)}\n"
            f"**Fases:** {completed}/{len(self.metrics)} completadas\n"
            f"**Archivos generados:**\n"
        )
        for f in self.generated_files:
            summary += f"  - ✅ `{f}`\n"
        summary += (
            f"\n📂 Todos los archivos en: `{self.project_path}`\n"
            f"💡 Usa `/add <archivo>` para trabajar con un agente específico."
        )
        return summary
