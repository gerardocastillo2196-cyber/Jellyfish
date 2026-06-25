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

# Auditoría — Caché L1 por turno para evitar llamadas LLM duplicadas.
# Se limpia al inicio de cada turno con clear_llm_cache().
_llm_call_cache: dict[str, str] = {}

def clear_llm_cache() -> None:
    """Limpia la caché L1 de llamadas LLM. Llamar al inicio de cada turno."""
    _llm_call_cache.clear()

# Regex para detectar bloques de código bash/sh/shell
_BASH_REGEX = re.compile(
    r"```(?:bash|sh|shell|zsh)?\s*\n(.*?)\n```",
    re.DOTALL
)

# Sprint 8.0 — Cliente HTTP persistente (singleton) para reutilizar conexiones
_http_client: httpx.Client | None = None
_http_client_lock = threading.Lock()

def _get_sync_client() -> httpx.Client:
    global _http_client
    with _http_client_lock:
        if _http_client is None:
            _http_client = httpx.Client(
                timeout=httpx.Timeout(300.0, connect=30.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                follow_redirects=True,
            )
        return _http_client

import atexit
def _close_http_client():
    global _http_client
    with _http_client_lock:
        if _http_client is not None:
            _http_client.close()
            _http_client = None

atexit.register(_close_http_client)


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
    console.print(f"⚠ Ollama no responde en {base_url}. Intentando iniciar 'ollama serve' en segundo plano...")
    
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
                        console.print("✓ Ollama iniciado correctamente en segundo plano.")
                        logger.info("Ollama iniciado exitosamente en el intento %d", i+1)
                        return True
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
                pass
    except FileNotFoundError:
        console.print("⚠ Alerta: El comando 'ollama' no está instalado en el sistema.")
        logger.warning("El ejecutable 'ollama' no fue encontrado.")
        return False
    except Exception as e:
        console.print(f"⚠ Alerta: No se pudo iniciar Ollama automáticamente: {e}")
        logger.error("Error al levantar Ollama: %s", e)
        return False
        
    console.print("⚠ Advertencia: Se ejecutó 'ollama serve' pero no responde. Es posible que debas iniciarlo manualmente.")
    logger.warning("Ollama se ejecutó pero no responde en %s", base_url)
    return False


def _chat_completions_url(base_url: str) -> str:
    """Construye el endpoint Chat Completions sin duplicar el sufijo."""
    base = (base_url or "").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _get_provider_config(state, provider: str | None = None) -> tuple[str, dict]:
    """Retorna (url, headers) para el proveedor activo u override.

    Ollama usa su endpoint nativo. Los demas proveedores pasan por endpoints
    compatibles con OpenAI Chat Completions, a menos que sea el proveedor native Claude.
    """
    provider_name = normalize_provider(provider or state.provider)
    if provider_name == "ollama":
        return state.ollama_base_url, {"Content-Type": "application/json"}

    base_url = state.base_urls.get(provider_name) or getattr(state, f"{provider_name}_base_url", "")
    if not base_url:
        raise ValueError(f"Proveedor '{provider_name}' requiere configurar base_url.")

    api_key = state.api_keys.get(provider_name) or getattr(state, f"{provider_name}_api_key", "")
    
    # Soporte nativo para Anthropic si el base_url apunta a su endpoint oficial
    if provider_name == "claude" and "api.anthropic.com" in base_url:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        url = f"{base_url.rstrip('/')}/messages"
        return url, headers

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if provider_name == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/jellyfish-os"
        headers["X-Title"] = "Jellyfish OS"

    return _chat_completions_url(base_url), headers


def _parse_sse_line(line_bytes: bytes, provider: str) -> str:
    """Parsea una línea del stream SSE (OpenAI/Anthropic compatible) y retorna el contenido delta."""
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
            return choices[0].get("delta", {}).get("content", "") or ""
        
        # Formato Anthropic SSE
        if data.get("type") == "content_block_delta":
            return data.get("delta", {}).get("text", "") or ""
            
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


def _prepare_payload(provider_name: str, url: str, model_name: str, messages: list, attempt: int = 1) -> dict:
    is_cloud = provider_name != "ollama"
    is_native_anthropic = (provider_name == "claude" and "api.anthropic.com" in url)

    # Mapeo de modelos locales/antigravity de Gemini a IDs oficiales de la API de Google
    if provider_name == "gemini":
        gemini_mapping = {
            "gemini-2.5-flash": "gemini-2.5-flash",
            "gemini-2.5-pro": "gemini-2.5-pro",
            "gemini-2.0-flash": "gemini-2.0-flash",
            "gemini-1.5-flash": "gemini-1.5-flash",
            "gemini-1.5-pro": "gemini-1.5-pro",
        }
        model_name = gemini_mapping.get(model_name, model_name)

    payload = {
        "model": model_name,
        "stream": True,
    }
    if is_cloud:
        payload["temperature"] = max(0.0, 0.2 - 0.05 * (attempt - 1))

    if is_native_anthropic:
        payload["max_tokens"] = 4096
        system_prompt = ""
        filtered_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt += msg.get("content", "") + "\n"
            else:
                role = msg.get("role")
                if role not in ("user", "assistant"):
                    role = "user"
                filtered_messages.append({"role": role, "content": msg.get("content", "")})
        payload["messages"] = filtered_messages
        if system_prompt:
            payload["system"] = system_prompt.strip()
    else:
        payload["messages"] = messages

    return payload


def _call_llm_silent(
    state,
    messages: list,
    provider: str | None = None,
    model: str | None = None,
    timeout: float | None = None,
) -> str | None:
    """Llama al LLM sin mostrar streaming en pantalla (para subagentes internos).

    Sprint 1.2 — Usa httpx en modo síncrono con streaming silencioso.
    Sprint 3.1 — Migrado de requests a httpx.
    Auditoría — Reestructurado el bucle de reintento: el bug anterior hacía
    que el `continue` dentro del `with client.stream(...)` no escapara al
    loop de reintentos, causando ráfagas masivas de 429 sin backoff real.
    Auditoría — Añadida caché L1 por turno para evitar llamadas duplicadas.
    """
    provider_name = normalize_provider(provider or state.provider)
    url, headers = _get_provider_config(state, provider_name)
    is_cloud = provider_name != "ollama"
    model_name = model or state.model

    # --- Caché L1 por turno: evitar llamadas duplicadas con los mismos mensajes ---
    import hashlib as _hashlib
    cache_key = _hashlib.sha256(
        f"{provider_name}:{model_name}:{json.dumps(messages, ensure_ascii=False, sort_keys=True)}".encode()
    ).hexdigest()
    if cache_key in _llm_call_cache:
        logger.debug("Cache hit para _call_llm_silent (hash=%s…)", cache_key[:12])
        return _llm_call_cache[cache_key]

    max_attempts = 5
    initial_delay = 2.0
    backoff_factor = 2.0

    for attempt in range(1, max_attempts + 1):
        payload = _prepare_payload(provider_name, url, model_name, messages, attempt)
        try:
            full = ""
            parse_fn = (
                (lambda line: _parse_sse_line(line, provider_name))
                if is_cloud
                else _parse_ollama_line
            )
            
            client = _get_sync_client()
            # Auditoría: usamos request() sin streaming primero para verificar
            # el status code, y luego procesamos el stream solo si es 200.
            # Esto evita el bug donde `continue` no escapaba del context manager.
            should_retry = False
            with client.stream("POST", url, headers=headers, json=payload, timeout=timeout) as response:
                if response.status_code == 429 or (500 <= response.status_code < 600):
                    should_retry = True
                    # Consumir el body para liberar la conexión
                    try:
                        response.read()
                    except Exception:
                        pass
                elif response.status_code != 200:
                    logger.warning(
                        "_call_llm_silent HTTP %s de %s", response.status_code, provider_name
                    )
                    return None
                else:
                    # Status 200 — procesar stream normalmente
                    for line in response.iter_lines():
                        if not line:
                            continue
                        chunk = parse_fn(line.encode("utf-8"))
                        if chunk:
                            full += chunk

            # Evaluar resultado FUERA del context manager del stream
            if should_retry:
                delay = initial_delay * (backoff_factor ** (attempt - 1))
                logger.warning(
                    "_call_llm_silent HTTP retryable de %s. Reintentando en %.1fs (Intento %d/%d)...",
                    provider_name, delay, attempt, max_attempts
                )
                time.sleep(delay)
                continue

            if full:
                tokens_input = sum(estimate_tokens(m.get("content", "")) for m in messages)
                tokens_output = estimate_tokens(full)
                total_tokens = tokens_input + tokens_output
                if hasattr(state, "add_session_tokens"):
                    state.add_session_tokens(total_tokens)
                # Guardar en caché L1
                _llm_call_cache[cache_key] = full
                return full
            else:
                # Output vacío sin error HTTP — reintentar
                if attempt < max_attempts:
                    delay = initial_delay * (backoff_factor ** (attempt - 1))
                    logger.warning(
                        "_call_llm_silent retornó output vacío de %s. Reintentando en %.1fs...",
                        provider_name, delay
                    )
                    time.sleep(delay)
                    continue
                return None

        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
            if attempt < max_attempts:
                delay = initial_delay * (backoff_factor ** (attempt - 1))
                logger.warning(
                    "Error de conexión/red en _call_llm_silent: %s. Reintentando en %.1fs...",
                    e, delay
                )
                time.sleep(delay)
            else:
                logger.error("Error definitivo en _call_llm_silent tras %d intentos: %s", max_attempts, e)
                return None

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

    payload = _prepare_payload(provider_name, url, model_name, messages)

    full = ""
    provider_label = f"{provider_name}:{model_name}" if is_cloud else f"@{agent_name}"
    parse_fn = (
        (lambda line: _parse_sse_line(line, provider_name))
        if is_cloud
        else _parse_ollama_line
    )

    try:
        import asyncio

        async def _run_stream():
            nonlocal full
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(300.0, connect=30.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                follow_redirects=True,
            ) as client:
                status = console.status(f"[cyan]Pensando ({provider_name})...[/cyan]")
                status.start()
                try:
                    async with client.stream("POST", url, headers=headers, json=payload) as response:
                        status.stop()
                        if response.status_code != 200:
                            error_body = (await response.aread())[:500].decode("utf-8", errors="replace")
                            console.print(
                                f"Error HTTP {response.status_code} de {provider_name}:\n"
                                f"[dim]{error_body}[/dim]"
                            )
                            return
    
                        with Live(
                            "",
                            refresh_per_second=12,
                            console=console,
                        ) as live:
                            try:
                                async for line in response.aiter_lines():
                                    if _aborted and _aborted[0]:
                                        print("\n⚡ Stream interrumpido — respuesta parcial conservada.")
                                        break
    
                                    if not line:
                                        continue
    
                                    chunk = parse_fn(line.encode("utf-8"))
                                    if chunk:
                                        full += chunk
                                        live.update(Markdown(full))
                            except KeyboardInterrupt:
                                print("\n⚡ Stream interrumpido — respuesta parcial conservada.")
                                if _aborted is not None:
                                    _aborted[0] = True
                finally:
                    status.stop()

        asyncio.run(_run_stream())

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
                "Error: No se puede conectar a Ollama.\n"
                "[dim]Asegúrate de que Ollama esté ejecutándose: ollama serve[/dim]"
            )
        else:
            console.print(
                f"Error: No se puede conectar al proveedor {provider_name}.\n"
                "[dim]Verifica tu conexión a internet y la URL del API.[/dim]"
            )
        return None

    except httpx.TimeoutException:
        console.print("Error: Timeout en la conexión (>300s).")
        return None

    except Exception as e:
        console.print(f"Error LLM ({provider_name}): {e}")
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
    
    # Auditoría — Limpiar caché L1 al inicio de cada turno
    clear_llm_cache()
    # Esto asegura que el agente conversacional lea las últimas escrituras de
    # los tableros (DEV_BOARD.md) que hayan ocurrido durante ejecuciones en 2do plano.
    if hasattr(state, "refresh_static_context"):
        state.refresh_static_context()
        
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
                console.print("⚠ El modelo no generó respuesta.")
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
                    f"\n⚡ Auto-ejecutando comando de lectura:\n"
                    f"{cmd_display}"
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
        total_in = sum(s["input"] for s in state._turn_stats)
        total_out = sum(s["output"] for s in state._turn_stats)
        total_tok = total_in + total_out
        elapsed = time.perf_counter() - t_start
        print(f"\n[{total_in:,} → {total_out:,} tok | total {total_tok:,} | {elapsed:.1f}s]")

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
