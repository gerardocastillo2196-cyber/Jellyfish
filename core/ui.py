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

from core.state import get_term_width, get_term_height, AGENCY_DIR

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
                   token_budget=None, llm_busy=False, session_tokens=0,
                   active_agency="default"):
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
        active_agency: Nombre de la agencia activa.
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
                active_agency=active_agency,
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
    model_status_text = "OK"
    if provider == "ollama":
        if not ollama_ok:
            model_status_text = "ERR"
        elif not is_model_available_locally(model_name):
            model_status_text = "WARN"
    else:
        key_env = "GEMINI_API_KEY" if provider == "gemini" else "ANTHROPIC_API_KEY" if provider == "claude" else ""
        if key_env and not os.getenv(key_env):
            model_status_text = "NO_KEY"

    jelly = Text()
    jelly.append("\n", style="")
    jelly.append("        ▄███████▄\n", style="bold purple")
    jelly.append("       ███████████\n", style="bold violet")
    jelly.append("       ███▀███▀███\n", style="bold purple")
    jelly.append("       █  █  █  █\n", style="bold violet")
    jelly.append("       ▀  ▀  ▀  ▀\n", style="bold purple")
    local_console.print(jelly)

    ctx_color = "green" if num_docs > 0 else "dim"
    rag_color = "green" if "OFF" not in rag_status else "dim"
    ollama_color = "green" if ollama_ok else "red"
    
    proj_disp = ""
    if project_name:
        method_suffix = f" ({project_methodology.upper()})" if project_methodology else ""
        proj_name = project_name.split("/")[-1]
        proj_disp = f"PROJ: {proj_name[:15]}{method_suffix}"

    spinner_disp = ""
    if llm_busy:
        spinner_disp = " ⟳"

    budget_disp = ""
    if token_budget:
        used = token_budget.get("used_tokens", 0)
        total = token_budget.get("total_tokens", 8192)
        pct = token_budget.get("percent", 0)
        budget_disp = f"BUDGET: {used:,}/{total:,} ({pct}%)"

    model_short = model_name[:30] if len(model_name) > 30 else model_name

    from rich.table import Table
    table = Table(box=None, show_header=False, padding=(0, 2), expand=True)
    table.add_column("Col1", ratio=1)
    table.add_column("Col2", ratio=1)
    
    c1_r1 = f"JELLYFISH | AGENCY: {active_agency.upper()} | AGENT: @{active_agent.upper()[:10]}"
    c2_r1 = f"[white]MOD:[/white] {model_short} [{model_status_text}] \\[{provider.upper()}]"
    
    c1_r2 = f"[{ctx_color}]CTX:{num_docs}[/{ctx_color}] | [{rag_color}]{rag_status}[/{rag_color}] | SKL:{num_skills} | [{ollama_color}]OLLAMA:{'ON' if ollama_ok else 'OFF'}[/{ollama_color}]"
    c2_r2 = f"TOK: {session_tokens:,} {budget_disp}{spinner_disp}"

    table.add_row(c1_r1, c2_r1)
    table.add_row(c1_r2, c2_r2)
    if proj_disp:
        table.add_row(proj_disp, "")

    local_console.print(table)
    local_console.print(Text("─" * term_width, style="dim purple"))

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


def print_panel(content, title=None, border_style="dim white", is_markdown=False):
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
        border_style="dim white", expand=False, width=panel_width
    )
    _main_console.print(panel)


def interactive_picker(title: str, options: list, add_back: bool = True,
                       refresh_func=None) -> str | None:
    """Selector interactivo con flechas del teclado.

    Sprint 7.0 — Adaptado para funcionar dentro de la scroll region del TUI.
    El header NO se redibuja desde aquí; se mantiene fijo por el motor TUI.
    Sprint 9.0 — Paginación y cálculo dinámico de altura para evitar re-impresión
    acumulativa en terminales pequeñas.

    Args:
        title: Título del menú.
        options: Lista de opciones.
        add_back: Si True, agrega la opción 'VOLVER'.
        refresh_func: Función que retorna el header como string (para rendering atómico).

    Returns:
        La opción seleccionada, o None si se seleccionó 'VOLVER'.
    """
    if not options:
        console.print("⚠ No hay opciones disponibles.")
        return None

    if add_back:
        options = list(options) + [".. VOLVER"]

    current_index = 0
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    last_num_lines = 0

    try:
        tty.setraw(fd)
        while True:
            # Obtener dimensiones de terminal actuales
            term_width = get_term_width()
            term_height = get_term_height()

            # Altura máxima del viewport de opciones (dejando margen para el título, indicadores y prompt)
            max_display = max(3, min(15, term_height - 6))

            # Calcular viewport
            if len(options) <= max_display:
                start_index = 0
                end_index = len(options)
            else:
                half = max_display // 2
                start_index = current_index - half
                if start_index < 0:
                    start_index = 0
                if start_index + max_display > len(options):
                    start_index = len(options) - max_display
                end_index = start_index + max_display

            # Si no es la primera iteración, subir y borrar las líneas impresas anteriormente
            if last_num_lines > 0:
                sys.stdout.write("\r\x1b[2K" + "\x1b[A\x1b[2K" * last_num_lines)
                sys.stdout.flush()

            # Construir el menú
            buf = StringIO()
            local_console = Console(file=buf, force_terminal=True, width=term_width)
            
            # Título
            title_text = f" {title.upper()} "
            if len(title_text) > term_width:
                title_text = title_text[:term_width - 3] + "..."
            local_console.print(Text(title_text, style="bold white on #5e008b"))

            # Indicador superior si hay elementos ocultos arriba
            if start_index > 0:
                local_console.print(Text(f"   ▲ ... ({start_index} más arriba)", style="dim cyan"))
            
            # Elementos del viewport
            for i in range(start_index, end_index):
                opt = options[i]
                max_opt_len = term_width - 8
                opt_text = opt
                if len(opt_text) > max_opt_len:
                    opt_text = opt_text[:max_opt_len - 3] + "..."
                    
                if i == current_index:
                    local_console.print(Text(f" > {opt_text}", style="bold #df00ff"))
                else:
                    local_console.print(Text(f"   {opt_text}", style="dim white"))

            # Indicador inferior si hay elementos ocultos abajo
            if end_index < len(options):
                local_console.print(Text(f"   ▼ ... ({len(options) - end_index} más abajo)", style="dim cyan"))

            menu_output = buf.getvalue().replace("\n", "\x1b[K\r\n")
            sys.stdout.write(menu_output)
            sys.stdout.flush()

            # Guardar el número de líneas impresas en esta iteración para el borrado posterior
            last_num_lines = buf.getvalue().count("\n")

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
        if last_num_lines > 0:
            sys.stdout.write("\r\x1b[2K" + "\x1b[A\x1b[2K" * last_num_lines)
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


def handle_exit_flow(state) -> None:
    """Interacción de salida para analizar y reportar errores recolectados en la sesión.

    Sprint 9.0 — Captura, diagnóstico interactivo vía LLM y exportación a Markdown.
    """
    errors = getattr(state, "captured_errors", [])
    if not errors:
        return

    # Restaurar por si acaso el cursor y estilo
    sys.stdout.write("\n")
    sys.stdout.flush()

    console.print(Panel(
        f"Se detectaron {len(errors)} errores durante esta sesión de Jellyfish.\n"
        "Puedes generar un diagnóstico inteligente utilizando el modelo activo antes de salir.",
        title="⚠️ DIAGNÓSTICO DE ERRORES",
        border_style="dim white"
    ))

    try:
        resp = input("¿Deseas analizar los errores con el modelo de IA antes de salir? (S/n): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Saltando diagnóstico de errores.[/dim]")
        return

    if resp not in ("", "s", "si", "yes", "y"):
        return

    console.print("🤖 Analizando trazas de error con el LLM en segundo plano...")

    # Construir listado de trazas para el prompt
    error_list_str = ""
    for idx, err in enumerate(errors, 1):
        error_list_str += f"### ERROR #{idx}\n```python\n{err}\n```\n\n"

    system_prompt = (
        "Eres el Agente de Diagnóstico Técnico de Jellyfish OS.\n"
        "Tu misión es analizar la lista de errores proporcionados y generar un reporte técnico conciso.\n"
        "Debes estructurar tu respuesta en tres secciones principales:\n"
        "1. Breve descripción de los hallazgos y causa raíz de cada error.\n"
        "2. Propuesta paso a paso para solucionarlos (incluye fragmentos de código correctos si aplica).\n"
        "Por favor responde en español, de forma clara, directa y estructurada usando formato Markdown."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Aquí están las trazas de los errores capturados:\n\n{error_list_str}"}
    ]

    from core.llm_engine import _call_llm_silent
    # Activar un visualizador de progreso simple para que el usuario sepa que está trabajando
    from core.tui import TaskProgress, tui_engine
    
    analysis = None
    try:
        with TaskProgress(tui_engine, "error_diagnose", "Generando diagnóstico de errores..."):
            analysis = _call_llm_silent(state, messages)
    except Exception as le:
        logger.error("Error al invocar LLM para diagnóstico: %s", le)

    if not analysis:
        console.print("⚠ El modelo no pudo generar el diagnóstico o no está respondiendo.")
        return

    # Mostrar hallazgos en pantalla
    console.print(Panel(
        Markdown(analysis),
        title="📝 DIAGNÓSTICO DE LA IA",
        border_style="dim white",
        expand=False
    ))

    # Preguntar si desea guardar el reporte
    try:
        save_resp = input("¿Deseas guardar este reporte en un archivo Markdown (.md)? (S/n): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Reporte no guardado.[/dim]")
        return

    if save_resp in ("", "s", "si", "yes", "y"):
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"jellyfish_error_report_{timestamp}.md"
        
        # Determinar directorio destino (siempre en la raíz de Jellyfish)
        dest_dir = AGENCY_DIR
        filepath = os.path.join(dest_dir, filename)

        # Construir reporte completo
        report_content = (
            f"# Reporte de Diagnóstico de Errores — Jellyfish OS\n"
            f"**Fecha y Hora:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**Proveedor de IA:** {state.provider.upper()}\n"
            f"**Modelo de IA:** {state.model}\n\n"
            f"## Resumen del Diagnóstico y Soluciones\n"
            f"{analysis}\n\n"
            f"## Trazas Originales de los Errores\n"
            f"{error_list_str}"
        )

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report_content)
            
            link_text = osc8_link(f"file://{filepath}", filename)
            console.print(f"✓ Reporte guardado con éxito en: [bold]{link_text}[/bold]\n")
        except OSError as e:
            console.print(f"Error al escribir el archivo de reporte: {e}\n")

