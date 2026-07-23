#!/usr/bin/env python3
"""
╦╔═╗╦  ╦  ╦ ╦╔═╗╦╔═╗╦ ╦
║║╣ ║  ║  ╚╦╝╠╣ ║╚═╗╠═╣
╚╝╚═╝╩═╝╩═╝ ╩ ╚  ╩╚═╝╩ ╩

Jellyfish OS v5.1 — Framework de Agentes con RAG Local + Cloud AI
Orquestador principal. Toda la lógica vive en core/.

Sprint 7.0 — Integración TUI:
  - Header fijo que nunca se duplica (scroll region ANSI).
  - Historial de chat scrolleable en la zona central.
  - Paneles de progreso parpadeantes para tareas largas.
"""

import os
import sys
import signal
import logging

# --- Imports del Core ---
from core.state import JellyfishState, DB_PATH, PLUGINS_DIR, AGENCY_DIR
from core.rag_coder import CodeKnowledgeBase
from core.llm_engine import stream_ollama, LocalLLMTimeoutError
from core.plugin_manager import PluginManager
from core.crud import handle_slash_command
from core.ui import display_header, claude_style, console
from core.tui import tui_engine, TaskProgress

from logging.handlers import RotatingFileHandler

# --- Logging ---
# Refactorizado para evitar contaminación de la interfaz TUI con logs técnicos en stderr.
# Ahora se escribe de forma persistente en jellyfish.log en el directorio de la agencia.
# Se reduce backupCount a 1 para evitar un desgaste innecesario de escritura en disco por rotación agresiva.
log_file_path = os.path.join(AGENCY_DIR, "jellyfish.log")
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=1, encoding="utf-8")
    ]
)
logging.getLogger("chromadb").setLevel(logging.ERROR)
logging.getLogger("opentelemetry").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("dotenv.main").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.ERROR)


def _purge_stale_log_backups():
    """Elimina todos los archivos de log rotativos (jellyfish.log.1, .2, .3, ...).

    Deja únicamente el log principal activo.
    """
    import glob
    pattern = os.path.join(AGENCY_DIR, "jellyfish.log.*")
    for path in glob.glob(pattern):
        try:
            os.remove(path)
            logging.getLogger("jellyfish").info("Purged log backup: %s", os.path.basename(path))
        except OSError:
            pass

_purge_stale_log_backups()

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.document import Document



# --- AUTOCOMPLETADO ---
class JellyfishCompleter(Completer):
    """Autocompletado para comandos slash, aliases y agentes @."""

    COMMANDS = {
        "/add": "Vincular archivos al contexto + RAG",
        "/context": "Gestionar archivos vinculados (/c)",
        "/purge": "Purgar todo el contexto y el índice RAG",
        "/rag": "Control del motor RAG",
        "/agent": "Gestión de agentes (/a)",
        "/skill": "Gestión de habilidades (/s)",
        "/run": "Ejecutar comando en la terminal (/r)",
        "/plugin": "Ejecutar plugin local",
        "/model": "Selector interactivo de modelos (/m)",
        "/provider": "Info del proveedor de IA activo",
        "/config": "Configurar proveedor, modelo o API keys",
        "/ignore": "Gestionar exclusiones (.jellyfishignore)",
        "/project": "Gestión de proyectos Scrum (/p)",
        "/agency": "Gestión y cambio de agencias",
        "/clear": "Limpiar historial de chat",
        "/research": "Ejecutar agente investigador multi-pasos",
        "/auto": "Agencia autónoma de desarrollo (/build)",
        "/compile": "Compilar el proyecto activo",
        "/gon": "Activar guías de construcción",
        "/goff": "Desactivar guías de construcción",
        "/errors": "Ver y diagnosticar errores de la sesión (/d)",
        "/status": "Ver el estado actual del sistema y la configuración activa",
        "/help": "Ver guía de comandos (/h)",
        "/exit": "Cerrar Jellyfish",
    }

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # Autocompletado de comandos /
        if text.startswith('/') and ' ' not in text:
            for cmd, desc in self.COMMANDS.items():
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text), display_meta=desc)

        # Autocompletado de subcomandos /rag
        elif text.startswith('/rag '):
            sub = text[5:]
            for opt in ["status", "clear", "reindex", "remove", "preview"]:
                if opt.startswith(sub):
                    yield Completion(f"/rag {opt}", start_position=-len(text))

        # Autocompletado de subcomandos /config
        elif text.startswith('/config '):
            sub = text[8:]
            for opt in [
                "show", "providers", "provider", "model", "key", "endpoint",
                "subagent_provider", "subagent_model", "context_limit",
                "local_context_limit", "menu"
            ]:
                if opt.startswith(sub):
                    yield Completion(f"/config {opt}", start_position=-len(text))

        # Autocompletado de subcomandos /ignore
        elif text.startswith('/ignore '):
            sub = text[8:]
            for opt in ["show", "init", "add", "remove"]:
                if opt.startswith(sub):
                    yield Completion(f"/ignore {opt}", start_position=-len(text))

        # Autocompletado de subcomandos /project
        elif text.startswith('/project '):
            sub = text[9:]
            for opt in ["new", "info", "unlink"]:
                if opt.startswith(sub):
                    yield Completion(f"/project {opt}", start_position=-len(text))

        # Autocompletado de subcomandos /agency
        elif text.startswith('/agency '):
            sub = text[8:]
            if sub.startswith('switch '):
                target = sub[7:]
                for agency in state.agency_catalog.keys():
                    if agency.startswith(target):
                        yield Completion(f"/agency switch {agency}", start_position=-len(text))
            else:
                for opt in ["switch"]:
                    if opt.startswith(sub):
                        yield Completion(f"/agency {opt}", start_position=-len(text))

        # Autocompletado de agentes @ — Sprint 3.5: descripción dinámica desde .md, filtrado por agencia_activa
        elif text.startswith('@'):
            query = text[1:].lower()
            if "exit".startswith(query):
                yield Completion("@exit", start_position=-len(text), display_meta="Volver a default")
            agents_dir = os.path.join(AGENCY_DIR, "agents")
            if os.path.exists(agents_dir):
                active_agency = getattr(state, "active_agency", "default")
                allowed_agents = state.agency_catalog.get(active_agency, [])
                if not allowed_agents:
                    allowed_agents = state.agency_catalog.get("default", [])
                    
                for f in sorted(os.listdir(agents_dir)):
                    if f.endswith(".md") and not f.startswith("template"):
                        name = f[:-3]
                        if name.lower().startswith(query):
                            if name.lower() not in allowed_agents:
                                continue
                            
                            # Leer la primera línea no vacía del archivo como descripción
                            desc = "Agente"
                            try:
                                with open(os.path.join(agents_dir, f), encoding="utf-8", errors="ignore") as fh:
                                    for line in fh:
                                        stripped = line.strip().lstrip("#").strip()
                                        if stripped:
                                            desc = stripped[:50]
                                            break
                            except OSError:
                                pass
                            yield Completion(f"@{name}", start_position=-len(text), display_meta=desc)


# --- SYNTAX HIGHLIGHTING DEL PROMPT ---
# Sprint 8.0 — Colorea comandos slash en verde, rutas en amarillo, @agentes en púrpura
class JellyfishLexer(Lexer):
    """Resaltado de sintaxis en tiempo real para el prompt de entrada."""

    def lex_document(self, document: Document):
        text = document.text

        def get_line(lineno):
            line = document.lines[lineno]
            result = []
            if line.startswith('/'):
                # Comando slash: verde brillante
                parts = line.split(' ', 1)
                result.append(('ansibrightyellow', parts[0]))
                if len(parts) > 1:
                    result.append(('', ' '))
                    arg = parts[1]
                    if arg.startswith('@'):
                        result.append(('ansimagenta bold', arg))
                    elif '/' in arg or '.' in arg:
                        result.append(('ansicyan', arg))
                    else:
                        result.append(('', arg))
            elif line.startswith('@'):
                result.append(('ansimagenta bold', line))
            else:
                result.append(('', line))
            return result

        return get_line


# --- INICIALIZACIÓN ---
state = JellyfishState()

# Auto-migración de modelos obsoletos de Gemini
if state.provider == "gemini" and (not state.model or "gemini-3.5" in state.model or "gemini-3.1" in state.model):
    from core.config import save_config_to_env
    console.print(f"[yellow]⚠️  Modelo obsoleto '{state.model}' detectado. Migrando automáticamente a 'gemini-2.5-flash'...[/yellow]")
    save_config_to_env(state, model="gemini-2.5-flash")

# Verificar API Key si el proveedor no es Ollama
if state.provider != "ollama":
    from core.state import PROVIDER_CONFIGS
    prov_cfg = PROVIDER_CONFIGS.get(state.provider)
    if prov_cfg and prov_cfg.get("api_key_env"):
        env_var = prov_cfg["api_key_env"]
        key_val = os.getenv(env_var)
        if not key_val:
            console.print(f"[yellow]⚠ No se detectó la API Key para el proveedor '{state.provider}' ({env_var}).[/yellow]")
            key_val = PromptSession().prompt(f"Ingresa tu API Key para {state.provider} (se guardará de forma segura): ").strip()
            if key_val:
                from core.crud import _save_provider_key
                _save_provider_key(state, state.provider, key_val)
                state.load_config()
                os.environ[env_var] = key_val

# Sprint 11 — Asegurar que Ollama está levantado
from core.llm_engine import ensure_ollama_running
ollama_ok = ensure_ollama_running(state.ollama_base_url)

rag = CodeKnowledgeBase(DB_PATH, active_project=state.active_project, ollama_connected=ollama_ok)
state.rag = rag
plugins = PluginManager(PLUGINS_DIR)


def refresh_header(force=False):
    """Renderiza el header con el estado actual del sistema.
    
    Sprint 8.0 — Ahora pasa el token_budget para la barra visual
    y el flag _llm_busy para el spinner de conectividad.
    """
    if not force:
        return
    import core.state as _state_mod
    proj_name = os.path.basename(state.active_project) if state.active_project else ""
    proj_methodology = getattr(state, "project_methodology", "") if state.active_project else ""
    display_header(
        active_agent=state.active_agent,
        model_name=state.model,
        num_skills=len(state.active_skills),
        num_docs=len(state.context_files),
        rag_status=rag.status_text,
        provider=state.provider,
        project_name=proj_name,
        project_methodology=proj_methodology,
        token_budget=state.token_budget_info(),
        llm_busy=_state_mod._llm_busy,
        session_tokens=getattr(state, "session_tokens", 0),
        active_agency=getattr(state, "active_agency", "default"),
    )


def _sentinel_forensic_boot_scan(state):
    """Boot Hook Forense: escanea el directorio en busca de artefactos de colapso
    (jellyfish_error_report_*.md, jellyfish_debug.log) de sesiones anteriores.

    Si se encuentran, muestra una alerta visual rich al usuario y ofrece un menú
    interactivo para revisar, ignorar o borrar los archivos forenses.

    No invoca al LLM ni al agente @Sentinel directamente — es una función ligera
    de detección y reporte que se ejecuta antes de que el LLM esté disponible.
    """
    import glob
    from rich.panel import Panel
    from rich.markdown import Markdown

    forensic_files = []

    # Escanear reportes de error
    error_reports = glob.glob(os.path.join(AGENCY_DIR, "jellyfish_error_report_*.md"))
    forensic_files.extend(error_reports)

    # Escanear debug log
    debug_log = os.path.join(AGENCY_DIR, "jellyfish_debug.log")
    if os.path.isfile(debug_log) and os.path.getsize(debug_log) > 0:
        forensic_files.append(debug_log)

    # Escanear también en el proyecto activo si está configurado
    if state.active_project and os.path.isdir(state.active_project):
        proj_error_reports = glob.glob(os.path.join(state.active_project, "jellyfish_error_report_*.md"))
        forensic_files.extend(proj_error_reports)

        proj_debug_log = os.path.join(state.active_project, "jellyfish_debug.log")
        if os.path.isfile(proj_debug_log) and os.path.getsize(proj_debug_log) > 0:
            forensic_files.append(proj_debug_log)

    # Deduplicar (por si AGENCY_DIR == active_project)
    forensic_files = list(dict.fromkeys(forensic_files))

    if not forensic_files:
        return

    # Construir resumen de archivos encontrados
    file_list_md = ""
    for fp in forensic_files:
        basename = os.path.basename(fp)
        size_kb = os.path.getsize(fp) / 1024
        file_list_md += f"- `{basename}` ({size_kb:.1f} KB)\n"

    console.print(Panel(
        Markdown(
            f"### 🛡️ @Sentinel — Análisis Forense de Arranque\n\n"
            f"Se detectaron **{len(forensic_files)}** artefacto(s) de colapso de sesiones anteriores:\n\n"
            f"{file_list_md}\n"
            f"Estos archivos contienen trazas de errores y diagnósticos que pueden ayudar "
            f"a identificar la causa del último fallo del sistema."
        ),
        title="[bold yellow]⚠️ ARTEFACTOS FORENSES DETECTADOS[/bold yellow]",
        border_style="yellow"
    ))

    console.print("\n[bold yellow]Opciones:[/bold yellow]")
    console.print("  [1] Ver el contenido de los reportes.")
    console.print("  [2] Ignorar y continuar con el arranque normal.")
    console.print("  [3] Borrar todos los archivos forenses y continuar.")

    try:
        choice = input("\n✍ Elige una opción [1-3] > ").strip()
    except (KeyboardInterrupt, EOFError):
        console.print("[dim]Continuando con el arranque normal...[/dim]")
        return

    if choice == "1":
        for fp in forensic_files:
            basename = os.path.basename(fp)
            console.print(f"\n[bold cyan]{'─' * 60}[/bold cyan]")
            console.print(f"[bold cyan]📄 {basename}[/bold cyan]")
            console.print(f"[bold cyan]{'─' * 60}[/bold cyan]")
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(5000)  # Limitar a 5KB para no saturar la pantalla
                if len(content) >= 5000:
                    content += "\n\n[... TRUNCADO — archivo completo disponible en disco ...]"
                console.print(Markdown(content))
            except OSError as e:
                console.print(f"[red]Error al leer {basename}: {e}[/red]")

        console.print(f"\n[bold yellow]{'─' * 60}[/bold yellow]")
        console.print("[bold yellow]¿Qué deseas hacer ahora?[/bold yellow]")
        console.print("  [1] Borrar los archivos forenses y continuar.")
        console.print("  [2] Conservar los archivos y continuar.")
        try:
            sub_choice = input("✍ Elige una opción [1-2] > ").strip()
        except (KeyboardInterrupt, EOFError):
            sub_choice = "2"

        if sub_choice == "1":
            for fp in forensic_files:
                try:
                    os.remove(fp)
                except OSError:
                    pass
            console.print("[green]✓ Archivos forenses eliminados.[/green]")
        else:
            console.print("[dim]Archivos conservados. Continuando con el arranque...[/dim]")

    elif choice == "3":
        for fp in forensic_files:
            try:
                os.remove(fp)
            except OSError:
                pass
        console.print("[green]✓ Archivos forenses eliminados. Continuando con el arranque...[/green]")
    else:
        console.print("[dim]Continuando con el arranque normal...[/dim]")


def main():
    """Bucle principal de Jellyfish con TUI integrada.

    Sprint 7.0 — Inicializa el motor TUI para:
      - Header fijo en la zona superior (nunca se duplica).
      - Historial scrolleable en la zona central.
      - Paneles de progreso para tareas largas.
    """
    # --- Inicializar motor TUI ---
    tui_engine.init_terminal()

    # --- Boot Hook Forense: Sentinel ---
    _sentinel_forensic_boot_scan(state)

    # Renderizar header inicial
    refresh_header(force=True)

    # Mostrar la guía del proyecto si no hay un proyecto activo o está incompleto
    from core.crud import show_project_guide_if_needed
    show_project_guide_if_needed(state)

    # Sprint 11 — Aislamiento y Control de Ejecución Seguro
    console.print("[dim cyan]🛡  Modo de Aislamiento de Proyecto y Control de Ejecución Seguro Activo.[/dim cyan]")

    # Sprint 8.0 — Key bindings globales (FASE 1)
    from core.terminal import get_global_keybindings
    kb = get_global_keybindings(state)

    def process_command(user_input):
        user_input = user_input.strip()
        if not user_input:
            return

        try:
            # --- Cambio de agente con @ ---
            if user_input.startswith("@"):
                if user_input.lower() == "@exit":
                    state.load_agent("default")
                    refresh_header()
                    return
                name = user_input[1:].lower().strip()
                agent_file = os.path.join(AGENCY_DIR, "agents", f"{name}.md")
                if os.path.exists(agent_file):
                    state.load_agent(name)
                    refresh_header()
                    console.print(f"[green]✓ Agente cambiado a @{name}[/green]")
                else:
                    console.print(f"[yellow]Agente @{name} no encontrado.[/yellow]")
                return

            # --- Comandos slash ---
            if user_input.startswith("/"):
                if user_input.startswith("/research "):
                    from core.orchestrator import ResearchOrchestrator
                    orchestrator = ResearchOrchestrator(state, rag)
                    query = user_input[10:].strip()
                    if query:
                        with TaskProgress(tui_engine, "research", "Investigación multi-agente..."):
                            final_report = orchestrator.execute_task(query)
                        state.history.append({"role": "user", "content": user_input})
                        state.history.append({"role": "assistant", "content": final_report})
                    else:
                        console.print("[yellow]Uso: /research <consulta_compleja>[/yellow]")
                    refresh_header(force=True)
                    return

                handle_slash_command(
                    user_input, state, rag, plugins, refresh_header
                )
                return

            # --- RAG: Siempre buscar contexto relevante ---
            rag_context = ""
            if rag.is_active:
                rag_context = rag.query_code(user_input)

            # --- Agregar mensaje del usuario al historial ---
            state.history.append({"role": "user", "content": user_input})

            # --- Invocar LLM con contexto RAG ---
            result = stream_ollama(state, rag_context=rag_context)

            if result:
                state.history.append({"role": "assistant", "content": result})

        except LocalLLMTimeoutError as timeout_ex:
            console.print(f"[red]⚠ El modelo local superó el tiempo de espera (Timeout). Memoria saturada.[/red]")
            logging.getLogger("jellyfish").error("Timeout del modelo local (GPU saturada): %s", timeout_ex)
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            if not hasattr(state, "captured_errors"):
                state.captured_errors = []
            state.captured_errors.append(error_trace)
            console.print(f"[red]Error inesperado: {e}[/red]")
            logging.getLogger("jellyfish").error("Error en ejecución de comando: %s", e, exc_info=True)
        # Sprint 8.0 — Mantener el header visible actualizando antes del siguiente prompt
        # refresh_header(force=True)  # <-- Comentado nuevamente por petición del usuario (no reimprimir nunca)

    tui_engine.command_handler = process_command

    try:
        tui_engine.get_user_input(
            state,
            JellyfishCompleter(),
            kb,
            JellyfishLexer()
        )
    except KeyboardInterrupt:
        pass
    finally:
        # Restaurar la terminal al salir
        tui_engine.restore_terminal()
        from core.ui import handle_exit_flow, sync_readme_on_exit
        handle_exit_flow(state)
        sync_readme_on_exit(state)
        console.print("[bold purple]🪼 Jellyfish desconectado. Hasta pronto.[/bold purple]")


if __name__ == "__main__":
    main()
