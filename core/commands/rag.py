import os
import threading
from rich.panel import Panel
from rich.prompt import Confirm
from prompt_toolkit import PromptSession
from core.ui import console
from core.config import AGENCY_DIR
from core.ui import file_browser, interactive_picker
from core.tui import tui_engine, TaskProgress

def handle_rag_command(command: str, arg: str, state, rag, display_header_func) -> None:
    if command == "/add":
        _handle_add(arg, state, rag, display_header_func)
    elif command in ("/context", "/c"):
        _handle_context(state, display_header_func)
    elif command in ("/purge", "/context-f.del"):
        _handle_purge(state, rag, display_header_func)
    elif command == "/rag":
        _handle_rag(arg, rag, display_header_func)
    elif command == "/ignore":
        _handle_ignore(arg, state)

def _handle_add(arg: str, state, rag, display_header_func):
    """Procesa el comando /add con indexación RAG en hilo secundario."""
    if arg:
        candidate = os.path.abspath(os.path.expanduser(arg))
        if os.path.exists(candidate):
            path = candidate
        else:
            console.print(f"Ruta no encontrada: {arg}")
            return
    else:
        path = file_browser(".")
    if not path:
        return

    if os.path.isdir(path):
        console.print()
        try:
            rag.index_codebase(path)
        except KeyboardInterrupt:
            console.print("\n[bold yellow]⚠ Indexación cancelada por el usuario.[/bold yellow]")
    else:
        state.add_context_file(path)

    state.refresh_static_context()
    console.print(f"✓ Contexto actualizado: {len(state.context_files)} archivos.")
    input("\nPresiona Enter para continuar...")

def _handle_context(state, display_header_func):
    """Procesa el comando /context."""
    files = list(state.context_files)
    if not files:
        console.print("⚠ El contexto está vacío. Usa /add para vincular archivos.")
        input("\nPresiona Enter para continuar...")
    else:
        while True:
            files = list(state.context_files)
            if not files:
                break
            sel = interactive_picker("CONTEXTO", ["Limpiar todo"] + files)
            if not sel:
                break
            if sel == "Limpiar todo":
                state.context_files.clear()
                state.refresh_static_context()
                console.print("✓ Contexto limpiado.")
                break
            state.context_files.discard(sel)
            state.refresh_static_context()

def _handle_purge(state, rag, display_header_func):
    """Procesa el comando /purge."""
    if not state.context_files and not rag.is_active:
        console.print("⚠ No hay nada que purgar.")
        input("\nPresiona Enter para continuar...")
    else:
        state.context_files.clear()
        state.refresh_static_context()
        rag.clear_index()
        console.print("☢ Contexto y base RAG purgados por completo.")
        input("\nPresiona Enter para continuar...")

def _handle_rag(arg: str, rag, display_header_func):
    """Procesa el comando /rag con subcomandos extendidos."""
    arg = arg.strip()
    parts = arg.split(" ", 1)
    subcmd = parts[0].lower()
    val = parts[1].strip() if len(parts) > 1 else ""

    if subcmd == "clear":
        rag.clear_index()

    elif subcmd == "status":
        if rag.is_active:
            console.print(
                f"RAG activo: {rag.indexed_chunk_count} chunks, "
                f"{rag.indexed_file_count} archivos."
            )
        else:
            console.print("RAG inactivo. Usa /add para indexar una carpeta.")

    elif subcmd == "reindex":
        if not val:
            console.print("Uso: /rag reindex <ruta>")
        else:
            exp_val = os.path.expanduser(val)
            if os.path.isdir(exp_val):
                rag.clear_index()
                rag.index_codebase(exp_val)
            else:
                console.print(f"Ruta no válida: {val}")

    elif subcmd == "remove":
        if not val:
            console.print("Uso: /rag remove <ruta>")
        else:
            rag.remove_path(os.path.expanduser(val))

    elif subcmd == "preview":
        if not val:
            console.print("Uso: /rag preview <pregunta>")
        elif not rag.is_active:
            console.print("⚠ No hay índice RAG activo. Usa /add para indexar una carpeta.")
        else:
            raw_context = rag.query_code(val)
            if not raw_context:
                console.print("⚠ No se encontraron fragmentos relevantes para esa consulta.")
            else:
                import re as _re
                from core.rag_coder import _FRAG_OPEN
                _frag_prefix = _re.escape(_FRAG_OPEN.split(" ")[0])
                frag_pattern = _re.compile(
                    rf'{_frag_prefix}\s+source="([^"]+)"\s+relevance="([^"]+)"\s+match="([^"]+)"[^>]*>\n(.*?)\n\s*<',
                    _re.DOTALL
                )
                matches = frag_pattern.findall(raw_context)
                if matches:
                    from rich.table import Table
                    table = Table(title="🔍 Previsualización RAG", border_style="dim white", show_lines=True)
                    table.add_column("#", justify="center", width=3)
                    table.add_column("Fuente", style="bold cyan", max_width=40)
                    table.add_column("Distancia L2", justify="center", width=12)
                    table.add_column("Match", justify="center", width=8)
                    table.add_column("Fragmento (primeras 120 chars)", max_width=50)
                    for i, (source, relevance, match, content) in enumerate(matches, 1):
                        preview = content.strip()[:120].replace('\n', ' ')
                        table.add_row(str(i), source, relevance, match, preview)
                    console.print(table)
                    console.print(f"[dim]Total chars del contexto RAG: {len(raw_context):,}[/dim]")
                else:
                    console.print(Panel(raw_context[:2000], title="RAG Preview (crudo)", border_style="dim white"))

    else:
        if not subcmd:
            rag.enabled = not getattr(rag, "enabled", True)
            estado = "activado" if rag.enabled else "desactivado"
            console.print(f"✓ Inyección de contexto RAG {estado} temporalmente.")
        else:
            console.print(
                "Uso:\n"
                "  /rag status           — Ver estado del índice\n"
                "  /rag clear            — Eliminar el índice completo\n"
                "  /rag reindex <path>   — Reindexar una ruta\n"
                "  /rag remove <path>    — Eliminar una ruta del índice\n"
                "  /rag preview <query>  — Previsualizar fragmentos que se enviarían al LLM"
            )

    input("\nPresiona Enter para continuar...")
    os.system("cls" if os.name == "nt" else "clear")
    if getattr(tui_engine, "_initialized", False):
        tui_engine.print_welcome_logo()
    display_header_func()

def _handle_ignore(arg: str, state):
    """Manejador del comando /ignore para gestionar .jellyfishignore."""
    sub = arg.strip()
    ignore_file_path = os.path.join(AGENCY_DIR, ".jellyfishignore")

    def _read_patterns():
        if not os.path.exists(ignore_file_path):
            return []
        patterns = []
        with open(ignore_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
        return patterns

    def _write_patterns(patterns):
        with open(ignore_file_path, "w", encoding="utf-8") as f:
            f.write("# Patrones de exclusión para Jellyfish RAG\n")
            for p in patterns:
                f.write(f"{p}\n")

    if not sub:
        while True:
            action = interactive_picker(
                "GESTIÓN DE EXCLUSIONES (.jellyfishignore)",
                ["Ver Patrones", "Inicializar con Defaults", "Agregar Patrón", "Remover Patrón"]
            )
            if not action:
                break

            session = PromptSession()

            if action == "Ver Patrones":
                patterns = _read_patterns()
                if not patterns:
                    console.print("No hay patrones definidos en .jellyfishignore.")
                else:
                    content = "\n".join([f"  • {p}" for p in patterns])
                    console.print(Panel(content, title=".jellyfishignore", border_style="dim white"))
                input("\nPresiona Enter para continuar...")

            elif action == "Inicializar con Defaults":
                defaults = [
                    "venv/", ".venv/", "env/", ".git/", "__pycache__/",
                    "node_modules/", "code_vector_db/", "code_vector_db*/", "code_vector_db*", "test_db/",
                    "dist/", "build/", ".next/", "*.png", "*.jpg", "*.jpeg",
                    "*.exe", "*.so", "*.dll", "*.zip", "*.tar.gz"
                ]
                _write_patterns(defaults)
                console.print("✓ .jellyfishignore inicializado con patrones por defecto.")
                input("\nPresiona Enter para continuar...")

            elif action == "Agregar Patrón":
                pat = session.prompt("Escribe el patrón a excluir (ej. logs/ o *.log): ").strip()
                if pat:
                    patterns = _read_patterns()
                    if pat in patterns:
                        console.print("El patrón ya existe.")
                    else:
                        patterns.append(pat)
                        _write_patterns(patterns)
                        console.print(f"✓ Patrón '{pat}' agregado.")
                    input("\nPresiona Enter para continuar...")

            elif action == "Remover Patrón":
                patterns = _read_patterns()
                if not patterns:
                    console.print("No hay patrones para remover.")
                    input("\nPresiona Enter para continuar...")
                    continue
                sel = interactive_picker("SELECCIONA PATRÓN A REMOVER", patterns)
                if sel:
                    patterns.remove(sel)
                    _write_patterns(patterns)
                    console.print(f"✓ Patrón '{sel}' removido.")
                    input("\nPresiona Enter para continuar...")
        return

    parts = sub.split(" ", 1)
    subcmd = parts[0].lower()
    val = parts[1].strip() if len(parts) > 1 else ""

    if subcmd == "show":
        patterns = _read_patterns()
        if not patterns:
            console.print("No hay patrones definidos en .jellyfishignore.")
        else:
            content = "\n".join([f"  • {p}" for p in patterns])
            console.print(Panel(content, title=".jellyfishignore", border_style="dim white"))

    elif subcmd == "init":
        defaults = [
            "venv/", ".venv/", "env/", ".git/", "__pycache__/",
            "node_modules/", "code_vector_db/", "code_vector_db*/", "code_vector_db*", "test_db/",
            "dist/", "build/", ".next/", "*.png", "*.jpg", "*.jpeg",
            "*.exe", "*.so", "*.dll", "*.zip", "*.tar.gz"
        ]
        _write_patterns(defaults)
        console.print("✓ .jellyfishignore inicializado con patrones por defecto.")

    elif subcmd == "add":
        if not val:
            console.print("Por favor especifica el patrón a agregar.")
        else:
            patterns = _read_patterns()
            if val in patterns:
                console.print("El patrón ya existe.")
            else:
                patterns.append(val)
                _write_patterns(patterns)
                console.print(f"✓ Patrón '{val}' agregado.")

    elif subcmd == "remove":
        if not val:
            console.print("Por favor especifica el patrón a remover.")
        else:
            patterns = _read_patterns()
            if val in patterns:
                patterns.remove(val)
                _write_patterns(patterns)
                console.print(f"✓ Patrón '{val}' removido.")
            else:
                console.print(f"Patrón '{val}' no encontrado en .jellyfishignore.")
