"""
╔══════════════════════════════════════════════════════════════════╗
║  Jellyfish TUI Engine — Sprint 6.8                              ║
║  Layout Tiling (tmux/htop style) + Redirección de stdout         ║
╚══════════════════════════════════════════════════════════════════╝

Módulo de interfaz minimalista y eficiente:
- Divide la pantalla en 3 zonas fijas (Agentes, Logs, Prompt).
- Redirige stdout/stderr para actualizar el panel de logs.
- Branding compacto e integración de colores de estado.
"""

import os
import sys
import re
import time
import threading
import logging
from io import StringIO
from typing import Any, Dict, List, Optional

from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, WindowAlign, Float, FloatContainer
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import ANSI, HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from core.state import get_term_width, get_term_height

logger = logging.getLogger("jellyfish.tui")

# Expresión regular para limpiar secuencias ANSI de control de cursor y pantalla (evitando 25l, 25h, etc.)
ANSI_CLEAN_RE = re.compile(r'\x1b\[[\d;?]*[a-ln-zABCDEFGJKHST]')

# Estilo para el autocompletado y colores de la TUI
claude_style = Style.from_dict({
    'completion-menu': 'bg:#2d004d #ffffff',
    'completion-menu.completion': 'bg:#2d004d #bbbbbb',
    'completion-menu.completion.current': 'bg:#5e008b #ffffff',
    # Estilos del estado global (FASE 1)
    'status-ok': 'bg:#22c55e #ffffff bold',
    'status-process': 'bg:#eab308 #000000 bold',
    'status-error': 'bg:#ef4444 #ffffff bold',
    'status-input': 'bg:#3b82f6 #ffffff bold',
    'line': 'fg:#4b5563',
    'agent-header': 'fg:#a855f7 bold',
    'agent-active': 'fg:#22c55e bold',
    'agent-thinking': 'fg:#eab308 bold',
    'agent-inactive': 'fg:#6b7280',
    'prompt-label': 'bg:#0f172a #a78bfa bold',
    'prompt-area': 'bg:#0f172a #f8fafc',
    'left-panel': 'bg:#0f172a fg:#94a3b8',
    'log-panel': 'bg:#0f172a fg:#94a3b8',
})


class TUIRedirector:
    """Redirige stdout y stderr al panel de logs del TUI."""

    def __init__(self, tui_engine):
        self.tui_engine = tui_engine
        self.old_stdout = None
        self.old_stderr = None
        self.active = False
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if not self.active:
                self.old_stdout = sys.stdout
                self.old_stderr = sys.stderr
                sys.stdout = self
                sys.stderr = self
                self.active = True

    def stop(self):
        with self._lock:
            if self.active:
                sys.stdout = self.old_stdout
                sys.stderr = self.old_stderr
                self.active = False

    def write(self, data):
        # Escribir en la TUI
        self.tui_engine.append_log(data)
        # Escribir también en el log del sistema
        if data.strip():
            logger.info("[STDOUT/STDERR] %s", data.strip())

    def flush(self):
        if self.old_stdout:
            try:
                self.old_stdout.flush()
            except Exception:
                pass

    def isatty(self):
        if self.old_stdout and hasattr(self.old_stdout, "isatty"):
            return self.old_stdout.isatty()
        return sys.__stdout__.isatty()

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(f"'TUIRedirector' object has no attribute '{name}'")
        if self.old_stdout:
            return getattr(self.old_stdout, name)
        return getattr(sys.__stdout__, name)


class JellyfishTUIApp:
    """Aplicación prompt_toolkit de pantalla dividida (Tiling)."""

    def __init__(self, tui_engine, state, completer, key_bindings, lexer):
        self.tui_engine = tui_engine
        self.state = state
        self.completer = completer
        self.lexer = lexer
        self.key_bindings = key_bindings
        
        # Buffer de entrada para el prompt
        self.input_buffer = Buffer(
            completer=self.completer,
            complete_while_typing=True,
            accept_handler=self.handle_accept,
            multiline=True,
        )
        
        # Mapeo de Scroll Offset para panel central
        self.scroll_offset = 0
        
        # Definición de ventanas
        # 1. Barra de estado superior (Header con branding compacto de Medusa y Color global)
        self.header_window = Window(
            content=FormattedTextControl(self.get_header_text),
            height=1,
            style="bg:#1e1b4b #ffffff",
        )
        
        # 2. Panel Izquierdo (compacto): Estado de agentes
        self.left_window = Window(
            content=FormattedTextControl(self.get_left_panel_text),
            width=10,
            style="class:left-panel",
        )
        
        # 3. Prompt label (indicador visual)
        self.prompt_label = Window(
            content=FormattedTextControl(self.get_prompt_label_text),
            dont_extend_width=True,
            height=1,
            style="class:prompt-label",
        )
        
        # 4. Panel Central: Entrada de comandos y prompts
        self.prompt_window = Window(
            content=BufferControl(
                buffer=self.input_buffer,
                lexer=self.lexer,
            ),
            style="class:prompt-area",
            height=3,
        )
        
        # 5. Panel Inferior: Logs, discusiones y diffs de código
        self.log_window = Window(
            content=FormattedTextControl(self.get_log_text),
            wrap_lines=True,
            dont_extend_height=True,
            style="class:log-panel",
        )
        
        # Columna derecha: logs (arriba) y prompt (abajo)
        right_column = HSplit([
            self.log_window,
            VSplit([
                self.prompt_label,
                self.prompt_window,
            ]),
            Window(),  # Spacer para absorber el resto de altura
        ])
        
        # Cuerpo principal (header + panels)
        body = HSplit([
            self.header_window,
            Window(height=1, char="━", style="class:line"),
            VSplit([
                self.left_window,
                Window(width=1, char="┃", style="class:line"),
                right_column,
            ]),
        ])
        
        # Layout con FloatContainer para el menú de autocompletado
        self.layout = Layout(
            container=FloatContainer(
                content=body,
                floats=[
                    Float(
                        xcursor=True,
                        ycursor=True,
                        content=CompletionsMenu(max_height=12, scroll_offset=1),
                    ),
                ],
            ),
            focused_element=self.input_buffer,
        )
        
        # Configurar Keybindings de scroll
        self.setup_tui_keybindings()

        self.app = Application(
            layout=self.layout,
            style=claude_style,
            full_screen=True,
            key_bindings=self.key_bindings,
            mouse_support=False,
        )

    def setup_tui_keybindings(self):
        """Asigna atajos de teclado adicionales para navegación y scroll del panel central."""
        from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
        tui_kb = KeyBindings()
        
        @tui_kb.add('pageup')
        def _scroll_up(event):
            self.scroll_offset = max(0, self.scroll_offset - 10)
            self.app.invalidate()

        @tui_kb.add('pagedown')
        def _scroll_down(event):
            self.scroll_offset += 10
            self.app.invalidate()
            
        @tui_kb.add('enter')
        def _submit(event):
            buffer = event.current_buffer
            if buffer.complete_state and buffer.complete_state.current_completion:
                buffer.apply_completion(buffer.complete_state.current_completion)
            buffer.validate_and_handle()
            
        self.key_bindings = merge_key_bindings([self.key_bindings, tui_kb])

    def get_prompt_label_text(self) -> List[Any]:
        label = getattr(self.tui_engine, "_current_prompt_label", " 🪼 > ")
        return [('class:prompt-label', label)]

    def get_header_text(self) -> List[Any]:
        """Genera el texto de la barra de estado superior con la Medusa ASCII minimalista y el color global."""
        status = getattr(self.state, "global_status", "OK")
        status_style = "class:status-ok"
        if status == "PROCESS":
            status_style = "class:status-process"
        elif status == "ERROR":
            status_style = "class:status-error"
        elif status == "INPUT_REQUIRED":
            status_style = "class:status-input"
            
        proj_name = os.path.basename(self.state.active_project) if self.state.active_project else "Ninguno"
        
        tokens = [
            ("", " [🪼 Jellyfish 6.8]  |  ESTADO: "),
            (status_style, f" {status} "),
            ("", f"  |  PROYECTO: {proj_name}  |  AGENCIA: {self.state.active_agency.upper()}  |  Ctrl+A: Agentes  |  Ctrl+R: RAG"),
        ]
        return tokens

    def get_left_panel_text(self) -> List[Any]:
        """Genera el contenido del panel izquierdo compacto."""
        tokens = [
            ("class:agent-header", " AGENTES\n"),
            ("class:line", " ━━━━━━━━━━\n"),
        ]
        
        agent_statuses = getattr(self.state, "agent_statuses", {})
        for name, status in agent_statuses.items():
            short = name[:8]
            if status == "Ejecutando":
                tokens.append(("class:agent-active", f" ● {short}\n"))
            elif status == "Pensando":
                tokens.append(("class:agent-thinking", f" ◐ {short}\n"))
                
        return tokens

    def get_log_text(self) -> Any:
        """Retorna el buffer de logs procesando secuencias ANSI de color.
        
        Es defensivo contra excepciones para evitar que la ventana se renderice
        en rojo brillante por fallos de parseo o modificaciones concurrentes.
        """
        viewport_text = ""
        try:
            with self.tui_engine._lock:
                log_content = self.tui_engine._log_text
            lines = log_content.splitlines()
            if self.scroll_offset > 0:
                lines = lines[:-self.scroll_offset]
            viewport_text = "\n".join(lines[-100:])
            return ANSI(viewport_text)
        except Exception:
            return [("", viewport_text)]

    def handle_accept(self, buffer):
        """Manejador cuando el usuario envía una línea de comando."""
        if getattr(self.tui_engine, "_waiting_for_input", False):
            self.tui_engine._input_result = buffer.text
            buffer.reset()
            self.tui_engine._input_event.set()
            return

        user_input = buffer.text.strip()
        buffer.reset()
        if not user_input:
            return
        
        if user_input.lower() in ("/exit", "exit", "quit"):
            self.app.exit(result="/exit")
            return

        if hasattr(self.tui_engine, "command_handler") and self.tui_engine.command_handler:
            self.state.global_status = "PROCESS"
            self.app.invalidate()
            
            def run_wrapper():
                try:
                    if is_interactive_command(user_input):
                        import asyncio
                        from prompt_toolkit.application import run_in_terminal
                        
                        def run_cmd():
                            self.tui_engine.restore_terminal()
                            try:
                                self.tui_engine.command_handler(user_input)
                            finally:
                                self.tui_engine.init_terminal()
                        
                        async def main_thread_wrapper():
                            return await run_in_terminal(run_cmd)
                            
                        future = asyncio.run_coroutine_threadsafe(main_thread_wrapper(), self.app.loop)
                        future.result()
                    else:
                        self.tui_engine.command_handler(user_input)
                except Exception as e:
                    self.tui_engine.append_log(f"\n❌ Error al ejecutar: {e}\n")
                finally:
                    self.state.global_status = "OK"
                    self.app.invalidate()
            
            threading.Thread(target=run_wrapper, daemon=True).start()
        else:
            self.app.exit(result=user_input)


def is_interactive_command(user_input: str) -> bool:
    """Determina si un comando requiere interacción en la terminal host."""
    return False



class TUIEngine:
    """Motor de orquestación y renderizado TUI para Jellyfish OS."""

    def __init__(self):
        self._lock = threading.Lock()
        self._initialized = False
        self._log_text: str = ""
        self._redirector = TUIRedirector(self)
        self._active_tasks: dict = {}
        self.command_handler = None
        self.active_tui_app = None
        self._input_event = threading.Event()
        self._input_result = ""
        self._waiting_for_input = False
        self._current_prompt_label = " 🪼 > "

    def init_terminal(self):
        """Inicializa la terminal y activa la redirección de logs."""
        self._redirector.start()
        self._initialized = True
        
        import builtins
        if not hasattr(self, "_original_input"):
            self._original_input = builtins.input
        builtins.input = self._custom_input

    def restore_terminal(self):
        """Restaura la terminal desactivando la redirección de logs."""
        self._redirector.stop()
        self._initialized = False
        
        import builtins
        if hasattr(self, "_original_input"):
            builtins.input = self._original_input

    def _custom_input(self, prompt=""):
        if self._initialized and self.active_tui_app:
            return self.prompt_user(prompt)
        if hasattr(self, "_original_input"):
            return self._original_input(prompt)
        import builtins
        return builtins.input(prompt)

    def prompt_user(self, prompt_text: str) -> str:
        self._input_event.clear()
        self._input_result = ""
        self._waiting_for_input = True
        
        clean_prompt = prompt_text.strip()
        if clean_prompt.endswith(":"):
            clean_prompt = clean_prompt[:-1]
        if len(clean_prompt) > 30:
            clean_prompt = clean_prompt[:27] + "..."
            
        self._current_prompt_label = f" {clean_prompt} > "
        
        if self.active_tui_app:
            self.active_tui_app.app.loop.call_soon_threadsafe(
                self.active_tui_app.input_buffer.reset
            )
            self.active_tui_app.app.invalidate()
            
        self._input_event.wait()
        
        self._waiting_for_input = False
        self._current_prompt_label = " 🪼 > "
        if self.active_tui_app:
            self.active_tui_app.app.invalidate()
            
        return self._input_result

    def prompt_menu(self, title: str, options: List[str]) -> Optional[str]:
        """Presenta un menú dinámico usando el dropdown de autocompletado en el prompt."""
        if not self.active_tui_app:
            return None
            
        self._input_event.clear()
        self._input_result = ""
        self._waiting_for_input = True
        
        # Guardar completador y validador previos
        old_completer = self.active_tui_app.completer
        old_validator = self.active_tui_app.input_buffer.validator
        
        from prompt_toolkit.completion import WordCompleter
        menu_completer = WordCompleter(options, ignore_case=True)
        
        from prompt_toolkit.validation import Validator, ValidationError
        class MenuValidator(Validator):
            def validate(self, document):
                val = document.text.strip()
                if val.lower() not in [o.lower() for o in options]:
                    raise ValidationError(message="Selecciona una opción del menú")
                    
        # Configurar estado del menú
        self._current_prompt_label = f" {title[:20]} > "
        self.active_tui_app.completer = menu_completer
        self.active_tui_app.input_buffer.completer = menu_completer
        self.active_tui_app.input_buffer.validator = MenuValidator()
        
        # Resetear buffer y disparar autocompletado
        def setup_menu():
            self.active_tui_app.input_buffer.reset()
            self.active_tui_app.input_buffer.start_completion(select_first=True)
            
        self.active_tui_app.app.loop.call_soon_threadsafe(setup_menu)
        self.active_tui_app.app.invalidate()
        
        # Bloquear hasta recibir selección
        self._input_event.wait()
        
        # Restaurar estado original
        self._waiting_for_input = False
        self._current_prompt_label = " 🪼 > "
        self.active_tui_app.completer = old_completer
        self.active_tui_app.input_buffer.completer = old_completer
        self.active_tui_app.input_buffer.validator = old_validator
        
        def restore_menu():
            self.active_tui_app.input_buffer.reset()
            
        self.active_tui_app.app.loop.call_soon_threadsafe(restore_menu)
        self.active_tui_app.app.invalidate()
        
        result = self._input_result.strip()
        for opt in options:
            if opt.lower() == result.lower():
                return opt
        return None

    def clear_scroll_region(self):
        """Limpia el área de logs de la TUI (compatibilidad con comandos v6.8)."""
        with self._lock:
            self._log_text = ""
        if self.active_tui_app:
            self.active_tui_app.scroll_offset = 0
            self.active_tui_app.app.invalidate()

    def move_cursor_to_scroll_region(self):
        """No-op en layout tiling ya que el cursor se mantiene en el input buffer."""
        pass

    def print_welcome_logo(self):
        """Muestra el logo de Jellyfish en la consola (compatibilidad con comandos v6.8)."""
        logo = """[bold blue]
╦╔═╗╦  ╦  ╦ ╦╔═╗╦╔═╗╦ ╦
║║╣ ║  ║  ╚╦╝╠╣ ║╚═╗╠═╣
╚╝╚═╝╩═╝╩═╝ ╩ ╚  ╩╚═╝╩ ╩[/bold blue]
[bold cyan]Jellyfish OS v6.8 — Framework de Agentes[/bold cyan]
"""
        from core.ui import console
        console.print(logo)

    def append_log(self, text: str):
        """Añade texto a la base de logs de la TUI, interpretando \r y limpiando escape codes de cursor."""
        with self._lock:
            # Filtrar secuencias de control no deseadas
            cleaned_text = ANSI_CLEAN_RE.sub('', text)
            for char in cleaned_text:
                if char == '\r':
                    last_nl = self._log_text.rfind('\n')
                    if last_nl != -1:
                        self._log_text = self._log_text[:last_nl + 1]
                    else:
                        self._log_text = ""
                else:
                    self._log_text += char
            
            # Limitar tamaño de logs en memoria
            if len(self._log_text) > 100_000:
                self._log_text = self._log_text[-100_000:]
        
        # Forzar redibujado si la app está activa
        if getattr(self, "active_tui_app", None):
            try:
                self.active_tui_app.app.invalidate()
            except Exception:
                pass

    def render_header(self, **kwargs):
        """No-op en layout tiling ya que el header se maneja reactivamente."""
        pass

    def get_user_input(self, state, completer, key_bindings, lexer) -> str:
        """Inicia el TUI interactivo de pantalla dividida y retorna la entrada del usuario."""
        # Asegurar redirección activa
        self._redirector.start()
        
        # Crear instancia de la app
        tui_app = JellyfishTUIApp(self, state, completer, key_bindings, lexer)
        self.active_tui_app = tui_app
        
        # Ejecutar TUI
        try:
            user_input = tui_app.app.run()
            return user_input or ""
        except KeyboardInterrupt:
            return "/exit"
        except Exception as e:
            # En caso de error crítico, restaurar y mostrar traceback
            self._redirector.stop()
            logger.error("Error en TUI loop: %s", e, exc_info=True)
            raise e
        finally:
            self.active_tui_app = None
            self._input_event.set()

    # --- Compatibilidad con TaskProgress / Paneles de Progreso ---

    def start_task(self, task_id: str, description: str, agent: str = None) -> None:
        """Actualiza el estado del agente y añade la entrada a logs."""
        self.append_log(f"\n[⟳] INICIANDO: @{agent or 'agente'} -> {description}\n")
        logger.info("Task %s iniciada: %s", task_id, description)

    def finish_task(self, task_id: str, success: bool = True, tokens: int = None, agent: str = None) -> None:
        """Actualiza el estado del agente al finalizar."""
        status_text = "COMPLETADO" if success else "FALLIDO"
        tok_str = f" ({tokens:,} tokens)" if tokens else ""
        self.append_log(f"[✓] {status_text}: @{agent or 'agente'} -> {task_id}{tok_str}\n\n")
        logger.info("Task %s terminada (%s)", task_id, status_text)


class TaskProgress:
    """Context manager para visualización de progreso compatible con la TUI."""

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
        return False

    def set_tokens(self, tokens: int):
        self.tokens = tokens

    def fail(self):
        self._success = False


# Instancia única global del motor TUI
tui_engine = TUIEngine()
