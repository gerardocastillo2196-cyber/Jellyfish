"""
╔══════════════════════════════════════════════════════════════════╗
║  Jellyfish TUI Engine — Sprint 8.2                              ║
║  Header reimprimible + Scroll nativo + Paneles de Progreso      ║
╚══════════════════════════════════════════════════════════════════╝

Este módulo implementa una interfaz de terminal con:
  1. Header que se imprime como texto normal (sin scroll region ANSI).
  2. Scrollback nativo del terminal (el usuario puede hacer scroll
     con el mouse o el teclado sin restricciones).
  3. Paneles de progreso que parpadean en rojo y cambian a verde.

Sprint 8.2 — Se eliminó DECSTBM (scroll region) porque impedía
el scrollback del terminal, haciendo que el usuario no pudiera
revisar respuestas largas del LLM.
"""

import os
import sys
import time
import threading
import logging
from io import StringIO
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.markdown import Markdown

from core.state import get_term_width

logger = logging.getLogger("jellyfish.tui")


class TUIEngine:
    """Motor principal de la interfaz TUI de Jellyfish.
    
    Sprint 8.2 — Rediseñado sin scroll region ANSI.
    El header se imprime como texto normal y se reimprime
    cuando el estado cambia. El scroll del terminal funciona
    naturalmente.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._header_cache: str = ""
        self._term_width: int = get_term_width()
        self._initialized = False
        # Registro de tareas activas para progress panels
        self._active_tasks: dict[str, dict] = {}
        # Sprint 8.0 — Contador de spinner para animación braille
        self._spinner_frame: int = 0
        self._SPINNER_CHARS = "⠀⠁⠃⠇⠏⠟⠿⡿⣿⣾⣼⣸⣰⣠⣀⢀"

    # ─── Inicialización de la Terminal ────────────────────────────────

    def print_welcome_logo(self):
        """Muestra el arte ASCII de bienvenida de las Medusas de forma elegante."""
        self._term_width = get_term_width()
        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=min(120, self._term_width))
        
        jelly = Text()
        jelly.append("\n", style="")
        jelly.append("   ▄███▄           ▄███████▄           ▄███▄\n", style="bold purple")
        jelly.append("  ███████         ███████████         ███████\n", style="bold violet")
        jelly.append("  █▀█▀█▀█         ███▀███▀███         █▀█▀█▀█\n", style="bold purple")
        jelly.append("   █ █ █          █  █  █  █           █ █ █\n", style="bold violet")
        jelly.append("   ▀ ▀ ▀          ▀  ▀  ▀  ▀           ▀ ▀ ▀\n", style="bold purple")
        c.print(jelly)
        
        c.print(Text("   🪼  JELLYFISH OS v5.1 — Habilitado Gemini 3.1 Pro", style="bold #06b6d4"))
        c.print(Text("   ──────────────────────────────────────────────────────────", style="dim #4b5563"))
        c.print(Text("   Escribe /help para ver los comandos disponibles.", style="dim white"))
        c.print(Text("\n", style=""))
        
        sys.stdout.write(buf.getvalue())
        sys.stdout.flush()

    def init_terminal(self):
        """Inicializa la terminal limpiando la pantalla.
        
        Sprint 8.2 — Ya NO configura scroll regions ANSI.
        Solo limpia la pantalla y marca como inicializado.
        """
        # Limpiar pantalla de forma nativa
        os.system("cls" if os.name == "nt" else "clear")
        self.print_welcome_logo()
        self._initialized = True

    def restore_terminal(self):
        """Restaura la terminal al modo normal.
        
        Sprint 8.2 — Ya no hay scroll region que restaurar,
        solo movemos el cursor al final.
        """
        try:
            rows = self._get_term_rows()
            sys.stdout.write(f"\x1b[{rows};1H\n")
            sys.stdout.flush()
        except Exception:
            pass
        self._initialized = False

    def _get_term_rows(self) -> int:
        """Obtiene el número de filas de la terminal."""
        try:
            return os.get_terminal_size().lines
        except (OSError, ValueError):
            return 40

    # ─── Renderizado del Header ───────────────────────────────────────

    def render_header(self, active_agent="default", model_name="none",
                      num_skills=0, num_docs=0, rag_status="RAG[OFF]",
                      provider="ollama", project_name="", project_methodology="",
                      token_budget=None, llm_busy=False, session_tokens=0):
        """Renderiza el header como texto normal en la terminal.
        
        Sprint 8.2 — El header se imprime secuencialmente como texto.
        NO usa posicionamiento absoluto de cursor ni scroll regions.
        Se reimprime antes de cada prompt llamando a refresh_header().
        """
        with self._lock:
            self._term_width = get_term_width()
            term_width = min(120, self._term_width)

            buf = StringIO()
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
                import os
                key_env = "GEMINI_API_KEY" if provider == "gemini" else "ANTHROPIC_API_KEY" if provider == "claude" else ""
                if key_env and not os.getenv(key_env):
                    model_status_icon = "🔑"

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
                    self._spinner_frame = (self._spinner_frame + 1) % len(self._SPINNER_CHARS)
                    spinner_char = self._SPINNER_CHARS[self._spinner_frame]
                    status_line.append(f" {spinner_char}", style="bold #f97316 on #26004d")

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
                    self._spinner_frame = (self._spinner_frame + 1) % len(self._SPINNER_CHARS)
                    spinner_char = self._SPINNER_CHARS[self._spinner_frame]
                    row2.append(f" {spinner_char}", style="bold #f97316 on #26004d")

                len_row2 = len(row2.plain)
                if len_row2 < term_width:
                    row2.append(" " * (term_width - len_row2), style="on #26004d")

                local_console.print(row1, overflow="ellipsis", no_wrap=True)
                local_console.print(row2, overflow="ellipsis", no_wrap=True)

            local_console.print(Text("─" * term_width, style="dim #5e008b"))

            header_output = buf.getvalue()

            # Imprimir directamente como texto normal de una sola línea
            sys.stdout.write(header_output)
            sys.stdout.flush()

            self._header_cache = header_output

    # ─── Utilidades de pantalla ────────────────────────────────────────

    def print_in_scroll_region(self, text: str):
        """Imprime texto en la terminal (compatibilidad con código existente)."""
        with self._lock:
            sys.stdout.write(text)
            sys.stdout.flush()

    def move_cursor_to_scroll_region(self):
        """No-op en Sprint 8.2 — ya no hay scroll region."""
        pass

    def clear_scroll_region(self):
        """Limpia la pantalla de forma nativa y vuelve a imprimir el logo de bienvenida."""
        with self._lock:
            os.system("cls" if os.name == "nt" else "clear")
            self.print_welcome_logo()

    # ─── Paneles de Progreso (Task Boxes) ─────────────────────────────

    def start_task(self, task_id: str, description: str, agent: str = None) -> None:
        """Inicia un panel de progreso parpadeante para una tarea larga.
        
        Muestra una línea con fondo rojo parpadeante que indica que la tarea
        está en proceso. El parpadeo se logra con un hilo de animación.
        
        Args:
            task_id: Identificador único de la tarea.
            description: Descripción corta de lo que se está haciendo.
            agent: Nombre opcional del agente asignado.
        """
        self._active_tasks[task_id] = {
            "description": description,
            "status": "running",
            "start_time": time.time(),
            "stop_event": threading.Event(),
            "agent": agent,
        }

        # Imprimir el indicador inicial
        self._print_task_indicator(task_id, "running")

        # Iniciar hilo de animación del parpadeo
        def _animate():
            stop_event = self._active_tasks[task_id]["stop_event"]
            toggle = True
            while not stop_event.is_set():
                self._print_task_indicator(task_id, "running", blink_on=toggle)
                toggle = not toggle
                stop_event.wait(0.6)  # Velocidad de parpadeo

        thread = threading.Thread(target=_animate, daemon=True)
        thread.start()
        self._active_tasks[task_id]["thread"] = thread

    def finish_task(self, task_id: str, success: bool = True, tokens: int = None, agent: str = None) -> None:
        """Finaliza un panel de progreso, cambiándolo a verde (done) o rojo fijo (error).
        
        Args:
            task_id: Identificador de la tarea.
            success: True para verde "DONE", False para rojo fijo "ERROR".
            tokens: Número acumulado de tokens procesados en la tarea.
            agent: Nombre del agente que completó la tarea.
        """
        if task_id not in self._active_tasks:
            return

        task = self._active_tasks[task_id]
        task["stop_event"].set()
        
        # Esperar a que el hilo de animación termine
        if "thread" in task:
            task["thread"].join(timeout=2)

        elapsed = time.time() - task["start_time"]
        task["status"] = "done" if success else "error"
        task["elapsed"] = elapsed
        if tokens is not None:
            task["tokens"] = tokens
        if agent is not None:
            task["agent"] = agent

        # Pintar el estado final (verde o rojo fijo)
        self._print_task_indicator(task_id, task["status"])

        # Limpiar de activas
        del self._active_tasks[task_id]

    def _print_task_indicator(self, task_id: str, status: str, blink_on: bool = True):
        """Renderiza la línea de indicador de una tarea.
        
        Args:
            task_id: Identificador de la tarea.
            status: "running", "done" o "error".
            blink_on: Para el parpadeo, alterna entre visible e invisible.
        """
        if task_id not in self._active_tasks:
            return

        task = self._active_tasks[task_id]
        desc = task["description"]
        elapsed = time.time() - task["start_time"]
        agent_val = task.get("agent")

        buf = StringIO()
        term_width = min(120, get_term_width())
        local_console = Console(file=buf, force_terminal=True, width=term_width)

        if status == "running":
            if blink_on:
                indicator = Text()
                indicator.append(" ⟳ PROCESANDO ", style="bold white on red")
                if agent_val:
                    indicator.append(f" @{agent_val}: ", style="bold red")
                indicator.append(f"{desc} ", style="bold red")
                indicator.append(f" [{elapsed:.0f}s] ", style="dim red")
            else:
                indicator = Text()
                indicator.append("               ", style="on #1a1a1a")
                if agent_val:
                    indicator.append(f" @{agent_val}: ", style="dim #666666")
                indicator.append(f"{desc} ", style="dim #666666")
                indicator.append(f" [{elapsed:.0f}s] ", style="dim #444444")
        elif status == "done":
            indicator = Text()
            elapsed_final = task.get("elapsed", elapsed)
            tokens_final = task.get("tokens", None)
            agent_final = task.get("agent", agent_val)
            
            # Formato requerido: ✓ COMPLETADO @agente: [Descripción corta de la tarea] ([X] tokens · [Y]s)
            if agent_final:
                indicator.append(" ✓ COMPLETADO ", style="bold white on green")
                indicator.append(f" @{agent_final}: {desc} ", style="bold green")
                if tokens_final is not None:
                    indicator.append(f" ({tokens_final:,} tokens · {elapsed_final:.1f}s) ", style="dim green")
                else:
                    indicator.append(f" ({elapsed_final:.1f}s) ", style="dim green")
            else:
                indicator.append(" ✓ COMPLETADO ", style="bold white on green")
                indicator.append(f" {desc} ", style="bold green")
                indicator.append(f" [{elapsed_final:.1f}s] ", style="dim green")
        else:  # error
            indicator = Text()
            elapsed_final = task.get("elapsed", elapsed)
            agent_final = task.get("agent", agent_val)
            if agent_final:
                indicator.append(" ✗ ERROR ", style="bold white on red")
                indicator.append(f" @{agent_final}: {desc} ", style="bold red")
                indicator.append(f" [{elapsed_final:.1f}s] ", style="dim red")
            else:
                indicator.append(" ✗ ERROR ", style="bold white on red")
                indicator.append(f" {desc} ", style="bold red")
                indicator.append(f" [{elapsed_final:.1f}s] ", style="dim red")

        local_console.print(indicator)
        output = buf.getvalue()

        with self._lock:
            if status == "running":
                # Durante la animación, sobreescribimos la misma línea
                sys.stdout.write(f"\r{output.rstrip()}\x1b[K")
            else:
                # Estado final: imprimir y hacer newline
                sys.stdout.write(f"\r{output.rstrip()}\x1b[K\n")
            sys.stdout.flush()


class TaskProgress:
    """Context manager para paneles de progreso de tareas largas.
    
    Uso:
        with TaskProgress(tui, "indexing", "Indexando código con RAG..."):
            # ... código de la tarea larga ...
        # Al salir del with, automáticamente cambia a verde "COMPLETADO"
    """

    def __init__(self, tui: TUIEngine, task_id: str, description: str, agent: str = None):
        self.tui = tui
        self.task_id = task_id
        self.description = description
        self.agent = agent
        self.tokens = None
        self._success = True

    def __enter__(self):
        self.tui.start_task(self.task_id, self.description, agent=self.agent)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._success = False
        self.tui.finish_task(self.task_id, success=self._success, tokens=self.tokens, agent=self.agent)
        return False  # No suprimir excepciones

    def set_tokens(self, tokens: int):
        self.tokens = tokens

    def fail(self):
        """Marca la tarea como fallida (mostrará rojo en lugar de verde)."""
        self._success = False


# ─── Instancia Global ────────────────────────────────────────────────
# Se importa desde otros módulos como: from core.tui import tui_engine
tui_engine = TUIEngine()
