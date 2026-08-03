import os
import re
import time
import logging
from rich.console import Console
from rich.prompt import Confirm
from core.tui import tui_engine, TaskProgress
from core.state import estimate_tokens
from core.utils import _safe_read
from core.llm_engine import _call_llm_silent, LocalLLMTimeoutError
from core.terminal import run_terminal_command
from core.agents.registry import AgentRegistry
from core.skills.registry import SkillRegistry
from core.event_bus import event_bus, EventType

logger = logging.getLogger("jellyfish.orchestration.task_runner")
console = Console()

MAX_RETRIES = 3  # FASE 4: Límite de escalada para reintentos automáticos

SENTINEL_HEALER_SYSTEM = """Eres @Sentinel, el agente experto de control de calidad, depuración y auto-curación de Jellyfish OS.
Tu misión es recibir una tarea técnica, los archivos de código que se generaron, y el log detallado del error de compilación, sintaxis o DoD.
Debes analizar el log de error para diagnosticar exactamente qué causó el fallo.

Tienes tres opciones de respuesta. Debes elegir la más adecuada y responder en el formato exacto:

1) AUTO_FIX: Si puedes corregir el código del archivo que falló directamente (ej: añadir un import, corregir sintaxis YAML, cambiar una línea de código).
Formato de respuesta:
[AUTO_FIX]
Explicación breve de la corrección.
<write_file path="ruta/del/archivo.ext">
contenido del archivo corregido...
</write_file>

2) FEEDBACK: Si la corrección requiere lógica compleja en múltiples archivos o reestructuraciones que debe hacer el desarrollador original.
Formato de respuesta:
[FEEDBACK]
Instrucciones detalladas paso a paso para corregir el error en el próximo intento.

3) ASK_USER: Si necesitas aclarar requisitos críticos, decisiones de diseño o permisos especiales del usuario.
Formato de respuesta:
[ASK_USER]
Escribe la pregunta específica y directa para el usuario.
"""

def topological_sort(tasks: list[dict]) -> list[dict]:
    """Ordena las tareas del sprint respetando sus dependencias declaradas (DAG)."""
    task_map = {t["id"]: t for t in tasks}
    adj = {t["id"]: [] for t in tasks}
    in_degree = {t["id"]: 0 for t in tasks}
    
    for t in tasks:
        deps = t.get("dependencies", [])
        for dep in deps:
            if dep in task_map:
                adj[dep].append(t["id"])
                in_degree[t["id"]] += 1
                
    from collections import deque
    queue = deque([t["id"] for t in tasks if in_degree[t["id"]] == 0])
    
    sorted_ids = []
    while queue:
        u = queue.popleft()
        sorted_ids.append(u)
        for v in adj[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)
                
    if len(sorted_ids) != len(tasks):
        logger.warning("Ciclo detectado en dependencias de tareas, usando orden original.")
        return tasks
        
    return [task_map[tid] for tid in sorted_ids]


class TaskRunnerPhase:
    """Fase 3 del desarrollo autónomo: Task Runner, ReAct loop y control transaccional."""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def _build_valid_fallback_content(self, task_desc: str, output_file: str) -> str:
        """Genera contenido de andamiaje sintácticamente válido según la extensión del archivo."""
        ext = os.path.splitext(output_file)[1].lower()
        if ext == ".py":
            return (
                f"# {task_desc}\n"
                '"""\nComponente o especificación andamiada automáticamente por Jellyfish OS.\n"""\n\n'
                "def main():\n"
                '    """Punto de entrada principal para el componente."""\n'
                "    pass\n\n"
                'if __name__ == "__main__":\n'
                "    main()\n"
            )
        elif ext in (".js", ".ts", ".jsx", ".tsx"):
            return (
                f"// {task_desc}\n"
                "/**\n * Componente o especificación andamiada automáticamente por Jellyfish OS.\n */\n"
                "export function main() {\n"
                "  return true;\n"
                "}\n"
            )
        elif ext == ".dart":
            return (
                f"// {task_desc}\n"
                "void main() {\n"
                "  // Componente andamiado automáticamente\n"
                "}\n"
            )
        elif ext in (".html", ".xml", ".vue"):
            return f"<!-- {task_desc} -->\n<!-- Componente andamiado automáticamente para {output_file} -->\n"
        elif ext == ".json":
            import json
            return json.dumps({"description": task_desc, "status": "scaffolding_fallback"}, indent=2)
        else:
            return f"# {task_desc}\n\nComponente o especificación andamiada automáticamente para {output_file}\n"

    def _reconcile_missing_docker_context_files(self, created_files: list[str]) -> None:
        """
        Escanea los Dockerfiles recién creados para buscar instrucciones COPY/ADD.
        Si alguna instrucción copia un archivo local que no existe en el contexto de construcción,
        crea un archivo placeholder mínimo para evitar fallos de compilación prematuros en Sprint 0.
        """
        # Auto-crear Dockerfiles ya no es necesario gracias a la detección dirigida en _detect_build_command
        pass

        for path in created_files:
            if "dockerfile" in path.lower():
                abs_path = os.path.join(self.orchestrator.project_path, path)
                if not os.path.isfile(abs_path):
                    continue
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    
                    dockerfile_dir = os.path.dirname(abs_path)
                    for line in lines:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if line.upper().startswith("COPY ") or line.upper().startswith("ADD "):
                            parts = line.split()
                            if len(parts) < 3:
                                continue
                            
                            has_from = False
                            sources = []
                            for part in parts[1:-1]:
                                if part.startswith("--from="):
                                    has_from = True
                                elif part.startswith("--"):
                                    continue
                                else:
                                    sources.append(part)
                            
                            if has_from:
                                continue
                                
                            for src in sources:
                                src_clean = src.replace("*", "").replace("?", "")
                                if not src_clean or src_clean in (".", "/"):
                                    continue
                                
                                target_file_path = os.path.join(dockerfile_dir, src_clean)
                                if not os.path.exists(target_file_path):
                                    os.makedirs(os.path.dirname(target_file_path), exist_ok=True)
                                    if src_clean.endswith("package.json"):
                                        with open(target_file_path, "w", encoding="utf-8") as pf:
                                            pf.write('{\n  "name": "placeholder",\n  "version": "1.0.0"\n}\n')
                                    elif src_clean.endswith("pubspec.yaml"):
                                        with open(target_file_path, "w", encoding="utf-8") as pf:
                                            pf.write("name: placeholder\nversion: 1.0.0\nenvironment:\n  sdk: '>=3.0.0 <4.0.0'\n")
                                    elif src_clean.endswith("requirements.txt"):
                                        with open(target_file_path, "w", encoding="utf-8") as pf:
                                            pf.write("# Placeholder base\n")
                                    else:
                                        with open(target_file_path, "w", encoding="utf-8") as pf:
                                            pf.write("")
                                    logger.info("Auto-creado archivo de contexto Docker faltante: %s", target_file_path)
                                    console.print(f"       ⚡ Auto-creado placeholder requerido para Docker: [dim]{src_clean}[/dim]")
                except Exception as e:
                    logger.error("Error al reconciliar archivos de contexto Docker: %s", e)

    def _get_user_input_nonblocking(self, prompt: str) -> str:
        """Obtiene respuesta del usuario usando prompt_toolkit con un timeout de 60s."""
        import asyncio
        from prompt_toolkit import PromptSession
        from prompt_toolkit.patch_stdout import patch_stdout
        from core.terminal import screen_console as scr_console

        session = PromptSession()
        async def get_input():
            with patch_stdout():
                return await session.prompt_async(prompt)

        try:
            return asyncio.run(asyncio.wait_for(get_input(), timeout=60))
        except TimeoutError:
            scr_console.print("\n✗ Tiempo de espera agotado (60s). Asumiendo deny/skip por defecto.")
            return "deny/skip"
        except (KeyboardInterrupt, EOFError):
            scr_console.print("\n✗ Entrada interrumpida.")
            return "deny/skip"

    def _run_sentinel_auto_healing(
        self,
        task_id: str,
        agent_name: str,
        task_desc: str,
        output_file: str,
        error_log: str,
        created_files: list[str]
    ) -> tuple[str, str]:
        """
        Invoca autónomamente a @Sentinel para diagnosticar y auto-corregir el error.
        Retorna una tupla: (resolución, feedback/mensaje)
        """
        from core.orchestration.build_healer import run_sentinel_auto_healing
        return run_sentinel_auto_healing(
            self.orchestrator,
            task_id,
            agent_name,
            task_desc,
            output_file,
            error_log,
            created_files,
            self._get_user_input_nonblocking
        )

    def _run_strict_subprocess_dod_validation(self, project_path: str, created_files: list[str], output_file: str) -> tuple[bool, str]:
        """Ejecuta una validación estricta de compilación/sintaxis en un subproceso seguro (subprocess.run).
        
        Verifica activamente que los archivos generados o modificados no rompan el entorno
        e intenta compilar/instalar/lintear según el tipo de archivo.
        """
        import subprocess
        
        files_to_check = set(created_files)
        if output_file:
            files_to_check.add(output_file)
            
        real_files = []
        for rel_f in files_to_check:
            abs_f = os.path.join(project_path, rel_f.strip().replace("`", ""))
            if os.path.isfile(abs_f):
                real_files.append((rel_f, abs_f))
                
        if not real_files:
            return True, "No se encontraron archivos en disco para validar por subproceso."

        for rel_f, abs_f in real_files:
            ext = os.path.splitext(abs_f)[1].lower()
            basename = os.path.basename(abs_f).lower()
            
            # 1. Archivos Python (.py)
            if ext == ".py":
                try:
                    res = subprocess.run(
                        ["python3", "-m", "py_compile", abs_f],
                        capture_output=True, text=True, timeout=15, cwd=project_path
                    )
                    if res.returncode != 0:
                        err_msg = (res.stderr or res.stdout).strip()
                        return False, f"RECHAZO DOD (COMPILACIÓN PYTHON): El archivo '{rel_f}' falló la verificación de sintaxis (py_compile):\n{err_msg}"
                except Exception as e:
                    logger.warning("Error ejecutando py_compile en %s: %s", rel_f, e)

            # 2. Archivos JSON (.json)
            elif ext == ".json":
                try:
                    res = subprocess.run(
                        ["python3", "-m", "json.tool", abs_f],
                        capture_output=True, text=True, timeout=15, cwd=project_path
                    )
                    if res.returncode != 0:
                        err_msg = (res.stderr or res.stdout).strip()
                        return False, f"RECHAZO DOD (SINTAXIS JSON): El archivo '{rel_f}' contiene JSON malformado:\n{err_msg}"
                except Exception as e:
                    logger.warning("Error ejecutando json.tool en %s: %s", rel_f, e)

            # 3. Archivos JavaScript / TypeScript (.js, .jsx, .ts, .tsx)
            elif ext in (".js", ".jsx", ".ts", ".tsx"):
                try:
                    res = subprocess.run(
                        ["node", "--check", abs_f],
                        capture_output=True, text=True, timeout=15, cwd=project_path
                    )
                    if res.returncode != 0:
                        err_msg = (res.stderr or res.stdout).strip()
                        return False, f"RECHAZO DOD (SINTAXIS JS/TS): El archivo '{rel_f}' falló la verificación de sintaxis (node --check):\n{err_msg}"
                except FileNotFoundError:
                    pass
                except Exception as e:
                    logger.warning("Error ejecutando node --check en %s: %s", rel_f, e)

            # 4. Archivos Shell (.sh)
            elif ext == ".sh":
                try:
                    res = subprocess.run(
                        ["bash", "-n", abs_f],
                        capture_output=True, text=True, timeout=15, cwd=project_path
                    )
                    if res.returncode != 0:
                        err_msg = (res.stderr or res.stdout).strip()
                        return False, f"RECHAZO DOD (SINTAXIS BASH): El script '{rel_f}' falló la verificación bash -n:\n{err_msg}"
                except Exception as e:
                    logger.warning("Error ejecutando bash -n en %s: %s", rel_f, e)

            # 5. Archivos de Contenedor (docker-compose.yml / yaml)
            elif basename in ("docker-compose.yml", "docker-compose.yaml"):
                try:
                    res = subprocess.run(
                        ["docker", "compose", "config", "-q"],
                        capture_output=True, text=True, timeout=15, cwd=project_path
                    )
                    if res.returncode != 0 and res.stderr:
                        err_msg = res.stderr.strip()
                        return False, f"RECHAZO DOD (SINTAXIS DOCKER COMPOSE): El archivo '{rel_f}' falló la validación 'docker compose config':\n{err_msg}"
                except FileNotFoundError:
                    pass
                except Exception as e:
                    logger.warning("Error ejecutando docker compose config: %s", e)

        return True, "Validación de compilación y ejecución por subproceso (DoD) aprobada."

    def run(self, user_idea: str) -> None:
        """Parsea el tablero de la agencia y ejecuta cada tarea con su agente asignado."""
        tasks = []
        try:
            import json
            json_filename = self.orchestrator.board_filename.replace(".md", ".json")
            json_path = os.path.join(self.orchestrator.project_path, json_filename)
            if os.path.isfile(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    tasks = json.load(f)
                    console.print(f"[dim]       ⚙ Tablero JSON estructurado cargado exitosamente.[/dim]")
        except Exception as je:
            logger.warning("Error leyendo tablero JSON: %s. Reintentando por Markdown.", je)

        if not tasks:
            from core.project_orchestrator import _parse_sprint_tasks
            board = self.orchestrator._read_project_file(self.orchestrator.board_filename)
            tasks = _parse_sprint_tasks(board)

        if not tasks:
            console.print(f"⚠ No se encontraron tareas en el tablero {self.orchestrator.board_filename}.")
            return

        # FASE 2: Ordenamiento topológico del Grafo Dirigido (DAG)
        tasks = topological_sort(tasks)

        console.print(
            f"\n━━━ FASE 3: 🚀 Task Runner — {len(tasks)} tareas ordenadas por dependencias (DAG) ━━━\n"
        )

        for i, task in enumerate(tasks):
            task_num = i + 1
            agent_name = task["agent"].replace("`", "").strip()
            original_task_desc = task["task"]
            task_desc = original_task_desc
            output_file = task.get("output_file", "").strip().replace("`", "")
            task_id_str = task.get("id", f"T-{task_num:03d}").replace("*", "").replace("`", "").strip()

            if not output_file or output_file == "—":
                output_file = f"TASK_{task_id_str.replace('-', '_')}.md"

            files_to_generate = [f.strip() for f in output_file.split(",")] if "," in output_file else [output_file]

            # FASE 2 / FASE 3: Verificar que las dependencias de la tarea estén completadas en el Blackboard (H-03)
            deps_ok = True
            missing_dep = ""
            for dep_id in task.get("dependencies", []):
                dep_status = self.orchestrator.state.blackboard.get(f"task_status_{dep_id}")
                if dep_status != "completed":
                    deps_ok = False
                    missing_dep = dep_id
                    break
            if not deps_ok:
                self.orchestrator.state.blackboard.set(f"task_status_{task_id_str}", "blocked")
                task["status"] = "BLOCKED"
                task["state"] = "BLOCKED"
                self.orchestrator._save_board(tasks)
                event_bus.publish(EventType.TASK_BLOCKED, {
                    "task_id": task_id_str,
                    "missing_dep": missing_dep,
                    "agent_name": agent_name
                })
                self.orchestrator.metrics.append({
                    "fase": f"@{agent_name} ({task_id_str})",
                    "detalle": f"Bloqueada por dependencia: {missing_dep}",
                    "tiempo": 0.0,
                    "status": "⚠️ BLOCKED",
                })
                continue

            # Omitir tareas completadas o fallidas si estamos reanudando
            if task.get("status") in ("DONE", "HECHO", "FAILED") or task.get("state") in ("DONE", "HECHO", "FAILED"):
                status_lbl = "YA COMPLETADO" if task.get("status") in ("DONE", "HECHO") else "MARCADA COMO FALLIDA"
                console.print(
                    f"[bold green]  [{task_num}/{len(tasks)}] {task_id_str}:[/bold green] "
                    f"[dim]{status_lbl} (Saltando ejecución)[/dim]"
                )
                self.orchestrator.state.blackboard.set(f"task_status_{task_id_str}", "completed" if "COMPLETADO" in status_lbl else "failed")
                continue

            # FASE 4: Bucle de Retroalimentación Autónoma (Auto-Retry)
            task_retries = 0
            last_error_log = ""
            success_task = False
            task_result = ""
            created_files = []

            while task_retries < MAX_RETRIES:
                # FASE 1 & FASE 3: Actualizar estados de agente y TUI global
                event_bus.publish(EventType.AGENT_STATUS_CHANGE, {"agent": agent_name, "status": "Ejecutando"})
                self.orchestrator.state.global_status = "PROCESS"

                event_bus.publish(EventType.TASK_STARTED, {
                    "task_num": task_num,
                    "total_tasks": len(tasks),
                    "task_id": task_id_str,
                    "task_retries": task_retries,
                    "max_retries": MAX_RETRIES,
                    "task_desc": task_desc,
                    "agent_name": agent_name,
                    "output_file": output_file
                })

                # Realizar git snapshot de transaccionalidad via micro-branching
                use_microbranch = False
                original_branch = ""
                if self.orchestrator._is_git_repo():
                    use_microbranch, original_branch = self.orchestrator._git_start_task_branch(task_id_str)
                    snapshot_created = not use_microbranch
                else:
                    snapshot_created = self.orchestrator._git_commit_snapshot(task_id_str)

                t0 = time.perf_counter()

                agent_prompt = self.orchestrator._load_agent_prompt(agent_name)
                if not agent_prompt:
                    agent_prompt = f"Eres @{agent_name}, un especialista técnico del equipo de desarrollo."

                # Sprint 12 — Resolver agente Python para hooks de ciclo de vida
                py_agent = AgentRegistry.get(agent_name)
                task_context = {
                    "project_path": self.orchestrator.project_path,
                    "output_file": output_file,
                    "task_id": task_id_str,
                    "agent_name": agent_name,
                }

                # Sprint 12 — Hook pre_execute
                if py_agent:
                    try:
                        py_agent.pre_execute(task, task_context)
                    except Exception as pre_err:
                        logger.warning("pre_execute de @%s falló: %s", agent_name, pre_err)

                # Sprint 12 — Inyección selectiva de skills
                skills_context = ""
                relevant_skills = SkillRegistry.get_skills_for_task(
                    task_desc,
                    agency=getattr(self.orchestrator.state, "active_agency", "")
                )
                if relevant_skills:
                    skill_blocks = []
                    for sk in relevant_skills:
                        try:
                            skill_blocks.append(f"### SKILL: {sk.name}\n{sk.get_instructions()}")
                        except Exception as sk_err:
                            logger.warning("Skill '%s' falló en get_instructions: %s", sk.name, sk_err)
                    if skill_blocks:
                        skills_context = (
                            "\n\n[SKILLS RELEVANTES PARA ESTA TAREA]\n"
                            + "\n\n".join(skill_blocks)
                            + "\n"
                        )

                accumulated = self.orchestrator._build_intelligent_context(task_desc, output_file)

                system = (
                    f"{agent_prompt}\n\n"
                    f"{skills_context}"
                    f"[TAREA ASIGNADA POR EL SCRUM MASTER]\n"
                    f"ID: {task_id_str}\n"
                    f"Descripción: {task_desc}\n"
                    f"Tu entregable: Genera el contenido COMPLETO del archivo {output_file}.\n"
                    f"REGLA CRÍTICA DE RESPUESTA: NO des explicaciones verbales, saludos ni conclusiones. Sé extremadamente conciso y directo.\n"
                    f"REGLA CRÍTICA DE COMPLETITUD: NO trunques el código. Si el archivo es grande y necesitas más espacio, no te preocupes, el sistema te pedirá que continúes. "
                    f"Sin embargo, si has terminado de generar TODO el archivo y código correspondiente de forma exitosa, tu última línea debe ser exactamente la cadena de texto: [TAREA_COMPLETADA]\n\n"
                    f"[CAPACIDAD DE EJECUCIÓN DIRECTA (ReAct - Mejora 31)]\n"
                    f"Tienes la capacidad de ejecutar comandos en el terminal de forma autónoma durante esta tarea. "
                    f"Si necesitas verificar si un archivo existe, ver su contenido, verificar versiones, "
                    f"ejecutar un script de prueba o verificar la compilación antes de entregar, puedes hacerlo respondiendo únicamente con el comando envuelto en la etiqueta <run_command>.\n"
                    f"Ejemplo: <run_command>npm test</run_command> o <run_command>python3 -c \"import os; print(os.listdir('.'))\"</run_command>.\n"
                    f"El sistema ejecutará el comando y te devolverá el output. Después de recibir la respuesta, podrás continuar redactando el entregable o solicitar más comandos.\n\n"
                    f"[REGLAS DE AUTO-CORRECCIÓN DOD]\n"
                    f"Si el entregable es rechazado por control de calidad (DoD), recibirás retroalimentación específica. "
                    f"Deberás corregir los problemas indicados inmediatamente sin dejar placeholders, TODOs vacíos o secciones incompletas.\n\n"
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
                    f"Asegúrate de que las rutas relativas sean correctas a partir de la raíz del proyecto.\n\n"
                    f"[REGLA DE DECISIÓN TECNOLÓGICA]\n"
                    f"Si la tecnología no ha sido definida de forma explícita, asume los estándares modernos de la industria recomendados para este tipo de aplicación (ej. Python/FastAPI/Node.js para backend, Flutter/React Native para móvil, PostgreSQL/SQLite para BD, Docker/Docker-Compose para infraestructura). Procede a generar el código y entregables completos sin detenerte.\n\n"
                    f"[REGLAS DE INFRAESTRUCTURA]\n"
                    f"REGLA ESTRUCTURAL ESTRICTA: NUNCA referencies un directorio, archivo o contexto de compilación (ej. en docker-compose) sin haber verificado primero que existe usando comandos de consola. Si configuras un servicio que requiere compilación (build), ESTÁS OBLIGADO a crear el `Dockerfile` correspondiente en la ruta exacta que especificaste y a generar el `package.json` o `requirements.txt` base si no existen. NO puedes dar una tarea de DevOps por terminada si faltan los archivos de construcción.\n\n"
                    f"[NEGATIVE PROMPT GLOBAL: DIRECTIVA ANTI-ARCHIVOS HUÉRFANOS]\n"
                    f"🚫 PROHIBIDO ESTRICTAMENTE CREAR ARCHIVOS HUÉRFANOS.\n"
                    f"Está prohibido crear componentes, rutas, controladores, servicios, módulos o utilidades aislados que no estén conectados al sistema.\n"
                    f"REGLA DE INTEGRACIÓN OBLIGATORIA: Cada vez que generes un nuevo archivo o componente (ej. una nueva vista React, un módulo Python, una ruta Express, un controlador, etc.), ESTÁS OBLIGADO a importar e integrar dicho componente en el archivo de entrada principal del proyecto (ej. App.tsx, index.js, server.js, main.py, routes/index.ts, urls.py) en el MISMO paso o entrega.\n"
                    f"No se dará ninguna tarea por completada si el componente nuevo no está exportado, importado y montado activamente en la aplicación principal."
                )

                user_prompt = (
                    f"IDEA ORIGINAL DEL USUARIO:\n{user_idea}\n\n"
                    f"DOCUMENTOS PREVIOS DEL PROYECTO:\n{accumulated}\n\n"
                    f"TAREA: {task_desc}\n"
                    f"Genera el contenido completo de {output_file}."
                )

                # Cargar capacidades del entorno
                capabilities_str = ""
                cap_path = os.path.join(self.orchestrator.project_path, "env_capabilities.json")
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

                # Auto-Validación de Infraestructura
                task_desc_lower = task_desc.lower()
                if any(kw in task_desc_lower for kw in ["docker", "compose", "servidor", "despliegue"]):
                    infra_validation_prompt = (
                        "\n\n[INSTRUCCIÓN DE AUTO-VALIDACIÓN DE INFRAESTRUCTURA]\n"
                        "Dado que esta tarea involucra docker, compose, servidor o despliegue, ESTÁS OBLIGADO "
                        "a ejecutar obligatoriamente 'docker compose config' o 'docker compose build --no-cache' "
                        "usando la etiqueta <run_command> como un paso ReAct para validar la configuración o compilación "
                        "de los contenedores ANTES de emitir tu entregable final y finalizar la tarea con [TAREA_COMPLETADA]."
                    )
                    system = system + infra_validation_prompt

                last_task_result = ""
                task_elapsed = 0.0
                feedback = ""
                short_desc = f"Tarea {task_id_str}: {task_desc[:40]}..."

                # Lazo de compilación y depuración
                max_attempts = 5
                build_cmd = self.orchestrator._detect_compile_command()

                # Hook pre-flight check para ARCHITECTURE.md y JELLYFISH_HISTORY.md
                is_modifying_target_docs = (
                    output_file.lower() in ("architecture.md", "jellyfish_history.md") or
                    any(doc in task_desc.lower() for doc in ("architecture.md", "jellyfish_history.md"))
                )
                if is_modifying_target_docs:
                    from core.project_manager import get_environment_and_dependencies_summary
                    summary_context = get_environment_and_dependencies_summary(self.orchestrator.state)
                    system = system + "\n\n" + summary_context

                base_messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt}
                ]

                try:
                    with TaskProgress(tui_engine, f"auto_task_{i}", short_desc, agent=agent_name) as progress:
                        for attempt in range(1, max_attempts + 1):
                            attempt_t0 = time.perf_counter()

                            task_result = ""
                            created_files = []
                            attempt_success = True

                            for idx_sub, sub_file in enumerate(files_to_generate):
                                sub_task_context = {
                                    "project_path": self.orchestrator.project_path,
                                    "output_file": sub_file,
                                    "task_id": task_id_str,
                                    "agent_name": agent_name,
                                }

                                if py_agent:
                                    try:
                                        py_agent.pre_execute(task, sub_task_context)
                                    except Exception as pre_err:
                                        logger.warning("pre_execute de @%s falló: %s", agent_name, pre_err)

                                accumulated = self.orchestrator._build_intelligent_context(task_desc, sub_file)

                                # Adaptar System Prompt para el sub_file específico
                                sub_system = system
                                sub_system = sub_system.replace(
                                    f"Tu entregable: Genera el contenido COMPLETO del archivo {output_file}.",
                                    f"Tu entregable: Genera el contenido COMPLETO del archivo {sub_file}."
                                )
                                if f"Genera el contenido COMPLETO del archivo {sub_file}" not in sub_system:
                                    sub_system += f"\n\n[REGLA ADICIONAL]\nTu entregable: Genera el contenido COMPLETO del archivo '{sub_file}'."

                                if len(files_to_generate) > 1:
                                    sub_system += f"\n\n[INSTRUCCIÓN SECUENCIAL MULTI-ARCHIVO]\nEstás generando los archivos del proyecto uno por uno. El archivo actual a generar es: '{sub_file}'."
                                    if idx_sub > 0:
                                        already_done = ", ".join(files_to_generate[:idx_sub])
                                        sub_system += f" Ya has generado previamente los archivos: {already_done}. Concéntrate ÚNICAMENTE en generar el código completo para '{sub_file}'."

                                sub_user_prompt = (
                                    f"IDEA ORIGINAL DEL USUARIO:\n{user_idea}\n\n"
                                    f"DOCUMENTOS PREVIOS DEL PROYECTO:\n{accumulated}\n\n"
                                    f"TAREA: {task_desc}\n"
                                    f"Genera el contenido completo de {sub_file}."
                                )

                                sub_base_messages = [
                                    {"role": "system", "content": sub_system},
                                    {"role": "user", "content": sub_user_prompt}
                                ]

                                current_messages = list(sub_base_messages)
                                if attempt > 1 and feedback:
                                    current_messages.append({"role": "user", "content": f"[RETROALIMENTACIÓN DE INTENTO ANTERIOR]\n{feedback}"})

                                sub_task_result = ""
                                react_messages = list(current_messages)
                                max_react_steps = 15

                                from core.config import resolve_agent_role_category

                                if attempt == 1 and py_agent and resolve_agent_role_category(agent_name) == "executor" and hasattr(py_agent, "execute_local_microtask_loop"):
                                    try:
                                        micro_context = {
                                            "project_path": self.orchestrator.project_path,
                                            "accumulated_context": accumulated,
                                            "output_file": sub_file
                                        }
                                        local_code = py_agent.execute_local_microtask_loop(self.orchestrator.state, task, micro_context)
                                        if local_code and local_code.strip():
                                            sub_task_result = f"[WRITE_FILE: {sub_file}]\n```\n{local_code}\n```\n[TAREA_COMPLETADA]"
                                    except Exception as micro_err:
                                        logger.warning("Error en execute_local_microtask_loop de @%s: %s. Continuando flujo normal.", agent_name, micro_err)

                                if not sub_task_result:
                                    for step in range(1, max_react_steps + 1):
                                        response_chunk = _call_llm_silent(
                                            self.orchestrator.state, react_messages,
                                            agent_name=agent_name
                                        )

                                        if not response_chunk:
                                            break

                                        # Interceptor HITL
                                        if "[ASK_USER:" in response_chunk:
                                            ask_match = re.search(r'\[ASK_USER:\s*(.*?)\]', response_chunk, re.DOTALL)
                                            question = ask_match.group(1).strip() if ask_match else response_chunk.split("[ASK_USER:")[1].strip()

                                            console.print("\n[bold yellow]──────────────────────────────────────────────────────────────────────[/bold yellow]")
                                            console.print(f"[bold yellow]🤔 CONSULTA HITL DE @{agent_name}:[/bold yellow]")
                                            console.print(f"[yellow]{question}[/yellow]")
                                            console.print("[bold yellow]──────────────────────────────────────────────────────────────────────[/bold yellow]")

                                            user_response = self._get_user_input_nonblocking("✍ Escribe tu respuesta: ")

                                            react_messages.append({"role": "assistant", "content": response_chunk})
                                            user_msg = {"role": "user", "content": f"Respuesta del usuario a tu consulta: {user_response}"}
                                            react_messages.append(user_msg)
                                            current_messages.append({"role": "assistant", "content": response_chunk})
                                            current_messages.append(user_msg)
                                            continue

                                        # Detectar comandos
                                        cmd_match = re.search(r'<run_command>(.*?)</run_command>', response_chunk, re.DOTALL)
                                        if cmd_match:
                                            cmd_to_run = cmd_match.group(1).strip()
                                            console.print(f"       ⚙ Agente @{agent_name} ejecutando comando ReAct: {cmd_to_run} (Archivo: {sub_file})")

                                            ret_dict = {'returncode': 0}
                                            cmd_output = run_terminal_command(
                                                cmd_to_run,
                                                self.orchestrator.state,
                                                silent_history=True,
                                                timeout=120,
                                                force_confirm=False,
                                                return_code_dict=ret_dict
                                            )

                                            urgency_prompt = f"Analiza el resultado y continúa redactando el archivo '{sub_file}' o solicita más comandos si es necesario."
                                            if step >= max_react_steps - 3:
                                                urgency_prompt = f"Te quedan pocos pasos ReAct. Genera el entregable final del archivo '{sub_file}' AHORA usando etiquetas."

                                            react_messages.append({"role": "assistant", "content": response_chunk})
                                            react_messages.append({
                                                "role": "user",
                                                "content": f"Resultado de ejecución (Código {ret_dict['returncode']}):\n```\n{cmd_output[:3000]}\n```\n{urgency_prompt}"
                                            })
                                            continue

                                        sub_task_result += response_chunk

                                        if "[TAREA_COMPLETADA]" in response_chunk or "[TAREA_COMPLETADA]" in sub_task_result:
                                            sub_task_result = sub_task_result.replace("[TAREA_COMPLETADA]", "").strip()
                                            break

                                        if step < max_react_steps:
                                            react_messages.append({"role": "assistant", "content": response_chunk})
                                            react_messages.append({
                                                "role": "user",
                                                "content": "Tu respuesta anterior se cortó. Continúa exactamente desde donde te quedaste. Si terminaste, finaliza con: [TAREA_COMPLETADA]"
                                            })

                                if not sub_task_result:
                                    attempt_success = False
                                    last_error_log = f"El modelo LLM no generó contenido para la tarea {task_id_str} ({sub_file})."
                                    break

                                if py_agent:
                                    try:
                                        sub_task_result = py_agent.post_execute(sub_task_result, sub_task_context)
                                    except Exception as post_err:
                                        logger.warning("post_execute de @%s falló: %s", agent_name, post_err)

                                # Escribir a disco
                                self.orchestrator._write_project_file(sub_file, sub_task_result)
                                sub_created = self.orchestrator._extract_and_write_files(sub_task_result)

                                if not sub_created:
                                    sub_created = [sub_file]

                                created_files.extend(sub_created)
                                task_result += f"\n\n[FILE: {sub_file}]\n{sub_task_result}"

                            attempt_elapsed = time.perf_counter() - attempt_t0
                            task_elapsed += attempt_elapsed

                            if not attempt_success:
                                if attempt == max_attempts:
                                    for sub_file in files_to_generate:
                                        full_sub_path = os.path.join(self.orchestrator.project_path, sub_file)
                                        if not os.path.exists(full_sub_path):
                                            fallback_content = self._build_valid_fallback_content(task_desc, sub_file)
                                            self.orchestrator._write_project_file(sub_file, fallback_content)
                                            created_files.append(sub_file)
                                            task_result += f"\n\n[FILE: {sub_file}]\n{fallback_content}"
                                else:
                                    continue

                            # Auto-reconciliación de archivos copiados en Dockerfiles
                            self._reconcile_missing_docker_context_files(created_files)

                            # Pre-chequeo de infraestructura DoD simplificado (ya validado por la detección dirigida)
                            infra_ok = True
                            infra_error_msg = ""

                            # Validación de sintaxis estática y ejecución real por subproceso
                            syntax_ok = True
                            syntax_error_msg = ""
                            from core.orchestration.code_analyzer import validate_syntax
                            for f_created in created_files:
                                abs_f_path = os.path.join(self.orchestrator.project_path, f_created)
                                if os.path.isfile(abs_f_path):
                                    s_ok, s_err = validate_syntax(abs_f_path)
                                    if not s_ok:
                                        syntax_ok = False
                                        syntax_error_msg = s_err
                                        break

                            # Validación estricta en subproceso real (subprocess.run)
                            exec_subproc_ok, exec_subproc_reason = self._run_strict_subprocess_dod_validation(
                                self.orchestrator.project_path, created_files, output_file
                            )

                            # DoD Check sin compilación general
                            if not build_cmd:
                                if not infra_ok:
                                    dod_approved = False
                                    dod_reason = infra_error_msg
                                elif not syntax_ok:
                                    dod_approved = False
                                    dod_reason = f"Error de sintaxis estática detectado por el analizador: {syntax_error_msg}"
                                elif not exec_subproc_ok:
                                    dod_approved = False
                                    dod_reason = exec_subproc_reason
                                else:
                                    file_content = task_result if len(files_to_generate) > 1 else self.orchestrator._read_project_file(output_file)
                                    dod_approved, dod_reason = self.orchestrator._run_dod_validation(
                                        task_id_str, agent_name, task_desc, output_file, file_content
                                    )
                                if dod_approved:
                                    event_bus.publish(EventType.TASK_COMPLETED, {"task_id": task_id_str, "reason": dod_reason, "agent_name": agent_name})
                                    success_task = True
                                    break
                                else:
                                    console.print(f"       ❌ DoD Rechazado: {dod_reason}")
                                    last_error_log = f"DoD rechazado: {dod_reason}"
                                    res_type, res_val = self._run_sentinel_auto_healing(
                                        task_id_str, agent_name, task_desc, output_file, last_error_log, created_files
                                    )
                                    if res_type == "AUTO_FIX":
                                        syntax_ok = True
                                        syntax_error_msg = ""
                                        for f_created in created_files:
                                            abs_f_path = os.path.join(self.orchestrator.project_path, f_created)
                                            if os.path.isfile(abs_f_path):
                                                s_ok, s_err = validate_syntax(abs_f_path)
                                                if not s_ok:
                                                    syntax_ok = False
                                                    syntax_error_msg = s_err
                                                    break
                                        exec_subproc_ok, exec_subproc_reason = self._run_strict_subprocess_dod_validation(
                                            self.orchestrator.project_path, created_files, output_file
                                        )
                                        if syntax_ok and exec_subproc_ok:
                                            file_content = task_result if len(files_to_generate) > 1 else self.orchestrator._read_project_file(output_file)
                                            dod_approved, dod_reason = self.orchestrator._run_dod_validation(
                                                task_id_str, agent_name, task_desc, output_file, file_content
                                            )
                                            if dod_approved:
                                                console.print("       [green]🛡️ Auto-Curación exitosa! La validación DoD ha sido aprobada tras la corrección de Sentinel.[/green]")
                                                event_bus.publish(EventType.TASK_COMPLETED, {"task_id": task_id_str, "reason": "Aprobado tras Auto-Curación de Sentinel", "agent_name": agent_name})
                                                success_task = True
                                                break
                                    if attempt < max_attempts:
                                        feedback = f"Rechazado por DoD: {dod_reason}. Diagnóstico de Sentinel: {res_val}. Corrige e intenta de nuevo."
                                    else:
                                        success_task = False
                                        progress.fail()
                                    continue

                            # DoD Check con compilación general
                            returncode, build_output = self.orchestrator._run_build_command(build_cmd)
                            if returncode == 0:
                                if not infra_ok:
                                    dod_approved = False
                                    dod_reason = infra_error_msg
                                elif not syntax_ok:
                                    dod_approved = False
                                    dod_reason = f"Error de sintaxis estática detectado por el analizador: {syntax_error_msg}"
                                elif not exec_subproc_ok:
                                    dod_approved = False
                                    dod_reason = exec_subproc_reason
                                else:
                                    file_content = task_result if len(files_to_generate) > 1 else self.orchestrator._read_project_file(output_file)
                                    dod_approved, dod_reason = self.orchestrator._run_dod_validation(
                                        task_id_str, agent_name, task_desc, output_file, file_content
                                    )
                                if dod_approved:
                                    event_bus.publish(EventType.TASK_COMPLETED, {"task_id": task_id_str, "reason": dod_reason, "agent_name": agent_name})
                                    success_task = True
                                    break
                                else:
                                    console.print(f"       ❌ DoD Rechazado: {dod_reason}")
                                    last_error_log = f"DoD rechazado tras compilar con éxito: {dod_reason}"
                                    res_type, res_val = self._run_sentinel_auto_healing(
                                        task_id_str, agent_name, task_desc, output_file, last_error_log, created_files
                                    )
                                    if res_type == "AUTO_FIX":
                                        returncode, build_output = self.orchestrator._run_build_command(build_cmd)
                                        if returncode == 0:
                                            syntax_ok = True
                                            syntax_error_msg = ""
                                            for f_created in created_files:
                                                abs_f_path = os.path.join(self.orchestrator.project_path, f_created)
                                                if os.path.isfile(abs_f_path):
                                                    s_ok, s_err = validate_syntax(abs_f_path)
                                                    if not s_ok:
                                                        syntax_ok = False
                                                        syntax_error_msg = s_err
                                                        break
                                            exec_subproc_ok, exec_subproc_reason = self._run_strict_subprocess_dod_validation(
                                                self.orchestrator.project_path, created_files, output_file
                                            )
                                            if syntax_ok and exec_subproc_ok:
                                                file_content = task_result if len(files_to_generate) > 1 else self.orchestrator._read_project_file(output_file)
                                                dod_approved, dod_reason = self.orchestrator._run_dod_validation(
                                                    task_id_str, agent_name, task_desc, output_file, file_content
                                                )
                                                if dod_approved:
                                                    console.print("       [green]🛡️ Auto-Curación exitosa! La validación DoD ha sido aprobada tras la corrección de Sentinel.[/green]")
                                                    event_bus.publish(EventType.TASK_COMPLETED, {"task_id": task_id_str, "reason": "Aprobado tras Auto-Curación de Sentinel", "agent_name": agent_name})
                                                    success_task = True
                                                    break
                                    if attempt < max_attempts:
                                        feedback = f"Rechazado por DoD: {dod_reason}. Diagnóstico de Sentinel: {res_val}. Corrige e intenta de nuevo."
                                    else:
                                        success_task = False
                                        progress.fail()
                            else:
                                last_error_log = f"Error de compilación: {build_output}"
                                res_type, res_val = self._run_sentinel_auto_healing(
                                    task_id_str, agent_name, task_desc, output_file, last_error_log, created_files
                                )
                                if res_type == "AUTO_FIX":
                                    returncode, build_output = self.orchestrator._run_build_command(build_cmd)
                                    if returncode == 0:
                                        syntax_ok = True
                                        syntax_error_msg = ""
                                        for f_created in created_files:
                                            abs_f_path = os.path.join(self.orchestrator.project_path, f_created)
                                            if os.path.isfile(abs_f_path):
                                                s_ok, s_err = validate_syntax(abs_f_path)
                                                if not s_ok:
                                                    syntax_ok = False
                                                    syntax_error_msg = s_err
                                                    break
                                        exec_subproc_ok, exec_subproc_reason = self._run_strict_subprocess_dod_validation(
                                            self.orchestrator.project_path, created_files, output_file
                                        )
                                        if syntax_ok and exec_subproc_ok:
                                            file_content = task_result if len(files_to_generate) > 1 else self.orchestrator._read_project_file(output_file)
                                            dod_approved, dod_reason = self.orchestrator._run_dod_validation(
                                                task_id_str, agent_name, task_desc, output_file, file_content
                                            )
                                            if dod_approved:
                                                console.print("       [green]🛡️ Auto-Curación exitosa! La validación DoD ha sido aprobada tras la corrección de Sentinel.[/green]")
                                                event_bus.publish(EventType.TASK_COMPLETED, {"task_id": task_id_str, "reason": "Aprobado tras Auto-Curación de Sentinel", "agent_name": agent_name})
                                                success_task = True
                                                break
                                if attempt < max_attempts:
                                    error_lines = self.orchestrator._extract_relevant_errors(build_output)
                                    feedback = f"Error de compilación:\n```\n{error_lines}\n```\nDiagnóstico de Sentinel: {res_val}. Corrige y vuelve a generar."
                                else:
                                    success_task = False
                                    progress.fail()

                        if success_task and task_result:
                            tokens = estimate_tokens(task_result)
                            progress.set_tokens(tokens)

                except LocalLLMTimeoutError as timeout_ex:
                    logger.error("Timeout del modelo local (GPU saturada) en la tarea %s: %s", task_id_str, timeout_ex)
                    success_task = False
                    last_error_log = str(timeout_ex)
                    task_retries = MAX_RETRIES  # Forzar abortar reintentos locales
                except Exception as ex:
                    logger.error("Excepción durante intento de ejecución de tarea: %s", ex, exc_info=True)
                    success_task = False
                    last_error_log = f"Excepción interna del runner: {ex}"

                if success_task:
                    # Tarea completada con éxito. Romper el bucle de Auto-Retry
                    self.orchestrator.state.blackboard.set(f"task_status_{task_id_str}", "completed")
                    break
                else:
                    task_retries += 1
                    # Rollback git
                    if use_microbranch:
                        self.orchestrator._git_end_task_branch(task_id_str, original_branch, success=False)
                    else:
                        self.orchestrator._git_rollback(task_id_str, snapshot_created)
                    
                    if task_retries < MAX_RETRIES:
                        # Auto-Retry: reasignar con FIX REQUIRED y el log del error (FASE 4)
                        task_desc = f"FIX REQUIRED: [Log del error: {last_error_log}]\nOriginal task description: {original_task_desc}"
                        console.print(f"       🔄 [Auto-Retry] Reintentando tarea {task_id_str} (Reintento {task_retries}/{MAX_RETRIES})...")
                    else:
                        # FASE 4: Límite de escalada MAX_RETRIES alcanzado. Bloquear la TUI
                        self.orchestrator.state.global_status = "ERROR"
                        event_bus.publish(EventType.AGENT_STATUS_CHANGE, {"agent": agent_name, "status": "Inactivo"})
                        event_bus.publish(EventType.TASK_FAILED, {
                            "task_id": task_id_str,
                            "max_retries": MAX_RETRIES,
                            "error_log": last_error_log
                        })
                        
                        self.orchestrator.metrics.append({
                            "fase": f"@{agent_name} ({task_id_str})",
                            "detalle": f"Fallo Crítico: {last_error_log[:50]}...",
                            "tiempo": getattr(self, "task_elapsed", 0.0),
                            "status": "❌",
                        })

                        # Sentinel Interactive Pause (SIP)
                        self.orchestrator.state.set_pipeline_status("PIPELINE_PAUSED", {
                            "task_id": task_id_str,
                            "agent_name": agent_name,
                            "error_log": last_error_log,
                            "task_desc": original_task_desc,
                            "output_file": output_file
                        })
                        
                        from core.agency_orchestrator import AgencyOrchestrator
                        ceo = AgencyOrchestrator(self.orchestrator.state)
                        sentinel_res = ceo.run_sentinel_session()
                        
                        # Si el usuario resolvió la pausa mediante retornos de control directos ([RETRY] o [FORCE_CONTINUE])
                        if not self.orchestrator.state.is_pipeline_paused() or sentinel_res in ("[RETRY]", "[FORCE_CONTINUE]"):
                            import json
                            json_filename = self.orchestrator.board_filename.replace(".md", ".json")
                            json_path = os.path.join(self.orchestrator.project_path, json_filename)
                            if os.path.isfile(json_path):
                                try:
                                    with open(json_path, "r", encoding="utf-8") as f:
                                        updated_tasks = json.load(f)
                                    for ut in updated_tasks:
                                        if ut.get("id") == task_id_str:
                                            task_desc = ut.get("task")
                                            task["task"] = task_desc
                                            task["status"] = ut.get("status")
                                            task["state"] = ut.get("state")
                                            break
                                except Exception as err_json:
                                    logger.warning("Error leyendo tablero actualizado tras SIP: %s", err_json)

                            # Si la tarea fue marcada como DONE o FAILED
                            if task.get("status") in ("DONE", "HECHO", "FAILED") or task.get("state") in ("DONE", "HECHO", "FAILED"):
                                if task.get("status") == "FAILED" or task.get("state") == "FAILED":
                                    self.orchestrator.state.blackboard.set(f"task_status_{task_id_str}", "failed")
                                else:
                                    self.orchestrator.state.blackboard.set(f"task_status_{task_id_str}", "completed")
                                break  # Romper el bucle task_retries para avanzar linealmente a la siguiente tarea
                            
                            # Si se seleccionó reintentar ([RETRY] o status en TODO)
                            task_retries = 0
                            continue
                        
                        # Si sigue pausado o la sesión fue abortada, detener la ejecución de forma limpia
                        return

            if use_microbranch and success_task:
                self.orchestrator._git_end_task_branch(task_id_str, original_branch, success=True)

            tokens = estimate_tokens(task_result) if task_result else 0
            status_symbol = "✅" if success_task else "⚠"
            status_text = "Completado con éxito" if success_task else "Completado con advertencias"

            self.orchestrator.metrics.append({
                "fase": f"@{agent_name} ({task_id_str})",
                "detalle": f"~{tokens:,} tokens → {output_file}",
                "tiempo": task_elapsed,
                "status": status_symbol,
            })

            # Actualizar DAILY.md
            self.orchestrator._write_task_handoff_with_status(task_id_str, agent_name, task_desc, output_file, status_text)

            # Actualizar DEVELOPMENT_LOG.md
            try:
                from core.orchestration.code_analyzer import format_analysis_for_log
                
                semantic_summary = ""
                summary_sys = "Eres el Escritor de Bitácoras de Jellyfish. Genera un resumen semántico de 1 sola oración y muy breve (máximo 15 palabras) de los cambios realizados en esta tarea."
                summary_user = f"Tarea: {task_desc}\nCódigo generado:\n{task_result[:1500] if task_result else 'Sin código'}"
                try:
                    summary_res = _call_llm_silent(
                        self.orchestrator.state,
                        [
                            {"role": "system", "content": summary_sys},
                            {"role": "user", "content": summary_user}
                        ],
                        provider=self.orchestrator.state.provider,
                        model=self.orchestrator.state.model
                    )
                    if summary_res:
                        semantic_summary = summary_res.strip().replace("\n", " ")
                except Exception as llm_err:
                    logger.warning("No se pudo generar el resumen semántico con LLM: %s", llm_err)
                
                if not semantic_summary:
                    semantic_summary = f"Completó la tarea: {task_desc[:60]}..."

                log_entry = format_analysis_for_log(
                    task_id=task_id_str,
                    agent_name=agent_name,
                    task_desc=task_desc,
                    created_files=created_files,
                    project_path=self.orchestrator.project_path,
                    semantic_summary=semantic_summary
                )

                log_filename = "DEVELOPMENT_LOG.md"
                existing_log = self.orchestrator._read_project_file(log_filename) or ""
                
                if not existing_log.strip():
                    existing_log = (
                        "# Jellyfish OS — Bitácora de Desarrollo Coherente\n\n"
                        "Este archivo documenta las modificaciones realizadas por cada agente en el pipeline.\n\n"
                    )
                
                updated_log = existing_log.rstrip() + "\n\n" + log_entry
                self.orchestrator._write_project_file(log_filename, updated_log)
                console.print("       [dim]✓ Bitácora de desarrollo actualizada (DEVELOPMENT_LOG.md)[/dim]")
            except Exception as log_err:
                logger.warning("No se pudo escribir en DEVELOPMENT_LOG.md: %s", log_err)

            # Actualizar estado del agente a Inactivo y global status a OK
            if agent_name in self.orchestrator.state.agent_statuses:
                self.orchestrator.state.agent_statuses[agent_name] = "Inactivo"
            self.orchestrator.state.global_status = "OK"

            # Actualizar estado de tarea individual y guardar tablero
            from datetime import datetime
            task["status"] = "DONE"
            task["state"] = "DONE"
            task["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.orchestrator._save_board(tasks)
