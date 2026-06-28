import os
import re
import time
import logging
from rich.console import Console
from rich.prompt import Confirm
from core.tui import tui_engine, TaskProgress
from core.state import estimate_tokens, _safe_read
from core.llm_engine import _call_llm_silent, LocalLLMTimeoutError
from core.terminal import run_terminal_command
from core.agents.registry import AgentRegistry
from core.skills.registry import SkillRegistry

logger = logging.getLogger("jellyfish.orchestration.task_runner")
console = Console()

MAX_RETRIES = 3  # FASE 4: Límite de escalada para reintentos automáticos

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

            # FASE 2 / FASE 3: Verificar que las dependencias de la tarea estén completadas en el Blackboard
            deps_ok = True
            for dep_id in task.get("dependencies", []):
                dep_status = self.orchestrator.state.blackboard.get(f"task_status_{dep_id}")
                if dep_status != "completed":
                    deps_ok = False
                    break
            if not deps_ok:
                console.print(f"       ⚠️ Tarea {task_id_str} bloqueada/saltada esperando a que sus dependencias se completen.")
                continue

            # Omitir tareas completadas si estamos reanudando
            if task.get("status") in ("DONE", "HECHO") or task.get("state") in ("DONE", "HECHO"):
                console.print(
                    f"[bold green]  [{task_num}/{len(tasks)}] {task_id_str}:[/bold green] "
                    f"[dim]YA COMPLETADO (Saltando ejecución)[/dim]"
                )
                self.orchestrator.state.blackboard.set(f"task_status_{task_id_str}", "completed")
                continue

            # FASE 4: Bucle de Retroalimentación Autónoma (Auto-Retry)
            task_retries = 0
            last_error_log = ""
            success_task = False
            task_result = ""
            created_files = []

            while task_retries < MAX_RETRIES:
                # FASE 1 & FASE 3: Actualizar estados de agente y TUI global
                if agent_name in self.orchestrator.state.agent_statuses:
                    self.orchestrator.state.agent_statuses[agent_name] = "Ejecutando"
                self.orchestrator.state.global_status = "PROCESS"

                console.print(
                    f"[bold white]  [{task_num}/{len(tasks)}] {task_id_str} (Intento {task_retries + 1}/{MAX_RETRIES}):[/bold white] "
                    f"{task_desc[:60]}{'...' if len(task_desc) > 60 else ''}"
                )
                console.print(f"[dim]       → @{agent_name} → {output_file}[/dim]")

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
                    f"REGLA DE DECISIÓN TECNOLÓGICA: Si el usuario no ha especificado explícitamente el stack tecnológico (lenguajes, bases de datos, frameworks, librerías principales) en su requerimiento, ESTÁ ESTRICTAMENTE PROHIBIDO que lo inventes o asumas. Debes detenerte y emitir la etiqueta `[ASK_USER: <tu pregunta detallada con opciones sugeridas>]`. No generes código ni diagramas de arquitectura hasta que el usuario responda.\n\n"
                    f"[REGLAS DE INFRAESTRUCTURA]\n"
                    f"REGLA ESTRUCTURAL ESTRICTA: NUNCA referencies un directorio, archivo o contexto de compilación (ej. en docker-compose) sin haber verificado primero que existe usando comandos de consola. Si configuras un servicio que requiere compilación (build), ESTÁS OBLIGADO a crear el `Dockerfile` correspondiente en la ruta exacta que especificaste y a generar el `package.json` o `requirements.txt` base si no existen. NO puedes dar una tarea de DevOps por terminada si faltan los archivos de construcción."
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

                # Lazo de compilación y depuración
                max_attempts = 5
                build_cmd = self.orchestrator._detect_compile_command()

                base_messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt}
                ]

                last_task_result = ""
                task_elapsed = 0.0
                feedback = ""
                
                short_desc = f"Tarea {task_id_str}: {task_desc[:40]}..."

                try:
                    with TaskProgress(tui_engine, f"auto_task_{i}", short_desc, agent=agent_name) as progress:
                        for attempt in range(1, max_attempts + 1):
                            attempt_t0 = time.perf_counter()

                            current_messages = list(base_messages)
                            if attempt > 1:
                                current_messages.append({"role": "assistant", "content": last_task_result})
                                if feedback:
                                    current_messages.append({"role": "user", "content": feedback})

                            task_result = ""
                            react_messages = list(current_messages)
                            max_react_steps = 15
                            
                            for step in range(1, max_react_steps + 1):
                                response_chunk = _call_llm_silent(
                                    self.orchestrator.state, react_messages,
                                    provider=self.orchestrator.state.provider,
                                    model=self.orchestrator.state.model
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
                                    
                                    user_response = input("✍ Escribe tu respuesta: ")
                                    
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
                                    console.print(f"       ⚙ Agente @{agent_name} ejecutando comando ReAct: {cmd_to_run}")
                                    
                                    ret_dict = {'returncode': 0}
                                    cmd_output = run_terminal_command(
                                        cmd_to_run,
                                        self.orchestrator.state,
                                        silent_history=True,
                                        timeout=120,
                                        force_confirm=False,
                                        return_code_dict=ret_dict
                                    )
                                    
                                    urgency_prompt = "Analiza el resultado y continúa redactando el archivo o solicita más comandos si es necesario."
                                    if step >= max_react_steps - 3:
                                        urgency_prompt = "Te quedan pocos pasos ReAct. Genera el entregable final AHORA usando etiquetas."

                                    react_messages.append({"role": "assistant", "content": response_chunk})
                                    react_messages.append({
                                        "role": "user",
                                        "content": f"Resultado de ejecución (Código {ret_dict['returncode']}):\n```\n{cmd_output[:3000]}\n```\n{urgency_prompt}"
                                    })
                                    continue
                                
                                task_result += response_chunk
                                
                                if "[TAREA_COMPLETADA]" in response_chunk or "[TAREA_COMPLETADA]" in task_result:
                                    task_result = task_result.replace("[TAREA_COMPLETADA]", "").strip()
                                    break
                                    
                                if step < max_react_steps:
                                    react_messages.append({"role": "assistant", "content": response_chunk})
                                    react_messages.append({
                                        "role": "user",
                                        "content": "Tu respuesta anterior se cortó. Continúa exactamente desde donde te quedaste. Si terminaste, finaliza con: [TAREA_COMPLETADA]"
                                    })

                            attempt_elapsed = time.perf_counter() - attempt_t0
                            task_elapsed += attempt_elapsed

                            if not task_result:
                                feedback = "Tu entregable estuvo vacío. Genera el código utilizando [WRITE_FILE: ...]."
                                if attempt == max_attempts:
                                    progress.fail()
                                continue

                            last_task_result = task_result

                            if py_agent:
                                try:
                                    task_result = py_agent.post_execute(task_result, task_context)
                                except Exception as post_err:
                                    logger.warning("post_execute de @%s falló: %s", agent_name, post_err)

                            # Escribir a disco
                            self.orchestrator._write_project_file(output_file, task_result)
                            created_files = self.orchestrator._extract_and_write_files(task_result)

                            # Pre-chequeo de infraestructura DoD
                            infra_ok = True
                            infra_error_msg = ""
                            for path in created_files:
                                if "docker-compose.yml" in path or "docker-compose.yaml" in path:
                                    abs_compose_path = os.path.join(self.orchestrator.project_path, path)
                                    try:
                                        with open(abs_compose_path, "r", encoding="utf-8") as f:
                                            content = f.read()
                                        context_matches = re.findall(r'context:\s*[\'"]?([^\s\'"#]+)[\'"]?', content)
                                        for rel_ctx in context_matches:
                                            compose_dir = os.path.dirname(abs_compose_path)
                                            abs_ctx_dir = os.path.abspath(os.path.join(compose_dir, rel_ctx))
                                            dockerfile_path = os.path.join(abs_ctx_dir, "Dockerfile")
                                            
                                            if not os.path.exists(abs_ctx_dir) or not os.path.exists(dockerfile_path):
                                                infra_ok = False
                                                infra_error_msg = f"ERROR DE INFRAESTRUCTURA: El archivo docker-compose.yml apunta al contexto '{rel_ctx}', pero no existe su Dockerfile."
                                                break
                                    except Exception as e:
                                        logger.error("Error al validar infraestructura en DoD: %s", e)
                                if not infra_ok:
                                    break

                            # Validación de sintaxis estática (FASE 4)
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

                            # DoD Check sin compilación
                            if not build_cmd:
                                if not infra_ok:
                                    dod_approved = False
                                    dod_reason = infra_error_msg
                                elif not syntax_ok:
                                    dod_approved = False
                                    dod_reason = f"Error de sintaxis estática detectado por el analizador: {syntax_error_msg}"
                                else:
                                    file_content = self.orchestrator._read_project_file(output_file)
                                    dod_approved, dod_reason = self.orchestrator._run_dod_validation(
                                        task_id_str, agent_name, task_desc, output_file, file_content
                                    )
                                if dod_approved:
                                    console.print(f"       ✓ DoD Aprobado: {dod_reason}")
                                    success_task = True
                                    break
                                else:
                                    console.print(f"       ❌ DoD Rechazado: {dod_reason}")
                                    last_error_log = f"DoD rechazado: {dod_reason}"
                                    if attempt < max_attempts:
                                        feedback = f"Rechazado por DoD: {dod_reason}. Corrige e intenta de nuevo."
                                    else:
                                        success_task = False
                                        progress.fail()
                                    continue

                            # DoD Check con compilación
                            returncode, build_output = self.orchestrator._run_build_command(build_cmd)
                            if returncode == 0:
                                if not infra_ok:
                                    dod_approved = False
                                    dod_reason = infra_error_msg
                                elif not syntax_ok:
                                    dod_approved = False
                                    dod_reason = f"Error de sintaxis estática detectado por el analizador: {syntax_error_msg}"
                                else:
                                    file_content = self.orchestrator._read_project_file(output_file)
                                    dod_approved, dod_reason = self.orchestrator._run_dod_validation(
                                        task_id_str, agent_name, task_desc, output_file, file_content
                                    )
                                if dod_approved:
                                    console.print(f"       ✓ DoD Aprobado: {dod_reason}")
                                    success_task = True
                                    break
                                else:
                                    console.print(f"       ❌ DoD Rechazado: {dod_reason}")
                                    last_error_log = f"DoD rechazado tras compilar con éxito: {dod_reason}"
                                    if attempt < max_attempts:
                                        feedback = f"Rechazado por DoD: {dod_reason}. Corrige e intenta de nuevo."
                                    else:
                                        success_task = False
                                        progress.fail()
                            else:
                                last_error_log = f"Error de compilación: {build_output}"
                                if attempt < max_attempts:
                                    error_lines = self.orchestrator._extract_relevant_errors(build_output)
                                    feedback = f"Error de compilación:\n```\n{error_lines}\n```\nCorrige y vuelve a generar."
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
                        if agent_name in self.orchestrator.state.agent_statuses:
                            self.orchestrator.state.agent_statuses[agent_name] = "Inactivo"
                        
                        console.print(f"\n❌ [BLOQUEADO] La tarea {task_id_str} ha fallado {MAX_RETRIES} veces consecutivas.")
                        console.print(f"       Último error registrado: {last_error_log}")
                        
                        # Solicitar intervención manual
                        input("\n⚠️ Flujo autónomo bloqueado. Presiona Enter para intervención manual en la TUI...")
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
