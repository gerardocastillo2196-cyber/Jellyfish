"""
╔══════════════════════════════════════════════════════════════════╗
║  Jellyfish CLI Engine — Sprint 7.1 (Refactored)                 ║
║  CLI REPL Engine with prompt_toolkit & rich                      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import logging
import threading
from typing import Any, Dict, List, Optional
from prompt_toolkit import PromptSession

logger = logging.getLogger("jellyfish.tui")

class TUIEngine:
    """Motor de orquestación y renderizado CLI para Jellyfish OS."""

    def __init__(self):
        self._lock = threading.Lock()
        self._initialized = False
        self._log_text: str = ""
        self.command_handler = None
        self.active_tui_app = None
        self.cli_mode = True  # Para compatibilidad con tests y código heredado

    def init_terminal(self):
        """Inicializa la terminal en modo CLI."""
        self._initialized = True

        import builtins
        if not hasattr(self, "_original_input"):
            self._original_input = builtins.input
        builtins.input = self._custom_input

    def restore_terminal(self):
        """Restaura los manejadores de la terminal."""
        self._initialized = False

        import builtins
        if hasattr(self, "_original_input"):
            builtins.input = self._original_input

    def _custom_input(self, prompt=""):
        return self.prompt_user(prompt)

    def prompt_user(self, prompt_text: str) -> str:
        """Pide una entrada al usuario usando un PromptSession simple."""
        try:
            session = PromptSession()
            return session.prompt(prompt_text)
        except (KeyboardInterrupt, EOFError):
            return ""

    def prompt_menu(self, title: str, options: List[str]) -> Optional[str]:
        """Presenta un menú interactivo usando el selector de flechas."""
        from core.ui import interactive_picker
        return interactive_picker(title, options, add_back=False)

    def clear_scroll_region(self):
        """Limpia la terminal estándar."""
        os.system("cls" if os.name == "nt" else "clear")

    def move_cursor_to_scroll_region(self):
        """No-op en CLI."""
        pass

    def print_welcome_logo(self):
        """Muestra el logo de Jellyfish en la consola."""
        pass

    def append_log(self, text: str):
        """Imprime directamente al stdout estándar de la terminal."""
        sys.stdout.write(text)
        sys.stdout.flush()

    def render_header(self, **kwargs):
        """No-op en CLI pura."""
        pass

    def get_user_input(self, state, completer, key_bindings, lexer) -> str:
        """Inicia el bucle de REPL de CLI interactiva y procesa los comandos."""
        session = PromptSession(
            completer=completer,
            key_bindings=key_bindings,
            lexer=lexer,
        )

        while True:
            try:
                # El prompt será directamente session.prompt('🐙> ')
                user_input = session.prompt('🐙> ')
                user_input = user_input.strip()
                if not user_input:
                    continue

                if user_input.lower() in ("/exit", "exit", "quit"):
                    break

                if self.command_handler:
                    self.command_handler(user_input)

            except KeyboardInterrupt:
                print("\n(Usa /exit para salir)")
                continue
            except EOFError:
                break
            except Exception as e:
                print(f"\n❌ Error al ejecutar: {e}\n")

        return "/exit"

    def start_task(self, task_id: str, description: str, agent: str = None) -> None:
        """Registra el inicio de una tarea en segundo plano."""
        self.append_log(f"\n[⟳] INICIANDO: @{agent or 'agente'} -> {description}\n")
        logger.info("Task %s iniciada: %s", task_id, description)

    def finish_task(self, task_id: str, success: bool = True, tokens: int = None, agent: str = None) -> None:
        """Registra la finalización de una tarea en segundo plano."""
        status_text = "COMPLETADO" if success else "FALLIDO"
        tok_str = f" ({tokens:,} tokens)" if tokens else ""
        self.append_log(f"[✓] {status_text}: @{agent or 'agente'} -> {task_id}{tok_str}\n\n")
        logger.info("Task %s terminada (%s)", task_id, status_text)


class TaskProgress:
    """Context manager para visualización de progreso compatible con la CLI."""

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


tui_engine = TUIEngine()
