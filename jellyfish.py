#!/usr/bin/env python3
"""
╦╔═╗╦  ╦  ╦ ╦╔═╗╦╔═╗╦ ╦
║║╣ ║  ║  ╚╦╝╠╣ ║╚═╗╠═╣
╚╝╚═╝╩═╝╩═╝ ╩ ╚  ╩╚═╝╩ ╩

Jellyfish OS v5.0 — Framework de Agentes con RAG Local + Cloud AI
Orquestador principal. Toda la lógica vive en core/.
"""

import os
import sys
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

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import Completer, Completion


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
        "/clear": "Limpiar historial de chat",
        "/research": "Ejecutar agente investigador multi-pasos",
        "/help": "Ver guía de comandos",
        "/exit": "Cerrar Jellyfish",
        # Aliases
        "/a": "→ /agent",
        "/s": "→ /skill",
        "/c": "→ /context",
        "/r": "→ /run",
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
            for opt in ["status", "clear", "reindex", "remove"]:
                if opt.startswith(sub):
                    yield Completion(f"/rag {opt}", start_position=-len(text))

        # Autocompletado de subcomandos /config
        elif text.startswith('/config '):
            sub = text[8:]
            for opt in ["show", "provider", "model", "key", "menu"]:
                if opt.startswith(sub):
                    yield Completion(f"/config {opt}", start_position=-len(text))

        # Autocompletado de subcomandos /ignore
        elif text.startswith('/ignore '):
            sub = text[8:]
            for opt in ["show", "init", "add", "remove"]:
                if opt.startswith(sub):
                    yield Completion(f"/ignore {opt}", start_position=-len(text))

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


# --- INICIALIZACIÓN ---
state = JellyfishState()
rag = CodeKnowledgeBase(DB_PATH)
plugins = PluginManager(PLUGINS_DIR)


def refresh_header():
    """Renderiza el header con el estado actual del sistema."""
    display_header(
        active_agent=state.active_agent,
        model_name=state.model,
        num_skills=len(state.active_skills),
        num_docs=len(state.context_files),
        rag_status=rag.status_text,
        provider=state.provider,
    )


def main():
    """Bucle principal de Jellyfish."""
    refresh_header()
    session = PromptSession(completer=JellyfishCompleter(), style=claude_style)

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


if __name__ == "__main__":
    main()