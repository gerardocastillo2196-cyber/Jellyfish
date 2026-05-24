import os
import sys
import tty
import termios
import logging
from io import StringIO
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.syntax import Syntax
from prompt_toolkit.styles import Style

from core.state import get_term_width

logger = logging.getLogger("jellyfish.ui")

# --- CONFIGURACIÓN DE APARIENCIA ---
console = Console()

# Estilo para el autocompletado (Púrpura Profundo)
claude_style = Style.from_dict({
    'completion-menu': 'bg:#2d004d #ffffff',
    'completion-menu.completion': 'bg:#2d004d #bbbbbb',
    'completion-menu.completion.current': 'bg:#5e008b #ffffff',
})

# Consola global con ancho controlado
_main_console = Console(force_terminal=True, width=120)


def display_header(active_agent="default", model_name="none", num_skills=0,
                   num_docs=0, rag_status="RAG[OFF]", provider="ollama",
                   project_name="", project_methodology="", silent=False,
                   token_budget=None, llm_busy=False, session_tokens=0):
    """Renderiza el header usando el motor TUI (header fijo).

    Sprint 7.0 — Delega al TUIEngine para pintar el header en la zona fija.
    Si el TUI no está inicializado, usa el fallback clásico.
    Sprint 8.0 — Soporta token_budget y llm_busy para el header enriquecido.

    Args:
        active_agent: Nombre del agente activo.
        model_name: Nombre del modelo LLM.
        num_skills: Número de skills cargadas.
        num_docs: Número de documentos en contexto.
        rag_status: Estado del motor RAG.
        provider: Nombre del proveedor de IA activo.
        project_name: Nombre del proyecto activo.
        project_methodology: Metodología del proyecto activo.
        silent: Si True, retorna el output como string sin imprimir.
        token_budget: Dict con info del presupuesto de tokens (de state.token_budget_info()).
        llm_busy: True si hay una petición LLM en vuelo.
        session_tokens: Tokens totales consumidos en la sesión actual.
    """
    try:
        from core.tui import tui_engine
        if tui_engine._initialized:
            tui_engine.render_header(
                active_agent=active_agent,
                model_name=model_name,
                num_skills=num_skills,
                num_docs=num_docs,
                rag_status=rag_status,
                provider=provider,
                project_name=project_name,
                project_methodology=project_methodology,
                token_budget=token_budget,
                llm_busy=llm_busy,
                session_tokens=session_tokens,
            )
            return
    except ImportError:
        pass

    # Fallback clásico (para compatibilidad)
    buf = StringIO()
    term_width = min(_main_console.width, get_term_width())
    local_console = Console(file=buf, force_terminal=True, width=term_width)

    from core.llm_engine import is_ollama_running, is_model_available_locally
    ollama_ok = is_ollama_running()
    model_status_icon = "🟢"
    if provider == "ollama":
        if not ollama_ok:
            model_status_icon = "🔴"
        elif not is_model_available_locally(model_name):
            model_status_icon = "⚠️"
    else:
        key_env = "GEMINI_API_KEY" if provider == "gemini" else "ANTHROPIC_API_KEY" if provider == "claude" else ""
        if key_env and not os.getenv(key_env):
            model_status_icon = "🔑"

    # Arte ASCII
    jelly = Text()
    jelly.append("   ▄███▄           ▄███████▄           ▄███▄\n", style="bold purple")
    jelly.append("  ███████         ███████████         ███████\n", style="bold violet")
    jelly.append("  █▀█▀█▀█         ███▀███▀███         █▀█▀█▀█\n", style="bold purple")
    jelly.append("   █ █ █          █  █  █  █           █ █ █\n", style="bold violet")
    jelly.append("   ▀ ▀ ▀          ▀  ▀  ▀  ▀           ▀ ▀ ▀", style="bold purple")
    local_console.print(jelly)

    # Barra de estado responsive (una fila o dos filas)
    if term_width >= 115:
        status_line = Text(no_wrap=True)
        status_line.append(" JELLYFISH ", style="bold white on #5e008b")
        status_line.append(" AGENT ", style="bold #df00ff on #26004d")
        status_line.append(f"{active_agent.upper()[:10]} ", style="bold white on #26004d")
        
        status_line.append("│", style="bold #5e008b on #26004d")
        ctx_color = "#00ff00" if num_docs > 0 else "dim white"
        status_line.append(f" CTX[{num_docs}] ", style=f"bold {ctx_color} on #26004d")
        
        status_line.append("│", style="bold #5e008b on #26004d")
        rag_color = "#00ff00" if "OFF" not in rag_status else "dim white"
        status_line.append(f" {rag_status} ", style=f"bold {rag_color} on #26004d")

        status_line.append("│", style="bold #5e008b on #26004d")
        ollama_color = "#00ff00" if ollama_ok else "#ef4444"
        status_line.append(" OLLAMA[ON] " if ollama_ok else " OLLAMA[OFF] ", style=f"bold {ollama_color} on #26004d")
        
        status_line.append("│", style="bold #5e008b on #26004d")
        status_line.append(f" SKL[{num_skills}] ", style="bold cyan on #26004d")
        
        if project_name:
            status_line.append("│", style="bold #5e008b on #26004d")
            method_suffix = f" ({project_methodology.upper()})" if project_methodology else ""
            proj_disp = project_name.split("/")[-1]
            status_line.append(f" PROJ: {proj_disp[:15]}{method_suffix} ", style="bold #f59e0b on #26004d")
            
        status_line.append("│", style="bold #5e008b on #26004d")
        status_line.append(f" TOK: {session_tokens:,} ", style="bold #38bdf8 on #26004d")

        status_line.append("│", style="bold #5e008b on #26004d")
        model_short = model_name[:20] if len(model_name) > 20 else model_name
        status_line.append(f" {model_short} ({model_status_icon}) [{provider.upper()}] ", style="bold white on #26004d")

        if llm_busy:
            status_line.append(" ⟳", style="bold #f97316 on #26004d")

        len_line = len(status_line.plain)
        if len_line < term_width:
            status_line.append(" " * (term_width - len_line), style="on #26004d")
        
        local_console.print(status_line, overflow="ellipsis", no_wrap=True)
    else:
        # Two rows
        row1 = Text(no_wrap=True)
        row1.append(" JELLYFISH ", style="bold white on #5e008b")
        row1.append(" AGENT ", style="bold #df00ff on #26004d")
        row1.append(f"{active_agent.upper()[:10]} ", style="bold white on #26004d")
        
        row1.append("│", style="bold #5e008b on #26004d")
        ctx_color = "#00ff00" if num_docs > 0 else "dim white"
        row1.append(f" CTX[{num_docs}] ", style=f"bold {ctx_color} on #26004d")
        
        row1.append("│", style="bold #5e008b on #26004d")
        rag_color = "#00ff00" if "OFF" not in rag_status else "dim white"
        row1.append(f" {rag_status} ", style=f"bold {rag_color} on #26004d")

        row1.append("│", style="bold #5e008b on #26004d")
        ollama_color = "#00ff00" if ollama_ok else "#ef4444"
        row1.append(" OLL[ON] " if ollama_ok else " OLL[OFF] ", style=f"bold {ollama_color} on #26004d")
        
        row1.append("│", style="bold #5e008b on #26004d")
        row1.append(f" SKL[{num_skills}] ", style="bold cyan on #26004d")
        
        if project_name:
            row1.append("│", style="bold #5e008b on #26004d")
            method_suffix = f" ({project_methodology.upper()})" if project_methodology else ""
            proj_disp = project_name.split("/")[-1]
            row1.append(f" PROJ: {proj_disp[:15]}{method_suffix} ", style="bold #f59e0b on #26004d")

        len_row1 = len(row1.plain)
        if len_row1 < term_width:
            row1.append(" " * (term_width - len_row1), style="on #26004d")

        row2 = Text(no_wrap=True)
        row2.append(" TOK: ", style="bold #38bdf8 on #26004d")
        row2.append(f"{session_tokens:,} ", style="bold white on #26004d")
        
        row2.append("│", style="bold #5e008b on #26004d")
        model_short = model_name[:40] if len(model_name) > 40 else model_name
        row2.append(f" {model_short} ({model_status_icon}) [{provider.upper()}] ", style="bold white on #26004d")

        if llm_busy:
            row2.append(" ⟳", style="bold #f97316 on #26004d")

        len_row2 = len(row2.plain)
        if len_row2 < term_width:
            row2.append(" " * (term_width - len_row2), style="on #26004d")

        local_console.print(row1, overflow="ellipsis", no_wrap=True)
        local_console.print(row2, overflow="ellipsis", no_wrap=True)

    local_console.print(Text("─" * term_width, style="dim #5e008b"))

    output = buf.getvalue()
    if silent:
        return output

    # Sprint 8.2 — Imprimir como texto normal (sin posicionamiento de cursor)
    sys.stdout.write(output)
    sys.stdout.flush()


def osc8_link(url: str, text: str) -> str:
    """Genera un hipervínculo clickable en terminales compatibles con OSC 8.

    Sprint 8.0 — Soportado por iTerm2, Kitty, WezTerm, Alacritty (>= 0.14),
    VSCode Terminal, GNOME Terminal (>= 3.26) y Windows Terminal.

    Args:
        url: La URL del enlace (puede ser file:// para archivos locales).
        text: El texto visible del enlace.

    Returns:
        String con secuencias de escape OSC 8 que la terminal interpreta como enlace.
    """
    return f"\x1b]8;;{url}\x1b\\{text}\x1b]8;;\x1b\\"


def print_panel(content, title=None, border_style="#af00ff", is_markdown=False):
    """Imprime un panel con ancho controlado."""
    renderable = Markdown(content) if is_markdown else content
    term_width = get_term_width()
    panel_width = min(80, term_width - 4)
    panel = Panel(
        renderable, title=title, border_style=border_style,
        expand=False, padding=(1, 2), width=panel_width
    )
    _main_console.print(panel)


def print_code(code: str, filename: str = "", language: str = "python"):
    """Muestra código con resaltado de sintaxis usando Rich Syntax.

    Args:
        code: El código fuente a mostrar.
        filename: Nombre del archivo (para el título del panel).
        language: Lenguaje para el resaltado de sintaxis.
    """
    # Auto-detectar lenguaje por extensión
    ext_lang_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".html": "html", ".css": "css", ".sh": "bash", ".md": "markdown",
        ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
        ".go": "go", ".rs": "rust", ".java": "java", ".cpp": "cpp",
    }
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        language = ext_lang_map.get(ext, language)

    syntax = Syntax(
        code, language,
        theme="monokai", line_numbers=True,
        word_wrap=True,
    )
    term_width = get_term_width()
    panel_width = min(100, term_width - 4)
    panel = Panel(
        syntax, title=filename or "Código",
        border_style="cyan", expand=False, width=panel_width
    )
    _main_console.print(panel)


def interactive_picker(title: str, options: list, add_back: bool = True,
                       refresh_func=None) -> str | None:
    """Selector interactivo con flechas del teclado.

    Sprint 7.0 — Adaptado para funcionar dentro de la scroll region del TUI.
    El header NO se redibuja desde aquí; se mantiene fijo por el motor TUI.

    Args:
        title: Título del menú.
        options: Lista de opciones.
        add_back: Si True, agrega la opción 'VOLVER'.
        refresh_func: Función que retorna el header como string (para rendering atómico).

    Returns:
        La opción seleccionada, o None si se seleccionó 'VOLVER'.
    """
    if not options:
        console.print("[yellow]⚠ No hay opciones disponibles.[/yellow]")
        return None

    if add_back:
        options = list(options) + [".. VOLVER"]

    current_index = 0
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    # El número total de líneas que ocupará el menú (título + opciones)
    num_lines = len(options) + 1
    first_iter = True

    try:
        tty.setraw(fd)
        while True:
            # Si no es la primera iteración, subir y borrar las líneas impresas anteriormente
            if not first_iter:
                sys.stdout.write("\r\x1b[2K" + "\x1b[A\x1b[2K" * num_lines)
                sys.stdout.flush()
            else:
                first_iter = False

            # Construir el menú
            buf = StringIO()
            term_width = get_term_width()
            local_console = Console(file=buf, force_terminal=True, width=term_width)
            
            local_console.print(Text(f" {title.upper()} ", style="bold white on #5e008b"))
            for i, opt in enumerate(options):
                if i == current_index:
                    local_console.print(Text(f" > {opt}", style="bold #df00ff"))
                else:
                    local_console.print(Text(f"   {opt}", style="dim white"))

            menu_output = buf.getvalue().replace("\n", "\x1b[K\r\n")
            sys.stdout.write(menu_output)
            sys.stdout.flush()

            char = sys.stdin.read(1)
            if char == '\x1b':
                char2 = sys.stdin.read(2)
                if char2 == '[A':
                    current_index = (current_index - 1) % len(options)
                elif char2 == '[B':
                    current_index = (current_index + 1) % len(options)
            elif char in ['\r', '\n']:
                break
            elif char == '\x03':
                raise KeyboardInterrupt

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        # Limpiar el menú por completo de la pantalla al terminar
        if not first_iter:
            sys.stdout.write("\r\x1b[2K" + "\x1b[A\x1b[2K" * num_lines)
            sys.stdout.flush()

    selected = options[current_index]
    return None if selected == ".. VOLVER" else selected


def file_browser(start_path: str = ".", header_func=None) -> str | None:
    """Explorador de archivos interactivo con navegación por flechas.

    Args:
        start_path: Ruta inicial.
        header_func: Función que genera el header (para rendering atómico).

    Returns:
        Ruta seleccionada, o None si se canceló.
    """
    curr = os.path.abspath(start_path)
    ignore_folders = {"venv", ".git", "__pycache__", "node_modules",
                      "code_vector_db", "test_db", ".next", "dist"}

    while True:
        try:
            items = sorted([
                f for f in os.listdir(curr)
                if not f.startswith(".") and f not in ignore_folders
            ])

            options = ["( SELECCIONAR CARPETA ACTUAL )", "<- .. (SUBIR NIVEL)"]
            for item in items:
                full_path = os.path.join(curr, item)
                prefix = "[D]" if os.path.isdir(full_path) else "[F]"
                options.append(f"{prefix} {item}")

            sel = interactive_picker(f"EXPLORADOR: {curr}", options, refresh_func=header_func)
            if not sel:
                return None
            if "SELECCIONAR CARPETA ACTUAL" in sel:
                return curr
            if "SUBIR NIVEL" in sel:
                curr = os.path.dirname(curr)
                continue

            # Extraer nombre limpio
            clean_name = sel[4:] if sel.startswith("[") else sel
            path = os.path.join(curr, clean_name)
            if os.path.isdir(path):
                curr = path
            else:
                return path

        except KeyboardInterrupt:
            return None
        except Exception as e:
            logger.warning("Error en file browser: %s", e)
            return None
