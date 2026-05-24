import os
import time
import json
import re
import logging
import threading
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.prompt import Confirm

from core.terminal import run_terminal_command, is_readonly_command
from core.state import normalize_provider, estimate_tokens
import core.state as _state_module

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

# Sprint 8.0 — Cliente HTTP persistente (singleton) para reutilizar conexiones
_http_client: httpx.Client | None = None
_http_client_lock = threading.Lock()


def ensure_ollama_running(ollama_url: str = "http://localhost:11434") -> bool:
    """Verifica si Ollama está activo. Si no, intenta levantarlo en segundo plano.

    Sprint 11 — Levantamiento automático de Ollama.
    """
    import subprocess
    from urllib.parse import urlparse
    parsed = urlparse(ollama_url)
    if parsed.scheme and parsed.netloc:
        base_url = f"{parsed.scheme}://{parsed.netloc}"
    else:
        base_url = ollama_url.rstrip("/")
    api_url = f"{base_url}/api/tags"
    
    try:
        # Intentar una petición rápida con timeout corto
        with httpx.Client(timeout=1.5) as client:
            resp = client.get(api_url)
            if resp.status_code == 200:
                logger.info("Ollama ya se encuentra activo en %s", base_url)
                return True
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
        pass
        
    # Si no responde, intentar levantarlo
    logger.info("Ollama no responde. Intentando iniciar servicio 'ollama serve'...")
    console.print(f"[yellow]⚠ Ollama no responde en {base_url}. Intentando iniciar 'ollama serve' en segundo plano...[/yellow]")
    
    try:
        # Ejecutar ollama serve en segundo plano
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp if hasattr(os, "setpgrp") else None
        )
        
        # Esperar y verificar hasta 3 veces si responde (cada 2 segundos)
        for i in range(3):
            time.sleep(2.0)
            try:
                with httpx.Client(timeout=1.5) as client:
                    resp = client.get(api_url)
                    if resp.status_code == 200:
                        console.print("[green]✓ Ollama iniciado correctamente en segundo plano.[/green]")
                        logger.info("Ollama iniciado exitosamente en el intento %d", i+1)
                        return True
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
                pass
    except FileNotFoundError:
        console.print("[bold red]⚠ Alerta: El comando 'ollama' no está instalado en el sistema.[/bold red]")
        logger.warning("El ejecutable 'ollama' no fue encontrado.")
        return False
    except Exception as e:
        console.print(f"[bold red]⚠ Alerta: No se pudo iniciar Ollama automáticamente: {e}[/bold red]")
        logger.error("Error al levantar Ollama: %s", e)
        return False
        
    console.print("[bold yellow]⚠ Advertencia: Se ejecutó 'ollama serve' pero no responde. Es posible que debas iniciarlo manualmente.[/bold yellow]")
    logger.warning("Ollama se ejecutó pero no responde en %s", base_url)
    return False


def _get_http_client() -> httpx.Client:
    """Retorna un cliente httpx persistente con connection pooling.

    Sprint 8.0 — Evita crear un nuevo cliente en cada request, reduciendo
    la latencia por renegociación SSL y establecimiento de conexión TCP.
    """
    global _http_client
    if _http_client is None or _http_client.is_closed:
        with _http_client_lock:
            if _http_client is None or _http_client.is_closed:
                _http_client = httpx.Client(
                    timeout=httpx.Timeout(300.0, connect=30.0),
                    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                    follow_redirects=True,
                )
    return _http_client


def _chat_completions_url(base_url: str) -> str:
    """Construye el endpoint Chat Completions sin duplicar el sufijo."""
    base = (base_url or "").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _get_provider_config(state, provider: str | None = None) -> tuple[str, dict]:
    """Retorna (url, headers) para el proveedor activo u override.

    Ollama usa su endpoint nativo. Los demas proveedores pasan por endpoints
    compatibles con OpenAI Chat Completions.
    """
    provider_name = normalize_provider(provider or state.provider)
    if provider_name == "ollama":
        return state.ollama_base_url, {"Content-Type": "application/json"}

    base_url = state.base_urls.get(provider_name) or getattr(state, f"{provider_name}_base_url", "")
    if not base_url:
        raise ValueError(f"Proveedor '{provider_name}' requiere configurar base_url.")

    api_key = state.api_keys.get(provider_name) or getattr(state, f"{provider_name}_api_key", "")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if provider_name == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/jellyfish-os"
        headers["X-Title"] = "Jellyfish OS"

    return _chat_completions_url(base_url), headers


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


def _call_llm_silent(
    state,
    messages: list,
    provider: str | None = None,
    model: str | None = None,
) -> str | None:
    """Llama al LLM sin mostrar streaming en pantalla (para subagentes internos).

    Sprint 1.2 — Usa httpx en modo síncrono con streaming silencioso.
    Sprint 3.1 — Migrado de requests a httpx.

    Args:
        state: Instancia del estado.
        messages: Lista de mensajes en formato Chat Completions.

    Returns:
        La respuesta completa del modelo como string, o None si hay error.
    """
    provider_name = normalize_provider(provider or state.provider)
    url, headers = _get_provider_config(state, provider_name)
    is_cloud = provider_name != "ollama"
    payload = {
        "model": model or state.model,
        "messages": messages,
        "stream": True,
    }
    if is_cloud:
        payload["temperature"] = 0.2

    try:
        full = ""
        parse_fn = (
            (lambda line: _parse_sse_line(line, provider_name))
            if is_cloud
            else _parse_ollama_line
        )
        # Sprint 8.0 — Reusar cliente HTTP persistente
        client = _get_http_client()
        with client.stream("POST", url, headers=headers, json=payload) as response:
            if response.status_code != 200:
                logger.warning(
                    "_call_llm_silent HTTP %s de %s", response.status_code, provider_name
                )
                return None
            for line in response.iter_lines():
                if not line:
                    continue
                chunk = parse_fn(line.encode("utf-8"))
                if chunk:
                    full += chunk
        if full:
            tokens_input = sum(estimate_tokens(m.get("content", "")) for m in messages)
            tokens_output = estimate_tokens(full)
            total_tokens = tokens_input + tokens_output
            if hasattr(state, "add_session_tokens"):
                state.add_session_tokens(total_tokens)
        return full if full else None

    except httpx.ConnectError:
        logger.error("No se puede conectar al proveedor %s (silent)", provider_name)
        return None
    except Exception as e:
        logger.error("Error en _call_llm_silent: %s", e)
        return None


def _stream_request(
    state,
    messages: list,
    agent_name: str,
    _aborted: list | None = None,
    provider: str | None = None,
    model: str | None = None,
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
    provider_name = normalize_provider(provider or state.provider)
    model_name = model or state.model
    url, headers = _get_provider_config(state, provider_name)
    is_cloud = provider_name != "ollama"

    payload = {
        "model": model_name,
        "messages": messages,
        "stream": True,
    }
    if is_cloud:
        payload["temperature"] = 0.2

    full = ""
    provider_label = f"{provider_name}:{model_name}" if is_cloud else f"@{agent_name}"
    parse_fn = (
        (lambda line: _parse_sse_line(line, provider_name))
        if is_cloud
        else _parse_ollama_line
    )

    try:
        # Sprint 8.0 — Reusar cliente HTTP persistente
        client = _get_http_client()
        with client.stream("POST", url, headers=headers, json=payload) as response:
            if response.status_code != 200:
                error_body = response.read()[:500].decode("utf-8", errors="replace")
                console.print(
                    f"[bold red]Error HTTP {response.status_code} de {provider_name}:[/bold red]\n"
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

        if full:
            tokens_input = sum(estimate_tokens(m.get("content", "")) for m in messages)
            tokens_output = estimate_tokens(full)
            total_tokens = tokens_input + tokens_output
            if hasattr(state, "add_session_tokens"):
                state.add_session_tokens(total_tokens)
            
            if not hasattr(state, "_turn_stats"):
                state._turn_stats = []
            state._turn_stats.append({
                "input": tokens_input,
                "output": tokens_output,
                "total": total_tokens
            })
            logger.info("Respuesta: %d tokens (Input: %d | Output: %d)", total_tokens, tokens_input, tokens_output)
        return full if full else None

    except httpx.ConnectError:
        if provider_name == "ollama":
            console.print(
                "[bold red]Error: No se puede conectar a Ollama.[/bold red]\n"
                "[dim]Asegúrate de que Ollama esté ejecutándose: ollama serve[/dim]"
            )
        else:
            console.print(
                f"[bold red]Error: No se puede conectar al proveedor {provider_name}.[/bold red]\n"
                "[dim]Verifica tu conexión a internet y la URL del API.[/dim]"
            )
        return None

    except httpx.TimeoutException:
        console.print("[bold red]Error: Timeout en la conexión (>300s).[/bold red]")
        return None

    except Exception as e:
        console.print(f"[red]Error LLM ({provider_name}): {e}[/red]")
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
    t_start = time.perf_counter()
    state._turn_stats = []
    react_iteration = 0
    final_response = None
    _aborted = [False]  # Sprint 3.3 — señal mutable de cancelación

    # Limpiar comandos denegados en este turno para prevenir prompts y ejecuciones duplicadas
    state.denied_commands = set()

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

        # Sprint 8.0 — Activar flag de spinner en TUI
        _state_module._llm_busy = True
        try:
            full = _stream_request(state, messages, state.active_agent, _aborted=_aborted)
        finally:
            _state_module._llm_busy = False

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

            # Sprint 8.0 — Auto-aprobación para comandos de solo lectura
            if is_readonly_command(cmd_clean):
                cmd_display = cmd_clean[:200] + "..." if len(cmd_clean) > 200 else cmd_clean
                console.print(
                    f"\n[bold green]⚡ Auto-ejecutando comando de lectura:[/bold green]\n"
                    f"[cyan]{cmd_display}[/cyan]"
                )
                output = run_terminal_command(cmd_clean, state, force_confirm=False)
            else:
                # La confirmación, validación y [y/n/a] se manejan centralizadamente en terminal.py
                output = run_terminal_command(cmd_clean, state, force_confirm=True)

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

    # --- Resumen Consolidado de Métricas del Turno ---
    if hasattr(state, "_turn_stats") and state._turn_stats:
        from rich.text import Text
        total_in = sum(s["input"] for s in state._turn_stats)
        total_out = sum(s["output"] for s in state._turn_stats)
        total_tok = total_in + total_out
        elapsed = time.perf_counter() - t_start
        
        summary_text = Text()
        summary_text.append("\n📊 MÉTRICAS DE LA PREGUNTA:\n", style="bold cyan")
        summary_text.append(f"  Input: {total_in:,} tokens  |  Output: {total_out:,} tokens\n", style="dim white")
        summary_text.append(f"  Total: {total_tok:,} tokens  |  Tiempo: {elapsed:.2f}s\n", style="bold green")
        console.print(summary_text)

    return final_response


def is_ollama_running(url: str = "http://localhost:11434") -> bool:
    """Verifica de forma ultra-rápida si Ollama está respondiendo en localhost."""
    import httpx
    try:
        with httpx.Client(timeout=0.5) as client:
            resp = client.get(url)
            return resp.status_code == 200 or resp.status_code == 404
    except Exception:
        return False


def is_model_available_locally(model_name: str, url: str = "http://localhost:11434") -> bool:
    """Verifica de forma ultra-rápida si el modelo de Ollama está descargado localmente."""
    import httpx
    try:
        with httpx.Client(timeout=1.0) as client:
            resp = client.get(f"{url.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                if model_name in models:
                    return True
                # También buscar por nombre base sin tag/versión
                model_base = model_name.split(":")[0]
                for m in models:
                    if m.split(":")[0] == model_base:
                        return True
    except Exception:
        pass
    return False
