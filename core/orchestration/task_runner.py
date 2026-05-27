import os
import time
import logging
from rich.console import Console
from core.tui import tui_engine, TaskProgress
from core.state import estimate_tokens, _safe_read
from core.llm_engine import _call_llm_silent
from core.terminal import run_terminal_command

logger = logging.getLogger("jellyfish.orchestration.task_runner")
console = Console()

class TaskRunnerPhase:
    """Fase 3 del desarrollo autónomo: Task Runner, ReAct loop y control transaccional."""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def run(self, user_idea: str) -> None:
        """Parsea el tablero de la agencia y ejecuta cada tarea con su agente asignado."""
        # Cargar tareas prioritariamente desde JSON estructurado, con fallback a Markdown (Mejora 11)
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

        console.print(
            f"\n━━━ FASE 3: 🚀 Task Runner — {len(tasks)} tareas ━━━\n"
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

            # Realizar git snapshot de transaccionalidad via micro-branching (Mejora 41)
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

            accumulated = self.orchestrator._build_intelligent_context(task_desc, output_file)

            system = (
                f"{agent_prompt}\n\n"
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

            # Lazo de compilación y depuración (Compile & Debug Loop) - Sprint 12
            max_attempts = 5
            build_cmd = self.orchestrator._detect_compile_command()

            # Definir la estructura base de los mensajes de forma inmutable para la tarea actual
            base_messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt}
            ]

            last_task_result = ""
            success_task = False
            task_elapsed = 0.0
            task_result = None

            short_desc = f"Tarea {task_id_str}: {task_desc[:50]}..."
            try:
                with TaskProgress(tui_engine, f"auto_task_{i}", short_desc, agent=agent_name) as progress:
                    for attempt in range(1, max_attempts + 1):
                        attempt_t0 = time.perf_counter()

                        # Clonar la lista base en una variable temporal para evitar contaminación de contexto
                        current_messages = list(base_messages)
                        if attempt > 1:
                            current_messages.append({"role": "assistant", "content": last_task_result})
                            current_messages.append({"role": "user", "content": feedback})

                        # Bucle de Continuación de Tarea + ReAct Loop (Mejora 31)
                        task_result = ""
                        react_messages = list(current_messages)
                        max_react_steps = 6
                        
                        for step in range(1, max_react_steps + 1):
                            response_chunk = _call_llm_silent(
                                self.orchestrator.state, react_messages,
                                provider=self.orchestrator.state.provider,
                                model=self.orchestrator.state.model
                            )
                            
                            if not response_chunk:
                                break
                                
                            # Detectar si solicita ejecutar comando
                            import re as _re
                            cmd_match = _re.search(r'<run_command>(.*?)</run_command>', response_chunk, _re.DOTALL)
                            if cmd_match:
                                cmd_to_run = cmd_match.group(1).strip()
                                console.print(f"       ⚙ Agente @{agent_name} ejecutando comando ReAct: {cmd_to_run}")
                                
                                ret_dict = {'returncode': 0}
                                cmd_output = run_terminal_command(
                                    cmd_to_run,
                                    self.orchestrator.state,
                                    silent_history=True,
                                    timeout=120,
                                    force_confirm=False, # Auto-aprobado en sandbox para fluidez del bucle ReAct
                                    return_code_dict=ret_dict
                                )
                                
                                react_messages.append({"role": "assistant", "content": response_chunk})
                                react_messages.append({
                                    "role": "user",
                                    "content": (
                                        f"Resultado de ejecución (Código {ret_dict['returncode']}):\n"
                                        f"```\n{cmd_output[:3000]}\n```\n"
                                        f"Analiza el resultado y continúa redactando el archivo o solicita más comandos si es necesario."
                                    )
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
                                    "content": "Tu respuesta anterior se cortó. Por favor, continúa exactamente desde donde te quedaste. Si terminaste, finaliza con la etiqueta: [TAREA_COMPLETADA]"
                                })

                        attempt_elapsed = time.perf_counter() - attempt_t0
                        task_elapsed += attempt_elapsed

                        if not task_result:
                            if attempt == max_attempts:
                                progress.fail()
                            continue

                        # Preservar el último resultado por si la compilación vuelve a fallar
                        last_task_result = task_result

                        # Guardar entregable en disco e interactuar con archivos reales
                        self.orchestrator._write_project_file(output_file, task_result)
                        self.orchestrator._extract_and_write_files(task_result)

                        # Si no hay comando de compilación, podemos validar DoD directamente
                        if not build_cmd:
                            # Validar DoD (Mejora 15)
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
                                if attempt < max_attempts:
                                    feedback = (
                                        f"Tu entregable fue RECHAZADO por control de calidad (DoD) por el siguiente motivo:\n"
                                        f"```\n{dod_reason}\n```\n"
                                        f"Por favor, corrige los archivos y vuelve a generarlos sin dejar ningún placeholder o comentario TODO incompleto."
                                    )
                                else:
                                    success_task = False
                                    progress.fail()
                                continue

                        returncode, build_output = self.orchestrator._run_build_command(build_cmd)
                        if returncode == 0:
                            # Validar DoD
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
                                if attempt < max_attempts:
                                    feedback = (
                                        f"Tu entregable fue RECHAZADO por control de calidad (DoD) por el siguiente motivo:\n"
                                        f"```\n{dod_reason}\n```\n"
                                        f"Por favor, corrige los archivos y vuelve a generarlos sin dejar ningún placeholder o comentario TODO incompleto."
                                    )
                                else:
                                    success_task = False
                                    progress.fail()
                        else:
                            if attempt < max_attempts:
                                error_lines = self.orchestrator._extract_relevant_errors(build_output)
                                feedback = (
                                    f"Tu código falló en la compilación con el siguiente error. Analiza las dependencias, corrígelo e itera:\n"
                                    f"```\n{error_lines}\n```\n"
                                    f"Corrige los archivos correspondientes y vuelve a generarlos utilizando las etiquetas <write_file> o [WRITE_FILE: ...]."
                                )
                            else:
                                success_task = False
                                progress.fail()

                    if success_task and task_result:
                        tokens = estimate_tokens(task_result)
                        progress.set_tokens(tokens)

                if not task_result or not success_task:
                    if use_microbranch:
                        self.orchestrator._git_end_task_branch(task_id_str, original_branch, success=False)
                    else:
                        self.orchestrator._git_rollback(task_id_str, snapshot_created)
                    
                    # ── Agente de Recuperación ──────────────────────────────────────
                    # En lugar de silenciosamente saltar la tarea, Jellyfish analiza el
                    # fallo, propone un plan correctivo y requiere aprobación del usuario.
                    console.print(f"\n[bold yellow]⚠ TAREA FALLIDA:[/bold yellow] {task_id_str} — @{agent_name}")
                    console.print(f"[dim]  Motivo: agotados {max_attempts} intentos sin pasar el DoD.[/dim]")
                    console.print("[bold white]🔍 Activando Agente de Recuperación...[/bold white]")

                    # Recopilar contexto del fallo para el agente recuperador
                    failure_context = (
                        f"TAREA FALLIDA:\n"
                        f"  ID: {task_id_str}\n"
                        f"  Agente asignado: @{agent_name}\n"
                        f"  Descripción: {task_desc}\n"
                        f"  Archivo esperado: {output_file}\n"
                        f"  Intentos realizados: {max_attempts}\n"
                        f"  Último resultado generado (fragmento):\n{(last_task_result or 'Sin resultado')[:1500]}\n"
                    )
                    remaining_tasks = [
                        f"  - [{t.get('id','?')}] {t.get('task','?')[:60]} → @{t.get('agent','?')}"
                        for t in tasks[i+1:]
                    ]
                    remaining_str = "\n".join(remaining_tasks) if remaining_tasks else "  (ninguna)"

                    recovery_system = (
                        "Eres el Agente de Recuperación de Jellyfish OS. Tu rol es EXCLUSIVAMENTE analítico y ejecutivo.\n"
                        "Un agente del pipeline autónomo ha fallado tras múltiples intentos. Tu misión es:\n"
                        "1. Identificar la causa raíz del fallo con precisión técnica (1-3 oraciones).\n"
                        "2. Proponer un plan de acción concreto y numerado para resolver el problema.\n"
                        "3. Indicar si las tareas restantes del pipeline se ven afectadas por este fallo.\n"
                        "4. Ser BREVE y EJECUTIVO. Máximo 15 líneas en total. Sin introducciones ni despedidas."
                    )
                    recovery_prompt = (
                        f"{failure_context}\n"
                        f"TAREAS RESTANTES EN EL PIPELINE:\n{remaining_str}\n\n"
                        f"Analiza el fallo y genera el plan de acción correctivo."
                    )

                    recovery_response = _call_llm_silent(
                        self.orchestrator.state,
                        [
                            {"role": "system", "content": recovery_system},
                            {"role": "user", "content": recovery_prompt},
                        ],
                        provider=self.orchestrator.state.provider,
                        model=self.orchestrator.state.model,
                    )

                    if recovery_response:
                        console.print("\n[bold white]📋 PLAN DE RECUPERACIÓN:[/bold white]")
                        console.print(recovery_response.strip())
                    else:
                        console.print("[dim]  El agente de recuperación no pudo generar un plan.[/dim]")

                    # Escribir plan de recuperación en disco para trazabilidad
                    try:
                        recovery_path = os.path.join(
                            self.orchestrator.project_path,
                            f"RECOVERY_{task_id_str}.md"
                        )
                        with open(recovery_path, "w", encoding="utf-8") as rf:
                            rf.write(f"# Plan de Recuperación — {task_id_str}\n\n")
                            rf.write(f"**Agente:** @{agent_name}  \n")
                            rf.write(f"**Tarea:** {task_desc}  \n\n")
                            rf.write("## Análisis del Fallo\n\n")
                            rf.write(recovery_response or "Sin análisis disponible.")
                            rf.write("\n")
                        console.print(f"[dim]  ✓ Plan guardado en {recovery_path}[/dim]")
                    except Exception as rw_err:
                        logger.warning("No se pudo guardar el plan de recuperación: %s", rw_err)

                    # Solicitar aprobación del usuario
                    console.print()
                    from rich.prompt import Confirm
                    try:
                        skip_approved = Confirm.ask(
                            "¿Continuar el pipeline saltando esta tarea? [y=continuar / n=detener pipeline]",
                            default=True
                        )
                    except (EOFError, KeyboardInterrupt):
                        skip_approved = True  # En modo no interactivo, continuar

                    self.orchestrator.metrics.append({
                        "fase": f"@{agent_name} ({task_id_str})",
                        "detalle": f"FALLIDO — Plan en RECOVERY_{task_id_str}.md",
                        "tiempo": task_elapsed,
                        "status": "❌",
                    })

                    if not skip_approved:
                        console.print("[bold red]Pipeline detenido por el usuario.[/bold red]")
                        return
                    continue

                if use_microbranch:
                    self.orchestrator._git_end_task_branch(task_id_str, original_branch, success=True)

                tokens = estimate_tokens(task_result)
                status_symbol = "✅" if success_task else "⚠"
                status_text = "Completado con éxito" if success_task else "Completado con advertencias (fallo de compilación)"

                self.orchestrator.metrics.append({
                    "fase": f"@{agent_name} ({task_id_str})",
                    "detalle": f"~{tokens:,} tokens → {output_file}",
                    "tiempo": task_elapsed,
                    "status": status_symbol,
                })

                # Actualizar DAILY.md con handoff
                self.orchestrator._write_task_handoff_with_status(task_id_str, agent_name, task_desc, output_file, status_text)

            except Exception as ex:
                if use_microbranch:
                    self.orchestrator._git_end_task_branch(task_id_str, original_branch, success=False)
                else:
                    self.orchestrator._git_rollback(task_id_str, snapshot_created)
                import traceback
                error_trace = traceback.format_exc()
                if not hasattr(self.orchestrator.state, "captured_errors"):
                    self.orchestrator.state.captured_errors = []
                self.orchestrator.state.captured_errors.append(
                    f"Error crítico en la ejecución de la tarea {task_id_str} por el agente @{agent_name}:\n"
                    f"{error_trace}"
                )
                logger.error(f"Error crítico en tarea {task_id_str}: {ex}", exc_info=True)
                self.orchestrator.metrics.append({
                    "fase": f"@{agent_name} ({task_id_str})",
                    "detalle": f"FALLIDO — Error interno: {str(ex)[:40]}",
                    "tiempo": task_elapsed,
                    "status": "❌",
                })

        # Actualizar tablero: mover todo a DONE
        self.orchestrator._mark_all_done(tasks)
