import os
import re
import shlex
import subprocess
import logging
import signal
from rich.panel import Panel
from rich.console import Console

logger = logging.getLogger("jellyfish.terminal")
console = Console()

# Timeout por defecto en segundos
DEFAULT_TIMEOUT = 120

# Sprint 1.3 — Lista negra de comandos destructivos (regex).
# Estos patrones nunca se ejecutarán, sin importar la confirmación del usuario.
_DESTRUCTIVE_PATTERNS: list[re.Pattern] = [
    # rm con flags que incluyan r y f en cualquier orden (-rf, -fr, -Rf, -rRf, etc.)
    re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\b|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\b", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),                       # mkfs.*
    re.compile(r"\bdd\b.*\bof=/dev/", re.IGNORECASE),             # dd of=/dev/sda
    re.compile(r"\bchmod\s+(-[a-zA-Z]*R[a-zA-Z]*|--recursive)\s+[0-7]*7[0-7]*\s+/", re.IGNORECASE),  # chmod -R 777 /
    re.compile(r">\s*/dev/sda", re.IGNORECASE),                   # > /dev/sda
    re.compile(r"\bformat\b.*[cCdDeE]:\\\\", re.IGNORECASE),     # format C:\ (Windows)
    re.compile(r":\(\)\{.*\};:", re.IGNORECASE),                  # fork bomb
    re.compile(r"\b(find|fd)\b.*\s-delete\b", re.IGNORECASE),     # borrado masivo via find/fd
    re.compile(r"\b(wipefs|fdisk|sfdisk|parted)\b", re.IGNORECASE),  # particiones/discos
    re.compile(r"\bshred\b.*\s(/|~|\$HOME)\b", re.IGNORECASE),    # destrucción de datos
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

    # Sprint 1.3 — Bloqueo de comandos destructivos
    dangerous, matched_pattern = _is_destructive(actual_command)
    if dangerous:
        msg = (
            f"🛑 Comando bloqueado por política de seguridad.\n"
            f"   Patrón detectado: {matched_pattern}\n"
            f"   Comando: {actual_command[:120]}"
        )
        console.print(f"[bold red]{msg}[/bold red]")
        logger.warning("Comando destructivo bloqueado: %s", actual_command[:120])
        return msg

    try:
        popen_command, use_shell = _prepare_subprocess_command(actual_command)
        # Sprint 8.4 — Ejecutar comandos en la carpeta del proyecto activo si está configurado
        exec_cwd = state.active_project if getattr(state, "active_project", None) and os.path.exists(state.active_project) else None

        import threading
        import sys
        
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
        def _stream_output():
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                captured_lines.append(line)
                
        reader = threading.Thread(target=_stream_output)
        reader.start()

        # Esperar al proceso respetando el timeout
        process.wait(timeout=actual_timeout)
        reader.join()
        
        console.print(f"╰{'─'*80}╯")

        res = "".join(captured_lines).strip()
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
        console.print(f"[bold red]{msg}[/bold red]")
        logger.warning("Timeout ejecutando: %s", actual_command[:100])
        return msg

    except FileNotFoundError as e:
        msg = f"Comando no encontrado: {e}"
        console.print(f"[dim red]{msg}[/dim red]")
        logger.error("Comando no encontrado: %s", e)
        return msg

    except Exception as e:
        msg = f"Error al ejecutar comando: {e}"
        console.print(f"[dim red]{msg}[/dim red]")
        logger.error("Error terminal: %s", e)
        return str(e)
