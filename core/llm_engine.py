import os
import signal
import time
import json
import re
import logging
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.prompt import Confirm

from core.terminal import run_terminal_command
from core.state import (
    OPENAI_BASE_URL, DEEPSEEK_BASE_URL, OPENROUTER_BASE_URL,
)

# Timeout en segundos para la confirmación interactiva del Action Loop (Sprint 1.4)
_CONFIRM_TIMEOUT_S = 60

logger = logging.getLogger("jellyfish.llm")
console = Console()

# Máximo de iteraciones Auto-ReAct (evitar bucles infinitos)
MAX_REACT_LOOPS = 3

# Regex para detectar bloques de código bash/sh/shell
_BASH_REGEX = re.compile(
    r"```(?:bash|sh|shell|zsh)?\s*\n(.*?)\n```",
    re.DOTALL
)


def _get_provider_config(state) -> tuple:
    """Retorna (url, headers) según el proveedor configurado en la instancia del estado."""
    if state.provider == "openai":
        return f"{OPENAI_BASE_URL}/chat/completions", {
            "Authorization": f"Bearer {state.openai_api_key}",
            "Content-Type": "application/json",
        }
    elif state.provider == "deepseek":
        return f"{state.deepseek_base_url}/chat/completions", {
            "Authorization": f"Bearer {state.deepseek_api_key}",
            "Content-Type": "application/json",
        }
    elif state.provider == "openrouter":
        return f"{OPENROUTER_BASE_URL}/chat/completions", {
            "Authorization": f"Bearer {state.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/jellyfish-os",
            "X-Title": "Jellyfish OS",
        }
    else:  # ollama (default)
        return state.ollama_url, {"Content-Type": "application/json"}


def _parse_sse_line(line_bytes: bytes, provider: str) -> str:
    """Parsea una línea del stream SSE (OpenAI-compatible) y retorna el contenido delta."""
    decoded = line_bytes.decode("utf-8").strip()
    if not decoded.startswith("data: "):
        return ""
    payload = decoded[6:]
    if payload == "[DONE]":
        return ""
    try:
        data = json.loads(payload)
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("delta", {}).get("content", "")
    except json.JSONDecodeError:
        pass
    return ""


def _parse_ollama_line(line_bytes: bytes) -> str:
    """Parsea una línea del stream nativo de Ollama."""
    try:
        data = json.loads(line_bytes.decode("utf-8"))
        if "message" in data:
            return data["message"].get("content", "")
    except json.JSONDecodeError:
        pass
    return ""


def _call_llm_silent(state, messages: list) -> str | None:
    """Llama al LLM sin mostrar streaming en pantalla (para subagentes internos).

    Sprint 1.2 — Usa httpx en modo síncrono con streaming silencioso.
    Sprint 3.1 — Migrado de requests a httpx.

    Args:
        state: Instancia del estado.
        messages: Lista de mensajes en formato Chat Completions.

    Returns:
        La respuesta completa del modelo como string, o None si hay error.
    """
    url, headers = _get_provider_config(state)
    is_cloud = state.provider != "ollama"
    payload = {
        "model": state.model,
        "messages": messages,
        "stream": True,
    }
    if is_cloud:
        payload["temperature"] = 0.2

    try:
        full = ""
        parse_fn = (
            (lambda line: _parse_sse_line(line, state.provider))
            if is_cloud
            else _parse_ollama_line
        )
        # Sprint 3.1 — httpx con streaming síncrono
        with httpx.Client(timeout=300) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    logger.warning(
                        "_call_llm_silent HTTP %s de %s", response.status_code, state.provider
                    )
                    return None
                for line in response.iter_lines():
                    if not line:
                        continue
                    chunk = parse_fn(line.encode("utf-8"))
                    if chunk:
                        full += chunk
        return full if full else None

    except httpx.ConnectError:
        logger.error("No se puede conectar al proveedor %s (silent)", state.provider)
        return None
    except Exception as e:
        logger.error("Error en _call_llm_silent: %s", e)
        return None


def _stream_request(
    state,
    messages: list,
    agent_name: str,
    _aborted: list | None = None,
) -> str | None:
    """Realiza la petición HTTP con streaming al proveedor configurado en el estado.

    Sprint 3.1 — Migrado de requests a httpx (mejor soporte para cancelación).
    Sprint 3.3 — Soporta interrupción grácil via Ctrl+C: aborta solo el stream
                  HTTP sin matar el proceso completo. Señal via lista _aborted mutable.

    Args:
        state: Instancia del estado.
        messages: Lista de mensajes en formato Chat Completions.
        agent_name: Nombre del agente (para el título del panel).
        _aborted: Lista mutable [False] para señalizar cancelación desde fuera.

    Returns:
        La respuesta completa del modelo, o None si hay error / cancelación.
    """
    url, headers = _get_provider_config(state)
    is_cloud = state.provider != "ollama"

    payload = {
        "model": state.model,
        "messages": messages,
        "stream": True,
    }
    if is_cloud:
        payload["temperature"] = 0.2

    full = ""
    provider_label = f"{state.provider}:{state.model}" if is_cloud else f"@{agent_name}"
    parse_fn = (
        (lambda line: _parse_sse_line(line, state.provider))
        if is_cloud
        else _parse_ollama_line
    )

    try:
        with httpx.Client(timeout=300) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    error_body = response.read()[:500].decode("utf-8", errors="replace")
                    console.print(
                        f"[bold red]Error HTTP {response.status_code} de {state.provider}:[/bold red]\n"
                        f"[dim]{error_body}[/dim]"
                    )
                    return None

                # Sprint 3.3 — Streaming con soporte de interrupción grácil
                with Live(
                    Panel("", title=provider_label),
                    refresh_per_second=12,
                    console=console,
                ) as live:
                    try:
                        for line in response.iter_lines():
                            # Verificar señal de cancelación (Ctrl+C capturado en jellyfish.py)
                            if _aborted and _aborted[0]:
                                console.print(
                                    "\n[dim]⚡ Stream interrumpido — respuesta parcial conservada.[/dim]"
                                )
                                break

                            if not line:
                                continue

                            chunk = parse_fn(line.encode("utf-8"))
                            if chunk:
                                full += chunk
                                live.update(Panel(
                                    Markdown(full),
                                    title=provider_label,
                                    border_style="bright_black",
                                ))

                    except KeyboardInterrupt:
                        # Sprint 3.3 — Ctrl+C dentro del stream: conservar lo recibido
                        console.print(
                            "\n[dim]⚡ Stream interrumpido — respuesta parcial conservada.[/dim]"
                        )
                        if _aborted is not None:
                            _aborted[0] = True

        return full if full else None

    except httpx.ConnectError:
        if state.provider == "ollama":
            console.print(
                "[bold red]Error: No se puede conectar a Ollama.[/bold red]\n"
                "[dim]Asegúrate de que Ollama esté ejecutándose: ollama serve[/dim]"
            )
        else:
            console.print(
                f"[bold red]Error: No se puede conectar al proveedor {state.provider}.[/bold red]\n"
                "[dim]Verifica tu conexión a internet y la URL del API.[/dim]"
            )
        return None

    except httpx.TimeoutException:
        console.print("[bold red]Error: Timeout en la conexión (>300s).[/bold red]")
        return None

    except Exception as e:
        console.print(f"[red]Error LLM ({state.provider}): {e}[/red]")
        logger.error("Error en _stream_request: %s", e, exc_info=True)
        return None


def stream_ollama(state, rag_context: str = "") -> str | None:
    """Envía los mensajes al LLM y hace streaming de la respuesta.

    Implementa un bucle Auto-ReAct: si el modelo sugiere comandos bash
    y el usuario los aprueba, el output del terminal se envía de vuelta
    al modelo para que pueda razonar sobre el resultado.

    Sprint 3.1 — Migrado a httpx.
    Sprint 3.3 — Ctrl+C aborta solo el stream, no el proceso.

    Args:
        state: Instancia de JellyfishState con el historial completo.
        rag_context: Contexto RAG pre-recuperado para inyectar.

    Returns:
        La respuesta completa del modelo (última iteración), o None si hay error.
    """
    react_iteration = 0
    final_response = None
    _aborted = [False]  # Sprint 3.3 — señal mutable de cancelación

    while react_iteration < MAX_REACT_LOOPS:
        react_iteration += 1

        messages = state.get_full_history()

        # Inyectar contexto RAG como mensaje de sistema justo antes del final
        if rag_context:
            messages = messages.copy()
            messages.insert(-1, {
                "role": "system",
                "content": (
                    "[INSTRUCCIÓN: El siguiente contexto fue recuperado automáticamente "
                    "del código fuente indexado. Úsalo para fundamentar tu respuesta "
                    "cuando sea relevante, pero no lo cites textualmente a menos que "
                    "el usuario lo solicite.]\n" + rag_context
                )
            })

        # Realizar la petición — Sprint 3.3: pasar la señal _aborted
        full = _stream_request(state, messages, state.active_agent, _aborted=_aborted)

        # Si fue cancelado por Ctrl+C, conservar lo que llegó y salir del ReAct
        if _aborted[0]:
            final_response = full or final_response
            break

        if not full:
            if react_iteration == 1:
                console.print("[yellow]⚠ El modelo no generó respuesta.[/yellow]")
            return final_response

        final_response = full

        # --- Action Loop: Interceptor de comandos bash ---
        matches = _BASH_REGEX.findall(full)
        if not matches:
            break

        executed_any = False
        for cmd in matches:
            cmd_clean = cmd.strip()
            if not cmd_clean:
                continue

            cmd_display = cmd_clean[:200] + "..." if len(cmd_clean) > 200 else cmd_clean

            # Bug fix: rich.Confirm.ask atrapa SIGALRM internamente y reimprime
            # el prompt en bucle. Usamos input() nativo que SÍ respeta la señal.
            approved = False
            try:
                def _timeout_handler(signum, frame):
                    raise TimeoutError
                old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(_CONFIRM_TIMEOUT_S)
                console.print(
                    f"\n[bold yellow]¿Ejecutar comando sugerido?[/bold yellow]\n"
                    f"[cyan]{cmd_display}[/cyan]\n"
                    f"[dim](auto-rechaza en {_CONFIRM_TIMEOUT_S}s)[/dim] "
                    "[bold][[y/n][/bold]: ",
                    end=""
                )
                raw = input().strip().lower()
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
                approved = raw in ("y", "yes", "s", "si", "sí")
            except (TimeoutError, OSError, EOFError):
                signal.alarm(0)
                console.print("\n[dim]⏰ Sin respuesta — comando rechazado automáticamente.[/dim]")
                approved = False

            if approved:
                output = run_terminal_command(cmd_clean, state)
                executed_any = True

                state.history.append({"role": "assistant", "content": full})
                state.history.append({
                    "role": "user",
                    "content": (
                        f"El comando se ejecutó. Aquí está el resultado:\n"
                        f"<terminal_output>\n{output[:3000]}\n</terminal_output>\n"
                        f"Analiza el resultado y continúa."
                    )
                })

        if not executed_any:
            break

        console.print(f"[dim]🔄 Auto-ReAct: iteración {react_iteration}/{MAX_REACT_LOOPS}...[/dim]")

    # --- Citador Heurístico (Sprint 1 Quick Win) ---
    if final_response and rag_context:
        from core.rag_coder import _FRAG_OPEN
        import re as _re
        _frag_prefix = _re.escape(_FRAG_OPEN.split(" ")[0])
        sources = set(_re.findall(
            rf'{_frag_prefix}\s+source="([^"]+)"', rag_context
        ))
        actual_citations: set = set()
        for source in sources:
            basename = source.split("/")[-1]
            if basename in final_response or source in final_response:
                actual_citations.add(source)

        if actual_citations:
            citation_block = "\n\n---\n**📚 Fuentes Citadas:**\n"
            for src in sorted(actual_citations):
                abs_path = os.path.abspath(src)
                citation_block += f"- [{src}](file://{abs_path})\n"
            final_response += citation_block
            console.print(Markdown(citation_block))

    return final_response
