import re
import subprocess
import logging
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
    re.compile(r"\bchmod\s+-R\s+777\s+/\b", re.IGNORECASE),      # chmod -R 777 /
    re.compile(r">\s*/dev/sda", re.IGNORECASE),                   # > /dev/sda
    re.compile(r"\bformat\b.*[cCdDeE]:\\\\", re.IGNORECASE),     # format C:\ (Windows)
    re.compile(r":\(\)\{.*\};:", re.IGNORECASE),                  # fork bomb
]


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
        f"[dim]... [{omitted:,} caracteres omitidos] ...[/dim]\n\n"
        f"{tail}"
    )


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
        process = subprocess.Popen(
            actual_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate(timeout=actual_timeout)

        # Combinar stdout y stderr
        res = stdout.strip()
        if stderr.strip():
            res = f"{res}\n[stderr]\n{stderr.strip()}" if res else stderr.strip()
        if not res:
            res = f"✓ Comando ejecutado (exit code: {process.returncode})"

        # Sprint 1.4 — Truncamiento inteligente (head + tail)
        display_res = _smart_truncate(res, max_chars=5000)
        console.print(Panel(display_res, title="Terminal", border_style="yellow"))

        if not silent_history:
            # Historial recibe versión compacta head+tail de 3000 chars
            history_res = _smart_truncate(res, max_chars=3000)
            state.history.append({
                "role": "system",
                "content": f"[SALIDA TERMINAL: {actual_command[:80]}]\n{history_res}",
            })

        return res

    except subprocess.TimeoutExpired:
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
