"""core/agency_orchestrator.py - Orquestador de Agencias (CEO) para Jellyfish OS v6

Clasifica los prompts de usuario y los redirige a la agencia correspondiente,
configurando el estado global antes de delegar la ejecución a ProjectOrchestrator.
Refactored to inherit from BaseOrchestrator.
"""

import logging
from core.state import JellyfishState
from core.orchestration import BaseOrchestrator

logger = logging.getLogger("jellyfish.agency_orchestrator")

class AgencyOrchestrator(BaseOrchestrator):
    """El CEO invisible del sistema. Clasifica intenciones y delega a la agencia correcta."""
    
    def __init__(self, state: JellyfishState):
        super().__init__(state)

    def classify_agency(self, user_prompt: str) -> str:
        """Determina cuál es la mejor agencia para resolver el requerimiento (forzando JSON)."""
        import json
        agencies = list(self.state.agency_catalog.keys())
        if not agencies:
            agencies = ["default", "development", "marketing", "research"]
        
        system_prompt = (
            "Eres el CEO de Jellyfish OS. Tu trabajo es clasificar la idea del usuario "
            "y asignarla a la agencia más calificada para realizar el proyecto.\n"
            f"Agencias disponibles: {', '.join(agencies)}\n\n"
            "Reglas de clasificación:\n"
            "- 'development': Para construir software, programar, resolver bugs, desarrollo web, scripts, etc.\n"
            "- 'marketing': Para estrategias de venta, redacción publicitaria, SEO, campañas, copy, etc.\n"
            "- 'research': Para investigación profunda, análisis científico, reportes, ciencia de datos, etc.\n"
            "- 'management': Para planificar proyectos abstractos o puramente metodológicos.\n"
            "- 'default': Cualquier tema genérico que no encaje en las anteriores.\n\n"
            "CRÍTICO: Debes responder ÚNICAMENTE con un objeto JSON puro, sin bloques markdown. "
            'Ejemplo: {"agency": "development"}'
        )
        
        try:
            response = self._generate_silent(
                system_prompt,
                f"Idea del usuario: {user_prompt}",
                provider=self.state.provider,
                model=self.state.model
            )
            
            if not response:
                return "development"

            import re
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                classified = data.get("agency", "development").lower().strip()
                if classified in agencies:
                    return classified
                for agency in agencies:
                    if agency in classified:
                        return agency
        except Exception as e:
            logger.error("Error al clasificar agencia con JSON: %s", e)
        
        return "development"

    def route_and_execute(self, user_prompt: str) -> str:
        """Clasifica el prompt, cambia la agencia activa y ejecuta el orquestador."""
        from core.tui import TaskProgress, tui_engine
        
        # Interceptar estado de pausa del pipeline
        if self.state.is_pipeline_paused():
            from core.ui import console
            console.print("\n[bold red]⚠️  PIPELINE BLOQUEADO - Sentinel Interactive Pause (SIP) Activo[/bold red]")
            console.print("[yellow]El proyecto se encuentra en modo de 'Esperando Intervención' debido a un fallo previo.[/yellow]")
            return self.run_sentinel_session()

        try:
            with TaskProgress(tui_engine, "auto_ceo", "CEO: Analizando requerimientos y seleccionando agencia idónea..."):
                agency = self.classify_agency(user_prompt)
        except Exception as e:
            logger.error("Error al clasificar agencia en CEO: %s", e)
            agency = "development"
            
        self.state.active_agency = agency
        
        try:
            from core.project_orchestrator import ProjectOrchestrator
            orchestrator = ProjectOrchestrator(self.state)
            return orchestrator.run(user_prompt)
        except Exception as e:
            logger.error("Error crítico durante la ejecución de la agencia %s: %s", agency, e, exc_info=True)
            from core.ui import console
            console.print(f"\n[bold red]❌ Error Crítico en Orquestador de Agencia ({agency}):[/bold red] {e}")
            return f"Error de orquestación en la agencia '{agency}': {e}"

    def run_sentinel_session(self) -> str:
        """Controla el flujo de interacción manual del agente @Sentinel con el usuario."""
        import os
        import json
        import subprocess
        from rich.panel import Panel
        from rich.markdown import Markdown
        from core.ui import console

        # Cargar agente @Sentinel para tomar el control de la consola
        self.state.load_agent("sentinel")
        
        # Recuperar el contexto de la pausa
        ctx = self.state.get_paused_context()
        task_id = ctx.get("task_id", "Desconocido")
        agent_name = ctx.get("agent_name", "Desconocido")
        error_log = ctx.get("error_log", "Sin log de error.")
        task_desc = ctx.get("task_desc", "Sin descripción.")
        output_file = ctx.get("output_file", "")

        while True:
            # Mostrar panel visual rich del error
            console.print("\n" + "=" * 80)
            console.print(Panel(
                Markdown(
                    f"### 🛡️ @Sentinel — Alerta de Interrupción del Pipeline (SIP)\n\n"
                    f"**Agente Asignado:** @{agent_name}\n"
                    f"**ID Tarea:** {task_id}\n"
                    f"**Descripción:** {task_desc}\n"
                    f"**Entregable:** `{output_file}`\n\n"
                    f"---"
                    f"#### 🔍 LOG CORTO DEL ERROR (Los 3 intentos fallaron):\n"
                    f"```\n{error_log[:1500] if len(error_log) > 1500 else error_log}\n```"
                ),
                title="[bold red]🚨 SENTINEL INTERACTIVE PAUSE 🚨[/bold red]",
                border_style="red"
            ))
            
            console.print("\n[bold yellow]Opciones de Intervención:[/bold yellow]")
            console.print("  [1] Ver log completo y reintentar con nuevas instrucciones.")
            console.print("  [2] Ignorar este error y marcar tarea como [FAILED].")
            console.print("  [3] Modificar código manualmente (abrir editor).")
            console.print("  [4] Modificar el System Prompt del agente encargado de esta tarea.")
            console.print("  [exit] Salir de Jellyfish.")
            console.print("=" * 80)
            
            try:
                choice = input("✍ Elige una opción > ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return "Intervención de Sentinel abortada por señal del terminal."

            if choice == "exit":
                import sys
                console.print("[bold purple]🪼 Jellyfish desconectado. Hasta pronto.[/bold purple]")
                sys.exit(0)

            elif choice == "1":
                console.print("\n[bold cyan]------------------ LOG COMPLETO DEL ERROR ------------------[/bold cyan]")
                console.print(error_log)
                console.print("[bold cyan]------------------------------------------------------------[/bold cyan]\n")
                
                try:
                    new_instructions = input("✍ Ingresa las nuevas instrucciones para reintentar la tarea: ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue

                if new_instructions:
                    combined_input = (
                        f"Error anterior:\n{error_log}\n"
                        f"Nuevas instrucciones de corrección del usuario:\n{new_instructions}"
                    )
                    
                    from core.translator import IntentTranslator
                    translator = IntentTranslator(self.state)
                    intent_token = translator.translate(combined_input)
                    
                    console.print(f"[green]✓ @translator generó e indexó el token: {intent_token}[/green]")
                    
                    # Actualizar descripción en la tabla de tareas
                    updated_desc = f"FIX REQUIRED [{intent_token}]: {new_instructions}. Original: {task_desc}"
                    self.update_task_in_board(task_id, new_desc=updated_desc)
                    
                    # Desbloquear pipeline y reanudar
                    self.state.set_pipeline_status("OK")
                    self.state.load_agent("default")
                    console.print("[green]✓ Pipeline desbloqueado. Reanudando ejecución de tareas...[/green]")
                    return self.route_and_execute("Reanudación de Sprint Activo")
                else:
                    console.print("[yellow]Instrucciones vacías. Retornando al menú...[/yellow]")
                    continue

            elif choice == "2":
                self.update_task_in_board(task_id, new_status="FAILED")
                self.state.set_pipeline_status("OK")
                self.state.load_agent("default")
                console.print(f"[green]✓ Tarea {task_id} marcada como FAILED. Continuando con la siguiente tarea...[/green]")
                return self.route_and_execute("Reanudación de Sprint Activo")

            elif choice == "3":
                editor = os.environ.get("EDITOR", "nano")
                try:
                    filepath = input(f"Archivo a editar (por defecto: {output_file}): ").strip() or output_file
                except (KeyboardInterrupt, EOFError):
                    continue

                file_abs_path = os.path.join(self.state.active_project, filepath)
                if os.path.exists(file_abs_path):
                    subprocess.run([editor, file_abs_path])
                else:
                    console.print(f"[red]El archivo {filepath} no existe.[/red]")
                    continue
                
                console.print("\n[bold yellow]¿Qué deseas hacer ahora?[/bold yellow]")
                console.print("  [1] Reintentar la tarea con el código modificado.")
                console.print("  [2] Marcar la tarea como completada con éxito (DONE) y reanudar.")
                console.print("  [3] Volver al menú principal de Sentinel.")
                
                try:
                    sub_choice = input("✍ Selecciona una opción [1-3] > ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue

                if sub_choice == "1":
                    self.state.set_pipeline_status("OK")
                    self.state.load_agent("default")
                    return self.route_and_execute("Reanudación de Sprint Activo")
                elif sub_choice == "2":
                    self.update_task_in_board(task_id, new_status="DONE")
                    self.state.set_pipeline_status("OK")
                    self.state.load_agent("default")
                    return self.route_and_execute("Reanudación de Sprint Activo")
                else:
                    continue

            elif choice == "4":
                agent_py = os.path.join(self.state.agency_dir, "agents", f"{agent_name}.py")
                agent_md = os.path.join(self.state.agency_dir, "agents", f"{agent_name}.md")
                
                file_to_open = None
                if os.path.isfile(agent_py):
                    file_to_open = agent_py
                elif os.path.isfile(agent_md):
                    file_to_open = agent_md
                
                if file_to_open:
                    editor = os.environ.get("EDITOR", "nano")
                    subprocess.run([editor, file_to_open])
                    self.state.scan_agencies()
                else:
                    console.print(f"[red]No se encontró el archivo del agente @{agent_name}.[/red]")
                    continue

                console.print("\n[bold yellow]¿Qué deseas hacer ahora?[/bold yellow]")
                console.print("  [1] Reintentar la tarea con el System Prompt modificado.")
                console.print("  [2] Volver al menú principal de Sentinel.")
                
                try:
                    sub_choice = input("✍ Selecciona una opción [1-2] > ").strip()
                except (KeyboardInterrupt, EOFError):
                    continue

                if sub_choice == "1":
                    self.state.set_pipeline_status("OK")
                    self.state.load_agent("default")
                    return self.route_and_execute("Reanudación de Sprint Activo")
                else:
                    continue
            else:
                console.print("[red]Opción inválida.[/red]")

    def update_task_in_board(self, task_id: str, new_desc: str = None, new_status: str = None) -> None:
        """Busca y actualiza una tarea específica en el sprint board del proyecto (Markdown y JSON)."""
        import os
        import json
        from core.project_orchestrator import ProjectOrchestrator
        
        orch = ProjectOrchestrator(self.state)
        board_path = os.path.join(self.state.active_project, orch.board_filename)
        json_board_path = board_path.replace(".md", ".json")
        
        tasks = []
        if os.path.isfile(json_board_path):
            try:
                with open(json_board_path, "r", encoding="utf-8") as f:
                    tasks = json.load(f)
            except Exception:
                pass
        
        if not tasks and os.path.isfile(board_path):
            from core.project_orchestrator import _parse_sprint_tasks
            board_content = orch._read_project_file(orch.board_filename)
            tasks = _parse_sprint_tasks(board_content)
            
        for t in tasks:
            if t.get("id") == task_id:
                if new_desc:
                    t["task"] = new_desc
                if new_status:
                    t["status"] = new_status
                    t["state"] = new_status
                break
                
        orch._save_board(tasks)
