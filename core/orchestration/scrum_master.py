import os
import time
import logging
from datetime import datetime
from rich.console import Console
from core.tui import tui_engine, TaskProgress
from core.state import estimate_tokens, AGENCY_DIR
from core.agents.registry import AgentRegistry

logger = logging.getLogger("jellyfish.orchestration.scrum_master")

# Roles de gestión que no deben ser asignados a tareas de ejecución
_MANAGEMENT_ROLES = {"product_owner", "scrum_master", "template", "researcher"}


def _resolve_agent_assignments(tasks: list[dict], active_agency: str = "") -> int:
    """Resuelve asignaciones '@autodetect' o agentes no reconocidos usando Python puro.

    Recorre cada tarea y si su agente es 'autodetect' o no existe en el
    AgentRegistry, lo reemplaza por el agente con mayor puntaje de
    matches_task(). Cero tokens consumidos.

    Args:
        tasks: Lista de dicts con claves 'task', 'agent', etc.
        active_agency: Agencia activa para filtrar agentes.

    Returns:
        Número de asignaciones resueltas.
    """
    resolved = 0
    for task in tasks:
        agent_name = task.get("agent", "").lower().strip()
        needs_resolve = (
            not agent_name
            or agent_name == "autodetect"
            or agent_name in _MANAGEMENT_ROLES
            or not AgentRegistry.has(agent_name)
        )
        if needs_resolve:
            task_desc = task.get("task", "")
            best = AgentRegistry.best_agent_for_task(task_desc, agency=active_agency)
            if best and best.name.lower() not in _MANAGEMENT_ROLES:
                task["agent"] = best.name.lower()
                resolved += 1
                logger.info(
                    "Asignación programática: tarea '%s' → @%s (score=%.3f)",
                    task_desc[:50], best.name, best.matches_task(task_desc)
                )
    return resolved
console = Console()

class ScrumMasterPhase:
    """Fase 2 y Cierre del desarrollo autónomo: Scrum Master, Planificación y Retrospectiva."""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def _validate_and_heal_backlog(self, backlog_content: str) -> str:
        """Valida BACKLOG.json contra el esquema estricto y realiza Auto-Healing si falla."""
        import json
        import re
        from datetime import datetime
        
        is_valid = True
        try:
            data = json.loads(backlog_content)
            if not isinstance(data, dict):
                is_valid = False
            else:
                if "proyecto" not in data or "vision" not in data or "user_stories" not in data:
                    is_valid = False
                elif not isinstance(data.get("user_stories"), list):
                    is_valid = False
                else:
                    for us in data["user_stories"]:
                        if not isinstance(us, dict):
                            is_valid = False
                            break
                        for f in ("id", "titulo", "como", "quiero", "para"):
                            if f not in us or not isinstance(us[f], str):
                                is_valid = False
                                break
                        for f in ("criterios_aceptacion", "contexto_rag_necesario", "definition_of_done"):
                            if f not in us or not isinstance(us[f], list):
                                is_valid = False
                                break
                        if not is_valid:
                            break
        except Exception:
            is_valid = False

        if is_valid:
            return backlog_content

        # Loguear en jellyfish_debug.log el JSON exacto
        debug_log_path = os.path.join(self.orchestrator.project_path, "jellyfish_debug.log")
        log_msg = (
            f"\n\n[SCRUM MASTER SCHEMA CHECK ERROR - {datetime.now().isoformat()}]\n"
            f"El archivo BACKLOG.json falló la validación del esquema estricto.\n"
            f"JSON exacto que intentó procesar:\n"
            f"{backlog_content}\n"
            f"--------------------------------------------------\n"
        )
        try:
            with open(debug_log_path, "a", encoding="utf-8") as f:
                f.write(log_msg)
        except Exception as log_err:
            logger.warning("No se pudo escribir en jellyfish_debug.log: %s", log_err)

        console.print("[yellow]⚠ BACKLOG.json no cumple con el esquema estricto. Iniciando Auto-Healing del Backlog...[/yellow]")
        
        # Llamar silenciosamente a LLM
        from core.llm_engine import _call_llm_silent
        heal_system = (
            "Eres un Scrum Master experto. El archivo BACKLOG.json del proyecto no cumple con el esquema estricto requerido.\n"
            "Debes corregir y transformar el JSON para que coincida exactamente con el siguiente formato:\n"
            "{\n"
            '  "proyecto": "Nombre del proyecto (string)",\n'
            '  "vision": "Visión general (string)",\n'
            '  "user_stories": [\n'
            "    {\n"
            '      "id": "US-001 (string)",\n'
            '      "titulo": "Título (string)",\n'
            '      "como": "Rol (string)",\n'
            '      "quiero": "Acción (string)",\n'
            '      "para": "Beneficio (string)",\n'
            '      "criterios_aceptacion": ["Criterio 1"] (list of strings),\n'
            '      "contexto_rag_necesario": ["Ruta sugerida"] (list of strings),\n'
            '      "definition_of_done": ["DoD 1"] (list of strings)\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Tu ÚNICO entregable es el JSON corregido y sanitizado. No devuelvas explicaciones ni texto markdown fuera del JSON."
        )
        heal_messages = [
            {"role": "system", "content": heal_system},
            {"role": "user", "content": f"CONTENIDO PROBLEMÁTICO:\n{backlog_content}"}
        ]
        
        healed_result = _call_llm_silent(
            self.orchestrator.state,
            heal_messages,
            provider=self.orchestrator.state.provider,
            model=self.orchestrator.state.model
        )
        if healed_result:
            json_clean = healed_result.strip()
            match = re.search(r'\{.*\}', json_clean, re.DOTALL)
            if match:
                json_clean = match.group(0)
            try:
                # Validar el healed JSON
                json.loads(json_clean)
                self.orchestrator._write_project_file("BACKLOG.json", json_clean)
                console.print("[green]✓ Auto-Healing exitoso. BACKLOG.json corregido.[/green]")
                return json_clean
            except Exception:
                pass
                
        console.print("[red]❌ Falló el Auto-Healing del BACKLOG.json. Continuando con el backlog existente.[/red]")
        return backlog_content

    def run(self, user_idea: str) -> bool:
        """SM escanea agentes, arma equipo y genera el tablero correspondiente a la agencia."""
        console.print(f"\n━━━ FASE 2: 📋 Scrum Master (Team Assembly - Agencia: {self.orchestrator.state.active_agency.upper()}) ━━━")
        t0 = time.perf_counter()

        # Importar helpers de orquestador para escaneo y parseo
        from core.project_orchestrator import _scan_available_agents, _parse_sprint_tasks

        # Escanear agentes disponibles
        available_agents = _scan_available_agents(self.orchestrator.state)
        agent_lines = []
        for a in available_agents:
            line = f"  - @{a['name']}: {a['role']}"
            if "expertise" in a and a["expertise"]:
                line += f" (Expertise: {', '.join(a['expertise'])})"
            agent_lines.append(line)
        agents_catalog = "\n".join(agent_lines)
        console.print(f"[dim]   Agentes disponibles en la agencia '{self.orchestrator.state.active_agency}': {len(available_agents)}[/dim]")

        # FASE 2: Leer BACKLOG.json si existe, si no, caer a BACKLOG.md
        backlog_json = self.orchestrator._read_project_file("BACKLOG.json")
        if backlog_json:
            backlog_json = self._validate_and_heal_backlog(backlog_json)
        backlog = backlog_json if backlog_json else self.orchestrator._read_project_file("BACKLOG.md")
        
        agent_prompt = self.orchestrator._load_agent_prompt("scrum_master")
        
        last_exit = self.orchestrator._get_last_exit_code()
        alert_prefix = ""
        if last_exit != 0:
            alert_prefix = "[SYSTEM ALERT: THE BUILD/PIPELINE IS CURRENTLY BROKEN. PRIORITIZE FIXING EXISTING FATAL ERRORS BEFORE ADDING FEATURES OR MOVING FORWARD].\n\n"

        system = (
            f"{alert_prefix}"
            f"{agent_prompt}\n\n"
            "[INSTRUCCIONES ESPECÍFICAS PARA ESTA TAREA]\n"
            f"Tu ÚNICO entregable es el contenido completo del archivo {self.orchestrator.board_filename}.\n"
            "Genera SOLAMENTE Markdown listo para guardar.\n\n"
            "EQUIPO DISPONIBLE (solo puedes asignar tareas a estos agentes):\n"
            f"{agents_catalog}\n\n"
            "REGLAS DE ASIGNACIÓN:\n"
            "1. Analiza las historias de BACKLOG.json y decide qué agentes se necesitan.\n"
            "2. Desglosa cada historia en tareas técnicas concretas.\n"
            "3. Asigna cada tarea al agente más adecuado usando EXACTAMENTE su @nombre.\n"
            "4. Define un archivo de código fuente real para el entregable de la tarea (ej: src/main.dart, app/server.js, lib/database.py). Usa extensión .md SOLO si la tarea es puramente de documentación, investigación o arquitectura.\n"
            "5. TRASPASOS INTER-AGENCIA (HANDOFFS): Si una tarea técnica excede las capacidades de tu agencia actual (agencia activa: '{self.orchestrator.state.active_agency}'), "
            "puedes definir como 'Entregable' un archivo que servirá de insumo para otra agencia (ej: un COPY_LANDING.md generado por MKT para que DEV lo consuma).\n"
            "6. DEFINICIÓN DE DEPENDENCIAS (DAG): En la sexta columna, especifica los IDs de las tareas predecesoras que deben completarse antes de iniciar esta tarea, separados por coma (ej. 'T-001' o 'T-001, T-002'). Si no tiene dependencias, escribe 'Ninguna'.\n"
            "7. MAPEO OBLIGATORIO DE HISTORIAS DE USUARIO: En la columna 'Tarea', DEBES incluir explícitamente el ID de la Historia de Usuario correspondiente entre corchetes, por ejemplo: '[US-001] Crear pantalla de login' o '[US-002] Desarrollar API de autenticación'.\n\n"
            "REQUISITOS DE CALIDAD Y RIQUEZA DE CONTENIDO:\n"
            "Queremos un tablero de sprint extremadamente rico en detalles técnicos. Sigue estas directrices:\n"
            "- Las descripciones de las tareas en la tabla deben ser detalladas y explícitas sobre qué construir (no usar resúmenes vagos).\n"
            "- Abajo de la tabla de tareas, debes incluir obligatoriamente una sección titulada '### 📋 Especificaciones de Tareas y Criterios de Aceptación Técnicos'.\n"
            "- En esta sección, desglosa cada ID de tarea (T-001, T-002, etc.) y detalla paso a paso qué debe implementar el agente, qué APIs o controladores usar, qué validaciones hacer, y los entregables esperados en el archivo destino.\n"
            "- Asegúrate de incluir las secciones de '## ⏳ EN PROCESO (IN PROGRESS)' y '## ✅ HECHO (DONE)' vacías como marcadores.\n\n"
            f"FORMATO OBLIGATORIO del tablero (la tabla TODO DEBE tener exactamente 6 columnas en {self.orchestrator.board_filename}):\n"
            "```\n"
            "## 📋 POR HACER (TODO)\n"
            "| ID | Tarea | Asignado | Estimación | Entregable | Dependencias |\n"
            "|---|---|---|---|---|---|\n"
            "| T-001 | [US-001] Diseñar la arquitectura del sistema | @arquitecto_software | M | ARCHITECTURE.md | Ninguna |\n"
            "| T-002 | [US-001] Implementar modelos de datos | @backend_dev | L | src/database/models.js | T-001 |\n"
            "| T-003 | [US-002] Crear componente de Login | @frontend_dev | S | lib/components/Login.tsx | T-002 |\n"
            "```\n\n"
            "IMPORTANTE:\n"
            "- La columna 'Asignado' DEBE ser exactamente un @nombre de la lista de agentes. "
            "Si no estás seguro de qué agente asignar, puedes usar '@autodetect' y el sistema lo resolverá automáticamente.\n"
            "- La columna 'Entregable' DEBE ser la ruta de un archivo de CÓDIGO FUENTE REAL adecuado para la tecnología del proyecto.\n"
            "- Ordena las tareas en el orden lógico de ejecución.\n"
        )

        user_prompt = (
            f"IDEA ORIGINAL:\n{user_idea}\n\n"
            f"BACKLOG.md:\n{backlog}\n\n"
            f"Genera el {self.orchestrator.board_filename} asignando tareas a los agentes del equipo."
        )

        with TaskProgress(tui_engine, "auto_sm", "Scrum Master: Armando equipo y planificando sprint..."):
            result = self.orchestrator._call_agent(system, user_prompt)

        elapsed = time.perf_counter() - t0

        if not result:
            self.orchestrator.metrics.append({"fase": "📋 Scrum Master", "detalle": "ERROR", "tiempo": elapsed, "status": "❌"})
            console.print("✗ Scrum Master no produjo resultado.")
            return False

        target_board = self.orchestrator.board_filename

        self.orchestrator._write_project_file(target_board, result)
        tokens = estimate_tokens(result)

        # Mostrar equipo seleccionado y guardar tablero en formato JSON (Mejora 11)
        tasks = _parse_sprint_tasks(result)
        
        # Validar mapeo de historias del Backlog
        import json
        import re
        user_stories = []
        try:
            backlog_data = json.loads(backlog)
            user_stories = backlog_data.get("user_stories", [])
        except Exception:
            pass

        unmapped_stories = []
        if user_stories:
            for us in user_stories:
                us_id = us.get("id", "")
                if not us_id:
                    continue
                found = False
                for t in tasks:
                    if us_id.lower() in t.get("task", "").lower() or us_id.lower() in t.get("id", "").lower():
                        found = True
                        break
                if not found:
                    unmapped_stories.append(us_id)

        # Si no hay tareas o hay historias de usuario sin mapear, iniciamos Auto-Healing
        if not tasks or unmapped_stories:
            # 1. Loggear en jellyfish_debug.log el JSON exacto de BACKLOG
            debug_log_path = os.path.join(self.orchestrator.project_path, "jellyfish_debug.log")
            log_msg = (
                f"\n\n[SCRUM MASTER MAPPING ERROR - {datetime.now().isoformat()}]\n"
                f"No se pudieron mapear las historias de usuario al SPRINT_BOARD.md.\n"
                f"Historias no mapeadas: {unmapped_stories}\n"
                f"Tareas detectadas inicialmente: {len(tasks)}\n"
                f"JSON exacto del backlog recibido:\n"
                f"{backlog}\n"
                f"--------------------------------------------------\n"
            )
            try:
                with open(debug_log_path, "a", encoding="utf-8") as f:
                    f.write(log_msg)
            except Exception as log_err:
                logger.warning("No se pudo escribir en jellyfish_debug.log: %s", log_err)

            console.print("[yellow]⚠ Scrum Master detectó historias no mapeadas o tabla vacía. Iniciando Auto-Healing del Tablero...[/yellow]")
            
            # Auto-Healing: transformar la estructura JSON de forma que coincida con el formato del SPRINT_BOARD.md
            from core.llm_engine import _call_llm_silent
            heal_system = (
                f"Eres el Scrum Master de Jellyfish OS.\n"
                f"Tu tarea es realizar un Auto-Healing del SPRINT_BOARD.md. Debes asegurar que TODAS las historias del Backlog "
                f"estén mapeadas a tareas técnicas concretas en la tabla de Markdown.\n\n"
                f"EQUIPO DISPONIBLE:\n{agents_catalog}\n\n"
                f"FORMATO REQUERIDO DE TABLA:\n"
                f"## 📋 POR HACER (TODO)\n"
                f"| ID | Tarea | Asignado | Estimación | Entregable | Dependencias |\n"
                f"|---|---|---|---|---|---|\n"
                f"| T-001 | [Detalle técnico para US-001] | @agente | M | archivo_de_salida | Dependencia |\n\n"
                f"Genera la tabla completa de SPRINT_BOARD.md mapeando de forma segura cada una de las historias."
                f"Devuelve ÚNICAMENTE el Markdown con la tabla y su especificación de tareas."
            )
            heal_messages = [
                {"role": "system", "content": heal_system},
                {"role": "user", "content": f"BACKLOG:\n{backlog}\n\nTABLERO ANTERIOR GENERADO:\n{result}"}
            ]
            healed_board = _call_llm_silent(
                self.orchestrator.state,
                heal_messages,
                provider=self.orchestrator.state.provider,
                model=self.orchestrator.state.model
            )
            if healed_board:
                healed_tasks = _parse_sprint_tasks(healed_board)
                if healed_tasks:
                    result = healed_board
                    self.orchestrator._write_project_file(target_board, result)
                    tasks = healed_tasks
                    console.print("[green]✓ Auto-Healing del Tablero completado con éxito.[/green]")
                else:
                    logger.warning("Auto-Healing no produjo tareas parseables válidas. Preservando tareas generadas inicialmente.")

        if not tasks:
            console.print("[yellow]⚠ Sintetizando tablero de tareas de contingencia directamente a partir del Backlog...[/yellow]")
            tasks = self._synthesize_fallback_board(target_board, backlog)

        # Sprint 13 — Resolver asignaciones @autodetect programáticamente (Python puro, 0 tokens)
        active_agency = getattr(self.orchestrator.state, "active_agency", "")
        resolved_count = _resolve_agent_assignments(tasks, active_agency)
        if resolved_count:
            console.print(f"[dim]   ⚙ Asignación programática: {resolved_count} tarea(s) resueltas automáticamente por Python[/dim]")

        try:
            import json
            json_filename = target_board.replace(".md", ".json")
            self.orchestrator._write_project_file(json_filename, json.dumps(tasks, indent=2, ensure_ascii=False))
            console.print(f"       [dim]✓ Tablero JSON estructurado guardado: {json_filename}[/dim]")
        except Exception as je:
            logger.warning("No se pudo escribir el tablero JSON: %s", je)

        unique_agents = set(t["agent"] for t in tasks)
        console.print(f"✓ {target_board} [dim]({tokens:,} tokens · {elapsed:.1f}s)[/dim]")
        console.print(f"[dim]   Equipo seleccionado: {', '.join(f'@{a}' for a in sorted(unique_agents))}[/dim]")
        console.print(f"[dim]   Tareas planificadas: {len(tasks)}[/dim]")
        return True

    def _synthesize_fallback_board(self, target_board: str, backlog_str: str) -> list[dict]:
        """Sintetiza tareas de contingencia directamente desde las Historias de Usuario de BACKLOG.json/md."""
        import json
        tasks = []
        user_stories = []
        try:
            data = json.loads(backlog_str)
            user_stories = data.get("user_stories", [])
        except Exception:
            pass

        if not user_stories:
            user_stories = [{
                "id": "US-001",
                "titulo": "Implementación de Arquitectura y Estructura Base",
                "como": "Desarrollador del sistema",
                "quiero": "Andamiar el proyecto con los componentes solicitados",
                "para": "Iniciar desarrollo del sistema"
            }]

        board_lines = [
            "## 📋 POR HACER (TODO)",
            "| ID | Tarea | Asignado | Estimación | Entregable | Dependencias |",
            "|---|---|---|---|---|---|"
        ]

        for idx, us in enumerate(user_stories, start=1):
            t_id = f"T-{idx:03d}"
            us_id = us.get("id", f"US-{idx:03d}")
            title = us.get("titulo", "Desarrollar componente de aplicación")
            task_desc = f"[{us_id}] {title}"
            output_file = f"src/feature_{idx}.py"
            
            tasks.append({
                "id": t_id,
                "task": task_desc,
                "agent": "@autodetect",
                "estimate": "M",
                "output_file": output_file,
                "dependencies": [],
                "status": "TODO"
            })
            board_lines.append(f"| {t_id} | {task_desc} | @autodetect | M | {output_file} | Ninguna |")

        board_lines.extend([
            "",
            "## ⏳ EN PROCESO (IN PROGRESS)",
            "",
            "## ✅ HECHO (DONE)",
            ""
        ])

        synthetic_md = "\n".join(board_lines)
        self.orchestrator._write_project_file(target_board, synthetic_md)
        return tasks

    def run_retrospective(self) -> None:
        """Analiza DAILY.md y guarda aprendizajes en retrospective_rules.md para futuros sprints."""
        daily_path = os.path.join(self.orchestrator.project_path, "DAILY.md")
        if not os.path.isfile(daily_path):
            return

        daily_content = self.orchestrator._read_project_file("DAILY.md")
        if not daily_content:
            return

        console.print("\n━━━ FASE COMPLEMENTARIA: 🧠 Retrospectiva Autónoma ━━━")
        
        system_prompt = (
            "Eres el Scrum Master de Jellyfish OS.\n"
            "Tu tarea es analizar la bitácora DAILY.md de la ejecución del sprint y extraer lecciones aprendidas.\n"
            "Identifica:\n"
            "1. Qué falló durante el sprint (ej. errores de compilación, de auto-healing, dependencias).\n"
            "2. Reglas recomendadas (Negative Prompts o mejores directrices) para que futuros agentes no cometan los mismos errores.\n\n"
            "Genera tu reporte en Markdown limpio, directo y enfocado en reglas de acción."
        )

        with TaskProgress(tui_engine, "auto_retro", "Scrum Master: Analizando lecciones aprendidas..."):
            rules = self.orchestrator._call_agent(system_prompt, f"DAILY.md:\n{daily_content}")

        if rules:
            retro_dir = os.path.join(AGENCY_DIR, "memory")
            os.makedirs(retro_dir, exist_ok=True)
            retro_file = os.path.join(retro_dir, "retrospective_rules.md")
            
            existing = ""
            if os.path.isfile(retro_file):
                try:
                    with open(retro_file, "r", encoding="utf-8") as f:
                        existing = f.read() + "\n\n---\n\n"
                except Exception:
                    pass
            
            try:
                with open(retro_file, "w", encoding="utf-8") as f:
                    f.write(existing + f"## Retrospectiva {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n" + rules)
                console.print("✓ Lecciones guardadas en memory/retrospective_rules.md")
            except (OSError, IOError) as e:
                logger.warning("Error guardando retrospectiva: %s", e)
