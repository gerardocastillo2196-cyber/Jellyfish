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

# Agentes que son roles de gestión y NO deben asignarse a tareas de ejecución
_MANAGEMENT_ROLES = {"product_owner", "scrum_master", "template", "researcher"}


def _scan_available_agents() -> list[dict]:
    """Escanea agents/ y retorna nombre + primera línea de rol de cada uno."""
    agents_dir = os.path.join(AGENCY_DIR, "agents")
    agents = []
    if not os.path.isdir(agents_dir):
        return agents
    for fname in sorted(os.listdir(agents_dir)):
        if not fname.endswith(".md"):
            continue
        name = fname[:-3]  # quitar .md
        if name in _MANAGEMENT_ROLES:
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

    Busca filas de tabla Markdown en la sección TODO con formato:
    | ID | Tarea | Asignado | Estimación | Entregable |

    Retorna lista de dicts con keys: id, task, agent, estimate, output_file.
    """
    tasks = []
    in_todo = False
    header_passed = False

    for line in board_content.split("\n"):
        stripped = line.strip()

        # Detectar inicio de sección TODO
        if "TODO" in stripped.upper() and ("##" in stripped or "POR HACER" in stripped.upper()):
            in_todo = True
            header_passed = False
            continue

        # Detectar fin de sección TODO (otra sección ##)
        if in_todo and stripped.startswith("##"):
            break

        if not in_todo:
            continue

        # Saltar líneas de separador de tabla (|---|---|...)
        if stripped.startswith("|") and "---" in stripped:
            header_passed = True
            continue

        # Saltar encabezado de tabla
        if stripped.startswith("|") and not header_passed:
            header_passed = False
            continue

        # Parsear filas de datos
        if stripped.startswith("|") and header_passed:
            cells = [c.strip() for c in stripped.split("|")]
            # Filtrar celdas vacías del split
            cells = [c for c in cells if c]

            if len(cells) < 3:
                continue
            # Ignorar filas placeholder
            if cells[0] == "—" or cells[1] == "—":
                continue

            task_data = {
                "id": cells[0] if len(cells) > 0 else "",
                "task": cells[1] if len(cells) > 1 else "",
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
        """Llama al LLM en modo silencioso."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = _call_llm_silent(
            self.state, messages,
            provider=self.state.provider,
            model=self.state.model,
        )
        return response if response else ""

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
        """SM escanea agentes, arma equipo y genera SPRINT_BOARD.md."""
        console.print("\n[bold cyan]━━━ FASE 2: 📋 Scrum Master (Team Assembly) ━━━[/bold cyan]")
        t0 = time.perf_counter()

        # Escanear agentes disponibles
        available_agents = _scan_available_agents()
        agents_catalog = "\n".join(
            f"  - @{a['name']}: {a['role']}" for a in available_agents
        )
        console.print(f"[dim]   Agentes disponibles: {len(available_agents)}[/dim]")

        backlog = self._read_project_file("BACKLOG.md")
        agent_prompt = self._load_agent_prompt("scrum_master")

        system = (
            f"{agent_prompt}\n\n"
            "[INSTRUCCIONES ESPECÍFICAS PARA ESTA TAREA]\n"
            "Tu ÚNICO entregable es el contenido completo del archivo SPRINT_BOARD.md.\n"
            "Genera SOLAMENTE Markdown listo para guardar.\n\n"
            "EQUIPO DISPONIBLE (solo puedes asignar tareas a estos agentes):\n"
            f"{agents_catalog}\n\n"
            "REGLAS DE ASIGNACIÓN:\n"
            "1. Analiza las historias del BACKLOG.md y decide qué agentes se necesitan.\n"
            "2. Desglosa cada historia en tareas técnicas concretas.\n"
            "3. Asigna cada tarea al agente más adecuado usando EXACTAMENTE su @nombre.\n"
            "4. Define un archivo de entregable para cada tarea (ej: ARCHITECTURE.md, API_DESIGN.md).\n\n"
            "FORMATO OBLIGATORIO del tablero (la tabla TODO DEBE tener exactamente 5 columnas):\n"
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
            f"Genera el SPRINT_BOARD.md asignando tareas a los agentes del equipo."
        )

        with TaskProgress(tui_engine, "auto_sm", "Scrum Master: Armando equipo y planificando sprint..."):
            result = self._call_agent(system, user_prompt)

        elapsed = time.perf_counter() - t0

        if not result:
            self.metrics.append({"fase": "📋 Scrum Master", "detalle": "ERROR", "tiempo": elapsed, "status": "❌"})
            console.print("[red]✗ Scrum Master no produjo resultado.[/red]")
            return False

        self._write_project_file("SPRINT_BOARD.md", result)
        tokens = estimate_tokens(result)

        # Mostrar equipo seleccionado
        tasks = _parse_sprint_tasks(result)
        unique_agents = set(t["agent"] for t in tasks)
        console.print(f"[green]✓ SPRINT_BOARD.md[/green] [dim]({tokens:,} tokens · {elapsed:.1f}s)[/dim]")
        console.print(f"[dim]   Equipo seleccionado: {', '.join(f'@{a}' for a in sorted(unique_agents))}[/dim]")
        console.print(f"[dim]   Tareas planificadas: {len(tasks)}[/dim]")

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
        """Parsea SPRINT_BOARD.md y ejecuta cada tarea con su agente asignado."""
        board = self._read_project_file("SPRINT_BOARD.md")
        tasks = _parse_sprint_tasks(board)

        if not tasks:
            console.print("[yellow]⚠ No se encontraron tareas en el Sprint Board.[/yellow]")
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
            
            agent_messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt}
            ]
            
            success_task = False
            task_result = ""
            task_elapsed = 0.0
            
            for attempt in range(1, max_attempts + 1):
                attempt_t0 = time.perf_counter()
                if attempt > 1:
                    console.print(f"       [bold yellow]🔄 Reintento {attempt}/{max_attempts} de compilación y corrección...[/bold yellow]")
                
                progress_msg = f"@{agent_name}: {task_desc[:40]}... (Intento {attempt}/{max_attempts})"
                with TaskProgress(tui_engine, f"auto_task_{i}_{attempt}", progress_msg):
                    task_result = _call_llm_silent(
                        self.state, agent_messages,
                        provider=self.state.provider,
                        model=self.state.model
                    )
                
                attempt_elapsed = time.perf_counter() - attempt_t0
                task_elapsed += attempt_elapsed
                
                if not task_result:
                    console.print(f"[red]       ✗ Sin respuesta de @{agent_name}[/red]")
                    break
                    
                # Escribir el entregable principal
                self._write_project_file(output_file, task_result)
                
                # Extraer y escribir archivos de código real
                created_files = self._extract_and_write_files(task_result)
                if created_files:
                    console.print("       [bold green]⚒ Archivos reales creados/actualizados en el disco:[/bold green]")
                    for f_path in created_files:
                        console.print(f"         [green]- {f_path}[/green]")
                
                # Si no hay comando de compilación detectado, asumimos éxito inmediato
                if not build_cmd:
                    console.print("       [dim]ℹ No se detectó comando de compilación para este proyecto. Completando tarea.[/dim]")
                    success_task = True
                    break
                    
                # Intentar compilar el proyecto
                returncode, build_output = self._run_build_command(build_cmd)
                if returncode == 0:
                    console.print("       [bold green]✓ ¡Compilación exitosa! Tarea validada con éxito.[/bold green]")
                    success_task = True
                    break
                else:
                    if attempt < max_attempts:
                        error_lines = self._extract_relevant_errors(build_output)
                        console.print(f"       [bold red]⚠ La compilación falló (código {returncode}). Preparando feedback para reintento...[/bold red]")
                        
                        agent_messages.append({"role": "assistant", "content": task_result})
                        
                        feedback = (
                            f"Tu código falló en la compilación con el siguiente error. Analiza las dependencias, corrígelo e itera:\n"
                            f"```\n{error_lines}\n```\n"
                            f"Corrige los archivos correspondientes y vuelve a generarlos utilizando las etiquetas <write_file> o [WRITE_FILE: ...]."
                        )
                        agent_messages.append({"role": "user", "content": feedback})
                    else:
                        console.print(f"       [bold red]❌ Se alcanzó el límite de {max_attempts} intentos. La compilación sigue fallando.[/bold red]")
                        success_task = False

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
        """Mueve todas las tareas a la sección DONE del Sprint Board."""
        board = self._read_project_file("SPRINT_BOARD.md")
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
        self._write_project_file("SPRINT_BOARD.md", new_board)

    # ─── Orquestación Principal ─────────────────────────────────────────

    def run(self, user_idea: str) -> str:
        """Ejecuta el pipeline completo de desarrollo autónomo dinámico."""
        total_start = time.perf_counter()

        # Header
        console.print()
        console.print(Panel(
            f"[bold white]{user_idea}[/bold white]",
            title="[bold purple]🪼 JELLYFISH — AGENCIA AUTÓNOMA (Scrum Dinámico)[/bold purple]",
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

        # Fase 3: Task Runner (Ejecución Dinámica)
        self._run_task_runner(user_idea)

        # Compilación automática final del pipeline (Sprint 11)
        build_cmd = self._detect_compile_command()
        if build_cmd:
            console.print("\n[bold yellow]🛠 Ejecutando compilación de validación final del proyecto...[/bold yellow]")
            returncode, build_output = self._run_build_command(build_cmd)
            if returncode == 0:
                console.print("[bold green]✓ ¡Compilación final exitosa! El proyecto está listo.[/bold green]\n")
                self.metrics.append({
                    "fase": "🛠 Compilación Final",
                    "detalle": f"Comando: {build_cmd}",
                    "tiempo": 0.0,
                    "status": "✅",
                })
            else:
                console.print(f"[bold red]⚠ La compilación final falló con código {returncode}.[/bold red]\n")
                self.metrics.append({
                    "fase": "🛠 Compilación Final",
                    "detalle": "Fallo de compilación",
                    "tiempo": 0.0,
                    "status": "❌",
                })

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
