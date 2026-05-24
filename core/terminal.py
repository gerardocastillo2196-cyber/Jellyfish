import os
import re
import shlex
import subprocess
import logging
import signal
import sys
from rich.panel import Panel
from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.validation import Validator, ValidationError

logger = logging.getLogger("jellyfish.terminal")
console = Console()
screen_console = Console(file=sys.stdout)

# Timeout por defecto en segundos
DEFAULT_TIMEOUT = 120

# Sprint 1.3 — Lista negra de comandos destructivos (regex).
# Estos patrones nunca se ejecutarán, sin importar la confirmación del usuario.
_DESTRUCTIVE_PATTERNS: list[re.Pattern] = [
    # 1. Eliminaciones masivas fuera del scope o destructivas (rm recursivo)
    re.compile(r"\brm\s+(-[a-zA-Z]*[rR][a-zA-Z]*|--recursive)\b", re.IGNORECASE),
    # 2. Comandos de formateo o manipulación cruda de discos
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r"\bdd\b.*\bof=/dev/", re.IGNORECASE),
    re.compile(r"\b(wipefs|fdisk|sfdisk|parted|gparted)\b", re.IGNORECASE),
    re.compile(r">\s*/dev/sda", re.IGNORECASE),
    re.compile(r"\bformat\b.*[cCdDeE]:\\\\", re.IGNORECASE),
    # 3. Alteraciones críticas de usuarios o del sistema (chmod/chown masivos en raíz)
    re.compile(r"\b(chmod|chown)\b.*(-R|--recursive).*(?:/(?:$|\s)|/(etc|var|usr|bin|sbin|lib|sys|proc|dev|boot|root|home|opt|srv)\b)", re.IGNORECASE),
    re.compile(r"\bchmod\s+(-[a-zA-Z]*R[a-zA-Z]*|--recursive)\s+[0-7]*7[0-7]*\s+/", re.IGNORECASE),
    # 4. Comandos de red o ejecución remota sospechosos
    re.compile(r"\b(curl|wget)\b.*\s*\|\s*(sh|bash|zsh|dash|ash)\b", re.IGNORECASE),
    re.compile(r"\b(sh|bash|zsh|dash|ash)\s+<.*\b(curl|wget)\b", re.IGNORECASE),
    # Fork bomb / shred / borrado masivo find
    re.compile(r":\(\)\{.*\};:", re.IGNORECASE),
    re.compile(r"\b(find|fd)\b.*\s-delete\b", re.IGNORECASE),
    re.compile(r"\bshred\b.*\s(/|~|\$HOME)\b", re.IGNORECASE),
]

# Fase 2 - Barrera de Red
_NETWORK_PATTERNS = [
    re.compile(r"\b(curl|wget|ping|ssh|scp|ftp|nc|netcat|nmap|telnet)\b", re.IGNORECASE)
]

_SHELL_META_RE = re.compile(r"[|&;<>()$`*?\[\]{}~]")

# Sprint 8.0 — Prefijos de comandos de solo lectura que no necesitan confirmación
# del usuario en el bucle Auto-ReAct. Solo aplica cuando el LLM sugiere
# comandos, no cuando el usuario ejecuta manualmente con /run.
_READONLY_PREFIXES = (
    "ls", "cat", "head", "tail", "wc", "file", "stat", "du", "df",
    "find", "fd", "which", "where", "type", "echo", "printf",
    "date", "uname", "whoami", "id", "hostname", "pwd", "env",
    "printenv", "tree", "diff", "grep", "rg", "ag", "awk", "sed -n",
    "python3 --version", "python --version", "node --version",
    "go version", "rustc --version", "java -version",
    "git log", "git status", "git diff", "git show", "git branch",
    "git remote", "git tag", "git rev-parse",
)


def is_readonly_command(command: str) -> bool:
    """Determina si un comando es de solo lectura (seguro para auto-aprobación).

    Sprint 8.0 — Comandos de lectura pueden auto-ejecutarse en el Action Loop
    sin requerir confirmación manual del usuario.

    Args:
        command: El comando a evaluar.

    Returns:
        True si el comando es de solo lectura.
    """
    cmd_stripped = command.strip()
    # No auto-aprobar comandos con pipe, redirect o encadenamiento
    if any(c in cmd_stripped for c in ('|', '>', '>>', '&&', '||', ';')):
        return False
    for prefix in _READONLY_PREFIXES:
        if cmd_stripped.startswith(prefix):
            return True
    return False


def _is_destructive(command: str) -> tuple[bool, str]:
    """Verifica si un comando coincide con patrones destructivos conocidos.

    Sprint 1.3 — Previene ejecución de comandos catastróficos generados por el LLM.

    Returns:
        (True, patrón_detectado) si es peligroso, (False, "") si es seguro.
    """
    for pattern in _DESTRUCTIVE_PATTERNS:
        if pattern.search(command):
            return True, pattern.pattern
    return False, ""


def _smart_truncate(text: str, max_chars: int = 5000) -> str:
    """Truncamiento inteligente que preserva inicio y final del output.

    Sprint 1.4 — En lugar de cortar sólo al inicio (donde suele estar el output normal),
    preserva las primeras y últimas líneas porque los errores de compilación y ejecución
    suelen aparecer al FINAL del stderr/stdout.

    Args:
        text: Texto completo a truncar.
        max_chars: Límite máximo de caracteres en la salida.

    Returns:
        Texto truncado con marcador visual en el centro.
    """
    if len(text) <= max_chars:
        return text

    half = max_chars // 2
    head = text[:half]
    tail = text[-half:]
    omitted = len(text) - max_chars
    return (
        f"{head}\n\n"
        f"[dim]... [{omitted:,} caracteres omitidos — usa '/run' para ver la salida completa] ...[/dim]\n\n"
        f"{tail}"
    )


def _prepare_subprocess_command(command: str):
    """Prefiere shell=False cuando no hacen falta metacaracteres de shell."""
    if _SHELL_META_RE.search(command):
        return command, True
    try:
        return shlex.split(command), False
    except ValueError:
        return command, True


def run_terminal_command(
    command_str: str,
    state,
    silent_history: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    force_confirm: bool = False,
    return_code_dict: dict = None,
) -> str:
    """Ejecuta un comando en la terminal del sistema.

    Usa subprocess.Popen para capturar stdout y stderr por separado.
    El resultado se muestra en un panel Rich y se inyecta en el historial
    del estado (a menos que silent_history sea True).

    Parches Sprint 1:
    - 1.3: Bloqueo de comandos destructivos antes de cualquier ejecución.
    - 1.4: Truncamiento inteligente head+tail para preservar errores al final.

    Args:
        command_str: El comando a ejecutar.
        state: Instancia de JellyfishState para inyectar el resultado.
        silent_history: Si es True, no agrega el resultado al historial.
        timeout: Segundos máximos de ejecución antes de abortar.
        force_confirm: Si es True, requiere confirmación del usuario [y/n/a].
        return_code_dict: Diccionario opcional para retornar el código de salida.

    Returns:
        La salida del comando como string.
    """
    # Parsear flag --timeout si está presente en el comando
    actual_command = command_str
    actual_timeout = timeout
    if "--timeout=" in command_str:
        parts = command_str.split()
        clean_parts = []
        for part in parts:
            if part.startswith("--timeout="):
                try:
                    actual_timeout = int(part.split("=")[1])
                except ValueError:
                    pass
            else:
                clean_parts.append(part)
        actual_command = " ".join(clean_parts)
    # Fase 2: Modo Dry Run (Validación de sintaxis Bash)
    import subprocess
    try:
        syntax_check = subprocess.run(
            ["bash", "-n", "-c", actual_command],
            capture_output=True,
            text=True
        )
        if syntax_check.returncode != 0:
            error_msg = f"❌ Error de sintaxis (Dry Run AST): {syntax_check.stderr.strip()}"
            console.print(f"[bold red]{error_msg}[/bold red]\n")
            if return_code_dict is not None:
                return_code_dict['returncode'] = -1
            return error_msg
    except Exception as e:
        logger.warning("No se pudo ejecutar bash -n para dry run: %s", e)

    # Sprint 1.3 — Bloqueo de comandos destructivos
    dangerous, matched_pattern = _is_destructive(actual_command)
    if dangerous:
        msg = (
            f"🛑 INCIDENTE DE SEGURIDAD: Comando destructivo detectado y bloqueado automáticamente.\n"
            f"   Patrón de lista negra: {matched_pattern}\n"
            f"   Comando: {actual_command[:150]}"
        )
        console.print(f"\n[bold red]{'━'*80}\n{msg}\n{'━'*80}[/bold red]\n")
        logger.error("COMANDO DESTRUCTIVO BLOQUEADO: %s (Patrón: %s)", actual_command, matched_pattern)
        if return_code_dict is not None:
            return_code_dict['returncode'] = -1
        return msg

    # Prevenir prompts repetidos para comandos denegados o fallidos en este turno
    if actual_command in getattr(state, "denied_commands", set()):
        msg = f"✗ Comando denegado automáticamente porque ya fue rechazado o falló previamente en este turno."
        console.print(f"[red]{msg}[/red]\n")
        if return_code_dict is not None:
            return_code_dict['returncode'] = -1
        return msg

    # Fase 2: Barrera de Red Estricta
    is_network = any(pattern.search(actual_command) for pattern in _NETWORK_PATTERNS)

    # Sprint 11 — Sistema de permisos dinámicos y configuración por proyecto [y/n/a]
    requires_prompt = force_confirm
    if requires_prompt and state.is_project_auto_approved():
        requires_prompt = False

    # Nunca auto-aprobar comandos de red
    if is_network:
        requires_prompt = True

    if requires_prompt:
        from rich.syntax import Syntax
        
        class YesNoAlwaysValidator(Validator):
            def validate(self, document):
                text = document.text.strip().lower()
                valid_opts = ('y', 'n') if is_network else ('y', 'n', 'a')
                if text not in valid_opts:
                    if is_network:
                        raise ValidationError(message="Comandos de RED detectados. Ingresa 'y' (una vez) o 'n' (denegar)")
                    raise ValidationError(message="Ingresa 'y' (una vez), 'n' (denegar) o 'a' (siempre en este proyecto)")

        subtitle_text = (
            "[bold white][y][/bold white] Permitir una vez  ·  [bold white][n][/bold white] Denegar"
            if is_network
            else "[bold white][y][/bold white] Permitir una vez  ·  [bold white][n][/bold white] Denegar  ·  [bold white][a][/bold white] Permitir siempre para este proyecto"
        )
        title_text = (
            "[bold red]⚡ SOLICITUD ESTRICTA DE RED (BLOQUEADA)[/bold red]"
            if is_network
            else "[bold yellow]⚡ SOLICITUD DE EJECUCIÓN DE COMANDO[/bold yellow]"
        )

        syntax = Syntax(actual_command, "bash", theme="monokai", word_wrap=True)
        panel = Panel(
            syntax,
            title=title_text,
            subtitle=subtitle_text,
            border_style="red" if is_network else "yellow",
            expand=False,
            padding=(1, 2)
        )
        screen_console.print()
        screen_console.print(panel)

        try:
            import asyncio
            session = PromptSession()
            async def get_decision():
                return await session.prompt_async("Decisión [y/n/a]: ", validator=YesNoAlwaysValidator())
            decision = asyncio.run(asyncio.wait_for(get_decision(), timeout=60)).strip().lower()
        except TimeoutError:
            if is_network:
                decision = 'n'
                screen_console.print("\n[red]✗ Tiempo de espera agotado (60s). Comando de RED denegado por seguridad.[/red]")
            else:
                decision = 'y'
                screen_console.print("\n[green]✓ Tiempo de espera agotado (60s). Comando aceptado automáticamente.[/green]")
        except (KeyboardInterrupt, EOFError):
            decision = 'n'
            screen_console.print("\n[red]✗ Comando denegado por interrupción.[/red]")

        if decision == 'n':
            if not hasattr(state, "denied_commands"):
                state.denied_commands = set()
            state.denied_commands.add(actual_command)
            screen_console.print("[red]✗ Ejecución denegada por el usuario.[/red]\n")
            if return_code_dict is not None:
                return_code_dict['returncode'] = -1
            return "Ejecución denegada por el usuario."
        elif decision == 'a':
            state.enable_project_auto_approve()
            screen_console.print("[green]✓ Auto-aprobación activada para este proyecto en adelante.[/green]\n")

    try:
        # Sprint 8.4 — Ejecutar comandos en la carpeta del proyecto activo si está configurado
        exec_cwd = state.active_project if getattr(state, "active_project", None) and os.path.exists(state.active_project) else None

        # Sprint 11 — Activar entorno virtual si existe en el proyecto
        if exec_cwd and os.path.isfile(os.path.join(exec_cwd, ".venv", "bin", "activate")):
            import shlex
            venv_activate = os.path.join(exec_cwd, ".venv", "bin", "activate")
            popen_command = f". {shlex.quote(venv_activate)} && {actual_command}"
            use_shell = True
        else:
            popen_command, use_shell = _prepare_subprocess_command(actual_command)

        # Fase 2: Inyección de Bubblewrap (bwrap)
        import shutil
        has_bwrap = shutil.which("bwrap") is not None
        if has_bwrap and exec_cwd:
            if isinstance(popen_command, list):
                popen_command = [
                    "bwrap",
                    "--ro-bind", "/", "/",
                    "--dev", "/dev",
                    "--proc", "/proc",
                    "--tmpfs", "/tmp",
                    "--bind", exec_cwd, exec_cwd,
                    "--chdir", exec_cwd,
                ] + popen_command
            else:
                import shlex
                bwrap_prefix = f"bwrap --ro-bind / / --dev /dev --proc /proc --tmpfs /tmp --bind {shlex.quote(exec_cwd)} {shlex.quote(exec_cwd)} --chdir {shlex.quote(exec_cwd)}"
                popen_command = f"{bwrap_prefix} sh -c {shlex.quote(popen_command)}"

        # Check if silent execution is active
        is_silent = getattr(state, "silent_execution", False)

        import threading
        
        # Prepare debug log path
        debug_log_path = os.path.join(exec_cwd, "jellyfish_debug.log") if exec_cwd else "jellyfish_debug.log"

        if not is_silent:
            console.print(f"\n╭─[bold yellow] Salida de Terminal [/bold yellow]{'─'*60}╮")
        
        process = subprocess.Popen(
            popen_command,
            shell=use_shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            preexec_fn=os.setpgrp,
            cwd=exec_cwd,
        )
        
        captured_lines = []
        stdout_lock = threading.Lock()
        def _stream_output():
            try:
                with open(debug_log_path, "a", encoding="utf-8") as f:
                    for line in process.stdout:
                        f.write(line)
                        f.flush()
                        if not is_silent:
                            with stdout_lock:
                                sys.stdout.write(line)
                                sys.stdout.flush()
                        captured_lines.append(line)
            except Exception:
                for line in process.stdout:
                    if not is_silent:
                        with stdout_lock:
                            sys.stdout.write(line)
                            sys.stdout.flush()
                    captured_lines.append(line)
                 
        reader = threading.Thread(target=_stream_output)
        reader.start()

        # Esperar al proceso respetando el timeout
        process.wait(timeout=actual_timeout)
        reader.join()
        
        if not is_silent:
            console.print(f"╰{'─'*80}╯")

        res = "".join(captured_lines).strip()
        if return_code_dict is not None:
            return_code_dict['returncode'] = process.returncode

        if is_silent:
            if process.returncode != 0:
                screen_console.print(f"\n[bold red]❌ Comando falló con código {process.returncode}:[/bold red]")
                screen_console.print(res)
        else:
            if not res:
                res = f"✓ Comando ejecutado sin salida (exit code: {process.returncode})"
                console.print(f"[dim]{res}[/dim]")
            elif process.returncode != 0:
                console.print(f"[red]✗ Comando finalizó con código {process.returncode}[/red]")
            else:
                console.print("[green]✓ Comando ejecutado exitosamente[/green]")

        if not silent_history:
            # Historial recibe versión compacta head+tail de 3000 chars
            history_res = _smart_truncate(res, max_chars=3000)
            state.history.append({
                "role": "system",
                "content": f"[SALIDA TERMINAL: {actual_command[:80]}]\n{history_res}",
            })

        return res

    except subprocess.TimeoutExpired:
        # Sprint 8.0 — Matar todo el process group, no solo el proceso padre
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
                process.wait(timeout=5)
            except Exception:
                pass
        msg = f"⏰ Timeout: el comando excedió los {actual_timeout} segundos."
        screen_console.print(f"[bold red]{msg}[/bold red]")
        logger.warning("Timeout ejecutando: %s", actual_command[:100])
        
        # Registrar como denegado/fallido para prevenir loops infinitos de reintento en este turno
        if not hasattr(state, "denied_commands"):
            state.denied_commands = set()
        state.denied_commands.add(actual_command)
        
        if return_code_dict is not None:
            return_code_dict['returncode'] = -1
        return msg

    except FileNotFoundError as e:
        msg = f"Comando no encontrado: {e}"
        screen_console.print(f"[dim red]{msg}[/dim red]")
        logger.error("Comando no encontrado: %s", e)
        if return_code_dict is not None:
            return_code_dict['returncode'] = -1
        return msg

    except Exception as e:
        msg = f"Error al ejecutar comando: {e}"
        screen_console.print(f"[dim red]{msg}[/dim red]")
        logger.error("Error terminal: %s", e)
        if return_code_dict is not None:
            return_code_dict['returncode'] = -1
        return str(e)
