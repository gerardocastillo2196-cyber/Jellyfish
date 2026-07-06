"""
╔══════════════════════════════════════════════════════════════════╗
║  Jellyfish TUI Engine — Sprint 7.1                              ║
║  CLI Incrustado con Output Panel + Input Panel (TextArea)        ║
╚══════════════════════════════════════════════════════════════════╝

Módulo de interfaz minimalista y eficiente:
- Divide la pantalla en 3 zonas fijas (Header, Output, Input).
- Output Panel: TextArea read-only con scrollbar para historial.
- Input Panel: TextArea de 1 línea con autocompletado y lexer.
- Redirige stdout/stderr para actualizar el Output Panel.
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
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, WindowAlign, Float, FloatContainer, DynamicContainer
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import ANSI, HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.widgets import TextArea

from core.state import get_term_width, get_term_height

logger = logging.getLogger("jellyfish.tui")

# Expresión regular comprehensiva para limpiar TODAS las secuencias ANSI
# (cursor, color, SGR, CSI, OSC, etc.) del texto antes de volcarlo al Output Panel
ANSI_CLEAN_RE = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[()][A-Z0-9]|\x1b[\x20-\x2F]*[\x40-\x7E]')


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

# Mapeo de acrónimos descriptivos para que los agentes siempre quepan completos en el layout
AGENT_ACRONYMS = {
    "default": "PO",
    "product_owner": "PO",
    "scrum_master": "SM",
    "developer": "DEV",
    "backend_dev": "B-DEV",
    "frontend_dev": "F-DEV",
    "qa_engineer": "QA",
    "arquitecto_software": "ARCH",
    "devops": "DEVOPS",
    "devops_engineer": "DEVOPS",
    "copywriter": "COPY",
    "designer": "DES",
    "ui_designer": "UI",
    "marketing_director": "MKT",
    "data_scientist": "DATA",
    "security_auditor": "SEC",
    "seo_specialist": "SEO",
    "researcher": "RES"
}


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
    """Aplicación prompt_toolkit de pantalla dividida con Output Panel + Input Panel."""

    def __init__(self, tui_engine, state, completer, key_bindings, lexer):
        self.tui_engine = tui_engine
        self.state = state
        self.completer = completer
        self.lexer = lexer
        self.key_bindings = key_bindings

        # ── Output Panel: TextArea multilínea, read-only, con scrollbar ──
        self.output_area = TextArea(
            text="",
            read_only=True,
            scrollbar=True,
            style="class:log-panel",
            wrap_lines=True,
            focusable=False,
        )

        # ── Input Panel: TextArea de una línea con accept_handler ──
        self.input_area = TextArea(
            height=1,
            prompt=" 🪼 > ",
            style="class:prompt-area",
            multiline=False,
            completer=self.completer,
            lexer=self.lexer,
            accept_handler=self.handle_accept,
        )

        # ── Header Window ──
        self.header_window = Window(
            content=FormattedTextControl(self.get_header_text),
            height=self.get_header_height,
            style="bg:#1e1b4b #ffffff",
        )

        # ── Layout responsivo ──
        def get_body_layout():
            return HSplit([
                self.header_window,
                Window(height=1, char="━", style="class:line"),
                self.input_area,
                self.output_area,
            ])

        body = DynamicContainer(get_body_layout)

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
            focused_element=self.input_area,
        )

        # Configurar Keybindings
        self.setup_tui_keybindings()

        self.app = Application(
            layout=self.layout,
            style=claude_style,
            full_screen=True,
            key_bindings=self.key_bindings,
            mouse_support=True,
        )

    def setup_tui_keybindings(self):
        """Asigna atajos de teclado adicionales para el Input Panel."""
        from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
        tui_kb = KeyBindings()

        @tui_kb.add('enter')
        def _submit(event):
            buffer = event.current_buffer
            if buffer.complete_state and buffer.complete_state.current_completion:
                buffer.apply_completion(buffer.complete_state.current_completion)
            buffer.validate_and_handle()

        self.key_bindings = merge_key_bindings([self.key_bindings, tui_kb])

    def get_header_height(self) -> int:
        """Determina la altura de la cabecera en función del ancho de la terminal."""
        width = get_term_width()
        return 2 if width < 120 else 1

    def get_header_text(self) -> List[Any]:
        """Genera el texto de la barra de estado superior."""
        status = getattr(self.state, "global_status", "OK")
        status_style = "class:status-ok"
        if status == "PROCESS":
            status_style = "class:status-process"
        elif status == "ERROR":
            status_style = "class:status-error"
        elif status == "INPUT_REQUIRED":
            status_style = "class:status-input"

        proj_name = os.path.basename(self.state.active_project) if self.state.active_project else "Ninguno"
        model_name = getattr(self.state, "model", "Ninguno")
        provider_name = getattr(self.state, "provider", "ollama").upper()

        active = getattr(self.state, "active_agent", "default")
        active_display = AGENT_ACRONYMS.get(active.lower(), active.upper()[:6])

        width = get_term_width()
        if width < 120:
            # Cabecera en 2 filas para pantallas angostas
            tokens = [
                ("", " [🪼 Jellyfish 7.1]  |  ESTADO: "),
                (status_style, f" {status} "),
                ("", f"  |  AGENTE: @{active_display}\n"),
                ("", f" MODELO: {model_name} ({provider_name})  |  PROYECTO: {proj_name}  |  Ctrl+A: Agentes"),
            ]
        else:
            # Cabecera en 1 fila para pantallas anchas
            tokens = [
                ("", " [🪼 Jellyfish 7.1]  |  ESTADO: "),
                (status_style, f" {status} "),
                ("", f"  |  AGENTE: @{active_display}  |  MODELO: {model_name} ({provider_name})  |  PROYECTO: {proj_name}  |  AGENCIA: {self.state.active_agency.upper()}  |  Ctrl+A: Agentes"),
            ]
        return tokens

    def get_left_panel_text(self) -> List[Any]:
        """Genera el contenido del panel izquierdo/superior de agentes basándose en la agencia activa."""
        active = getattr(self.state, "active_agent", "default")
        active_agency = getattr(self.state, "active_agency", "default")

        # Obtener los agentes de la agencia actual o caer a default
        agency_agents = self.state.agency_catalog.get(active_agency, [])
        if not agency_agents:
            agency_agents = [active]
        else:
            agency_agents = list(agency_agents)
            if active not in agency_agents:
                agency_agents.append(active)

        # Preparar listado con mapeo de nombre a acrónimo
        display_agents = []
        for name in sorted(list(set(agency_agents))):
            disp_name = AGENT_ACRONYMS.get(name.lower(), name.upper()[:6])
            display_agents.append((name, disp_name))

        width = get_term_width()
        if width < 80:
            # Layout Horizontal para terminal angosta
            tokens = [("class:agent-header", " AGENTES: ")]
            for name, disp in display_agents:
                if name == active:
                    tokens.append(("class:agent-active", f"● {disp}  "))
                else:
                    tokens.append(("class:agent-inactive", f"{disp}  "))
            return tokens
        else:
            # Layout Vertical para terminal ancha
            tokens = [
                ("class:agent-header", " AGENTES\n"),
                ("class:line", " ━━━━━━━━━━\n"),
            ]
            for name, disp in display_agents:
                if name == active:
                    tokens.append(("class:agent-active", f" ● {disp}\n"))
                else:
                    tokens.append(("class:agent-inactive", f"   {disp}\n"))
            return tokens

    # ── Métodos del Output Panel ──

    def append_to_output(self, text: str):
        """Agrega texto al Output Panel y hace auto-scroll al final."""
        current = self.output_area.text
        new_text = current + text
        # Limitar tamaño para rendimiento
        if len(new_text) > 100_000:
            new_text = new_text[-100_000:]
        self.output_area.text = new_text
        # Auto-scroll: mover cursor al final del buffer
        self.output_area.buffer.cursor_position = len(self.output_area.text)

    def scroll_output_to_bottom(self):
        """Fuerza el scroll del Output Panel al final."""
        try:
            self.output_area.buffer.cursor_position = len(self.output_area.text)
        except Exception:
            pass

    # ── Manejador de Enter ──

    def handle_accept(self, buffer):
        """Manejador cuando el usuario envía una línea de comando."""
        # Caso 1: Estamos esperando input del usuario (prompt_user / prompt_menu)
        if getattr(self.tui_engine, "_waiting_for_input", False):
            self.tui_engine._input_result = buffer.text
            prompt_label = getattr(self.tui_engine, "_current_prompt_label", " 🪼 > ")
            self.append_to_output(f"\n {prompt_label}{buffer.text}\n")
            self.tui_engine._input_event.set()
            return

        # Caso 2: Comando normal del usuario
        user_input = buffer.text.strip()
        if user_input:
            self.append_to_output(f"\n[Usuario]: {user_input}\n")

        self.scroll_output_to_bottom()
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
                    self.append_to_output(f"\n❌ Error al ejecutar: {e}\n")
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
        self._log_text: str = ""  # Buffer de respaldo cuando no hay TUI activa
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

        # Mostrar la pregunta en el Output Panel
        if self.active_tui_app:
            self.active_tui_app.append_to_output(f"\n❓ {prompt_text}\n")
            self.active_tui_app.app.loop.call_soon_threadsafe(
                self.active_tui_app.input_area.buffer.reset
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
        old_validator = self.active_tui_app.input_area.buffer.validator

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
        self.active_tui_app.input_area.buffer.completer = menu_completer
        self.active_tui_app.input_area.buffer.validator = MenuValidator()

        # Resetear buffer y disparar autocompletado
        def setup_menu():
            self.active_tui_app.input_area.buffer.reset()
            self.active_tui_app.input_area.buffer.start_completion(select_first=True)

        self.active_tui_app.app.loop.call_soon_threadsafe(setup_menu)
        self.active_tui_app.app.invalidate()

        # Bloquear hasta recibir selección
        self._input_event.wait()

        # Restaurar estado original
        self._waiting_for_input = False
        self._current_prompt_label = " 🪼 > "
        self.active_tui_app.completer = old_completer
        self.active_tui_app.input_area.buffer.completer = old_completer
        self.active_tui_app.input_area.buffer.validator = old_validator

        def restore_menu():
            self.active_tui_app.input_area.buffer.reset()

        self.active_tui_app.app.loop.call_soon_threadsafe(restore_menu)
        self.active_tui_app.app.invalidate()

        result = self._input_result.strip()
        for opt in options:
            if opt.lower() == result.lower():
                return opt
        return None

    def clear_scroll_region(self):
        """Limpia el área de output de la TUI."""
        if getattr(self, "active_tui_app", None):
            self.active_tui_app.output_area.text = ""
            self.active_tui_app.app.invalidate()
        else:
            with self._lock:
                self._log_text = ""

    def move_cursor_to_scroll_region(self):
        """No-op en layout tiling ya que el cursor se mantiene en el input buffer."""
        pass

    def print_welcome_logo(self):
        """Muestra el logo de Jellyfish en la consola (compatibilidad con comandos v6.9)."""
        logo = """[bold blue]
╦╔═╗╦  ╦  ╦ ╦╔═╗╦╔═╗╦ ╦
║║╣ ║  ║  ╚╦╝╠╣ ║╚═╗╠═╣
╚╝╚═╝╩═╝╩═╝ ╩ ╚  ╩╚═╝╩ ╩[/bold blue]
[bold cyan]Jellyfish OS v7.1 — Framework de Agentes[/bold cyan]
"""
        from core.ui import console
        console.print(logo)

    def append_log(self, text: str):
        """Añade texto al Output Panel de la TUI, limpiando secuencias ANSI."""
        # Limpiar TODAS las secuencias ANSI (color, cursor, etc.)
        cleaned = ANSI_CLEAN_RE.sub('', text)

        # Manejar \r (retorno de carro) para soporte de barras de progreso
        processed = ""
        for char in cleaned:
            if char == '\r':
                # Retorno de carro: buscar la última línea y sobrescribirla
                last_nl = processed.rfind('\n')
                if last_nl != -1:
                    processed = processed[:last_nl + 1]
                else:
                    processed = ""
            else:
                processed += char

        if getattr(self, "active_tui_app", None):
            try:
                self.active_tui_app.append_to_output(processed)
                self.active_tui_app.app.invalidate()
            except Exception:
                pass
        else:
            # Respaldo: almacenar en buffer interno
            with self._lock:
                self._log_text += processed
                if len(self._log_text) > 100_000:
                    self._log_text = self._log_text[-100_000:]

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

        # Si hay texto en el buffer de respaldo, volcarlo al Output Panel
        if self._log_text:
            tui_app.append_to_output(self._log_text)
            with self._lock:
                self._log_text = ""

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
