import os
from rich.panel import Panel
from core.ui import console
from core.tui import TaskProgress, tui_engine

def handle_orchestration_command(command: str, arg: str, state, rag, display_header_func) -> None:
    if command == "/auto":
        _handle_auto(arg, state, display_header_func)
    elif command == "/research":
        _handle_research(arg, state, rag, display_header_func)
    elif command == "/agency":
        _handle_agency(arg, state, display_header_func)

def _handle_auto(arg: str, state, display_header_func) -> None:
    """Manejador del comando /auto — Agencia Autónoma de Desarrollo."""
    idea = arg.strip()

    if not state.active_project:
        console.print(
            "⚠ No hay un proyecto activo. "
            "Usa [bold]/project new <ruta>[/bold] primero para crear uno."
        )
        return

    if not idea:
        # Determinar si existe un tablero previo en el proyecto activo para permitir /auto vacío
        from core.project_orchestrator import ProjectOrchestrator
        try:
            temp_orch = ProjectOrchestrator(state)
            board_filename = temp_orch.board_filename
            board_path = os.path.join(state.active_project, board_filename)
            json_board_path = os.path.join(state.active_project, board_filename.replace(".md", ".json"))
            has_existing_board = os.path.isfile(board_path) or os.path.isfile(json_board_path)
        except Exception:
            has_existing_board = False

        if has_existing_board:
            idea = "Reanudación de Sprint Activo"
        else:
            console.print(
                "Uso: [bold]/auto <descripción de tu proyecto>[/bold]\n"
                "[dim]Ejemplo: /auto Quiero una API REST con FastAPI para gestionar "
                "inventario con exportación a PDF[/dim]"
            )
            return

    from core.agency_orchestrator import AgencyOrchestrator

    orchestrator = AgencyOrchestrator(state)
    final_report = orchestrator.route_and_execute(idea)

    state.history.append({"role": "user", "content": f"/auto {idea}"})
    state.history.append({"role": "assistant", "content": final_report})

def _handle_research(arg: str, state, rag, display_header_func) -> None:
    """Manejador del comando /research — Investigación Autónoma Multi-Paso."""
    query = arg.strip()
    if not query:
        console.print("Uso: /research <consulta_compleja>")
        return

    from core.orchestrator import ResearchOrchestrator
    orchestrator = ResearchOrchestrator(state, rag)
    
    with TaskProgress(tui_engine, "research", "Investigación multi-agente..."):
        final_report = orchestrator.execute_task(query)
        
    state.history.append({"role": "user", "content": f"/research {query}"})
    state.history.append({"role": "assistant", "content": final_report})
    display_header_func()

def _handle_agency(arg: str, state, display_header_func) -> None:
    """Manejador del comando /agency."""
    parts = arg.strip().split()
    if not parts:
        console.print("\n🏢 Catálogo de Agencias de Jellyfish OS v6")
        console.print(f"Agencia activa actual: {state.active_agency.upper()}\n")
        for agency, agents in state.agency_catalog.items():
            active_marker = "★ " if agency == state.active_agency else "  "
            agents_list = ", ".join(f"@{a}" for a in agents)
            console.print(f"{active_marker}{agency.upper()} -> {agents_list}")
        console.print("\n[dim]Usa `/agency switch <nombre>` para cambiar de agencia.[/dim]\n")
        return

    subcmd = parts[0].lower()
    if subcmd == "switch":
        if len(parts) < 2:
            console.print("Uso: /agency switch <nombre_de_agencia>")
            return
        target_agency = parts[1].lower().strip()
        
        state.scan_agencies()
        
        if target_agency not in state.agency_catalog:
            state.agency_catalog.setdefault(target_agency, [])
        
        state.active_agency = target_agency
        state.load_agent("default")
        state.active_agency = target_agency
        
        console.print(f"✓ Cambiado exitosamente a la agencia: {target_agency.upper()}")
        if display_header_func:
            display_header_func()
    else:
        console.print(f"Subcomando desconocido: {subcmd}. Usa `/agency` o `/agency switch <nombre>`.")
