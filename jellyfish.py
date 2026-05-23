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

# --- Logging ---
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)

# --- Imports del Core ---
from core.state import JellyfishState, DB_PATH, PLUGINS_DIR, AGENCY_DIR
from core.rag_coder import CodeKnowledgeBase
from core.llm_engine import stream_ollama
from core.plugin_manager import PluginManager
from core.crud import handle_slash_command
from core.ui import display_header, claude_style, console
from core.tui import tui_engine, TaskProgress

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.document import Document

# --- MONKEY PATCH PARA DESPLEGAR AUTOCOMPLETADO SIEMPRE HACIA ARRIBA ---
try:
    import prompt_toolkit.layout.containers as pt_containers
    _orig_float_init = pt_containers.Float.__init__
    def _patched_float_init(self, content, *args, **kwargs):
        content_name = type(content).__name__
        if "Completion" in content_name or "Menu" in content_name:
            kwargs["bottom"] = 1
            kwargs["top"] = None
        _orig_float_init(self, content, *args, **kwargs)
    pt_containers.Float.__init__ = _patched_float_init
except Exception:
    pass


# --- AUTOCOMPLETADO ---
class JellyfishCompleter(Completer):
    """Autocompletado para comandos slash, aliases y agentes @."""

    COMMANDS = {
        "/add": "Vincular archivos al contexto + RAG",
        "/context": "Gestionar archivos vinculados",
        "/purge": "Purgar todo el contexto y el índice RAG",
        "/rag": "Control del motor RAG",
        "/agent": "Gestión de agentes (Personalidades)",
        "/skill": "Gestión de habilidades (Funciones)",
        "/run": "Ejecutar comando en la terminal",
        "/plugin": "Ejecutar plugin local",
        "/provider": "Info del proveedor de IA activo",
        "/config": "Configurar proveedor, modelo o API keys",
        "/ignore": "Gestionar exclusiones (.jellyfishignore)",
        "/project": "Gestión de proyectos con metodología Scrum",
        "/clear": "Limpiar historial de chat",
        "/research": "Ejecutar agente investigador multi-pasos",
        "/auto": "Ejecutar agencia autónoma de desarrollo completa",
        "/build": "→ /auto (alias)",
        "/help": "Ver guía de comandos",
        "/exit": "Cerrar Jellyfish",
        "/Goff": "Desactivar guías de construcción del proyecto",
        "/Gon": "Activar guías de construcción del proyecto",
        # Aliases
        "/a": "→ /agent",
        "/s": "→ /skill",
        "/c": "→ /context",
        "/r": "→ /run",
        "/p": "→ /project",
        "/h": "→ /help",
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
                "subagent_provider", "subagent_model", "context_limit", "menu"
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

        # Autocompletado de agentes @ — Sprint 3.5: descripción dinámica desde .md
        elif text.startswith('@'):
            query = text[1:].lower()
            if "exit".startswith(query):
                yield Completion("@exit", start_position=-len(text), display_meta="Volver a default")
            agents_dir = os.path.join(AGENCY_DIR, "agents")
            if os.path.exists(agents_dir):
                for f in sorted(os.listdir(agents_dir)):
                    if f.endswith(".md") and not f.startswith("template"):
                        name = f[:-3]
                        if name.lower().startswith(query):
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

# Sprint 11 — Asegurar que Ollama está levantado
from core.llm_engine import ensure_ollama_running
ollama_ok = ensure_ollama_running(state.ollama_base_url)

rag = CodeKnowledgeBase(DB_PATH, active_project=state.active_project, ollama_connected=ollama_ok)
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
    )


def main():
    """Bucle principal de Jellyfish con TUI integrada.

    Sprint 7.0 — Inicializa el motor TUI para:
      - Header fijo en la zona superior (nunca se duplica).
      - Historial scrolleable en la zona central.
      - Paneles de progreso para tareas largas.
    """
    # --- Inicializar motor TUI ---
    tui_engine.init_terminal()

    # Manejar SIGWINCH (cambio de tamaño de ventana)
    def _handle_resize(signum, frame):
        pass  # El header se reimprime antes de cada prompt

    signal.signal(signal.SIGWINCH, _handle_resize)

    # Renderizar header inicial
    refresh_header(force=True)

    # Mostrar la guía del proyecto si no hay un proyecto activo o está incompleto
    from core.crud import show_project_guide_if_needed
    show_project_guide_if_needed(state)

    # Sprint 8.0 — Key bindings globales
    kb = KeyBindings()

    @kb.add('c-l')
    def _clear_screen(event):
        """Ctrl+L — Limpia la pantalla sin perder historial."""
        tui_engine.clear_scroll_region()
        refresh_header(force=True)

    @kb.add('c-s')
    def _save_chat(event):
        """Ctrl+S — Guarda el chat actual en un archivo Markdown."""
        import time as _time
        chat_dir = os.path.join(os.path.expanduser("~/MisModelosIA/agencia"), "memory")
        os.makedirs(chat_dir, exist_ok=True)
        filename = f"chat_{_time.strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(chat_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# Chat Jellyfish — {_time.strftime('%Y-%m-%d %H:%M')}\n\n")
                f.write(f"**Agente:** @{state.active_agent}\n")
                f.write(f"**Modelo:** {state.model} ({state.provider})\n\n---\n\n")
                for msg in state.history:
                    role = msg.get('role', 'unknown').upper()
                    content = msg.get('content', '')
                    f.write(f"### {role}\n\n{content}\n\n---\n\n")
            console.print(f"[green]✓ Chat guardado: {filepath}[/green]")
        except OSError as e:
            console.print(f"[red]Error guardando chat: {e}[/red]")

    session = PromptSession(
        completer=JellyfishCompleter(),
        style=claude_style,
        auto_suggest=AutoSuggestFromHistory(),
        key_bindings=kb,
        lexer=JellyfishLexer(),
    )



    try:
        while True:
            try:
                # Prompt dinámico con nombre del agente y proveedor en tiempo real
                provider_tag = f":{state.provider}" if state.provider != "ollama" else ""
                prompt_html = (
                    f"<b><ansigreen>@{state.active_agent}</ansigreen>"
                    f"<ansigray>{provider_tag}</ansigray>"
                    f" <ansiblue>&gt; </ansiblue></b>"
                )
                user_input = session.prompt(HTML(prompt_html)).strip()

                if not user_input:
                    continue

                # --- Cambio de agente con @ ---
                if user_input.startswith("@"):
                    if user_input.lower() == "@exit":
                        state.load_agent("default")
                        refresh_header()
                        continue
                    name = user_input[1:].lower().strip()
                    agent_file = os.path.join(AGENCY_DIR, "agents", f"{name}.md")
                    if os.path.exists(agent_file):
                        state.load_agent(name)
                        refresh_header()
                        console.print(f"[green]✓ Agente cambiado a @{name}[/green]")
                    else:
                        console.print(f"[yellow]Agente @{name} no encontrado.[/yellow]")
                    continue

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
                        continue

                    handle_slash_command(
                        user_input, state, rag, plugins, refresh_header
                    )
                    continue

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

            except KeyboardInterrupt:
                console.print("\n[dim]Ctrl+C — Usa /exit para salir.[/dim]")
                continue

            except EOFError:
                console.print("\n[bold purple]🪼 Jellyfish desconectado.[/bold purple]")
                break

            except Exception as e:
                console.print(f"[red]Error inesperado: {e}[/red]")
                logging.getLogger("jellyfish").error("Error en main loop: %s", e, exc_info=True)

    finally:
        # Restaurar la terminal al salir
        tui_engine.restore_terminal()


if __name__ == "__main__":
    main()
