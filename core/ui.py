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
                   silent=False):
    """Renderiza el header completo de Jellyfish de forma atómica.
    
    Args:
        active_agent: Nombre del agente activo.
        model_name: Nombre del modelo LLM.
        num_skills: Número de skills cargadas.
        num_docs: Número de documentos en contexto.
        rag_status: Estado del motor RAG.
        provider: Nombre del proveedor de IA activo.
        silent: Si True, retorna el output como string sin imprimir.
    """
    buf = StringIO()
    term_width = min(_main_console.width, get_term_width())
    local_console = Console(file=buf, force_terminal=True, width=term_width)

    # Arte ASCII
    jelly = Text()
    jelly.append("▄███▄          ▄███████▄          ▄███▄\n", style="bold purple")
    jelly.append("███████        ███████████        ███████\n", style="bold violet")
    jelly.append("█▀█▀█▀█        ███▀███▀███        █▀█▀█▀█\n", style="bold purple")
    jelly.append(" ▀ ▀ ▀          █  █  █  █         ▀ ▀ ▀\n", style="bold violet")
    jelly.append("                ▀  ▀  ▀  ▀", style="bold purple")
    local_console.print(jelly)

    # Barra de estado responsive
    status_line = Text(no_wrap=True)
    is_narrow = term_width < 100

    status_line.append(" JELLYFISH ", style="bold white on #5e008b")
    status_line.append(" AGENT ", style="bold #df00ff on #26004d")
    status_line.append(f"{active_agent.upper()[:10]} ", style="bold white on #26004d")

    status_line.append("│", style="bold #5e008b on #26004d")
    ctx_color = "#00ff00" if num_docs > 0 else "dim white"
    status_line.append(f" CTX[{num_docs}] ", style=f"bold {ctx_color} on #26004d")

    status_line.append("│", style="bold #5e008b on #26004d")
    rag_color = "#00ff00" if "OFF" not in rag_status else "dim white"
    status_line.append(f" {rag_status} ", style=f"bold {rag_color} on #26004d")

    if not is_narrow:
        status_line.append("│", style="bold #5e008b on #26004d")
        status_line.append(f" SKL[{num_skills}] ", style="bold cyan on #26004d")
        status_line.append("│", style="bold #5e008b on #26004d")
        model_short = model_name[:20] if len(model_name) > 20 else model_name
        status_line.append(f" {model_short} ", style="bold white on #26004d")

    status_line.append("│", style="bold #5e008b on #26004d")
    provider_color = "#00bfff" if provider != "ollama" else "#00ff00"
    provider_label = provider.upper()[:8]
    status_line.append(f" {provider_label} ", style=f"bold {provider_color} on #26004d")

    local_console.print(status_line)
    local_console.print(Text("─" * term_width, style="dim #5e008b"))

    output = buf.getvalue().replace("\n", "\x1b[K\r\n")
    if silent:
        return output

    sys.stdout.write("\x1b[H" + output + "\x1b[J")
    sys.stdout.flush()


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

    try:
        tty.setraw(fd)
        while True:
            # Renderizar header + menú en un solo buffer
            full_output = ""
            if refresh_func:
                header_out = refresh_func()
                if header_out:
                    full_output = header_out

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

            # Envío atómico único (Cero Parpadeo)
            sys.stdout.write("\x1b[H" + full_output + menu_output + "\x1b[J")
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
